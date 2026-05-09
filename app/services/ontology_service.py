import logging
from collections import Counter

from sqlalchemy.orm import Session

from app.models.symptom import Symptom
from app.models.specialty import Specialty
from app.schemas.specialty import SpecialtySuggestion

logger = logging.getLogger(__name__)


class OntologyService:
    def __init__(self, db: Session):
        self.db = db
        self._symptom_cache: dict[str, Symptom] = {}

    def _load_symptom(self, name: str) -> Symptom | None:
        if name.lower() not in self._symptom_cache:
            result = self.db.query(Symptom).filter(Symptom.name.ilike(name)).first()
            if result:
                self._symptom_cache[result.name.lower()] = result
        return self._symptom_cache.get(name.lower())

    def query_specialties(self, symptom_names: list[str]) -> list[SpecialtySuggestion]:
        specialty_score: Counter = Counter()
        specialty_symptoms: dict[str, list[str]] = {}

        for symptom_name in symptom_names:
            symptom = self._load_symptom(symptom_name)
            if not symptom:
                logger.warning(f"Symptom not found in ontology: {symptom_name}")
                continue

            for spec_name in (symptom.related_specialties or []):
                specialty_score[spec_name] += 1
                if spec_name not in specialty_symptoms:
                    specialty_symptoms[spec_name] = []
                specialty_symptoms[spec_name].append(symptom.name)

        total_symptoms = len(symptom_names)
        results = []
        for spec_name, count in specialty_score.most_common():
            confidence = min(count / max(total_symptoms, 1), 1.0)
            spec = self.db.query(Specialty).filter(Specialty.name.ilike(spec_name)).first()
            results.append(
                SpecialtySuggestion(
                    name=spec_name,
                    icd11_chapter=spec.icd11_chapter if spec else None,
                    confidence=round(confidence, 2),
                    matching_symptoms=specialty_symptoms.get(spec_name, []),
                )
            )

        logger.info(f"Ontology query for {symptom_names} -> {[r.name for r in results]}")
        return results

    def get_symptom_details(self, symptom_name: str) -> dict | None:
        symptom = self._load_symptom(symptom_name)
        if not symptom:
            return None
        return {
            "name": symptom.name,
            "icd11_code": symptom.icd11_code,
            "body_system": symptom.body_system,
            "severity_default": symptom.severity_default,
            "related_specialties": symptom.related_specialties,
            "urgency_rules": symptom.urgency_rules,
        }