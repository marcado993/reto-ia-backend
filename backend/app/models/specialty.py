from sqlalchemy import Column, Integer, String, Text

from app.database import Base
from app.utils.types import JSONType


class Specialty(Base):
    __tablename__ = "specialties"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    related_symptoms = Column(JSONType, default=list)
    icd11_chapter = Column(String(10), nullable=True)