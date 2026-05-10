"""Endpoints de debug para inspeccionar el pipeline de diagnóstico.
Útil para ver QUÉ mapea el LLM (OpenRouter/Gemini) y QUÉ devuelve EndlessMedical.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.endless_medical_service import (
    EndlessMedicalError,
    EndlessMedicalService,
)
from app.services.llm_service import LLMService

router = APIRouter()


class DebugDiagnoseRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    age: int | None = None
    gender: str | None = None
    top_k: int = 5


@router.post("/diagnose")
async def debug_diagnose(req: DebugDiagnoseRequest):
    """Corre TODO el pipeline EndlessMedical y devuelve cada paso.
    Sirve para depurar por qué `condiciones_probables` viene vacío.
    """
    llm = LLMService()
    em = EndlessMedicalService()

    out: dict = {
        "input": req.model_dump(),
        "llm_disponible": llm._available,
        "valid_features_count": 0,
        "features_mapeadas_por_llm": {},
        "diagnostico": [],
        "error": None,
    }

    try:
        valid_features = await em.get_features()
        out["valid_features_count"] = len(valid_features)
        out["valid_features_sample"] = valid_features[:30]

        if not llm._available:
            out["error"] = (
                "LLM no disponible (configura OPENROUTER_API_KEY o GEMINI_API_KEY)"
            )
            return out

        features = await llm.map_text_to_features(
            req.message, valid_features, age=req.age, gender=req.gender
        )
        out["features_mapeadas_por_llm"] = features

        if not features:
            out["error"] = (
                "El LLM no mapeó ninguna feature válida. Mensaje muy corto o "
                "sin datos clínicos claros."
            )
            return out

        diseases = await em.diagnose(features, top_k=req.top_k)
        out["diagnostico"] = diseases
    except EndlessMedicalError as e:
        out["error"] = f"EndlessMedical: {e}"
    except Exception as e:
        out["error"] = f"Inesperado: {type(e).__name__}: {e}"

    return out


@router.get("/endless-features")
async def list_endless_features(limit: int = 50):
    """Lista las primeras N features disponibles en EndlessMedical."""
    em = EndlessMedicalService()
    features = await em.get_features()
    return {"total": len(features), "sample": features[:limit]}


@router.get("/endless-outcomes")
async def list_endless_outcomes(limit: int = 50):
    """Lista las primeras N enfermedades que EndlessMedical puede detectar."""
    em = EndlessMedicalService()
    outcomes = await em.get_outcomes()
    return {"total": len(outcomes), "sample": outcomes[:limit]}
