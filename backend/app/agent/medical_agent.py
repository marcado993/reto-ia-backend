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
    ServicioRecomendado,
    StructuredResponse,
)
from app.models.hospital import Hospital
from app.schemas.symptom import SymptomExtraction
from app.schemas.specialty import SpecialtySuggestion
from app.schemas.copago import CopagoResult
from app.services.nlp_service import NLPService, strip_accents
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
        servicio: ServicioRecomendado | None = None

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

        # Step 2.5: Red-flag detector sobre el texto CRUDO (defensa contra
        # un NLP que falle en extraer dolor torácico irradiado, sudoración, etc.)
        red_flag = self._detect_cardiac_red_flags(request.message, symptom_names)
        if red_flag:
            for forced in red_flag.get("force_symptoms", []):
                if forced not in symptom_names:
                    symptom_names.append(forced)
                    raw_symptoms.append(SymptomExtraction(
                        raw_text=request.message,
                        normalized=forced,
                        severity="alta",
                        confidence=0.9,
                    ))
            # Re-correr ontología con los síntomas reforzados
            specialties = self.ontology.query_specialties(symptom_names)

        # Step 3: Evaluate rules for urgency
        if symptom_names:
            rule_result = self.rules.evaluate(symptom_names, request.message)
            urgency = rule_result.get("urgency", "media")
            alert = rule_result.get("alert")
            rule_specs = rule_result.get("specialties", [])
            if rule_specs:
                if urgency == "alta":
                    # En emergencia, las especialidades de la regla mandan
                    existing_names = {s.name for s in specialties}
                    boosted = [
                        SpecialtySuggestion(name=s, confidence=0.95, matching_symptoms=[])
                        for s in rule_specs if s not in existing_names
                    ]
                    in_rule = [s for s in specialties if s.name in rule_specs]
                    rest = [s for s in specialties if s.name not in rule_specs]
                    specialties = boosted + in_rule + rest
                elif not specialties:
                    specialties = [
                        SpecialtySuggestion(name=s, confidence=0.9, matching_symptoms=[])
                        for s in rule_specs
                    ]

        # Si el red-flag detector dictaminó IAM probable, su urgencia/alerta
        # tiene prioridad sobre cualquier regla que haya quedado en estado más bajo
        if red_flag:
            urgency = "alta"
            alert = red_flag.get("alert", alert)
            forced_specs = red_flag.get("specialties", [])
            existing_names = {s.name for s in specialties}
            boosted = [
                SpecialtySuggestion(name=s, confidence=0.97, matching_symptoms=[])
                for s in forced_specs if s not in existing_names
            ]
            in_rule = [s for s in specialties if s.name in forced_specs]
            rest = [s for s in specialties if s.name not in forced_specs]
            specialties = boosted + in_rule + rest

        # Step 3b: EndlessMedical → enfermedades probables (Gemini hace de traductor)
        if symptom_names and self.llm._available:
            condiciones_probables = await self._diagnose_with_endless_medical(
                request.message, request.age, request.gender
            )

        # Step 4: Pick the specific service within the specialty
        plan_id = request.plan_id or (session.plan_id if session.plan_id else None)
        primary_specialty = specialties[0].name if specialties else None
        service_name: str | None = None

        if primary_specialty:
            servicio = await self._pick_service(
                primary_specialty, urgency, symptom_names, condiciones_probables
            )
            service_name = servicio.nombre if servicio else None

        # Step 5: Calculate copago and find hospital with the chosen service
        if plan_id and primary_specialty:
            try:
                service_type = "emergencia" if urgency == "alta" else "consulta"
                copago_result = self.copago.calculate(
                    plan_id, service_type, primary_specialty, service_name=service_name,
                )
            except Exception as e:
                logger.error(f"Copago calculation error: {e}")

        if plan_id and primary_specialty:
            try:
                hospital_results = self.hospitals.find_best(
                    plan_id, primary_specialty, urgency, service_name=service_name,
                )
            except Exception as e:
                logger.error(f"Hospital search error: {e}")

        # Step 6: Build structured response (antes del reply, así Gemini lo recibe)
        # NOTA: el cliente solo necesita UNA especialidad (la primary). La lista
        # completa se mantiene en memoria para el ranking interno pero no se expone.
        structured = StructuredResponse(
            sintomas=symptom_names,
            urgencia=urgency,
            especialidades_sugeridas=[primary_specialty] if primary_specialty else [],
            condiciones_probables=condiciones_probables,
            servicio_recomendado=servicio,
            plan_seguro=copago_result.plan_nombre if copago_result else "",
            costo_base=copago_result.costo_base if copago_result else 0.0,
            copago_estimado=copago_result.copago_estimado if copago_result else 0.0,
            moneda="USD",
            hospital_recomendado=hospital_results[0] if hospital_results else None,
            hospitales_comparacion=hospital_results,
            desglose_cobertura=copago_result.desglose if copago_result else "",
        )

        # Step 7: Generate text reply (Gemini si está disponible, fallback a template)
        reply = await self._generate_reply_smart(
            request.message, raw_symptoms, specialties, urgency, alert,
            copago_result, hospital_results, plan_id, condiciones_probables, servicio,
        )

        # Step 8: Determine if we need more info
        needs_more_info = len(symptom_names) == 0 or (plan_id is None and len(symptom_names) > 0)
        clarification_questions = []
        if needs_more_info:
            clarification_questions = self._generate_clarifications(symptom_names, plan_id)

        # Step 9: Solo añadir prefijo de alerta si Gemini no lo hizo y la urgencia es alta.
        if alert and urgency == "alta" and "EMERGENCIA" not in reply.upper():
            reply = f"EMERGENCIA: {alert}\n\n{reply}"

        # Step 10: Update session
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

    # ── Sub-paso: red-flags cardíacos (defensa contra NLP fallido) ──
    @staticmethod
    def _detect_cardiac_red_flags(
        text: str, symptom_names: list[str]
    ) -> dict | None:
        """Inspecciona el texto crudo en busca de combinaciones que sugieren
        síndrome coronario agudo (IAM, angina inestable). Si la suma de
        evidencia supera un umbral, fuerza urgencia=alta y especialidad
        cardiología/emergencias, e inyecta los síntomas que el NLP perdió.

        Esto compensa fallos del extractor (tildes, sinónimos, fuzzy ruidoso).
        """
        t = strip_accents(text.lower())
        sx = {s.lower() for s in symptom_names}

        pecho = (
            any(k in t for k in ["pecho", "torax", "toracico", "esternon"])
            or "dolor toracico" in sx
        )
        presion = any(k in t for k in [
            "presion", "opresion", "aplastante", "apretado",
            "como un peso", "no me deja respirar",
        ])
        sudor = (
            any(k in t for k in ["sudo", "sudor", "transpiracion", "sudoracion"])
            or "sudoracion excesiva" in sx
        )
        brazo_izq = any(k in t for k in [
            "brazo izquierdo", "brazo derecho", "irradia al brazo",
            "se va al brazo", "dolor en el brazo",
        ]) or "dolor en el brazo" in sx
        mandibula = any(k in t for k in [
            "mandibula", "quijada", "maxilar",
        ])
        cuello = any(k in t for k in ["cuello"]) and pecho
        disnea = any(k in t for k in [
            "falta el aire", "falta aire", "no puedo respirar",
            "me cuesta respirar", "dificultad para respirar", "ahogo",
        ]) or "disnea" in sx
        esfuerzo = any(k in t for k in [
            "al caminar", "al esfuerzo", "cuando camino", "subiendo",
            "al subir escaleras", "haciendo esfuerzo",
        ])

        # Antecedentes de riesgo cardiovascular (cuentan pero no son síntomas)
        antecedentes = sum([
            any(k in t for k in ["hipertension", "presion alta", "hipertenso"]),
            any(k in t for k in ["diabetes", "diabetico", "glucosa alta"]),
            any(k in t for k in ["colesterol", "dislipidemia", "trigliceridos"]),
            any(k in t for k in [
                "arteria tapada", "arterias tapadas", "stent",
                "cateterismo", "infarto previo", "bypass",
            ]),
            any(k in t for k in ["fumo", "fumador", "tabaco", "cigarrillo"]),
        ])

        score = 0
        if pecho and (brazo_izq or mandibula or cuello): score += 4
        if pecho and presion: score += 2
        if pecho and sudor: score += 2
        if pecho and disnea: score += 2
        if pecho and esfuerzo: score += 2
        if (brazo_izq or mandibula) and sudor: score += 1
        score += min(antecedentes, 3)  # tope: 3 puntos por antecedentes

        if score >= 5:
            forced = ["dolor toracico"]
            if sudor and "sudoracion excesiva" not in sx:
                forced.append("sudoracion excesiva")
            if disnea and "disnea" not in sx:
                forced.append("disnea")
            if brazo_izq and "dolor en el brazo" not in sx:
                forced.append("dolor en el brazo")
            return {
                "urgency": "alta",
                "specialties": ["cardiologia", "emergencias"],
                "alert": (
                    "Síndrome coronario agudo probable (dolor torácico "
                    "irradiado + síntomas neurovegetativos + factores de "
                    "riesgo). Llame al ECU-911 ahora, no conduzca usted mismo."
                ),
                "force_symptoms": forced,
                "score": score,
            }
        return None

    # ── Sub-paso: elección del servicio dentro de la especialidad ──
    async def _pick_service(
        self,
        specialty: str,
        urgency: str,
        symptom_names: list[str],
        condiciones: list[CondicionProbable],
    ) -> ServicioRecomendado | None:
        """Elige UN servicio dentro de la especialidad combinando:
        (1) heurística determinística para casos obvios,
        (2) Gemini si está disponible para el resto,
        (3) fallback a 'consulta'."""
        # Catálogo de servicios disponibles (cualquier hospital sirve, todos
        # comparten el mismo catálogo).
        sample = self.db.query(Hospital).filter(
            Hospital.specialty_costs.isnot(None)
        ).first()
        catalog = sample.list_services(specialty) if sample else []

        if not catalog:
            return ServicioRecomendado(nombre="consulta", label="Consulta", razon="Default")

        names = {s["name"] for s in catalog}

        # 1a) Alta urgencia: si la especialidad tiene servicio de emergencia
        # (típico de "emergencias"), úsalo de inmediato.
        if urgency == "alta":
            for k in ("atencion_emergencia", "estabilizacion", "trauma_mayor"):
                if k in names:
                    return ServicioRecomendado(
                        nombre=k,
                        label=next(s["label"] for s in catalog if s["name"] == k),
                        razon="Triaje de emergencia",
                    )

            # 1b) Alta urgencia + especialidad clínica: usar el procedimiento
            # diagnóstico crítico que se hace en el primer contacto (no consulta).
            critical_by_specialty = {
                "cardiologia": ("electrocardiograma", "Descartar infarto: ECG inmediato"),
                "neurologia": ("tomografia_cerebral", "Descartar ACV: TAC de inmediato"),
                "neumologia": ("rx_torax", "Descartar tromboembolia/neumonía: Rx tórax"),
                "gastroenterologia": ("endoscopia_alta", "Sangrado o perforación: endoscopía urgente"),
                "urologia": ("uroflujometria", "Evaluación urgente"),
            }
            target = critical_by_specialty.get(specialty)
            if target and target[0] in names:
                tname, treason = target
                return ServicioRecomendado(
                    nombre=tname,
                    label=next(s["label"] for s in catalog if s["name"] == tname),
                    razon=treason,
                )

        # 2) Heurística por palabras clave en condiciones / síntomas
        joined = " ".join(
            [c.nombre.lower() for c in condiciones]
            + [s.lower() for s in symptom_names]
        )
        keyword_map = [
            ("infarto", "electrocardiograma"),
            ("isquemia", "electrocardiograma"),
            ("arritmia", "electrocardiograma"),
            ("colon", "colonoscopia"),
            ("ulcera", "endoscopia_alta"),
            ("reflujo", "endoscopia_alta"),
            ("embarazo", "ecografia_pelvica"),
            ("menstrual", "ecografia_pelvica"),
            ("epilepsia", "electroencefalograma"),
            ("convuls", "electroencefalograma"),
            ("migraña", "tomografia_cerebral"),
            ("cefalea severa", "tomografia_cerebral"),
            ("asma", "espirometria"),
            ("epoc", "espirometria"),
            ("sueño", "polisomnografia"),
            ("diabetes", "perfil_diabetes"),
            ("tiroides", "perfil_tiroideo"),
            ("alergia", "test_alergeno"),
            ("catarata", "cirugia_catarata"),
            ("apend", "apendicectomia"),
            ("hernia", "hernioplastia"),
            ("vesicul", "colecistectomia"),
            ("cancer", "biopsia"),
            ("tumor", "biopsia"),
            ("varices", "varices_escleroterapia"),
            ("calculo renal", "litotripsia"),
            ("piedra rinon", "litotripsia"),
        ]
        for kw, target in keyword_map:
            if kw in joined and target in names:
                return ServicioRecomendado(
                    nombre=target,
                    label=next(s["label"] for s in catalog if s["name"] == target),
                    razon=f"Sugerido por '{kw}' en el cuadro clínico",
                )

        # 3) Gemini elige (si está disponible)
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
                    label = next((s["label"] for s in catalog if s["name"] == name), name)
                    return ServicioRecomendado(
                        nombre=name,
                        label=label,
                        razon=pick.get("razon", "Sugerencia del modelo"),
                    )
            except Exception as e:
                logger.warning("pick_service Gemini falló: %s", e)

        # 4) Fallback: consulta (o el primer servicio del catálogo)
        default_name = "consulta" if "consulta" in names else catalog[0]["name"]
        default_label = next(s["label"] for s in catalog if s["name"] == default_name)
        return ServicioRecomendado(
            nombre=default_name,
            label=default_label,
            razon="Evaluación inicial estándar",
        )

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
        servicio: ServicioRecomendado | None = None,
    ) -> str:
        if self.llm._available and (symptoms or condiciones):
            try:
                context = {
                    "mensaje_paciente": user_message,
                    "sintomas_detectados": [s.normalized for s in symptoms],
                    "urgencia": urgency,
                    "alerta": alert,
                    "especialidad_sugerida": specialties[0].name if specialties else None,
                    "condiciones_probables": [
                        {"nombre": c.nombre, "probabilidad": c.probabilidad}
                        for c in condiciones
                    ],
                    "servicio_recomendado": (
                        {"nombre": servicio.nombre, "label": servicio.label, "razon": servicio.razon}
                        if servicio else None
                    ),
                    "costo_base_usd": copago.costo_base if copago else None,
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
            copago, hospitals, plan_id, servicio,
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
                "Necesito mas datos clinicos para predecir. Describe: que sintoma tienes, "
                "intensidad (1-10), duracion, ubicacion exacta, y que lo empeora o alivia. "
                "Adjunta tu plan de seguro para calcular copago y hospital."
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