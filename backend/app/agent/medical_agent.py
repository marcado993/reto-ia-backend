import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.agent.prompts import SYSTEM_PROMPT, FOLLOW_UP_PROMPT, CLARIFICATION_PROMPT  # noqa: F401
from app.agent.tools import TOOLS  # noqa: F401
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    CondicionProbable,
    HospitalRecommendation,
    ServicioRecomendado,
    StructuredResponse,
)
from app.models.hospital import Hospital
from app.schemas.symptom import SymptomExtraction
from app.schemas.specialty import SpecialtySuggestion
from app.schemas.copago import CopagoResult
from app.services.rule_engine import RuleEngine
from app.services.copago_service import CopagoService
from app.services.hospital_service import HospitalService
from app.services.llm_service import LLMService
from app.models.chat_session import ChatSession

logger = logging.getLogger(__name__)

# Procedimientos que NUNCA deben ser recomendados como primer contacto
_PROHIBITED_FIRST_CONTACT = {
    "apendicectomia",
    "colecistectomia",
    "hernioplastia",
    "cirugia_catarata",
    "biopsia",
    "litotripsia",
    "biopsia_prostatica",
    "biopsia_intestinal",
    "biopsia_medula",
    "biopsia_hepatica",
    "biopsia_piel",
    "quimioterapia_sesion",
    "radioterapia_sesion",
    "angioplastia",
    "cateterismo",
    "reemplazo_cadera",
    "bypass_vascular",
    "artroscopia",
    "histeroscopia",
    "cesarea",
    "amigdalectomia",
    "cirugia_lesiones",
    "varices_escleroterapia",
    "inmunoterapia",
    "colonoscopia",
    "endoscopia_alta",
    "broncoscopia",
    "cistoscopia",
    "manometria",
}


class MedicalAgent:
    def __init__(self, db: Session):
        self.db = db
        self.rules = RuleEngine(db)
        self.copago = CopagoService(db)
        self.hospitals = HospitalService(db)
        self.llm = LLMService()
        self._specialty_services_catalog = self._load_specialty_services_catalog()

    @staticmethod
    def _load_specialty_services_catalog() -> dict[str, list[dict]]:
        """Carga el catálogo maestro de servicios por especialidad."""
        path = (
            Path(__file__).resolve().parent.parent.parent
            / "data"
            / "seed_specialty_services.json"
        )
        if not path.exists():
            logger.warning("seed_specialty_services.json no encontrado en %s", path)
            return {}
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith("_")}

    async def process(self, request: ChatRequest) -> ChatResponse:
        session = self._get_or_create_session(request.session_id, request.plan_id)
        specialties: list[SpecialtySuggestion] = []
        urgency = "media"
        alert = None
        copago_result: CopagoResult | None = None
        hospital_results: list[HospitalRecommendation] = []
        condiciones_probables: list[CondicionProbable] = []
        servicio: ServicioRecomendado | None = None
        symptom_names: list[str] = []
        raw_symptoms: list[SymptomExtraction] = []

        # ── Step 0: LLM debe estar disponible ───────────────────────
        if not self.llm._available:
            return ChatResponse(
                session_id=str(session.id),
                reply=(
                    "El servicio de inteligencia artificial no está disponible "
                    "en este momento. Por favor, inténtalo más tarde."
                ),
                structured=None,
                needs_more_info=True,
                clarification_questions=[],
            )

        # ── Step 1: LLM analiza paciente (síntomas + condiciones + especialidad + urgencia)
        analysis = await self.llm.analyze_patient(
            request.message, request.age, request.gender
        )
        raw_symptoms = analysis.get("sintomas", [])
        symptom_names = [s.normalized for s in raw_symptoms]
        condiciones_probables = analysis.get("condiciones_probables", [])
        specialty_name = analysis.get("especialidad_sugerida")
        urgency_llm = analysis.get("urgencia_sugerida", "media")

        # ── Step 2: Validación de seguridad con reglas locales ──────
        # Las reglas locales actúan como "guardia de seguridad".
        # Si el LLM subestima una emergencia, la regla eleva la urgencia.
        if symptom_names:
            rule_result = self.rules.evaluate(symptom_names, request.message)
            urgency_rule = rule_result.get("urgency", "media")
            alert = rule_result.get("alert")
            rule_specs = rule_result.get("specialties", [])

            # La regla SIEMPRE gana si dicta mayor urgencia
            urgency_levels = {"baja": 1, "media": 2, "alta": 3}
            if urgency_levels.get(urgency_rule, 2) >= urgency_levels.get(urgency_llm, 2):
                urgency = urgency_rule
            else:
                urgency = urgency_llm

            # Si hay especialidad de la regla, la priorizamos
            if rule_specs:
                if urgency == "alta":
                    # En emergencia, las especialidades de la regla mandan
                    boosted = [
                        SpecialtySuggestion(
                            name=s, confidence=0.95, matching_symptoms=[]
                        )
                        for s in rule_specs
                    ]
                    in_rule = [s for s in specialties if s.name in rule_specs]
                    rest = [s for s in specialties if s.name not in rule_specs]
                    specialties = boosted + in_rule + rest
                elif not specialty_name:
                    specialty_name = rule_specs[0]
        else:
            urgency = urgency_llm

        # Construir lista de especialidades para el contexto
        if specialty_name:
            specialties = [
                SpecialtySuggestion(
                    name=specialty_name,
                    confidence=0.9,
                    matching_symptoms=symptom_names,
                )
            ]

        # ── Step 3: Pick the specific service (primer contacto) ─────
        plan_id = request.plan_id or (
            session.plan_id if session.plan_id else None
        )
        primary_specialty = specialty_name
        service_name: str | None = None

        if primary_specialty:
            servicio = await self._pick_service(
                primary_specialty, urgency, symptom_names, condiciones_probables
            )
            service_name = servicio.nombre if servicio else None

        # ── Step 4: Calculate copago ────────────────────────────────
        if plan_id and primary_specialty:
            try:
                service_type = "emergencia" if urgency == "alta" else "consulta"
                copago_result = self.copago.calculate(
                    plan_id,
                    service_type,
                    primary_specialty,
                    service_name=service_name,
                )
            except Exception as e:
                logger.error(f"Copago calculation error: {e}")

        # ── Step 5: Find hospitals in network ───────────────────────
        if plan_id and primary_specialty:
            try:
                hospital_results = self.hospitals.find_best(
                    plan_id,
                    primary_specialty,
                    urgency,
                    user_lat=request.user_lat,
                    user_lon=request.user_lon,
                    service_name=service_name,
                )
            except Exception as e:
                logger.error(f"Hospital search error: {e}")

        # ── Step 6: Build structured response ───────────────────────
        structured = StructuredResponse(
            sintomas=symptom_names,
            urgencia=urgency,
            especialidades_sugeridas=[primary_specialty]
            if primary_specialty
            else [],
            condiciones_probables=condiciones_probables,
            servicio_recomendado=servicio,
            plan_seguro=copago_result.plan_nombre if copago_result else "",
            costo_base=copago_result.costo_base if copago_result else 0.0,
            copago_estimado=copago_result.copago_estimado
            if copago_result
            else 0.0,
            moneda="USD",
            hospital_recomendado=hospital_results[0]
            if hospital_results
            else None,
            hospitales_comparacion=hospital_results,
            desglose_cobertura=copago_result.desglose if copago_result else "",
        )

        # ── Step 7: Generate text reply (LLM) ───────────────────────
        reply = await self._generate_reply_smart(
            request.message,
            raw_symptoms,
            specialties,
            urgency,
            alert,
            copago_result,
            hospital_results,
            plan_id,
            condiciones_probables,
            servicio,
        )

        # ── Step 8: Determine if we need more info ─────────────────
        # SOLO pedimos más info si NO hay síntomas detectados.
        # NUNCA pedimos datos clínicos adicionales (duración, intensidad, etc.).
        needs_more_info = len(symptom_names) == 0
        clarification_questions = []
        if needs_more_info:
            clarification_questions = [
                "¿Qué síntomas presentas? Descríbelo brevemente."
            ]

        # ── Step 9: Solo añadir prefijo de alerta si no lo hizo LLM ─
        if alert and urgency == "alta" and "EMERGENCIA" not in reply.upper():
            reply = f"EMERGENCIA: {alert}\n\n{reply}"

        # ── Step 10: Update session ─────────────────────────────────
        self._update_session(session, request.message, reply, structured)

        return ChatResponse(
            session_id=str(session.id),
            reply=reply,
            structured=structured,
            needs_more_info=needs_more_info,
            clarification_questions=clarification_questions,
        )

    # ── Sub-paso: elección del servicio de PRIMER CONTACTO ────────
    async def _pick_service(
        self,
        specialty: str,
        urgency: str,
        symptom_names: list[str],
        condiciones: list[CondicionProbable],
    ) -> ServicioRecomendado | None:
        """Elige UN servicio de PRIMER CONTACTO dentro de la especialidad.

        Combina:
        (1) heurística determinística para emergencias con procedimiento
            diagnóstico inmediato,
        (2) LLM si está disponible,
        (3) fallback a 'consulta'.
        """
        catalog = self._specialty_services_catalog.get(specialty, [])
        if not catalog:
            return ServicioRecomendado(
                nombre="consulta", label="Consulta", razon="Default"
            )

        names = {s["name"] for s in catalog}

        # 1a) Alta urgencia + especialidad con emergencia propia
        if urgency == "alta":
            for k in ("atencion_emergencia", "estabilizacion", "trauma_mayor"):
                if k in names:
                    return ServicioRecomendado(
                        nombre=k,
                        label=next(s["label"] for s in catalog if s["name"] == k),
                        razon="Triaje de emergencia",
                    )

            # 1b) Procedimiento diagnóstico crítico de primer contacto
            critical_by_specialty = {
                "cardiologia": (
                    "electrocardiograma",
                    "Descartar infarto: ECG inmediato",
                ),
                "neurologia": (
                    "tomografia_cerebral",
                    "Descartar ACV: TAC de inmediato",
                ),
                "neumologia": (
                    "rx_torax",
                    "Descartar neumonía/tromboembolia: Rx tórax",
                ),
            }
            target = critical_by_specialty.get(specialty)
            if target and target[0] in names:
                tname, treason = target
                return ServicioRecomendado(
                    nombre=tname,
                    label=next(s["label"] for s in catalog if s["name"] == tname),
                    razon=treason,
                )

        # 2) LLM elige (si está disponible)
        if self.llm._available:
            try:
                pick = await self.llm.pick_service(
                    specialty=specialty,
                    urgency=urgency,
                    symptoms=symptom_names,
                    conditions=[{"nombre": c.nombre} for c in condiciones],
                    catalog=catalog,
                )
                if pick.get("service"):
                    name = pick["service"]
                    # Bloqueo de procedimientos programados como primer contacto
                    if name in _PROHIBITED_FIRST_CONTACT:
                        logger.warning(
                            "LLM eligió procedimiento programado como primer "
                            "contacto (%s). Forzando consulta.",
                            name,
                        )
                        default_name = (
                            "consulta" if "consulta" in names else catalog[0]["name"]
                        )
                        default_label = next(
                            s["label"] for s in catalog if s["name"] == default_name
                        )
                        return ServicioRecomendado(
                            nombre=default_name,
                            label=default_label,
                            razon="Evaluación inicial estándar",
                        )

                    label = next(
                        (s["label"] for s in catalog if s["name"] == name), name
                    )
                    return ServicioRecomendado(
                        nombre=name,
                        label=label,
                        razon=pick.get("razon", "Sugerencia del modelo"),
                    )
            except Exception as e:
                logger.warning("pick_service LLM falló: %s", e)

        # 3) Fallback: consulta (o el primer servicio del catálogo)
        default_name = "consulta" if "consulta" in names else catalog[0]["name"]
        default_label = next(
            s["label"] for s in catalog if s["name"] == default_name
        )
        return ServicioRecomendado(
            nombre=default_name,
            label=default_label,
            razon="Evaluación inicial estándar",
        )

    # ── Reply: LLM summarizer con fallback a template ─────────────
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
        servicio: ServicioRecomendado | None = None,
    ) -> str:
        if self.llm._available and (symptoms or condiciones):
            try:
                context = {
                    "mensaje_paciente": user_message,
                    "sintomas_detectados": [s.normalized for s in symptoms],
                    "urgencia": urgency,
                    "alerta": alert,
                    "especialidad_sugerida": specialties[0].name
                    if specialties
                    else None,
                    "condiciones_probables": [
                        {"nombre": c.nombre, "probabilidad": c.probabilidad}
                        for c in condiciones
                    ],
                    "servicio_recomendado": (
                        {
                            "nombre": servicio.nombre,
                            "label": servicio.label,
                            "razon": servicio.razon,
                        }
                        if servicio
                        else None
                    ),
                    "costo_base_usd": copago.costo_base if copago else None,
                    "copago_estimado_usd": copago.copago_estimado
                    if copago
                    else None,
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
                logger.warning("LLM summary falló, usando template: %s", e)

        return self._generate_reply(
            user_message,
            symptoms,
            specialties,
            urgency,
            alert,
            copago,
            hospitals,
            plan_id,
            servicio,
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
        servicio: ServicioRecomendado | None = None,
    ) -> str:
        if not symptoms and not specialties:
            return (
                "Necesito saber qué síntomas tienes para orientarte. "
                "Describe brevemente lo que sientes."
            )

        parts = []
        symptom_names = [s.normalized for s in symptoms]

        if symptom_names:
            parts.append(f"Sintomas: {', '.join(symptom_names)}.")

        if specialties:
            parts.append(f"Especialidad sugerida: {specialties[0].name}.")

        if servicio:
            parts.append(f"Servicio recomendado: {servicio.label}.")

        parts.append(f"Urgencia: {urgency}.")

        if copago:
            parts.append(
                f"Costo base ${copago.costo_base:.2f} USD. "
                f"Copago estimado: ${copago.copago_estimado:.2f} USD."
            )
            parts.append(f"Desglose: {copago.desglose}")

        if hospitals:
            parts.append("Hospitales recomendados:")
            for h in hospitals:
                dist = f" ({h.distancia_km} km)" if h.distancia_km else ""
                parts.append(
                    f"- {h.nombre} ({h.tipo}) — Copago: ${h.copago_paciente:.2f} USD{dist}"
                )

        if not plan_id:
            parts.append(
                "Sin plan de seguro no puedo calcular el copago exacto."
            )

        return "\n".join(parts)

    def _get_or_create_session(
        self, session_id: str | None, plan_id: int | None
    ) -> ChatSession:
        if session_id:
            session = (
                self.db.query(ChatSession)
                .filter(ChatSession.id == session_id)
                .first()
            )
            if session:
                if plan_id:
                    session.plan_id = plan_id
                return session
        session = ChatSession(plan_id=plan_id)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def _update_session(
        self,
        session: ChatSession,
        user_message: str,
        reply: str,
        structured: StructuredResponse,
    ):
        messages = session.messages or []
        messages.append(
            {
                "role": "user",
                "content": user_message,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": reply,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        session.messages = messages
        session.extracted_symptoms = structured.sintomas
        session.final_response = structured.model_dump()
        self.db.commit()
