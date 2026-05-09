from pydantic import BaseModel, Field
from app.schemas.chat import HospitalRecommendation


class HospitalSearchRequest(BaseModel):
    plan_id: int
    specialty: str | None = None
    urgency: str = "media"
    user_lat: float | None = None
    user_lon: float | None = None
    limit: int = Field(default=3, ge=1, le=10)


class HospitalSearchResult(BaseModel):
    hospitals: list[HospitalRecommendation]
    best: HospitalRecommendation | None