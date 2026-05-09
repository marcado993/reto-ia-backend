import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.agent.medical_agent import MedicalAgent

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def send_message(request: ChatRequest, db: Session = Depends(get_db)):
    agent = MedicalAgent(db)
    response = await agent.process(request)
    return response


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: Session = Depends(get_db)):
    from app.models.chat_session import ChatSession
    from uuid import UUID

    try:
        session = db.query(ChatSession).filter(ChatSession.id == UUID(session_id)).first()
        if not session:
            return {"error": "Session not found"}
        return {
            "id": str(session.id),
            "plan_id": session.plan_id,
            "messages": session.messages,
            "extracted_symptoms": session.extracted_symptoms,
            "final_response": session.final_response,
        }
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        return {"error": str(e)}