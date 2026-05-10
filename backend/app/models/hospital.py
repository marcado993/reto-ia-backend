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
    # Estructura nueva (post-expansión):
    #   {"cardiologia": {"consulta": {"label": "...", "base_price": 50.0}, ...}}
    # Soporta también el formato antiguo: {"cardiologia": 50.0}
    specialty_costs = Column(JSONType, default=dict)

    # ──────────────────────────────────────────────────────────
    # Helpers de precio
    # ──────────────────────────────────────────────────────────
    def _services_for(self, specialty: str | None) -> dict | None:
        """Devuelve el sub-dict de servicios para una especialidad,
        o None si la especialidad no existe en este hospital."""
        if not specialty:
            return None
        costs = self.specialty_costs or {}
        spec = costs.get(specialty.lower()) or costs.get(specialty)
        if spec is None:
            return None
        # Formato nuevo: dict de servicios
        if isinstance(spec, dict):
            return spec
        # Formato legacy: número directo → emulamos {"consulta": {...}}
        try:
            return {"consulta": {"label": "Consulta", "base_price": float(spec)}}
        except (TypeError, ValueError):
            return None

    def get_service_price(
        self,
        specialty: str,
        service: str | None = None,
    ) -> float | None:
        """Precio base del servicio dentro de la especialidad.
        Si no se pasa `service` se devuelve el de 'consulta' (o el primero).
        """
        services = self._services_for(specialty)
        if not services:
            return None

        # Servicio explícito
        if service and service in services:
            entry = services[service]
            if isinstance(entry, dict):
                return float(entry.get("base_price", 0.0))
            return float(entry)

        # Default: consulta o atencion_emergencia
        for key in ("consulta", "atencion_emergencia"):
            if key in services:
                entry = services[key]
                return float(entry["base_price"]) if isinstance(entry, dict) else float(entry)

        # Si no hay default, primer servicio
        first = next(iter(services.values()), None)
        if isinstance(first, dict):
            return float(first.get("base_price", 0.0))
        return float(first) if first is not None else None

    # Compatibilidad con código existente
    def get_cost(self, specialty: str) -> float | None:
        return self.get_service_price(specialty)

    def list_services(self, specialty: str) -> list[dict]:
        """Lista los servicios disponibles para una especialidad.
        Devuelve [{name, label, base_price}, ...]."""
        services = self._services_for(specialty)
        if not services:
            return []
        out = []
        for name, entry in services.items():
            if isinstance(entry, dict):
                out.append({
                    "name": name,
                    "label": entry.get("label", name.replace("_", " ").title()),
                    "base_price": float(entry.get("base_price", 0.0)),
                })
            else:
                out.append({
                    "name": name,
                    "label": name.replace("_", " ").title(),
                    "base_price": float(entry),
                })
        return out

    @property
    def is_public(self) -> bool:
        return self.type in ("public", "iess", "issfa", "isspol")
