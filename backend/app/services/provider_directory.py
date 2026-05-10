"""Directorio de prestadores en red (lectura del JSON unificado).

Lee `backend/data/prestadores_unificados_copago.json` y permite filtrar por
aseguradora. Se carga una sola vez en memoria (lazy) y se cachea en proceso.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

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
