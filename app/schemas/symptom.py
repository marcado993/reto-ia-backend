from pydantic import BaseModel, Field


class SymptomExtraction(BaseModel):
    raw_text: str
    normalized: str
    icd11_code: str | None = None
    severity: str = "media"
    body_system: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class SymptomResponse(BaseModel):
    id: int
    name: str
    icd11_code: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    body_system: str | None = None
    severity_default: str = "media"
    related_specialties: list[str] = Field(default_factory=list)