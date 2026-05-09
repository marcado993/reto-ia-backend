from sqlalchemy import Column, Integer, String, Numeric
from app.utils.types import JSONType

from app.database import Base


class MedicalService(Base):
    __tablename__ = "medical_services"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(200), nullable=False)
    service_type = Column(String(50), nullable=False)
    specialty = Column(String(100), nullable=True)
    base_cost_usd = Column(Numeric(10, 2), default=0)