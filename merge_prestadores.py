#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fusiona prestadores_bmi.json y prestadores_msp.json en una sola base unificada.
Mantiene compatibilidad con el formato BMI y añade fuente/origen.
Genera JSON y SQLite unificados.
"""
import json
import sqlite3
from pathlib import Path

BMI_JSON = Path("/mnt/d/solucion-chatbot/prestadores_bmi.json")
MSP_JSON = Path("/mnt/d/solucion-chatbot/prestadores_msp.json")
UNIFIED_JSON = Path("/mnt/d/solucion-chatbot/prestadores_unificados.json")
UNIFIED_DB = Path("/mnt/d/solucion-chatbot/prestadores_unificados.db")


def normalize(text):
    if text is None:
        return ""
    return " ".join(str(text).split())


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def adapt_bmi(record):
    """Adapta registro BMI al formato unificado."""
    return {
        "provincia": record.get("provincia", ""),
        "ciudad": record.get("ciudad", ""),
        "categoria": record.get("categoria", ""),
        "nombre": record.get("nombre", ""),
        "direccion": record.get("direccion", ""),
        "horarios": record.get("horarios") if record.get("horarios") else None,
        "contactos": record.get("contactos", []),
        "pagina_web": record.get("pagina_web") if record.get("pagina_web") else None,
        "beneficios": record.get("beneficios", []),
        "fuente": "BMI",
        "tipo": "PRIVADO",
        "institucion": None,
        "codigo_msp": None,
    }


def adapt_msp(record):
    """Adapta registro MSP al formato unificado."""
    return {
        "provincia": record.get("provincia", ""),
        "ciudad": record.get("ciudad", ""),
        "categoria": record.get("categoria", ""),
        "nombre": record.get("nombre", ""),
        "direccion": record.get("direccion", ""),
        "horarios": None,
        "contactos": [],
        "pagina_web": None,
        "beneficios": record.get("beneficios", []),
        "fuente": "MSP",
        "tipo": record.get("tipo", "DESCONOCIDO"),
        "institucion": record.get("institucion", None),
        "codigo_msp": record.get("codigo_msp", None),
    }


def main():
    print("🔍 Cargando bases de datos...")
    bmi_data = load_json(BMI_JSON)
    msp_data = load_json(MSP_JSON)

    print(f"📥 BMI: {len(bmi_data)} registros")
    print(f"📥 MSP: {len(msp_data)} registros")

    unified = []
    for r in bmi_data:
        unified.append(adapt_bmi(r))
    for r in msp_data:
        unified.append(adapt_msp(r))

    print(f"📊 Total unificado: {len(unified)} registros")

    # Guardar JSON
    with open(UNIFIED_JSON, "w", encoding="utf-8") as f:
        json.dump(unified, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON unificado guardado: {UNIFIED_JSON}")

    # Guardar SQLite
    conn = sqlite3.connect(UNIFIED_DB)
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
            codigo_msp TEXT
        )
    """)
    for r in unified:
        cur.execute("""
            INSERT INTO prestadores 
            (fuente, tipo, provincia, ciudad, categoria, nombre, direccion, horarios, contactos, pagina_web, beneficios, institucion, codigo_msp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["fuente"], r["tipo"], r["provincia"], r["ciudad"], r["categoria"],
            r["nombre"], r["direccion"], r["horarios"],
            json.dumps(r["contactos"], ensure_ascii=False),
            r["pagina_web"],
            json.dumps(r["beneficios"], ensure_ascii=False),
            r["institucion"], r["codigo_msp"],
        ))
    conn.commit()
    conn.close()
    print(f"✅ SQLite unificado guardado: {UNIFIED_DB}")

    # Resumen por fuente
    bmi_count = sum(1 for r in unified if r["fuente"] == "BMI")
    msp_count = sum(1 for r in unified if r["fuente"] == "MSP")
    public_count = sum(1 for r in unified if r["tipo"] == "PÚBLICO")
    private_count = sum(1 for r in unified if r["tipo"] == "PRIVADO")
    comp_count = sum(1 for r in unified if r["tipo"] == "COMPLEMENTARIO")

    print(f"\n📊 RESUMEN UNIFICADO")
    print(f"  Total registros: {len(unified)}")
    print(f"  BMI (Privados): {bmi_count}")
    print(f"  MSP Públicos: {public_count}")
    print(f"  MSP Complementarios: {comp_count}")
    print(f"  PRIVADOS totales: {private_count}")

    # Muestras
    print(f"\n📝 Muestra BMI:")
    for r in unified:
        if r["fuente"] == "BMI":
            print(json.dumps(r, ensure_ascii=False, indent=2))
            break

    print(f"\n📝 Muestra MSP Público:")
    for r in unified:
        if r["fuente"] == "MSP" and r["tipo"] == "PÚBLICO":
            print(json.dumps(r, ensure_ascii=False, indent=2))
            break

    print(f"\n📝 Muestra MSP Complementario:")
    for r in unified:
        if r["fuente"] == "MSP" and r["tipo"] == "COMPLEMENTARIO":
            print(json.dumps(r, ensure_ascii=False, indent=2))
            break


if __name__ == "__main__":
    main()
