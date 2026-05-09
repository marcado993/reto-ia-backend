import json
import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.prompts import SYSTEM_PROMPT, FOLLOW_UP_PROMPT, CLARIFICATION_PROMPT
from app.agent.tools import TOOLS
from app.schemas.chat import ChatRequest, ChatResponse, StructuredResponse, HospitalRecommendation
from app.schemas.symptom import SymptomExtraction
from app.schemas.specialty import SpecialtySuggestion
from app.schemas.copago import CopagoResult
from app.services.nlp_service import NLPService
from app.services.ontology_service import OntologyService
from app.services.rule_engine import RuleEngine
from app.services.copago_service import CopagoService
from app.services.hospital_service import HospitalService
from app.services.llm_service import LLMService
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

    async def process(self, request: ChatRequest) -> ChatResponse:
        session = self._get_or_create_session(request.session_id, request.plan_id)
        extracted_symptoms: list[SymptomExtraction] = []
        specialties: list[SpecialtySuggestion] = []
        urgency = "media"
        alert = None
        copago_result: CopagoResult | None = None
        hospital_results: list[HospitalRecommendation] = []

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

        # Step 5: Generate text reply
        reply = self._generate_reply(
            request.message, raw_symptoms, specialties, urgency, alert,
            copago_result, hospital_results, plan_id
        )

        # Step 6: Build structured response
        structured = StructuredResponse(
            sintomas=symptom_names,
            urgencia=urgency,
            especialidades_sugeridas=[s.name for s in specialties],
            plan_seguro=copago_result.plan_nombre if copago_result else "",
            copago_estimado=copago_result.copago_estimado if copago_result else 0.0,
            moneda="USD",
            hospital_recomendado=hospital_results[0] if hospital_results else None,
            hospitales_comparacion=hospital_results,
            desglose_cobertura=copago_result.desglose if copago_result else "",
        )

        # Step 7: Determine if we need more info
        needs_more_info = len(symptom_names) == 0 or (plan_id is None and len(symptom_names) > 0)
        clarification_questions = []
        if needs_more_info:
            clarification_questions = self._generate_clarifications(symptom_names, plan_id)

        # Step 8: Add alert prefix and disclaimer
        if alert and urgency == "alta":
            reply = f"⚠️ {alert}\n\n{reply}"
        reply += "\n\n---\n*Este sistema no sustituye consejo medico profesional. Consulte siempre a un profesional de salud.*"

        # Step 9: Update session
        self._update_session(session, request.message, reply, structured)

        return ChatResponse(
            session_id=session.id,
            reply=reply,
            structured=structured,
            needs_more_info=needs_more_info,
            clarification_questions=clarification_questions,
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
                "Hola, soy MediBot, su asistente de cobertura medica. Para poder orientarlo, necesito que me cuente que sintomas presenta.\n\n"
                "Por ejemplo, puede decir:\n"
                "- \"Me duele el pecho y me cuesta respirar\"\n"
                "- \"Tengo fiebre y dolor de cabeza\"\n"
                "- \"Me duele la barriga y tengo nauseas\"\n\n"
                "Tambien, seleccione su plan de seguro en el menu lateral para poder calcular su copago."
            )

        parts = []
        symptom_names = [s.normalized for s in symptoms]

        if symptom_names:
            parts.append(f"He identificado los siguientes sintomas: **{', '.join(symptom_names)}**.")

        if specialties:
            spec_names = [s.name for s in specialties]
            parts.append(f"Le sugiero consultar con: **{', '.join(spec_names)}**.")

        urgency_labels = {"baja": "baja ✓", "media": "media ⚡", "alta": "ALTA 🚨"}
        parts.append(f"Nivel de urgencia: **{urgency_labels.get(urgency, urgency)}**.")

        if copago:
            parts.append(f"\n**Desglose de cobertura:**\n{copago.desglose}")
            parts.append(f"**Copago estimado: ${copago.copago_estimado:.2f} USD**")

        if hospitals:
            parts.append("\n**Hospitales recomendados:**")
            for i, h in enumerate(hospitals, 1):
                emoji = "🟢" if i == 1 else "🏥"
                dist = f" ({h.distancia_km} km)" if h.distancia_km else ""
                parts.append(f"{emoji} **{h.nombre}** ({h.tipo}) — Copago: ${h.copago_paciente:.2f} USD{dist}")

        if not plan_id:
            parts.append("\n⚠️ Seleccione su plan de seguro para calcular el copago exacto.")

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