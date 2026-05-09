from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.hospital import Hospital
from app.services.hospital_service import HospitalService
from app.schemas.chat import HospitalRecommendation
from app.schemas.hospital import HospitalSearchRequest, HospitalSearchResult

router = APIRouter()


@router.get("/", response_model=list[dict])
async def list_hospitals(
    network: str | None = Query(None),
    zone: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Hospital)
    if network:
        query = query.filter(Hospital.network == network)
    if zone:
        query = query.filter(Hospital.zone.ilike(f"%{zone}%"))
    hospitals = query.limit(100).all()
    return [
        {
            "id": h.id,
            "name": h.name,
            "type": h.type,
            "network": h.network,
            "zone": h.zone,
            "lat": float(h.lat) if h.lat else None,
            "lon": float(h.lon) if h.lon else None,
            "specialty_costs": h.specialty_costs,
        }
        for h in hospitals
    ]


@router.post("/search", response_model=HospitalSearchResult)
async def search_hospitals(request: HospitalSearchRequest, db: Session = Depends(get_db)):
    service = HospitalService(db)
    results = service.find_best(
        plan_id=request.plan_id,
        specialty=request.specialty,
        urgency=request.urgency,
        user_lat=request.user_lat,
        user_lon=request.user_lon,
        limit=request.limit,
    )
    return HospitalSearchResult(
        hospitals=results,
        best=results[0] if results else None,
    )