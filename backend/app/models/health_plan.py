from sqlalchemy import Column, Integer, String, Numeric, Boolean
from app.utils.types import JSONType

from app.database import Base


class HealthPlan(Base):
    __tablename__ = "health_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    type = Column(String(20), nullable=False)
    deductible_usd = Column(Numeric(10, 2), default=0)
    max_oop_usd = Column(Numeric(10, 2), default=0)
    copago_consulta_usd = Column(Numeric(10, 2), nullable=True)
    copago_emergencia_usd = Column(Numeric(10, 2), nullable=True)
    copago_pct = Column(Numeric(5, 4), default=0)
    provider_network = Column(String(50), nullable=False)
    exempt_services = Column(JSONType, default=list)
    is_public = Column(Boolean, default=False)

    def copago_for_service(self, service_type: str, base_cost: float) -> float:
        if self.is_public:
            return 0.0
        if service_type == "consulta":
            if self.copago_consulta_usd is not None:
                return float(self.copago_consulta_usd)
            return round(base_cost * float(self.copago_pct), 2)
        if service_type == "emergencia":
            if self.copago_emergencia_usd is not None:
                return float(self.copago_emergencia_usd)
            return round(base_cost * float(self.copago_pct), 2)
        return round(base_cost * float(self.copago_pct), 2)