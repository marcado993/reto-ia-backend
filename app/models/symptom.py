from sqlalchemy import Column, Integer, String, Text

from app.database import Base
from app.utils.types import JSONType


class Symptom(Base):
    __tablename__ = "symptoms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False, index=True)
    icd11_code = Column(String(20), nullable=True)
    synonyms = Column(JSONType, default=list)
    body_system = Column(String(100), nullable=True)
    severity_default = Column(String(20), default="media")
    related_specialties = Column(JSONType, default=list)
    urgency_rules = Column(JSONType, default=list)
    description = Column(Text, nullable=True)

    def matches(self, text: str) -> bool:
        text_lower = text.lower().strip()
        if text_lower == self.name.lower():
            return True
        return any(s.lower() == text_lower for s in (self.synonyms or []))