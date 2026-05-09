from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.health_plan import HealthPlan
from app.schemas.copago import CopagoRequest, CopagoResult
from app.services.copago_service import CopagoService

router = APIRouter()


@router.get("/", response_model=list[dict])
async def list_plans(db: Session = Depends(get_db)):
    plans = db.query(HealthPlan).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "type": p.type,
            "is_public": p.is_public,
            "provider_network": p.provider_network,
            "copago_consulta_usd": float(p.copago_consulta_usd) if p.copago_consulta_usd else None,
            "copago_emergencia_usd": float(p.copago_emergencia_usd) if p.copago_emergencia_usd else None,
            "copago_pct": float(p.copago_pct) if p.copago_pct else None,
            "deductible_usd": float(p.deductible_usd) if p.deductible_usd else 0,
        }
        for p in plans
    ]


@router.get("/{plan_id}")
async def get_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(HealthPlan).filter(HealthPlan.id == plan_id).first()
    if not plan:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Plan not found")
    return {
        "id": plan.id,
        "name": plan.name,
        "type": plan.type,
        "is_public": plan.is_public,
        "provider_network": plan.provider_network,
        "copago_consulta_usd": float(plan.copago_consulta_usd) if plan.copago_consulta_usd else None,
        "copago_emergencia_usd": float(plan.copago_emergencia_usd) if plan.copago_emergencia_usd else None,
        "copago_pct": float(plan.copago_pct) if plan.copago_pct else None,
        "deductible_usd": float(plan.deductible_usd) if plan.deductible_usd else 0,
        "max_oop_usd": float(plan.max_oop_usd) if plan.max_oop_usd else 0,
        "exempt_services": plan.exempt_services,
    }


@router.post("/copago", response_model=CopagoResult)
async def calculate_copago(request: CopagoRequest, db: Session = Depends(get_db)):
    service = CopagoService(db)
    result = service.calculate(
        plan_id=request.plan_id,
        service_type=request.service_type,
        specialty=request.specialty,
        hospital_id=request.hospital_id,
    )
    return result