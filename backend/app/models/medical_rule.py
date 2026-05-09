from sqlalchemy import Column, Integer, String, Text
from app.utils.types import JSONType

from app.database import Base


class MedicalRule(Base):
    __tablename__ = "medical_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    conditions = Column(JSONType, nullable=False)
    result = Column(JSONType, nullable=False)
    priority = Column(Integer, default=5)

    def matches(self, symptoms: list[str]) -> bool:
        required = self.conditions.get("symptoms", [])
        if not required:
            return False
        all_required = self.conditions.get("all_required", True)
        symptoms_lower = [s.lower() for s in symptoms]
        required_lower = [r.lower() for r in required]
        if all_required:
            return all(r in symptoms_lower for r in required_lower)
        return any(r in symptoms_lower for r in required_lower)