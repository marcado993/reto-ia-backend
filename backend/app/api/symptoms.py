from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.symptom import Symptom
from app.schemas.symptom import SymptomResponse

router = APIRouter()


@router.get("/", response_model=list[SymptomResponse])
async def list_symptoms(
    search: str | None = Query(None, description="Buscar por nombre"),
    body_system: str | None = Query(None, description="Filtrar por sistema del cuerpo"),
    db: Session = Depends(get_db),
):
    query = db.query(Symptom)
    if search:
        query = query.filter(Symptom.name.ilike(f"%{search}%"))
    if body_system:
        query = query.filter(Symptom.body_system.ilike(f"%{body_system}%"))
    return query.limit(100).all()


@router.get("/{symptom_id}", response_model=SymptomResponse)
async def get_symptom(symptom_id: int, db: Session = Depends(get_db)):
    symptom = db.query(Symptom).filter(Symptom.id == symptom_id).first()
    if not symptom:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Symptom not found")
    return symptom