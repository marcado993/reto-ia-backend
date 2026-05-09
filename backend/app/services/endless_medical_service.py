"""Cliente de la API pública EndlessMedical (detección de enfermedades).

Documentación oficial:
    https://endlessmedical.com/wp-content/uploads/EndlessMedical%20API%20v%201.0%20User%20Guide.pdf

NO requiere API key ni registro.
Es session-based: cada conversación abre una sesión, le mete features
(síntomas + datos del paciente), y al final llama a /Analyze.

Flujo (4 pasos):
    1. init_session()                       → SessionID
    2. accept_terms(session_id)             → obligatorio para /Analyze
    3. update_feature(session_id, name, val)  N veces
    4. analyze(session_id)                  → diseases con probabilidades

Ejemplo de feature names: "Age", "BMI", "Temp", "ChestPainRadiates", ...
La lista completa la obtienes en runtime con `get_features()`.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Frase EXACTA exigida por la API. No la modifiques.
TERMS_PASSPHRASE = (
    "I have read, understood and I accept and agree to comply with the "
    "Terms of Use of EndlessMedicalAPI and Endless Medical services. "
    "The Terms of Use are available on endlessmedical.com"
)


class EndlessMedicalError(RuntimeError):
    """Error devuelto por la API o de red."""


class EndlessMedicalService:
    # Cache compartido entre instancias (la lista es estática).
    _features_cache: list[str] | None = None
    _outcomes_cache: list[str] | None = None

    def __init__(self) -> None:
        self.base_url = settings.ENDLESS_MEDICAL_BASE.rstrip("/")
        self._timeout = settings.ENDLESS_MEDICAL_TIMEOUT

    # ── HTTP helpers ──────────────────────────────────────────────
    def _check(self, resp: httpx.Response) -> dict[str, Any]:
        if resp.status_code >= 400:
            raise EndlessMedicalError(
                f"HTTP {resp.status_code} en {resp.url}: {resp.text[:300]}"
            )
        try:
            data = resp.json()
        except Exception as e:
            raise EndlessMedicalError(f"Respuesta no-JSON: {resp.text[:300]}") from e
        if data.get("status") == "error":
            raise EndlessMedicalError(data.get("error", "error desconocido"))
        return data

    async def _get(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self.base_url}/{path}", params=params or {})
        return self._check(resp)

    async def _post(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            # EndlessMedical usa query string también para POST. Body vacío.
            resp = await client.post(f"{self.base_url}/{path}", params=params or {})
        return self._check(resp)

    # ── Metadata (sin sesión, con cache) ──────────────────────────
    async def get_features(self, use_cache: bool = True) -> list[str]:
        """Lista de features (síntomas/medidas) que reconoce la API."""
        if use_cache and EndlessMedicalService._features_cache is not None:
            return EndlessMedicalService._features_cache
        data = await self._get("GetFeatures")
        EndlessMedicalService._features_cache = data.get("data", [])
        return EndlessMedicalService._features_cache

    async def get_outcomes(self, use_cache: bool = True) -> list[str]:
        """Lista de enfermedades que la API puede detectar."""
        if use_cache and EndlessMedicalService._outcomes_cache is not None:
            return EndlessMedicalService._outcomes_cache
        data = await self._get("GetOutcomes")
        EndlessMedicalService._outcomes_cache = data.get("data", [])
        return EndlessMedicalService._outcomes_cache

    # ── Sesión ────────────────────────────────────────────────────
    async def init_session(self) -> str:
        data = await self._get("InitSession")
        session_id = data.get("SessionID")
        if not session_id:
            raise EndlessMedicalError(f"No se recibió SessionID: {data}")
        return session_id

    async def accept_terms(self, session_id: str) -> None:
        await self._post(
            "AcceptTermsOfUse",
            params={"SessionID": session_id, "passphrase": TERMS_PASSPHRASE},
        )

    # ── Features ──────────────────────────────────────────────────
    async def update_feature(
        self, session_id: str, name: str, value: str | float | int
    ) -> None:
        await self._post(
            "UpdateFeature",
            params={"SessionID": session_id, "name": name, "value": str(value)},
        )

    async def update_features(
        self, session_id: str, features: dict[str, Any]
    ) -> None:
        """Helper para subir varios features en serie."""
        for name, value in features.items():
            await self.update_feature(session_id, name, value)

    # ── Sugerencias (opcional, para entrevista guiada) ────────────
    async def get_suggested_features_patient(self, session_id: str) -> list[str]:
        data = await self._get(
            "GetSuggestedFeatures_PatientProvided", params={"SessionID": session_id}
        )
        return data.get("SuggestedFeatures", [])

    # ── Análisis ──────────────────────────────────────────────────
    async def analyze(self, session_id: str, top_k: int = 5) -> list[dict]:
        """Devuelve las top_k enfermedades con su probabilidad.

        Formato de salida:
            [{"name": "Migraine", "probability": 0.42},
             {"name": "Tension headache", "probability": 0.18},
             ...]
        """
        data = await self._get("Analyze", params={"SessionID": session_id})
        diseases_raw = data.get("Diseases", [])
        result: list[dict] = []
        for entry in diseases_raw[:top_k]:
            if not isinstance(entry, dict) or not entry:
                continue
            (name, prob), = entry.items()
            try:
                prob_f = float(prob)
            except (TypeError, ValueError):
                prob_f = 0.0
            result.append({"name": name, "probability": prob_f})
        return result

    # ── Atajo "todo en uno" para el agente ────────────────────────
    async def diagnose(
        self, features: dict[str, Any], top_k: int = 5
    ) -> list[dict]:
        """Diagnóstico end-to-end: abre sesión, sube features, analiza.

        `features` es un dict como {"Age": 35, "GenderMale": 1, "Temp": 38.5, ...}.
        Los nombres deben coincidir con los de get_features().
        """
        session_id = await self.init_session()
        logger.info("[EM.diagnose] session=%s, subiendo %d features", session_id, len(features))
        await self.accept_terms(session_id)

        ok, ko = 0, []
        for name, value in features.items():
            try:
                await self.update_feature(session_id, name, value)
                ok += 1
            except EndlessMedicalError as e:
                ko.append((name, value, str(e)[:120]))
        if ko:
            logger.warning("[EM.diagnose] features rechazadas: %s", ko)
        logger.info("[EM.diagnose] %d features aceptadas, llamando /Analyze", ok)

        if ok == 0:
            return []
        return await self.analyze(session_id, top_k=top_k)
