import json
import logging
from pathlib import Path

from app.config import settings
from app.schemas.symptom import SymptomExtraction

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

EXTRACTION_PROMPT = """Eres un sistema de extraccion de sintomas medicos. Del siguiente texto en espanol, extrae los sintomas que describe el paciente.
Devuelve SOLO un JSON array con objetos que tengan: "normalized" (nombre medico normalizado del sintoma), "severity" (baja/media/alta), "confidence" (0.0-1.0).
Ejemplos de normalizacion: "me duele el pecho" -> "dolor toracico", "no puedo respirar" -> "disnea", "me arde al orinar" -> "disuria".
Si no detectas sintomas, devuelve [].
Texto: {text}"""


class LLMService:
    def __init__(self):
        self._available = bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "sk-your-openai-api-key-here")
        self.client = None
        self.model = settings.OPENAI_MODEL
        if self._available:
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("LLM Service initialized with OpenAI GPT-4o")
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI client: {e}")
                self._available = False
        if not self._available:
            logger.info("LLM Service running in offline mode (no OpenAI key)")

    async def extract_symptoms_from_text(self, text: str) -> list[SymptomExtraction]:
        if not self._available or not self.client:
            return []
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": EXTRACTION_PROMPT.format(text=text)},
                    {"role": "user", "content": text},
                ],
                temperature=0.1,
                max_tokens=512,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            parsed = json.loads(content)
            symptoms_data = parsed if isinstance(parsed, list) else parsed.get("symptoms", parsed.get("data", []))

            results = []
            for s in symptoms_data:
                if isinstance(s, dict) and "normalized" in s:
                    results.append(
                        SymptomExtraction(
                            raw_text=text,
                            normalized=s["normalized"],
                            severity=s.get("severity", "media"),
                            confidence=s.get("confidence", 0.8),
                        )
                    )
            return results
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return []

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        if not self._available or not self.client:
            return {"content": "", "tool_calls": []}
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": settings.OPENAI_TEMPERATURE,
                "max_tokens": settings.OPENAI_MAX_TOKENS,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = await self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message

            result = {
                "content": message.content or "",
                "tool_calls": [],
            }

            if hasattr(message, "tool_calls") and message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                    for tc in message.tool_calls
                ]

            return result
        except Exception as e:
            logger.error(f"LLM chat failed: {e}")
            return {"content": "", "tool_calls": []}