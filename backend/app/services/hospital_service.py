import logging
import math
from sqlalchemy.orm import Session

from app.models.hospital import Hospital
from app.models.health_plan import HealthPlan
from app.schemas.chat import HospitalRecommendation

logger = logging.getLogger(__name__)


class HospitalService:
    def __init__(self, db: Session):
        self.db = db

    def find_best(
        self,
        plan_id: int,
        specialty: str | None = None,
        urgency: str = "media",
        user_lat: float | None = None,
        user_lon: float | None = None,
        limit: int = 3,
        service_name: str | None = None,
    ) -> list[HospitalRecommendation]:
        plan = self.db.query(HealthPlan).filter(HealthPlan.id == plan_id).first()
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        network = plan.provider_network
        hospitals = self.db.query(Hospital).filter(Hospital.network == network).all()

        if not hospitals:
            hospitals = self.db.query(Hospital).all()

        # Si pedimos un servicio específico, priorizamos hospitales que lo tengan
        if service_name and specialty:
            with_service = [
                h for h in hospitals
                if any(s["name"] == service_name for s in h.list_services(specialty))
            ]
            if with_service:
                hospitals = with_service

        recs: list[HospitalRecommendation] = []
        for h in hospitals:
            cost = (
                h.get_service_price(specialty, service_name)
                if specialty
                else h.get_service_price("medicina_general")
            )
            if cost is None:
                cost = 0.0 if h.is_public else 40.0

            copago = self._calculate_copago(plan, h, specialty, service_name, urgency)
            service_type = "emergencia" if urgency == "alta" else "consulta"

            distance = None
            if user_lat is not None and user_lon is not None and h.lat and h.lon:
                distance = self._haversine_km(
                    user_lat, user_lon, float(h.lat), float(h.lon)
                )

            recs.append(
                HospitalRecommendation(
                    nombre=h.name,
                    tipo=h.type or "general",
                    red=network,
                    costo_consulta=cost,
                    copago_paciente=copago,
                    lat=float(h.lat) if h.lat else None,
                    lon=float(h.lon) if h.lon else None,
                    distancia_km=round(distance, 1) if distance is not None else None,
                )
            )

        if urgency == "alta":
            public = [h for h in recs if h.tipo in ("public", "iess", "issfa")]
            other = [h for h in recs if h.tipo not in ("public", "iess", "issfa")]
            recs = public + other

        recs.sort(key=lambda h: (h.copago_paciente, h.distancia_km or 9999))

        return recs[:limit]

    def _calculate_copago(
        self,
        plan: HealthPlan,
        hospital: Hospital,
        specialty: str | None,
        service_name: str | None,
        urgency: str,
    ) -> float:
        if plan.is_public:
            return 0.0
        cost = (
            hospital.get_service_price(specialty, service_name)
            if specialty
            else hospital.get_service_price("medicina_general")
        )
        if cost is None:
            cost = 40.0
        service_type = "emergencia" if urgency == "alta" else "consulta"
        return float(plan.copago_for_service(service_type, cost))

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(d_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
