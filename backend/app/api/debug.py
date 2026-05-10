"""Endpoints de debug para inspeccionar el pipeline de diagnóstico.
Útil para ver QUÉ detecta el LLM como síntomas, condiciones y especialidad.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.llm_service import LLMService

router = APIRouter()


class DebugDiagnoseRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    age: int | None = None
    gender: str | None = None


@router.post("/diagnose")
async def debug_diagnose(req: DebugDiagnoseRequest):
    """Corre el pipeline LLM y devuelve cada paso del análisis médico.
    Sirve para depurar por qué `condiciones_probables` o `especialidad` vienen vacíos.
    """
    llm = LLMService()

    out: dict = {
        "input": req.model_dump(),
        "llm_disponible": llm._available,
        "analisis": {},
        "error": None,
    }

    if not llm._available:
        out["error"] = (
            "LLM no disponible (configura OPENROUTER_API_KEY o GEMINI_API_KEY)"
        )
        return out

    try:
        analysis = await llm.analyze_patient(
            req.message, age=req.age, gender=req.gender
        )
        out["analisis"] = {
            "sintomas": [
                {"nombre": s.normalized, "severidad": s.severity, "confianza": s.confidence}
                for s in analysis.get("sintomas", [])
            ],
            "condiciones_probables": [
                {"nombre": c.nombre, "probabilidad": c.probabilidad}
                for c in analysis.get("condiciones_probables", [])
            ],
            "especialidad_sugerida": analysis.get("especialidad_sugerida"),
            "urgencia_sugerida": analysis.get("urgencia_sugerida"),
            "justificacion": analysis.get("justificacion"),
        }
    except Exception as e:
        out["error"] = f"Inesperado: {type(e).__name__}: {e}"

    return out
