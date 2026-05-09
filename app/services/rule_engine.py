import logging

from sqlalchemy.orm import Session

from app.models.medical_rule import MedicalRule
from app.schemas.specialty import SpecialtySuggestion

logger = logging.getLogger(__name__)

DEFAULT_URGENCY = "media"
DEFAULT_ALERT = None


class RuleEngine:
    def __init__(self, db: Session):
        self.db = db

    def evaluate(
        self, symptom_names: list[str], severity_notes: str = ""
    ) -> dict:
        rules = (
            self.db.query(MedicalRule)
            .order_by(MedicalRule.priority.asc())
            .all()
        )

        matched_rules = []
        for rule in rules:
            if rule.matches(symptom_names):
                matched_rules.append(rule)

        if not matched_rules:
            return self._evaluate_severity(symptom_names, severity_notes)

        best_rule = matched_rules[0]
        result = dict(best_rule.result) if best_rule.result else {}

        urgency = result.get("urgency", DEFAULT_URGENCY)
        specialties = result.get("specialties", [])
        alert = result.get("alert")

        if not alert and urgency == "alta":
            alert = "Se detectaron indicadores de urgencia. Se recomienda acudir a emergencias de inmediato."

        logger.info(f"Rule engine: symptoms={symptom_names} -> urgency={urgency}, specialties={specialties}")
        return {
            "urgency": urgency,
            "specialties": specialties,
            "alert": alert,
        }

    def _evaluate_severity(
        self, symptom_names: list[str], severity_notes: str
    ) -> dict:
        urgency = DEFAULT_URGENCY
        alert = DEFAULT_ALERT

        severe_keywords = ["intenso", "fuerte", "severo", "agudo", "insoportable"]
        moderate_keywords = ["moderado", "molesto", "constante", "persistente"]

        notes_lower = severity_notes.lower()
        if any(kw in notes_lower for kw in severe_keywords):
            urgency = "alta"
            alert = "Se describen sintomas de alta severidad. Considere atencion de urgencia."
        elif any(kw in notes_lower for kw in moderate_keywords):
            urgency = "media"

        if len(symptom_names) >= 3:
            if urgency == "media":
                urgency = "alta"
                alert = "Multiples sintomas combinados. Se recomienda evaluacion medica pronto."

        return {
            "urgency": urgency,
            "specialties": [],
            "alert": alert,
        }