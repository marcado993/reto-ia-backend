#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Geocodificación de prestadores médicos (BMI + MSP) usando Nominatim (OpenStreetMap).
Genera JSON y SQLite con campos latitud y longitud.

Ejecución: ~75-90 minutos para ~4500 registros (rate limit 1.5s).
Soporta reanudación automática vía cache.
"""
import json
import sqlite3
import time
from pathlib import Path
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

INPUT_JSON = Path("/mnt/d/solucion-chatbot/prestadores_unificados.json")
CACHE_PATH = Path("/mnt/d/solucion-chatbot/geocode_cache.json")
OUTPUT_JSON = Path("/mnt/d/solucion-chatbot/prestadores_con_coords.json")
OUTPUT_DB = Path("/mnt/d/solucion-chatbot/prestadores_con_coords.db")

geolocator = Nominatim(user_agent="BMI-MSP-Prestadores-Map/1.0 (educativo)")


def load_cache():
    if CACHE_PATH.exists():
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def geocode_address(address_text, retries=3):
    """Geocodifica una dirección con retries. Devuelve (lat, lng) o (None, None)."""
    for attempt in range(retries):
        try:
            location = geolocator.geocode(address_text, exactly_one=True, timeout=10)
            if location:
                return (round(location.latitude, 6), round(location.longitude, 6))
            return (None, None)
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            wait = 2 ** attempt
            print(f"  ⚠️ Timeout/error (intento {attempt+1}/{retries}), esperando {wait}s...")
            time.sleep(wait)
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
            return (None, None)
    return (None, None)


def build_query(record):
    """Construye la query de dirección óptima según la fuente."""
    nombre = record.get("nombre", "").strip()
    direccion = record.get("direccion", "").strip()
    ciudad = record.get("ciudad", "").strip()
    provincia = record.get("provincia", "").strip()
    fuente = record.get("fuente", "")

    parts = []
    if fuente == "BMI":
        # BMI tiene direcciones detalladas
        if direccion:
            parts.append(direccion)
    else:
        # MSP: usar nombre + ciudad para mejor precisión
        if nombre:
            parts.append(nombre)

    if ciudad:
        parts.append(ciudad)
    if provincia:
        parts.append(provincia)
    parts.append("Ecuador")

    return ", ".join(parts)


def build_fallback_query(record):
    """Query fallback con solo ciudad/provincia."""
    ciudad = record.get("ciudad", "").strip()
    provincia = record.get("provincia", "").strip()
    parts = []
    if ciudad:
        parts.append(ciudad)
    if provincia:
        parts.append(provincia)
    parts.append("Ecuador")
    return ", ".join(parts)


def main():
    print("🔍 Cargando datos...")
    with open(INPUT_JSON, encoding="utf-8") as f:
        records = json.load(f)
    total = len(records)
    print(f"📥 Total registros: {total}")

    cache = load_cache()
    print(f"💾 Cache existente: {len(cache)} registros")

    success = 0
    fallback_success = 0
    failed = 0
    start_time = time.time()

    for i, record in enumerate(records):
        # Reanudar desde cache
        cache_key = f"{record.get('fuente')}_{record.get('nombre')}_{record.get('ciudad')}"
        if cache_key in cache:
            lat, lng = cache[cache_key]
            record["latitud"] = lat
            record["longitud"] = lng
            if lat is not None:
                success += 1
            else:
                failed += 1
            continue

        # Construir query
        query = build_query(record)
        print(f"[{i+1}/{total}] {record.get('fuente')} | {record.get('nombre')[:50]}...")
        print(f"  📍 Query: {query[:80]}...")

        lat, lng = geocode_address(query)

        if lat is None:
            # Fallback: intentar solo ciudad/provincia
            fallback_query = build_fallback_query(record)
            print(f"  🔄 Fallback: {fallback_query}")
            time.sleep(1.5)
            lat, lng = geocode_address(fallback_query)
            if lat is not None:
                fallback_success += 1
            else:
                failed += 1
        else:
            success += 1

        record["latitud"] = lat
        record["longitud"] = lng
        cache[cache_key] = (lat, lng)

        # Guardar progreso cada 50 registros
        if (i + 1) % 50 == 0:
            save_cache(cache)
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (total - (i + 1)) / rate if rate > 0 else 0
            print(f"💾 Progreso guardado: {i+1}/{total} | OK:{success} FB:{fallback_success} FAIL:{failed} | ETA: {remaining/60:.1f}min")

        # Rate limit: esperar 1.5 segundos entre peticiones
        time.sleep(1.5)

    # Guardar cache final
    save_cache(cache)

    # Guardar JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    # Guardar SQLite
    conn = sqlite3.connect(OUTPUT_DB)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS prestadores")
    cur.execute("""
        CREATE TABLE prestadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fuente TEXT,
            tipo TEXT,
            provincia TEXT,
            ciudad TEXT,
            categoria TEXT,
            nombre TEXT,
            direccion TEXT,
            horarios TEXT,
            contactos TEXT,
            pagina_web TEXT,
            beneficios TEXT,
            institucion TEXT,
            codigo_msp TEXT,
            latitud REAL,
            longitud REAL
        )
    """)
    for r in records:
        cur.execute("""
            INSERT INTO prestadores 
            (fuente, tipo, provincia, ciudad, categoria, nombre, direccion, horarios, contactos, pagina_web, beneficios, institucion, codigo_msp, latitud, longitud)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r.get("fuente"), r.get("tipo"), r.get("provincia"), r.get("ciudad"),
            r.get("categoria"), r.get("nombre"), r.get("direccion"), r.get("horarios"),
            json.dumps(r.get("contactos", []), ensure_ascii=False),
            r.get("pagina_web"),
            json.dumps(r.get("beneficios", []), ensure_ascii=False),
            r.get("institucion"), r.get("codigo_msp"),
            r.get("latitud"), r.get("longitud"),
        ))
    conn.commit()
    conn.close()

    print(f"\n✅ COMPLETADO")
    print(f"  JSON: {OUTPUT_JSON}")
    print(f"  SQLite: {OUTPUT_DB}")
    print(f"  Total: {total}")
    print(f"  Geocodificados (directo): {success}")
    print(f"  Geocodificados (fallback): {fallback_success}")
    print(f"  Sin coordenadas: {failed}")


if __name__ == "__main__":
    main()
