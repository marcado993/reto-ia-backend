import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
from app.utils.types import JSONType
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id = Column(Integer, ForeignKey("health_plans.id"), nullable=True)
    user_name = Column(String(200), nullable=True)
    messages = Column(JSONType, default=list)
    extracted_symptoms = Column(JSONType, default=list)
    final_response = Column(JSONType, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)