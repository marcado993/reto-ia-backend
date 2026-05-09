from pydantic import BaseModel, Field


class CopagoRequest(BaseModel):
    plan_id: int
    service_type: str = "consulta"
    specialty: str | None = None
    hospital_id: int | None = None


class CopagoResult(BaseModel):
    plan_nombre: str
    plan_tipo: str
    service_type: str
    costo_base: float
    copago_estimado: float
    moneda: str = "USD"
    metodo: str = ""
    desglose: str = ""
    deducible_restante: float | None = None