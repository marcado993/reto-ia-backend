import json
import logging
import re
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from app.models.symptom import Symptom
from app.schemas.symptom import SymptomExtraction

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

WORD_BOUNDARY_RE = re.compile(r'\b')


def strip_accents(text: str) -> str:
    """Quita tildes/acentos para que 'presión' matchee con 'presion'."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


TEXT_NORMALIZATIONS = {
    # ── Cabeza / cuello ──────────────────────────────────────────
    "me duele la cabeza": "cefalea",
    "me duele el cuello": "dolor en el cuello",
    "rigidez en el cuello": "rigidez de nuca",
    "cuello rigido": "rigidez de nuca",
    "me duele el oido": "dolor de oido",
    "me duele la garganta": "dolor de garganta",
    "no puedo dormir": "insomnio",
    # ── Tórax / cardio ───────────────────────────────────────────
    "me duele el pecho": "dolor toracico",
    "me duele el torax": "dolor toracico",
    "dolor en el pecho": "dolor toracico",
    "presion en el pecho": "dolor toracico",
    "presion fuerte en el pecho": "dolor toracico",
    "opresion en el pecho": "dolor toracico",
    "siento presion": "dolor toracico",
    "presion fuerte pecho": "dolor toracico",
    "me aprieta el pecho": "dolor toracico",
    "ardor en el pecho": "dolor toracico",
    "me duele el corazon": "dolor toracico",
    "dolor irradiado al brazo": "dolor en el brazo",
    "dolor en la mandibula": "dolor toracico",
    "dolor en la quijada": "dolor toracico",
    "me duele la mandibula": "dolor toracico",
    "tengo palpitaciones": "palpitaciones",
    # ── Respiratorio ─────────────────────────────────────────────
    "no puedo respirar": "disnea",
    "me cuesta respirar": "disnea",
    "me falta el aire": "disnea",
    "falta de aire": "disnea",
    "ahogamiento": "disnea",
    "ahogo": "disnea",
    "respiro con dificultad": "disnea",
    # ── Sudoración / neurovegetativo ────────────────────────────
    "sudo mucho": "sudoracion excesiva",
    "sudo frio": "sudoracion excesiva",
    "sudor frio": "sudoracion excesiva",
    "tengo sudor frio": "sudoracion excesiva",
    "estoy sudando": "sudoracion excesiva",
    "transpiracion excesiva": "sudoracion excesiva",
    # ── Abdomen ──────────────────────────────────────────────────
    "me duele la barriga": "dolor abdominal",
    "me duele el estomago": "dolor abdominal",
    "tengo colico": "dolor abdominal",
    "me duele la espalda": "dolor lumbar",
    "se me sale el estomago": "ardor de estomago",
    # ── Piernas / extremidades ──────────────────────────────────
    "se me hincharon las piernas": "hinchazon de piernas",
    "se me hincho la cara": "hinchazon",
    "se me durmieron las manos": "entumecimiento",
    "se me durmieron los pies": "entumecimiento",
    # ── Piel ─────────────────────────────────────────────────────
    "me pica la piel": "picazon",
    "se me salen ronchas": "erupcion cutanea",
    # ── Genitourinario ───────────────────────────────────────────
    "tengo mucha sed": "sed excesiva",
    "orino mucho": "orina frecuente",
    "me arde al orinar": "disuria",
    # ── Generales ────────────────────────────────────────────────
    "me marea": "mareo",
    "tengo sangrado": "sangrado",
    "me sangra": "sangrado",
    "me-desmayo": "perdida de conciencia",
    "me-desmaye": "perdida de conciencia",
    "tengo tos": "tos",
    "tengo fiebre": "fiebre",
}


class NLPService:
    def __init__(self, db: Session):
        self.db = db
        self._symptom_cache: list[Symptom] = []

    def _load_symptoms(self) -> list[Symptom]:
        if not self._symptom_cache:
            self._symptom_cache = self.db.query(Symptom).all()
        return self._symptom_cache

    def extract_symptoms(self, text: str, confidence_threshold: float = 0.65) -> list[SymptomExtraction]:
        symptoms = self._load_symptoms()
        if not symptoms:
            logger.warning("No symptoms loaded in DB, using fallback")
            return self._extract_from_fallback(text)

        # Normalizar: minúsculas + sin tildes para que "presión" matchee "presion"
        text_lower_raw = strip_accents(text.lower().strip())
        for colloquial, medical in TEXT_NORMALIZATIONS.items():
            words = colloquial.split()
            if all(w in text_lower_raw for w in words):
                text_lower_raw = text_lower_raw + " " + medical
        text_lower = f" {text_lower_raw} "
        text_words = set(re.findall(r'\b\w+\b', text_lower))
        results: dict[int, SymptomExtraction] = {}

        for symptom in symptoms:
            name_words = set(re.findall(r'\b\w+\b', symptom.name.lower()))
            if name_words.issubset(text_words):
                if symptom.id not in results:
                    results[symptom.id] = SymptomExtraction(
                        raw_text=text,
                        normalized=symptom.name,
                        icd11_code=symptom.icd11_code,
                        severity=symptom.severity_default,
                        body_system=symptom.body_system,
                        confidence=1.0,
                    )
                continue

            for syn in (symptom.synonyms or []):
                syn_words = set(re.findall(r'\b\w+\b', syn.lower()))
                if syn_words.issubset(text_words):
                    if symptom.id not in results:
                        results[symptom.id] = SymptomExtraction(
                            raw_text=text,
                            normalized=symptom.name,
                            icd11_code=symptom.icd11_code,
                            severity=symptom.severity_default,
                            body_system=symptom.body_system,
                            confidence=0.95,
                        )
                    break

            if symptom.id in results:
                continue

            all_keywords = [symptom.name] + (symptom.synonyms or [])
            matched_keyword = False
            for kw in all_keywords:
                kw_lower = kw.lower()
                if len(kw_lower) >= 6 and f" {kw_lower} " in text_lower:
                    if symptom.id not in results:
                        results[symptom.id] = SymptomExtraction(
                            raw_text=text,
                            normalized=symptom.name,
                            icd11_code=symptom.icd11_code,
                            severity=symptom.severity_default,
                            body_system=symptom.body_system,
                            confidence=0.85,
                        )
                    matched_keyword = True
                    break

            if matched_keyword:
                continue

            key_words = set(re.findall(r'\b\w{4,}\b', symptom.name.lower()))
            key_words |= {w for syn in (symptom.synonyms or []) for w in re.findall(r'\b\w{4,}\b', syn.lower())}
            overlap = key_words & text_words
            if len(overlap) >= max(1, len(key_words) - 1):
                if symptom.id not in results:
                    results[symptom.id] = SymptomExtraction(
                        raw_text=text,
                        normalized=symptom.name,
                        icd11_code=symptom.icd11_code,
                        severity=symptom.severity_default,
                        body_system=symptom.body_system,
                        confidence=0.75,
                    )

        if len(results) < 3:
            existing_ids = set(results.keys())
            terms_dict: dict[str, int] = {}
            for symptom in symptoms:
                if symptom.id in existing_ids:
                    continue
                terms_dict[symptom.name.lower()] = symptom.id
                for syn in (symptom.synonyms or []):
                    terms_dict[syn.lower()] = symptom.id

            phrases = self._generate_phrases(text_lower)
            for phrase in phrases:
                if len(phrase) < 4:
                    continue
                matches = process.extract(
                    phrase,
                    list(terms_dict.keys()),
                    scorer=fuzz.ratio,
                    limit=3,
                )
                for match_term, score, _ in matches:
                    if score >= 85:
                        symptom_id = terms_dict.get(match_term.lower())
                        if symptom_id and symptom_id not in results and symptom_id not in existing_ids:
                            symptom_obj = next((s for s in symptoms if s.id == symptom_id), None)
                            if symptom_obj:
                                conf = round(score / 100.0, 2)
                                if conf >= confidence_threshold:
                                    results[symptom_id] = SymptomExtraction(
                                        raw_text=text,
                                        normalized=symptom_obj.name,
                                        icd11_code=symptom_obj.icd11_code,
                                        severity=symptom_obj.severity_default,
                                        body_system=symptom_obj.body_system,
                                        confidence=conf,
                                    )

        filtered = [r for r in results.values() if r.confidence >= confidence_threshold]
        logger.info(f"Extracted {len(filtered)} symptoms from text: {text[:80]}")
        return filtered

    def _generate_phrases(self, text: str) -> list[str]:
        words = text.split()
        phrases = []
        for i in range(len(words)):
            for length in range(2, min(5, len(words) - i + 1)):
                phrase = " ".join(words[i : i + length])
                phrases.append(phrase)
        return phrases

    def _extract_from_fallback(self, text: str) -> list[SymptomExtraction]:
        fallback_path = DATA_DIR / "seed_symptoms.json"
        if not fallback_path.exists():
            return []
        with open(fallback_path, encoding="utf-8") as f:
            symptoms_data = json.load(f)

        text_lower = text.lower()
        results = []
        for s in symptoms_data:
            name_words = set(re.findall(r'\b\w+\b', s["name"].lower()))
            text_words = set(re.findall(r'\b\w+\b', text_lower))
            name_match = name_words.issubset(text_words)
            synonyms_match = any(
                set(re.findall(r'\b\w+\b', syn.lower())).issubset(text_words)
                for syn in s.get("synonyms", [])
            )
            if name_match or synonyms_match:
                results.append(
                    SymptomExtraction(
                        raw_text=text,
                        normalized=s["name"],
                        icd11_code=s.get("hpo_id"),
                        severity=s.get("severity_default", "media"),
                        body_system=s.get("body_part"),
                        confidence=0.8 if name_match else 0.7,
                    )
                )
        return results