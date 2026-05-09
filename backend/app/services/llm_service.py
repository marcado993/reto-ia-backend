"""Servicio LLM basado en Google Gemini (google-genai SDK).

Si `GEMINI_API_KEY` no está configurada, el servicio funciona en modo offline
(devuelve listas/strings vacías) sin romper el agente.
"""

from __future__ import annotations

import json
import logging
import re

from app.agent.prompts import (
    EXTRACTION_PROMPT,
    FEATURE_MAPPING_PROMPT,
    SUMMARY_PROMPT,
)
from app.config import settings
from app.schemas.symptom import SymptomExtraction

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self) -> None:
        self._available = bool(
            settings.GEMINI_API_KEY
            and not settings.GEMINI_API_KEY.startswith("AIza-your")
        )
        self.client = None
        self.model = settings.GEMINI_MODEL
        if self._available:
            try:
                from google import genai

                self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
                logger.info("LLM Service initialized with Gemini (%s)", self.model)
            except Exception as e:
                logger.warning("Could not initialize Gemini client: %s", e)
                self._available = False
        if not self._available:
            logger.info("LLM Service running in offline mode (no Gemini key)")

    # ── Helpers ────────────────────────────────────────────────────
    @staticmethod
    def _strip_json_fence(text: str) -> str:
        """Quita ```json ... ``` que Gemini suele devolver."""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

    async def _generate(self, system: str, user: str, json_mode: bool = False) -> str:
        if not self._available or not self.client:
            return ""
        try:
            from google.genai import types

            cfg_kwargs: dict = {
                "system_instruction": system,
                "temperature": settings.GEMINI_TEMPERATURE,
                "max_output_tokens": settings.GEMINI_MAX_TOKENS,
                # Apaga "thinking" en gemini-2.5-flash: si no, los tokens internos
                # de razonamiento se comen los de output y la respuesta sale truncada.
                "thinking_config": types.ThinkingConfig(thinking_budget=0),
            }
            if json_mode:
                cfg_kwargs["response_mime_type"] = "application/json"

            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=user,
                config=types.GenerateContentConfig(**cfg_kwargs),
            )
            text = (response.text or "").strip()
            if not text:
                logger.warning(
                    "Gemini devolvió texto vacío. finish_reason=%s, usage=%s",
                    getattr(response.candidates[0], "finish_reason", "?")
                    if response.candidates
                    else "?",
                    getattr(response, "usage_metadata", "?"),
                )
            return text
        except Exception as e:
            logger.error("Gemini call failed: %s", e)
            return ""

    # ── API pública ────────────────────────────────────────────────
    async def extract_symptoms_from_text(self, text: str) -> list[SymptomExtraction]:
        if not self._available:
            return []
        raw = await self._generate(EXTRACTION_PROMPT, text, json_mode=True)
        if not raw:
            return []
        try:
            parsed = json.loads(self._strip_json_fence(raw))
        except json.JSONDecodeError:
            logger.warning("Gemini devolvió JSON inválido: %r", raw[:200])
            return []

        symptoms_data = (
            parsed
            if isinstance(parsed, list)
            else parsed.get("symptoms", parsed.get("data", []))
        )

        results: list[SymptomExtraction] = []
        for s in symptoms_data:
            if isinstance(s, dict) and "normalized" in s:
                results.append(
                    SymptomExtraction(
                        raw_text=text,
                        normalized=s["normalized"],
                        severity=s.get("severity", "media"),
                        confidence=float(s.get("confidence", 0.8)),
                    )
                )
        return results

    async def chat(
        self,
        system: str,
        user: str,
        json_mode: bool = False,
    ) -> str:
        """Chat genérico (single-turn). Para multi-turn usaremos client.aio.chats."""
        return await self._generate(system, user, json_mode=json_mode)

    # ── Feature mapping (texto libre → features de EndlessMedical) ──
    async def map_text_to_features(
        self,
        patient_text: str,
        valid_features: list[str],
        age: int | None = None,
        gender: str | None = None,
    ) -> dict[str, str | int | float]:
        """Pide a Gemini que traduzca el relato del paciente a un dict de features.

        Devuelve SOLO features cuyo nombre exista en `valid_features` (defensa
        contra alucinaciones del LLM).
        """
        if not self._available:
            return {}

        user_payload = (
            f"features_validos (usa SOLO nombres de esta lista, son {len(valid_features)} en total):\n"
            f"{', '.join(valid_features)}\n\n"
            f"age: {age if age is not None else 'desconocida'}\n"
            f"gender: {gender or 'desconocido'}\n\n"
            f"patient_text: {patient_text}"
        )
        raw = await self._generate(
            FEATURE_MAPPING_PROMPT, user_payload, json_mode=True
        )
        if not raw:
            return {}
        try:
            parsed = json.loads(self._strip_json_fence(raw))
        except json.JSONDecodeError:
            logger.warning("Gemini devolvió JSON inválido en map_features: %r", raw[:200])
            return {}

        features = parsed.get("features", parsed)
        if not isinstance(features, dict):
            return {}

        valid_set = set(valid_features)
        cleaned: dict[str, str | int | float] = {}
        for name, value in features.items():
            if name in valid_set and value is not None:
                cleaned[name] = value
        return cleaned

    # ── Summary humano del diagnóstico ──────────────────────────────
    async def summarize_diagnosis(self, context: dict) -> str:
        """Recibe un dict con todo el contexto y devuelve la respuesta final
        redactada por Gemini. Si no está disponible, devuelve "" para que el
        agente caiga en su redacción por templates.
        """
        if not self._available:
            return ""
        user_payload = json.dumps(context, ensure_ascii=False, indent=2)
        return await self._generate(SUMMARY_PROMPT, user_payload, json_mode=False)
