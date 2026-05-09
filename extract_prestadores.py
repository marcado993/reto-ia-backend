#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extracción de Prestadores Médicos del PDF de BMI.
Versión final robusta: usa posiciones de caracteres del header para cortar columnas exactas.
Genera JSON y SQLite.
"""
import json
import re
import sqlite3
import subprocess
from pathlib import Path

PDF_PATH = Path("/mnt/d/solucion-chatbot/docs/BMI-Prestadores-y-Red-medica-V10_2024_06_18.pdf")
JSON_PATH = Path("/mnt/d/solucion-chatbot/prestadores_bmi.json")
DB_PATH = Path("/mnt/d/solucion-chatbot/prestadores_bmi.db")

CATEGORIAS = {
    "AMBULATORIO",
    "CENTRO DE COPAGO",
    "CENTRO DE COPAGO DE CRÉDITO",
    "CENTRO DE COPAGO DE CRÉDITO AMBULATORIO",
    "CLÍNICAS Y HOSPITALES",
    "LABORATORIO",
    "HOSPITAL DEL DÍA",
}

PROVINCIAS_EC = {
    "AZUAY", "BOLÍVAR", "BOLIVAR", "CAÑAR", "CANAR", "CARCHI", "CHIMBORAZO",
    "COTOPAXI", "EL ORO", "ESMERALDAS", "GALÁPAGOS", "GALAPAGOS", "GUAYAS",
    "IMBABURA", "LOJA", "LOS RÍOS", "LOS RIOS", "MANABÍ", "MANABI",
    "MORONA SANTIAGO", "NAPO", "ORELLANA", "PASTAZA", "PICHINCHA",
    "SANTA ELENA", "SANTO DOMINGO DE LOS TSÁCHILAS", "SANTO DOMINGO DE LOS TSACHILAS",
    "SUCUMBÍOS", "SUCUMBIOS", "TUNGURAHUA", "ZAMORA CHINCHIPE",
}

RE_PHONE = re.compile(
    r"\(\d{2}\)\s*\d{3,4}\s*\d{3,4}|"
    r"\(?0\d{2}\)?\s*\d{3}\s*\d{4}|"
    r"1?800[\s\-]?\d{2,3}[\s\-]?\d{3,4}|"
    r"\d{3}[\s\-]?\d{3}[\s\-]?\d{3,4}|"
    r"\d{2}\s*\d{3}\s*\d{4}|"
    r"\d{3}\s*\d{4}\s*\d{3}",
    re.VERBOSE
)
RE_URL = re.compile(r"https?://[^\s|]+")
RE_DOMAIN = re.compile(
    r"(?:www\.)?[a-zA-Z0-9-]+\.(?:com\.ec|med\.ec|wixsite\.com|negocio\.site|webnode\.page|github\.io|com|ec|org|net|site|html|php)(?:/[a-zA-Z0-9_./?=&%-]*)?",
    re.IGNORECASE
)
RE_WHATSAPP = re.compile(r"Citas?:?\s*https?://[^\s|]+", re.IGNORECASE)
RE_BULLET = re.compile(r"^[·•\-]\s*")
RE_BENEFICIO_KEYWORDS = re.compile(
    r"CRÉDITO|DESCUENTO|CONVENIO|RED PREFERENCIAL|PRESTADOR HOSPITALARIO|CONSULTA MÉDICA|IMAGEN|LABORATORIO|AMBULATORIO|HOSPITALARIO|CO-PAGO|COPAGO",
    re.IGNORECASE
)
RE_HORARIO_KEYWORDS = re.compile(
    r"LUNES|MARTES|MIÉRCOLES|JUEVES|VIERNES|SÁBADO|DOMINGO|HORAS|PREVIA CITA|EMERGENCIAS|CERRADO|ABIERTO",
    re.IGNORECASE
)


def normalize(text: str) -> str:
    return " ".join(text.split())


def remove_urls(text: str) -> str:
    text = RE_URL.sub(" ", text)
    text = RE_DOMAIN.sub(" ", text)
    text = RE_WHATSAPP.sub(" ", text)
    text = re.sub(r"\s+\.(?:ec|com|org|net|html|php)\b", " ", text)
    return normalize(text)


def is_all_caps(text: str) -> bool:
    cleaned = text.replace(" ", "").replace("-", "").replace("/", "").strip()
    if len(cleaned) <= 2:
        return False
    return all(c.isupper() or c.isdigit() or c in ".,():/&-–—%?=_#·•" for c in cleaned)


def detect_header_slices(line):
    """
    Detecta las posiciones de corte del header Dirección/Horarios/Contactos/Beneficios.
    Devuelve tuplas (start, end, field_name) para cada columna.
    end=None significa 'hasta el final de la línea'.
    """
    pos_dir = line.find("Dirección")
    pos_hor = line.find("Horarios")
    pos_cont = line.find("Contactos")
    pos_ben = line.find("Beneficios")
    if pos_ben == -1:
        pos_ben = line.find("Beneficio")

    if pos_dir == -1 or pos_hor == -1 or pos_cont == -1:
        return None

    slices = []
    # Dirección: desde inicio hasta Horarios
    slices.append((0, pos_hor, "direccion"))
    # Horarios: desde Horarios hasta Contactos
    slices.append((pos_hor, pos_cont, "horarios"))
    # Contactos: desde Contactos hasta Beneficios (o hasta fin si no hay Beneficios)
    if pos_ben != -1:
        slices.append((pos_cont, pos_ben, "contactos"))
        slices.append((pos_ben, None, "beneficios"))
    else:
        slices.append((pos_cont, None, "contactos"))

    return slices


def extract_by_slices(line, slices):
    """Extrae campos de una línea usando los slices del header."""
    result = {"direccion": "", "horarios": "", "contactos": "", "beneficios": ""}
    has_beneficios_col = any(field == "beneficios" for _, _, field in slices)

    for start, end, field in slices:
        if start < len(line):
            if end is None:
                text = line[start:].strip()
            else:
                text = line[start:min(end, len(line))].strip()
            # Ignorar headers sueltos
            if text.upper() not in ("DIRECCIÓN", "HORARIOS", "CONTACTOS", "BENEFICIOS", "DIRECCION", "HORARIO", "CONTACTO", "BENEFICIO"):
                result[field] = text

    # Si no hay columna de beneficios en el header, intentar separar de contactos
    if not has_beneficios_col and result["contactos"]:
        cont = result["contactos"]
        # Buscar la palabra "Beneficios" como separador
        pos = cont.find("Beneficios")
        if pos != -1:
            result["contactos"] = cont[:pos].strip()
            result["beneficios"] = cont[pos + len("Beneficios"):].strip()
        else:
            # Buscar palabras clave de beneficios
            for keyword in ["Crédito", "Descuento", "Convenio", "Red Preferencial", "Prestador Hospitalario", "Consulta Médica", "Imagen", "Laboratorio"]:
                pos = cont.find(keyword)
                if pos != -1:
                    # Verificar que no sea parte de un teléfono o dirección
                    before = cont[:pos].strip()
                    after = cont[pos:].strip()
                    # Si antes hay un teléfono, separarlo
                    result["beneficios"] = after
                    result["contactos"] = before
                    break

    return result


def find_urls(lines_text):
    for line in lines_text:
        m = RE_URL.search(line)
        if m:
            return m.group(0)
    for line in lines_text:
        m = RE_DOMAIN.search(line)
        if m:
            domain = m.group(0)
            if domain.startswith("www."):
                return "https://" + domain
            elif not domain.startswith("http"):
                return "https://" + domain
            return domain
    return None


def clean_beneficios(text):
    parts = re.split(r"[;,]", text)
    out = []
    for p in parts:
        p = normalize(RE_BULLET.sub("", p))
        p = re.sub(r"^Beneficios\s*", "", p, flags=re.IGNORECASE).strip()
        if p and len(p) > 2 and RE_BENEFICIO_KEYWORDS.search(p):
            out.append(p)
    return out


def clean_contactos(text):
    out = []
    for m in RE_PHONE.finditer(text):
        val = normalize(m.group(0))
        if val and val not in out:
            out.append(val)
    return out


def get_text_lines():
    result = subprocess.run(
        ["pdftotext", "-layout", str(PDF_PATH), "-"],
        capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout.splitlines()


def parse_text():
    results = []
    lines = get_text_lines()

    prov = ""
    ciudad = ""
    categoria = ""
    clinica_name = ""
    entry_lines = []  # lista de line_text
    slices = None
    inside_entry = False
    skip_until_province = False

    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()

        # Detectar secciones a ignorar
        if "RED DE MÉDICOS" in upper or "RED DE MEDICOS" in upper or "PARA PROCEDIMIENTOS QUIRÚRGICOS" in upper:
            skip_until_province = True
            clinica_name = ""
            entry_lines = []
            inside_entry = False
            continue
        if "PRESTADORES DENTALES" in upper:
            skip_until_province = True
            clinica_name = ""
            entry_lines = []
            inside_entry = False
            continue
        if "RED MÉDICA" in upper and "PRESTADORES NACIONALES" in upper:
            skip_until_province = True
            clinica_name = ""
            entry_lines = []
            inside_entry = False
            continue
        m = re.match(r"^([A-ZÁÉÍÓÚÑa-záéíóúñ\s]{2,})\s*[-–—]\s*([A-ZÁÉÍÓÚÑa-záéíóúñ\s]{2,})$", stripped)
        if m:
            prov_candidate = normalize(m.group(1)).upper()
            if prov_candidate in PROVINCIAS_EC:
                skip_until_province = False

        if skip_until_province:
            continue

        # Filtros generales
        if "PRESTADORES NACIONALES" in upper and len(stripped) < 30:
            continue
        if re.match(r"^\s*\d+\s*$", stripped):
            continue
        if "ÍNDICE" in upper and ("PÁGINA" in upper or len(stripped) < 15):
            continue
        if not stripped:
            continue

        # Provincia - Ciudad
        m = re.match(r"^([A-ZÁÉÍÓÚÑa-záéíóúñ\s]{2,})\s*[-–—]\s*([A-ZÁÉÍÓÚÑa-záéíóúñ\s]{2,})$", stripped)
        if m:
            prov_candidate = normalize(m.group(1)).upper()
            if prov_candidate in PROVINCIAS_EC:
                if clinica_name and entry_lines:
                    rec = build_record(prov, ciudad, categoria, clinica_name, entry_lines, slices)
                    if rec:
                        results.append(rec)
                prov = normalize(m.group(1))
                ciudad = normalize(m.group(2))
                categoria = ""
                clinica_name = ""
                entry_lines = []
                slices = None
                inside_entry = False
                continue

        # Categoría
        if stripped in CATEGORIAS or normalize(stripped) in CATEGORIAS:
            if clinica_name and entry_lines:
                rec = build_record(prov, ciudad, categoria, clinica_name, entry_lines, slices)
                if rec:
                    results.append(rec)
            categoria = normalize(stripped)
            clinica_name = ""
            entry_lines = []
            slices = None
            inside_entry = False
            continue

        # Header de tabla
        hdr = detect_header_slices(line)
        if hdr:
            slices = hdr
            inside_entry = True
            continue

        # Nombre de clínica
        if is_all_caps(stripped) and len(stripped) > 3:
            if clinica_name and entry_lines:
                rec = build_record(prov, ciudad, categoria, clinica_name, entry_lines, slices)
                if rec:
                    results.append(rec)
            clinica_name = normalize(stripped)
            entry_lines = []
            slices = None
            inside_entry = True
            continue

        # Acumular líneas de datos
        if inside_entry and clinica_name:
            entry_lines.append(line)

    # Guardar última
    if clinica_name and entry_lines:
        rec = build_record(prov, ciudad, categoria, clinica_name, entry_lines, slices)
        if rec:
            results.append(rec)

    return results


def build_record(prov, ciudad, categoria, nombre, entry_lines, slices):
    direccion_parts = []
    horarios_parts = []
    contactos_parts = []
    beneficios_parts = []
    raw_lines = []

    for line in entry_lines:
        raw_lines.append(line)
        if slices:
            fields = extract_by_slices(line, slices)
            if fields["direccion"]:
                direccion_parts.append(fields["direccion"])
            if fields["horarios"]:
                horarios_parts.append(fields["horarios"])
            if fields["contactos"]:
                contactos_parts.append(fields["contactos"])
            if fields["beneficios"]:
                beneficios_parts.append(fields["beneficios"])
        else:
            # Fallback sin slices
            txt = line.strip()
            upper = txt.upper()
            if any(k in upper for k in ["CRÉDITO", "DESCUENTO", "CONVENIO", "RED PREFERENCIAL"]):
                beneficios_parts.append(txt)
            elif RE_PHONE.search(txt):
                contactos_parts.append(txt)
            elif RE_HORARIO_KEYWORDS.search(txt):
                horarios_parts.append(txt)
            else:
                direccion_parts.append(txt)

    pagina_web = find_urls(raw_lines)

    direccion = remove_urls(" ".join(direccion_parts))
    horarios = remove_urls(" ".join(horarios_parts))
    contactos_text = remove_urls(" ".join(contactos_parts))
    beneficios_text = remove_urls(" ".join(beneficios_parts))

    # Fallback beneficios
    if not beneficios_text:
        for line in entry_lines:
            clean = remove_urls(line.strip())
            if RE_BENEFICIO_KEYWORDS.search(clean):
                if slices:
                    fields = extract_by_slices(line, slices)
                    if fields["beneficios"]:
                        beneficios_text += " " + fields["beneficios"]
                else:
                    beneficios_text += " " + clean

    contactos = clean_contactos(contactos_text)
    beneficios = clean_beneficios(beneficios_text)

    if not nombre or not direccion:
        return None
    if "Contacto:" in direccion or "Contacto:" in horarios or "Contacto:" in contactos_text:
        return None

    return {
        "provincia": prov,
        "ciudad": ciudad,
        "categoria": categoria,
        "nombre": nombre,
        "direccion": direccion,
        "horarios": horarios,
        "contactos": contactos,
        "pagina_web": pagina_web,
        "beneficios": beneficios,
    }


def deduplicate(records):
    seen = set()
    out = []
    for r in records:
        key = (r["nombre"], r["direccion"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def save_json(records):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON guardado: {JSON_PATH} ({len(records)} registros)")


def save_sqlite(records):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS prestadores")
    cur.execute("""
        CREATE TABLE prestadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provincia TEXT,
            ciudad TEXT,
            categoria TEXT,
            nombre TEXT,
            direccion TEXT,
            horarios TEXT,
            contactos TEXT,
            pagina_web TEXT,
            beneficios TEXT
        )
    """)
    for r in records:
        cur.execute("""
            INSERT INTO prestadores (provincia, ciudad, categoria, nombre, direccion, horarios, contactos, pagina_web, beneficios)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["provincia"], r["ciudad"], r["categoria"], r["nombre"],
            r["direccion"], r["horarios"],
            json.dumps(r["contactos"], ensure_ascii=False),
            r["pagina_web"],
            json.dumps(r["beneficios"], ensure_ascii=False),
        ))
    conn.commit()
    conn.close()
    print(f"✅ SQLite guardado: {DB_PATH} ({len(records)} registros)")


def main():
    print("🔍 Analizando PDF (header slice positions)...")
    records = parse_text()
    records = deduplicate(records)
    print(f"📊 Registros extraídos: {len(records)}")
    save_json(records)
    save_sqlite(records)
    if records:
        print("\n📝 Primeros 5 registros:")
        for r in records[:5]:
            print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
