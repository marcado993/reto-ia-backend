import logging
import math
from sqlalchemy.orm import Session

from app.models.hospital import Hospital
from app.models.health_plan import HealthPlan
from app.schemas.chat import HospitalRecommendation
from app.services.provider_directory import ProviderDirectory

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

        # ── 1) Buscar en tabla SQL (hospitales con precios reales) ───
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

        # ── 2) Buscar en JSON unificado (prestadores geolocalizados) ──
        # Solo para planes privados (públicos no tienen red privada en el JSON)
        json_recs: list[HospitalRecommendation] = []
        if not plan.is_public:
            service_type = "emergencia" if urgency == "alta" else "consulta"
            try:
                json_entries = ProviderDirectory.find_best(
                    provider_network=plan.provider_network,
                    urgency=urgency,
                    user_lat=user_lat,
                    user_lon=user_lon,
                    limit=limit * 2,  # pedimos más para tener opciones de merge
                )
                for entry in json_entries:
                    distance = None
                    if user_lat is not None and user_lon is not None:
                        distance = ProviderDirectory._haversine_km(
                            user_lat, user_lon,
                            float(entry["latitud"]), float(entry["longitud"])
                        )
                    json_recs.append(
                        ProviderDirectory.to_recommendation(
                            entry=entry,
                            plan=plan,
                            service_type=service_type,
                            distance=distance,
                        )
                    )
            except Exception as e:
                logger.warning("Error cargando prestadores del JSON: %s", e)

        # ── 3) Merge y deduplicar por nombre ──────────────────────────
        seen_names: set[str] = set()
        merged: list[HospitalRecommendation] = []

        # Primero los de SQL (tienen precios reales por especialidad)
        for r in recs:
            norm = r.nombre.lower().strip()
            if norm not in seen_names:
                seen_names.add(norm)
                merged.append(r)

        # Luego los del JSON que no estén ya en la lista
        for r in json_recs:
            norm = r.nombre.lower().strip()
            if norm not in seen_names:
                seen_names.add(norm)
                merged.append(r)

        # ── 4) Aplicar offsets determinísticos a duplicados ──────────
        merged = self._apply_deterministic_offsets(merged)

        # Recalcular distancias después de offsets (si hay ubicación)
        if user_lat is not None and user_lon is not None:
            for r in merged:
                if r.lat is not None and r.lon is not None:
                    r.distancia_km = round(
                        self._haversine_km(user_lat, user_lon, r.lat, r.lon), 1
                    )

        # ── 5) Ordenar: primero por distancia, luego por copago ───────
        # Si hay ubicación del usuario, priorizamos cercanía.
        # Si no hay ubicación, priorizamos menor copago.
        has_location = user_lat is not None and user_lon is not None

        if has_location:
            merged.sort(key=lambda h: (h.distancia_km or 9999, h.copago_paciente))
        else:
            merged.sort(key=lambda h: (h.copago_paciente, h.distancia_km or 9999))

        return merged[:limit]

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

    @staticmethod
    def _hash_offset(name: str, max_offset: float = 0.003) -> tuple[float, float]:
        """Genera un offset determinístico (lat, lon) basado en el hash del nombre.

        Mismo nombre = mismo offset siempre. Diferentes nombres = offsets
        distribuidos en un círculo de radio máximo ~max_offset grados
        (~300 m en Ecuador).
        """
        h = sum(ord(c) for c in name)
        angle = (h % 360) * math.pi / 180
        radius = (h % 100) / 100 * max_offset
        lat_off = radius * math.cos(angle)
        lon_off = radius * math.sin(angle)
        return lat_off, lon_off

    @staticmethod
    def _apply_deterministic_offsets(
        recs: list[HospitalRecommendation],
    ) -> list[HospitalRecommendation]:
        """Aplica offsets determinísticos a hospitales con coordenadas duplicadas.

        Detecta grupos de hospitales que comparten lat/lon exactos y les
        asigna offsets únicos para que se vean separados en el mapa.
        """
        # Agrupar por coordenadas exactas
        groups: dict[tuple[float, float], list[int]] = {}
        for i, r in enumerate(recs):
            if r.lat is not None and r.lon is not None:
                key = (round(r.lat, 6), round(r.lon, 6))
                groups.setdefault(key, []).append(i)

        for indices in groups.values():
            if len(indices) <= 1:
                continue  # No hay duplicados
            for idx in indices:
                r = recs[idx]
                lat_off, lon_off = HospitalService._hash_offset(r.nombre)
                r.lat = round(r.lat + lat_off, 6)  # type: ignore[assignment]
                r.lon = round(r.lon + lon_off, 6)  # type: ignore[assignment]
                # Recalcular distancia si es posible (no siempre tenemos user_lat)
        return recs
