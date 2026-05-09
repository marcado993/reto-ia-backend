#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Procesamiento de datos de GeoSalud MSP Ecuador.
Adapta los datos descargados al formato JSON/SQLite del proyecto.
Fuente: https://geosalud.msp.gob.ec/geovisualizador/
"""
import json
import sqlite3
from pathlib import Path

RAW_PATH = Path("/tmp/geosalud_raw.json")
JSON_PATH = Path("/mnt/d/solucion-chatbot/prestadores_msp.json")
DB_PATH = Path("/mnt/d/solucion-chatbot/prestadores_msp.db")

# Instituciones consideradas públicas/gratuitas
PUBLIC_INSTITUTIONS = {
    "MSP", "IESS", "SNAI", "FUERZAS ARMADAS", "POLICIA NACIONAL",
    "JUNTA DE BENEFICENCIA", "SOLCA", "MUNICIPIO",
}


def is_public(record):
    """Determina si un establecimiento es público/gratuito."""
    red = record.get("rednombre", "").strip().upper()
    inst = record.get("institucionnombre", "").strip().upper()
    if red == "RED PUBLICA":
        return True
    if inst in PUBLIC_INSTITUTIONS:
        return True
    return False


def normalize(text):
    if not text:
        return ""
    return " ".join(str(text).split())


def process_record(raw):
    """Convierte un registro raw de GeoSalud al formato del proyecto."""
    provincia = normalize(raw.get("provincianombre", ""))
    ciudad = normalize(raw.get("cantonnombre", ""))
    parroquia = normalize(raw.get("parroquianombre", ""))
    
    # Construir dirección aproximada con la info disponible
    direccion_parts = []
    if parroquia and parroquia != ciudad:
        direccion_parts.append(f"Parroquia {parroquia}")
    if ciudad:
        direccion_parts.append(ciudad)
    if provincia:
        direccion_parts.append(provincia)
    direccion = ", ".join(direccion_parts)

    # Categoría: usar tipología o nivel de atención
    categoria = normalize(raw.get("tipopubliconombre", ""))
    if not categoria:
        categoria = normalize(raw.get("nivelpubliconombre", ""))

    return {
        "provincia": provincia,
        "ciudad": ciudad,
        "categoria": categoria,
        "nombre": normalize(raw.get("uninombreoficial", "")),
        "direccion": direccion,
        "horarios": None,
        "contactos": [],
        "pagina_web": None,
        "beneficios": ["Gratuito"] if is_public(raw) else [],
        "tipo": "PÚBLICO" if is_public(raw) else "COMPLEMENTARIO",
        "institucion": normalize(raw.get("institucionnombre", "")),
        "red_atencion": normalize(raw.get("rednombre", "")),
        "nivel_atencion": normalize(raw.get("nivelpubliconombre", "")),
        "codigo_msp": raw.get("unicodigo", ""),
    }


def main():
    print("🔍 Cargando datos descargados de GeoSalud...")
    with open(RAW_PATH, encoding="utf-8") as f:
        raw_data = json.load(f)
    print(f"📥 Registros descargados: {len(raw_data)}")

    records = [process_record(r) for r in raw_data]
    
    # Estadísticas
    public_count = sum(1 for r in records if r["tipo"] == "PÚBLICO")
    complementary_count = len(records) - public_count
    print(f"📊 Públicos/Gratuitos: {public_count}")
    print(f"📊 Complementarios: {complementary_count}")

    # Guardar JSON
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON guardado: {JSON_PATH}")

    # Guardar SQLite
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS prestadores_msp")
    cur.execute("""
        CREATE TABLE prestadores_msp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provincia TEXT,
            ciudad TEXT,
            categoria TEXT,
            nombre TEXT,
            direccion TEXT,
            horarios TEXT,
            contactos TEXT,
            pagina_web TEXT,
            beneficios TEXT,
            tipo TEXT,
            institucion TEXT,
            red_atencion TEXT,
            nivel_atencion TEXT,
            codigo_msp TEXT
        )
    """)
    for r in records:
        cur.execute("""
            INSERT INTO prestadores_msp 
            (provincia, ciudad, categoria, nombre, direccion, horarios, contactos, pagina_web, beneficios, tipo, institucion, red_atencion, nivel_atencion, codigo_msp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["provincia"], r["ciudad"], r["categoria"], r["nombre"],
            r["direccion"], r["horarios"],
            json.dumps(r["contactos"], ensure_ascii=False),
            r["pagina_web"],
            json.dumps(r["beneficios"], ensure_ascii=False),
            r["tipo"], r["institucion"], r["red_atencion"],
            r["nivel_atencion"], r["codigo_msp"],
        ))
    conn.commit()
    conn.close()
    print(f"✅ SQLite guardado: {DB_PATH}")

    # Muestra
    print("\n📝 Primeros 3 registros:")
    for r in records[:3]:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        print()

    print("\n📝 Ejemplo gratuito:")
    for r in records:
        if r["tipo"] == "PÚBLICO":
            print(json.dumps(r, ensure_ascii=False, indent=2))
            break

    print("\n📝 Ejemplo complementario:")
    for r in records:
        if r["tipo"] == "COMPLEMENTARIO":
            print(json.dumps(r, ensure_ascii=False, indent=2))
            break


if __name__ == "__main__":
    main()
