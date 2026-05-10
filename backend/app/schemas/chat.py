from __future__ import annotations

from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    plan_id: int | None = None
    age: int | None = Field(None, ge=0, le=120)
    gender: str | None = Field(None, pattern="^(male|female)$")


class HospitalRecommendation(BaseModel):
    nombre: str
    tipo: str = ""
    red: str = ""
    costo_consulta: float = 0.0
    copago_paciente: float = 0.0
    lat: float | None = None
    lon: float | None = None
    distancia_km: float | None = None


class CondicionProbable(BaseModel):
    nombre: str
    probabilidad: float = 0.0


class ServicioRecomendado(BaseModel):
    nombre: str = ""
    label: str = ""
    razon: str = ""


class StructuredResponse(BaseModel):
    sintomas: list[str] = Field(default_factory=list)
    urgencia: str = "media"
    especialidades_sugeridas: list[str] = Field(default_factory=list)
    condiciones_probables: list[CondicionProbable] = Field(default_factory=list)
    servicio_recomendado: ServicioRecomendado | None = None
    plan_seguro: str = ""
    costo_base: float = 0.0
    copago_estimado: float = 0.0
    moneda: str = "USD"
    hospital_recomendado: HospitalRecommendation | None = None
    hospitales_comparacion: list[HospitalRecommendation] = Field(default_factory=list)
    desglose_cobertura: str = ""


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    structured: StructuredResponse | None = None
    needs_more_info: bool = False
    clarification_questions: list[str] = Field(default_factory=list)