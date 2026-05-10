"""Endpoints para el directorio de prestadores en red por aseguradora."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.health_plan import HealthPlan
from app.services.provider_directory import ProviderDirectory

router = APIRouter()


@router.get("/by-plan/{plan_id}")
async def providers_by_plan(
    plan_id: int,
    only_with_coords: bool = Query(True, description="Filtrar entradas sin lat/lon"),
    db: Session = Depends(get_db),
):
    """Lista de prestadores en red de la aseguradora del plan dado.

    Mapea `plan.provider_network` (e.g. "saludsa_red") a la aseguradora del
    JSON unificado (e.g. "SALUDSA") y devuelve sus prestadores.
    """
    plan = db.query(HealthPlan).filter(HealthPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    if plan.is_public:
        return {
            "plan_id": plan.id,
            "plan_name": plan.name,
            "provider_network": plan.provider_network,
            "aseguradora": None,
            "providers": [],
            "count": 0,
            "note": "Plan público (IESS): no hay directorio de prestadores privados",
        }

    raw = ProviderDirectory.by_network(plan.provider_network)
    items = [ProviderDirectory.to_public(e) for e in raw]

    if only_with_coords:
        items = [e for e in items if e["lat"] is not None and e["lon"] is not None]

    aseguradora = items[0]["aseguradora"] if items else None
    return {
        "plan_id": plan.id,
        "plan_name": plan.name,
        "provider_network": plan.provider_network,
        "aseguradora": aseguradora,
        "providers": items,
        "count": len(items),
    }


@router.get("/by-aseguradora/{aseguradora}")
async def providers_by_aseguradora(
    aseguradora: str,
    only_with_coords: bool = Query(True),
):
    """Variante directa: filtra por nombre de aseguradora (BMI/SALUDSA/HUMANA/BUPA)."""
    raw = ProviderDirectory.by_aseguradora(aseguradora)
    items = [ProviderDirectory.to_public(e) for e in raw]
    if only_with_coords:
        items = [e for e in items if e["lat"] is not None and e["lon"] is not None]
    return {
        "aseguradora": aseguradora.upper(),
        "providers": items,
        "count": len(items),
    }
