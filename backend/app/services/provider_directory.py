"""Directorio de prestadores en red (lectura del JSON unificado).

Lee `backend/data/prestadores_unificados_copago.json` y permite filtrar por
aseguradora. Se carga una sola vez en memoria (lazy) y se cachea en proceso.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from app.schemas.chat import HospitalRecommendation

logger = logging.getLogger(__name__)

# Mapeo provider_network (DB / seed_health_plans.json) → llave en el JSON
# unificado (campo "aseguradora", uppercase).
NETWORK_TO_ASEGURADORA: dict[str, str] = {
    "saludsa_red": "SALUDSA",
    "bmi_red": "BMI",
    "bupa_red_interna": "BUPA",
    "bupa_red": "BUPA",
    "humana_red": "HUMANA",
}

# Ruta al archivo. Se resuelve relativo al directorio backend/.
_DATA_FILE = (
    Path(__file__).resolve().parent.parent.parent / "data" / "prestadores_unificados_copago.json"
)


class ProviderDirectory:
    """Cache estático del catálogo de prestadores por aseguradora."""

    _by_aseguradora: dict[str, list[dict[str, Any]]] | None = None

    @classmethod
    def _load(cls) -> dict[str, list[dict[str, Any]]]:
        if cls._by_aseguradora is not None:
            return cls._by_aseguradora

        if not _DATA_FILE.exists():
            logger.warning("prestadores_unificados_copago.json no encontrado en %s", _DATA_FILE)
            cls._by_aseguradora = {}
            return cls._by_aseguradora

        with _DATA_FILE.open("r", encoding="utf-8") as f:
            raw: list[dict[str, Any]] = json.load(f)

        bucket: dict[str, list[dict[str, Any]]] = {}
        for entry in raw:
            aseg = (entry.get("aseguradora") or "").strip().upper()
            if not aseg:
                continue
            bucket.setdefault(aseg, []).append(entry)

        logger.info(
            "ProviderDirectory cargado: %d prestadores en %d aseguradoras (%s)",
            sum(len(v) for v in bucket.values()),
            len(bucket),
            ", ".join(f"{k}={len(v)}" for k, v in bucket.items()),
        )
        cls._by_aseguradora = bucket
        return cls._by_aseguradora

    @classmethod
    def by_network(cls, provider_network: str | None) -> list[dict[str, Any]]:
        """Devuelve los prestadores de la aseguradora asociada al network del plan."""
        if not provider_network:
            return []
        aseg = NETWORK_TO_ASEGURADORA.get(provider_network.lower())
        if not aseg:
            return []
        return cls._load().get(aseg, [])

    @classmethod
    def by_aseguradora(cls, aseguradora: str) -> list[dict[str, Any]]:
        return cls._load().get(aseguradora.upper(), [])

    @staticmethod
    def to_public(entry: dict[str, Any]) -> dict[str, Any]:
        """Normaliza una entrada del JSON a la forma que consume el frontend.

        Sólo pasa los campos útiles para el mapa + lista (omite 'beneficios'
        y 'horarios' detallados para reducir el payload).
        """
        return {
            "nombre": entry.get("nombre"),
            "categoria": entry.get("categoria"),
            "ciudad": entry.get("ciudad"),
            "provincia": entry.get("provincia"),
            "direccion": entry.get("direccion"),
            "horarios": entry.get("horarios"),
            "lat": entry.get("latitud"),
            "lon": entry.get("longitud"),
            "aseguradora": entry.get("aseguradora"),
        }

    # ── Filtro de categorías según urgencia ─────────────────────────
    # En urgencia ALTA descartamos farmacias/laboratorios porque no atienden
    # emergencias médicas complejas.
    _CATEGORY_FILTER: dict[str, set[str]] = {
        "alta": {
            "HOSPITAL", "CLINICA", "CENTRO DE COPAGO", "CENTRO MEDICO",
            "CENTRO MEDICO", "CENTRO DE ESPECIALIDADES", "POLICLINICO",
            "UNIDAD MEDICA", "CONSULTORIO MEDICO",
        },
        "media": set(),   # vacío = sin filtro (todas las categorías)
        "baja": set(),
    }

    @classmethod
    def _haversine_km(cls, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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

    @classmethod
    def find_best(
        cls,
        provider_network: str | None,
        urgency: str = "media",
        user_lat: float | None = None,
        user_lon: float | None = None,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """Devuelve los prestadores del JSON más cercanos al usuario.

        Filtra por aseguradora (vía provider_network), descarta entradas sin
        coordenadas, aplica restricción de categoría según urgencia, calcula
        distancia con haversine y ordena por cercanía.
        """
        if not provider_network:
            return []

        raw = cls.by_network(provider_network)
        if not raw:
            return []

        allowed = cls._CATEGORY_FILTER.get(urgency.lower(), set())
        candidates: list[dict[str, Any]] = []

        for entry in raw:
            lat = entry.get("latitud")
            lon = entry.get("longitud")
            if lat is None or lon is None:
                continue

            # Filtro de categoría para urgencias altas
            if allowed:
                cat = (entry.get("categoria") or "").strip().upper()
                if cat not in allowed:
                    continue

            distance: float | None = None
            if user_lat is not None and user_lon is not None:
                distance = cls._haversine_km(
                    user_lat, user_lon, float(lat), float(lon)
                )

            candidates.append({"entry": entry, "distance": distance})

        # Ordenar: primero los que tienen distancia, luego por distancia ascendente
        candidates.sort(
            key=lambda x: (x["distance"] is None, x["distance"] or 9999)
        )
        return [c["entry"] for c in candidates[:limit]]

    @classmethod
    def to_recommendation(
        cls,
        entry: dict[str, Any],
        plan: Any,  # HealthPlan duck-typing para evitar circular import
        service_type: str = "consulta",
        distance: float | None = None,
    ) -> HospitalRecommendation:
        """Convierte una entrada del JSON a HospitalRecommendation.

        Como el JSON no tiene precios por especialidad, usamos el copago
        directo del plan (copago_consulta_usd o copago_emergencia_usd).
        """
        # Calcular copago desde el plan (duck typing, no importamos el modelo)
        copago = 0.0
        if plan and not getattr(plan, "is_public", False):
            if service_type == "emergencia" and getattr(plan, "copago_emergencia_usd", None) is not None:
                copago = float(plan.copago_emergencia_usd)
            elif getattr(plan, "copago_consulta_usd", None) is not None:
                copago = float(plan.copago_consulta_usd)
            elif getattr(plan, "copago_pct", None):
                # Fallback: 10% de un costo base estimado $40
                copago = round(40.0 * float(plan.copago_pct), 2)
            else:
                copago = 40.0  # default conservador

        return HospitalRecommendation(
            nombre=entry.get("nombre", "Desconocido"),
            tipo=(entry.get("categoria") or "general").lower().replace(" ", "_"),
            red=getattr(plan, "provider_network", "") if plan else "",
            costo_consulta=40.0,
            copago_paciente=copago,
            lat=float(entry["latitud"]) if entry.get("latitud") is not None else None,
            lon=float(entry["longitud"]) if entry.get("longitud") is not None else None,
            distancia_km=round(distance, 1) if distance is not None else None,
        )
