from pydantic import BaseModel, Field
from app.schemas.chat import StructuredResponse, HospitalRecommendation
from app.schemas.symptom import SymptomExtraction
from app.schemas.specialty import SpecialtySuggestion
from app.schemas.copago import CopagoResult


class AgentToolResults(BaseModel):
    symptoms: list[SymptomExtraction] = Field(default_factory=list)
    specialties: list[SpecialtySuggestion] = Field(default_factory=list)
    urgency: str = "media"
    alert: str | None = None
    copago: CopagoResult | None = None
    hospitals: list[HospitalRecommendation] = Field(default_factory=list)


class FullStructuredResponse(StructuredResponse):
    tool_results: AgentToolResults | None = None