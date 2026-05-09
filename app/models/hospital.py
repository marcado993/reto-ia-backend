from sqlalchemy import Column, Integer, String, Numeric
from app.utils.types import JSONType

from app.database import Base


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    osm_id = Column(Integer, nullable=True)
    name = Column(String(200), nullable=False, index=True)
    lat = Column(Numeric(10, 7), nullable=True)
    lon = Column(Numeric(10, 7), nullable=True)
    zone = Column(String(100), nullable=True)
    type = Column(String(50), nullable=True)
    network = Column(String(50), nullable=True)
    specialty_costs = Column(JSONType, default=dict)

    def get_cost(self, specialty: str) -> float | None:
        costs = self.specialty_costs or {}
        return costs.get(specialty.lower(), costs.get("medicina_general"))

    @property
    def is_public(self) -> bool:
        return self.type in ("public", "iess", "issfa", "isspol")