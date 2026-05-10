"""Servicio LLM: OpenRouter (API OpenAI-compatible) con fallback opcional a Gemini.

Si no hay `OPENROUTER_API_KEY` ni `GEMINI_API_KEY` válidas, el servicio opera en
modo offline (respuestas vacías) sin romper el agente.
"""

from __future__ import annotations

import json
import logging
import re

from app.agent.prompts import (
    EXTRACTION_PROMPT,
    PATIENT_ANALYSIS_PROMPT,
    SERVICE_PICK_PROMPT,
    SUMMARY_PROMPT,
    SYSTEM_PROMPT,
)
from app.config import settings
from app.schemas.chat import CondicionProbable
from app.schemas.symptom import SymptomExtraction

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self) -> None:
        self._backend: str | None = None
        self._openai = None
        self._gemini_client = None
        self.model = ""
        self._available = False
        self._fallback_models: list[str] = []

        # ── 1) Groq (primario) ───────────────────────────────────────
        groq_key = (settings.GROQ_API_KEY or "").strip()
        if groq_key and not groq_key.startswith(("gsk-your", "changeme")):
            try:
                from openai import AsyncOpenAI

                self._openai = AsyncOpenAI(
                    base_url=settings.GROQ_BASE_URL.rstrip("/"),
                    api_key=groq_key,
                    timeout=settings.GROQ_TIMEOUT,
                    max_retries=1,
                )
                self.model = settings.GROQ_MODEL
                self._backend = "groq"
                self._available = True
                # Parsear modelos fallback
                fallback = (settings.GROQ_FALLBACK_MODELS or "").strip()
                if fallback:
                    self._fallback_models = [m.strip() for m in fallback.split(",") if m.strip()]
                logger.info(
                    "LLM Service: Groq, modelo %s, fallbacks=%s",
                    self.model, self._fallback_models,
                )
            except Exception as e:
                logger.warning("No se pudo inicializar Groq: %s", e)

        # ── 2) OpenRouter (fallback) ─────────────────────────────────
        if not self._available:
            or_key = (settings.OPENROUTER_API_KEY or "").strip()
            if or_key and not or_key.startswith(("sk-or-your", "changeme")):
                try:
                    from openai import AsyncOpenAI

                    ref = (settings.OPENROUTER_HTTP_REFERER or "").strip()
                    headers_fixed: dict[str, str] = {"X-Title": settings.APP_NAME}
                    if ref:
                        headers_fixed["HTTP-Referer"] = ref
                    self._openai = AsyncOpenAI(
                        base_url=settings.OPENROUTER_BASE_URL.rstrip("/"),
                        api_key=or_key,
                        default_headers=headers_fixed,
                        timeout=settings.OPENROUTER_TIMEOUT,
                        max_retries=1,
                    )
                    self.model = settings.OPENROUTER_MODEL
                    self._backend = "openrouter"
                    self._available = True
                    logger.info("LLM Service: OpenRouter, modelo %s", self.model)
                except Exception as e:
                    logger.warning("No se pudo inicializar OpenRouter: %s", e)

        # ── 3) Gemini (fallback legado) ──────────────────────────────
        if not self._available:
            gem_ok = bool(
                settings.GEMINI_API_KEY
                and not settings.GEMINI_API_KEY.startswith("AIza-your")
            )
            if gem_ok:
                try:
                    from google import genai

                    self._gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
                    self.model = settings.GEMINI_MODEL
                    self._backend = "gemini"
                    self._available = True
                    logger.info("LLM Service: Gemini directo (%s)", self.model)
                except Exception as e:
                    logger.warning("No se pudo inicializar Gemini: %s", e)

        if not self._available:
            logger.info("LLM Service en modo offline (sin API key de LLM)")

    # ── Helpers ────────────────────────────────────────────────────
    @staticmethod
    def _strip_json_fence(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

    async def _generate_openrouter(
        self, system: str, user: str, json_mode: bool = False, model: str | None = None
    ) -> str:
        if not self._openai:
            return ""
        try:
            if self._backend == "groq":
                max_tokens = settings.GROQ_MAX_TOKENS
                temperature = settings.GROQ_TEMPERATURE
            else:
                max_tokens = settings.OPENROUTER_MAX_TOKENS
                temperature = settings.OPENROUTER_TEMPERATURE

            kwargs: dict = {
                "model": model or self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            try:
                resp = await self._openai.chat.completions.create(**kwargs)
            except Exception as e1:
                if json_mode:
                    logger.debug(
                        "OpenRouter json_object falló (%s), reintentando sin response_format",
                        e1,
                    )
                    kwargs.pop("response_format", None)
                    resp = await self._openai.chat.completions.create(**kwargs)
                else:
                    raise
            text = (resp.choices[0].message.content or "").strip()
            if not text:
                logger.warning("OpenRouter devolvió texto vacío")
            return text
        except Exception as e:
            logger.error("OpenRouter falló: %s", e)
            return ""

    async def _generate_with_fallback(
        self, system: str, user: str, json_mode: bool = False
    ) -> str:
        """Genera texto intentando el modelo primario y rotando por fallbacks."""
        if not self._available:
            return ""

        # Intentar modelo primario
        result = await self._generate_openrouter(system, user, json_mode=json_mode)
        if result:
            return result

        # Si falló y hay fallbacks, rotar
        if self._backend in ("groq", "openrouter") and self._fallback_models:
            for fallback_model in self._fallback_models:
                logger.warning(
                    "Modelo primario falló, intentando fallback: %s", fallback_model
                )
                try:
                    result = await self._generate_openrouter(
                        system, user, json_mode=json_mode, model=fallback_model
                    )
                    if result:
                        logger.info("Fallback exitoso: %s", fallback_model)
                        return result
                except Exception as e:
                    logger.warning("Fallback %s falló: %s", fallback_model, e)

        return ""

    async def _generate_gemini(
        self, system: str, user: str, json_mode: bool = False
    ) -> str:
        if not self._gemini_client:
            return ""
        try:
            from google.genai import types

            cfg_kwargs: dict = {
                "system_instruction": system,
                "temperature": settings.GEMINI_TEMPERATURE,
                "max_output_tokens": settings.GEMINI_MAX_TOKENS,
                "thinking_config": types.ThinkingConfig(thinking_budget=0),
            }
            if json_mode:
                cfg_kwargs["response_mime_type"] = "application/json"

            response = await self._gemini_client.aio.models.generate_content(
                model=self.model,
                contents=user,
                config=types.GenerateContentConfig(**cfg_kwargs),
            )
            text = (response.text or "").strip()
            if not text:
                logger.warning(
                    "Gemini devolvió texto vacío. finish_reason=%s",
                    getattr(response.candidates[0], "finish_reason", "?")
                    if response.candidates
                    else "?",
                )
            return text
        except Exception as e:
            logger.error("Gemini falló: %s", e)
            return ""

    async def _generate(self, system: str, user: str, json_mode: bool = False) -> str:
        if not self._available:
            return ""
        if self._backend in ("groq", "openrouter"):
            return await self._generate_with_fallback(system, user, json_mode=json_mode)
        if self._backend == "gemini":
            return await self._generate_gemini(system, user, json_mode=json_mode)
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
            logger.warning("LLM devolvió JSON inválido (extracción): %r", raw[:200])
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
        return await self._generate(system, user, json_mode=json_mode)

    async def analyze_patient(
        self,
        patient_text: str,
        age: int | None = None,
        gender: str | None = None,
    ) -> dict:
        """Análisis médico completo: síntomas + condiciones + especialidad + urgencia.

        Devuelve un dict con las claves:
            sintomas: list[SymptomExtraction]
            condiciones_probables: list[CondicionProbable]
            especialidad_sugerida: str | None
            urgencia_sugerida: str
            justificacion: str
        """
        if not self._available:
            return {
                "sintomas": [],
                "condiciones_probables": [],
                "especialidad_sugerida": None,
                "urgencia_sugerida": "media",
                "justificacion": "Servicio LLM no disponible",
            }

        user_payload = PATIENT_ANALYSIS_PROMPT.replace("{age}", str(age if age is not None else "desconocida")).replace("{gender}", str(gender or "desconocido")).replace("{text}", patient_text)
        raw = await self._generate(SYSTEM_PROMPT, user_payload, json_mode=True)
        if not raw:
            logger.warning("LLM analyze_patient devolvió vacío")
            return {
                "sintomas": [],
                "condiciones_probables": [],
                "especialidad_sugerida": None,
                "urgencia_sugerida": "media",
                "justificacion": "No se pudo analizar el texto",
            }

        try:
            parsed = json.loads(self._strip_json_fence(raw))
        except json.JSONDecodeError:
            logger.warning("LLM devolvió JSON inválido (analyze): %r", raw[:300])
            return {
                "sintomas": [],
                "condiciones_probables": [],
                "especialidad_sugerida": None,
                "urgencia_sugerida": "media",
                "justificacion": "Error de formato",
            }

        # Parse síntomas
        sintomas_raw = parsed.get("sintomas", [])
        sintomas: list[SymptomExtraction] = []
        for s in sintomas_raw:
            if isinstance(s, dict) and "normalized" in s:
                sintomas.append(
                    SymptomExtraction(
                        raw_text=patient_text,
                        normalized=s["normalized"],
                        severity=s.get("severidad", s.get("severity", "media")),
                        confidence=float(s.get("confianza", s.get("confidence", 0.8))),
                    )
                )

        # Parse condiciones probables
        cond_raw = parsed.get("condiciones_probables", [])
        condiciones: list[CondicionProbable] = []
        for c in cond_raw:
            if isinstance(c, dict) and "nombre" in c:
                condiciones.append(
                    CondicionProbable(
                        nombre=c["nombre"],
                        probabilidad=round(float(c.get("probabilidad", 0.0)), 4),
                    )
                )

        return {
            "sintomas": sintomas,
            "condiciones_probables": condiciones,
            "especialidad_sugerida": parsed.get("especialidad_sugerida")
            or parsed.get("especialidad")
            or None,
            "urgencia_sugerida": parsed.get("urgencia_sugerida")
            or parsed.get("urgencia")
            or "media",
            "justificacion": parsed.get("justificacion", ""),
        }

    async def summarize_diagnosis(self, context: dict) -> str:
        if not self._available:
            return ""
        user_payload = json.dumps(context, ensure_ascii=False, indent=2)
        return await self._generate(SUMMARY_PROMPT, user_payload, json_mode=False)

    async def pick_service(
        self,
        specialty: str,
        urgency: str,
        symptoms: list[str],
        conditions: list[dict],
        catalog: list[dict],
    ) -> dict:
        if not self._available or not catalog:
            return {}

        catalog_str = "\n".join(
            f"- {s['name']}: {s.get('label', s['name'])}"
            for s in catalog
        )
        valid_names = {s["name"] for s in catalog}
        user_payload = (
            f"especialidad: {specialty}\n"
            f"urgencia: {urgency}\n"
            f"sintomas: {', '.join(symptoms) if symptoms else '(ninguno)'}\n"
            f"condiciones_probables: "
            f"{', '.join(c.get('nombre','') for c in conditions) if conditions else '(ninguna)'}\n\n"
            f"catalogo de servicios disponibles:\n{catalog_str}\n"
        )
        raw = await self._generate(SERVICE_PICK_PROMPT, user_payload, json_mode=True)
        if not raw:
            return {}
        try:
            parsed = json.loads(self._strip_json_fence(raw))
        except json.JSONDecodeError:
            logger.warning("LLM devolvió JSON inválido (pick_service): %r", raw[:200])
            return {}
        service = parsed.get("service")
        if service not in valid_names:
            logger.warning("LLM eligió servicio fuera del catálogo: %r", service)
            return {}
        return {"service": service, "razon": parsed.get("razon", "")}
