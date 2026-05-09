from pydantic import BaseModel, Field


class SpecialtySuggestion(BaseModel):
    name: str
    icd11_chapter: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    matching_symptoms: list[str] = Field(default_factory=list)