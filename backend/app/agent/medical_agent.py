import json
import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.prompts import SYSTEM_PROMPT, FOLLOW_UP_PROMPT, CLARIFICATION_PROMPT  # noqa: F401
from app.agent.tools import TOOLS  # noqa: F401
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    CondicionProbable,
    HospitalRecommendation,
    StructuredResponse,
)
from app.schemas.symptom import SymptomExtraction
from app.schemas.specialty import SpecialtySuggestion
from app.schemas.copago import CopagoResult
from app.services.nlp_service import NLPService
from app.services.ontology_service import OntologyService
from app.services.rule_engine import RuleEngine
from app.services.copago_service import CopagoService
from app.services.hospital_service import HospitalService
from app.services.llm_service import LLMService
from app.services.endless_medical_service import (
    EndlessMedicalError,
    EndlessMedicalService,
)
from app.models.chat_session import ChatSession

logger = logging.getLogger(__name__)


class MedicalAgent:
    def __init__(self, db: Session):
        self.db = db
        self.nlp = NLPService(db)
        self.ontology = OntologyService(db)
        self.rules = RuleEngine(db)
        self.copago = CopagoService(db)
        self.hospitals = HospitalService(db)
        self.llm = LLMService()
        self.endless = EndlessMedicalService()

    async def process(self, request: ChatRequest) -> ChatResponse:
        session = self._get_or_create_session(request.session_id, request.plan_id)
        specialties: list[SpecialtySuggestion] = []
        urgency = "media"
        alert = None
        copago_result: CopagoResult | None = None
        hospital_results: list[HospitalRecommendation] = []
        condiciones_probables: list[CondicionProbable] = []

        # Step 1: Extract symptoms using NLP (always works offline)
        raw_symptoms = self.nlp.extract_symptoms(request.message)
        symptom_names = [s.normalized for s in raw_symptoms]

        # Step 1b: Try LLM for additional extraction if available
        if self.llm._available:
            try:
                llm_symptoms = await self.llm.extract_symptoms_from_text(request.message)
                existing_names = {s.normalized for s in raw_symptoms}
                for s in llm_symptoms:
                    if s.normalized.lower() not in existing_names:
                        raw_symptoms.append(s)
                        symptom_names.append(s.normalized)
            except Exception as e:
                logger.warning(f"LLM extraction failed, using NLP only: {e}")

        # Step 2: Query ontology for specialties
        if symptom_names:
            specialties = self.ontology.query_specialties(symptom_names)

        # Step 3: Evaluate rules for urgency
        if symptom_names:
            rule_result = self.rules.evaluate(symptom_names, request.message)
            urgency = rule_result.get("urgency", "media")
            alert = rule_result.get("alert")
            if not specialties and rule_result.get("specialties"):
                specialties = [
                    SpecialtySuggestion(name=s, confidence=0.9, matching_symptoms=[])
                    for s in rule_result["specialties"]
                ]

        # Step 3b: EndlessMedical → enfermedades probables (Gemini hace de traductor)
        if symptom_names and self.llm._available:
            condiciones_probables = await self._diagnose_with_endless_medical(
                request.message, request.age, request.gender
            )

        # Step 4: Calculate copago and find hospital
        plan_id = request.plan_id or (session.plan_id if session.plan_id else None)
        primary_specialty = specialties[0].name if specialties else None

        if plan_id and primary_specialty:
            try:
                service_type = "emergencia" if urgency == "alta" else "consulta"
                copago_result = self.copago.calculate(plan_id, service_type, primary_specialty)
            except Exception as e:
                logger.error(f"Copago calculation error: {e}")

        if plan_id and primary_specialty:
            try:
                hospital_results = self.hospitals.find_best(plan_id, primary_specialty, urgency)
            except Exception as e:
                logger.error(f"Hospital search error: {e}")

        # Step 5: Build structured response (antes del reply, así Gemini lo recibe)
        structured = StructuredResponse(
            sintomas=symptom_names,
            urgencia=urgency,
            especialidades_sugeridas=[s.name for s in specialties],
            condiciones_probables=condiciones_probables,
            plan_seguro=copago_result.plan_nombre if copago_result else "",
            copago_estimado=copago_result.copago_estimado if copago_result else 0.0,
            moneda="USD",
            hospital_recomendado=hospital_results[0] if hospital_results else None,
            hospitales_comparacion=hospital_results,
            desglose_cobertura=copago_result.desglose if copago_result else "",
        )

        # Step 6: Generate text reply (Gemini si está disponible, fallback a template)
        reply = await self._generate_reply_smart(
            request.message, raw_symptoms, specialties, urgency, alert,
            copago_result, hospital_results, plan_id, condiciones_probables,
        )

        # Step 7: Determine if we need more info
        needs_more_info = len(symptom_names) == 0 or (plan_id is None and len(symptom_names) > 0)
        clarification_questions = []
        if needs_more_info:
            clarification_questions = self._generate_clarifications(symptom_names, plan_id)

        # Step 8: Solo añadir prefijo de alerta si Gemini no lo hizo y la urgencia es alta.
        # Nada de disclaimers — el agente debe ser decisivo, no chatbot.
        if alert and urgency == "alta" and "EMERGENCIA" not in reply.upper():
            reply = f"EMERGENCIA: {alert}\n\n{reply}"

        # Step 9: Update session
        self._update_session(session, request.message, reply, structured)

        return ChatResponse(
            session_id=session.id,
            reply=reply,
            structured=structured,
            needs_more_info=needs_more_info,
            clarification_questions=clarification_questions,
        )

    # ── Sub-paso: EndlessMedical con Gemini como traductor ─────────
    async def _diagnose_with_endless_medical(
        self, patient_text: str, age: int | None, gender: str | None
    ) -> list[CondicionProbable]:
        try:
            valid_features = await self.endless.get_features()
            logger.info(
                "[EndlessMedical] valid_features cargados: %d", len(valid_features)
            )
            if not valid_features:
                logger.warning("[EndlessMedical] /GetFeatures vino vacío")
                return []

            features = await self.llm.map_text_to_features(
                patient_text, valid_features, age=age, gender=gender
            )
            logger.info(
                "[EndlessMedical] Gemini mapeó %d features: %s",
                len(features),
                features,
            )
            if not features:
                logger.warning(
                    "[EndlessMedical] Gemini no mapeó ninguna feature válida"
                )
                return []

            diseases = await self.endless.diagnose(features, top_k=3)
            logger.info("[EndlessMedical] Top diseases: %s", diseases)
            return [
                CondicionProbable(
                    nombre=d["name"],
                    probabilidad=round(d.get("probability", 0.0), 4),
                )
                for d in diseases
            ]
        except EndlessMedicalError as e:
            logger.warning("[EndlessMedical] falló: %s", e)
        except Exception as e:
            logger.exception("[EndlessMedical] error inesperado: %s", e)
        return []

    # ── Reply: Gemini summarizer con fallback a template ───────────
    async def _generate_reply_smart(
        self,
        user_message: str,
        symptoms: list[SymptomExtraction],
        specialties: list[SpecialtySuggestion],
        urgency: str,
        alert: str | None,
        copago: CopagoResult | None,
        hospitals: list[HospitalRecommendation],
        plan_id: int | None,
        condiciones: list[CondicionProbable],
    ) -> str:
        if self.llm._available and (symptoms or condiciones):
            try:
                context = {
                    "mensaje_paciente": user_message,
                    "sintomas_detectados": [s.normalized for s in symptoms],
                    "urgencia": urgency,
                    "alerta": alert,
                    "especialidades_sugeridas": [s.name for s in specialties],
                    "condiciones_probables": [
                        {"nombre": c.nombre, "probabilidad": c.probabilidad}
                        for c in condiciones
                    ],
                    "copago_estimado_usd": copago.copago_estimado if copago else None,
                    "plan_seguro": copago.plan_nombre if copago else None,
                    "desglose": copago.desglose if copago else None,
                    "hospital_recomendado": (
                        {
                            "nombre": hospitals[0].nombre,
                            "tipo": hospitals[0].tipo,
                            "copago_paciente": hospitals[0].copago_paciente,
                        }
                        if hospitals
                        else None
                    ),
                    "tiene_plan_id": plan_id is not None,
                }
                gemini_reply = await self.llm.summarize_diagnosis(context)
                if gemini_reply:
                    return gemini_reply
            except Exception as e:
                logger.warning("Gemini summary falló, usando template: %s", e)

        return self._generate_reply(
            user_message, symptoms, specialties, urgency, alert,
            copago, hospitals, plan_id,
        )

    def _generate_reply(
        self,
        user_message: str,
        symptoms: list[SymptomExtraction],
        specialties: list[SpecialtySuggestion],
        urgency: str,
        alert: str | None,
        copago: CopagoResult | None,
        hospitals: list[HospitalRecommendation],
        plan_id: int | None,
    ) -> str:
        if not symptoms and not specialties:
            return (
                "Necesito mas datos clinicos para predecir. Describe: que sintoma tienes, "
                "intensidad (1-10), duracion, ubicacion exacta, y que lo empeora o alivia. "
                "Adjunta tu plan de seguro para calcular copago y hospital."
            )

        parts = []
        symptom_names = [s.normalized for s in symptoms]

        if symptom_names:
            parts.append(f"Sintomas: {', '.join(symptom_names)}.")

        if specialties:
            spec_names = [s.name for s in specialties]
            parts.append(f"Especialidad sugerida: {', '.join(spec_names)}.")

        parts.append(f"Urgencia: {urgency}.")

        if copago:
            parts.append(f"Copago estimado: ${copago.copago_estimado:.2f} USD.")
            parts.append(f"Desglose: {copago.desglose}")

        if hospitals:
            parts.append("Hospitales recomendados:")
            for h in hospitals:
                dist = f" ({h.distancia_km} km)" if h.distancia_km else ""
                parts.append(f"- {h.nombre} ({h.tipo}) — Copago: ${h.copago_paciente:.2f} USD{dist}")

        if not plan_id:
            parts.append("Selecciona tu plan de seguro para calcular el copago exacto.")

        return "\n".join(parts)

    def _generate_clarifications(self, symptoms: list[str], plan_id: int | None) -> list[str]:
        questions = []
        if not symptoms:
            questions.append("¿Puede describir con mas detalle que sintomas presenta?")
        else:
            questions.append("¿Desde cuando presento estos sintomas?")
            questions.append("¿La intensidad es leve, moderada o severa?")
        if plan_id is None:
            questions.append("¿Cual es su plan de seguro medico?")
        return questions

    def _get_or_create_session(self, session_id: str | None, plan_id: int | None) -> ChatSession:
        if session_id:
            session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if session:
                if plan_id:
                    session.plan_id = plan_id
                return session
        session = ChatSession(plan_id=plan_id)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def _update_session(self, session: ChatSession, user_message: str, reply: str, structured: StructuredResponse):
        messages = session.messages or []
        messages.append({"role": "user", "content": user_message, "timestamp": datetime.utcnow().isoformat()})
        messages.append({"role": "assistant", "content": reply, "timestamp": datetime.utcnow().isoformat()})
        session.messages = messages
        session.extracted_symptoms = structured.sintomas
        session.final_response = structured.model_dump()
        self.db.commit()