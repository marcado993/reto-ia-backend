from fastapi import APIRouter

from app.api import chat, debug, health_plans, hospitals, symptoms

router = APIRouter()

router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(symptoms.router, prefix="/symptoms", tags=["symptoms"])
router.include_router(hospitals.router, prefix="/hospitals", tags=["hospitals"])
router.include_router(health_plans.router, prefix="/health-plans", tags=["health-plans"])
router.include_router(debug.router, prefix="/debug", tags=["debug"])