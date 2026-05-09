#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re

JSON_PATH = "prestadores_bmi.json"

RE_URL = re.compile(r"https?://[^\s]+")
RE_DOMAIN = re.compile(r"(?:www\.)?[a-zA-Z0-9-]+\.(?:com|com\.ec|ec|org|med\.ec|net|wixsite\.com|negocio\.site|site|webnode\.page|github\.io|html|php)(?:/[a-zA-Z0-9_./?=&%-]*)?", re.IGNORECASE)
RE_PHONE = re.compile(r"\(\d{2}\)\s*\d{3,4}\s*\d{3,4}|\(?0\d{2}\)?\s*\d{3}\s*\d{4}|1?800[\s\-]?\d{2,3}[\s\-]?\d{3,4}")
RE_BENEFICIO = re.compile(r"CRÉDITO|DESCUENTO|CONVENIO|RED PREFERENCIAL|PRESTADOR HOSPITALARIO|CONSULTA MÉDICA|IMAGEN|LABORATORIO|AMBULATORIO|HOSPITALARIO|CO-PAGO|COPAGO", re.IGNORECASE)
RE_HORARIO = re.compile(r"LUNES|MARTES|MIÉRCOLES|JUEVES|VIERNES|SÁBADO|DOMINGO|HORAS|PREVIA CITA|EMERGENCIAS|CERRADO|ABIERTO", re.IGNORECASE)

def load_data():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)

def check_url_in_field(value, field_name, record_id):
    issues = []
    if value and (RE_URL.search(str(value)) or RE_DOMAIN.search(str(value))):
        issues.append(f"  [{record_id}] URL en {field_name}: {value}")
    return issues

def main():
    data = load_data()
    issues = []
    stats = {
        "total": len(data),
        "empty_direccion": 0,
        "empty_horarios": 0,
        "empty_contactos": 0,
        "empty_beneficios": 0,
        "empty_web": 0,
        "mixed_direccion": 0,
        "mixed_horarios": 0,
        "mixed_beneficios": 0,
        "no_phone_in_contactos": 0,
        "url_in_direccion": 0,
        "url_in_horarios": 0,
        "url_in_beneficios": 0,
        "beneficio_not_beneficio": 0,
        "horario_not_horario": 0,
    }

    for i, r in enumerate(data):
        rid = f"#{i} {r['nombre']}"

        # Vacíos
        if not r["direccion"]:
            stats["empty_direccion"] += 1
        if not r["horarios"]:
            stats["empty_horarios"] += 1
        if not r["contactos"]:
            stats["empty_contactos"] += 1
        if not r["beneficios"]:
            stats["empty_beneficios"] += 1
        if not r["pagina_web"]:
            stats["empty_web"] += 1

        # URLs en campos incorrectos
        if RE_URL.search(r["direccion"]) or RE_DOMAIN.search(r["direccion"]):
            stats["url_in_direccion"] += 1
            issues.append(f"  [{rid}] URL en direccion: {r['direccion']}")
        if RE_URL.search(r["horarios"]) or RE_DOMAIN.search(r["horarios"]):
            stats["url_in_horarios"] += 1
            issues.append(f"  [{rid}] URL en horarios: {r['horarios']}")
        for b in r["beneficios"]:
            if RE_URL.search(b) or RE_DOMAIN.search(b):
                stats["url_in_beneficios"] += 1
                issues.append(f"  [{rid}] URL en beneficios: {b}")
                break

        # Dirección con palabras de horario o contacto
        if r["direccion"] and RE_HORARIO.search(r["direccion"]):
            stats["mixed_direccion"] += 1
            issues.append(f"  [{rid}] Direccion mezclada con horario: {r['direccion']}")

        # Horarios con palabras de beneficios
        if r["horarios"] and RE_BENEFICIO.search(r["horarios"]):
            stats["mixed_horarios"] += 1
            issues.append(f"  [{rid}] Horarios mezclados con beneficios: {r['horarios']}")

        # Beneficios que no contienen palabras de beneficio (excepto vacíos)
        for b in r["beneficios"]:
            if not RE_BENEFICIO.search(b):
                stats["beneficio_not_beneficio"] += 1
                issues.append(f"  [{rid}] Beneficio sin palabra clave: {b}")

        # Contactos sin teléfono válido
        if r["contactos"]:
            has_phone = any(RE_PHONE.search(c) for c in r["contactos"])
            if not has_phone:
                stats["no_phone_in_contactos"] += 1
                issues.append(f"  [{rid}] Contactos sin teléfono: {r['contactos']}")

        # Horarios sin palabra de horario
        if r["horarios"] and not RE_HORARIO.search(r["horarios"]):
            stats["horario_not_horario"] += 1
            issues.append(f"  [{rid}] Horarios sin palabra clave: {r['horarios']}")

    print("=== ESTADÍSTICAS ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print(f"\n=== PROBLEMAS ENCONTRADOS ({len(issues)}) ===")
    for issue in issues[:50]:
        print(issue)
    if len(issues) > 50:
        print(f"  ... y {len(issues) - 50} más")

    # Mostrar algunos ejemplos de registros buenos vs malos
    print("\n=== EJEMPLOS DE REGISTROS CON PROBLEMAS ===")
    for i, r in enumerate(data):
        has_issue = False
        if not r["direccion"] or RE_HORARIO.search(r["direccion"]) or RE_URL.search(r["direccion"]):
            has_issue = True
        if r["horarios"] and (RE_BENEFICIO.search(r["horarios"]) or not RE_HORARIO.search(r["horarios"])):
            has_issue = True
        for b in r["beneficios"]:
            if RE_URL.search(b) or not RE_BENEFICIO.search(b):
                has_issue = True
        if has_issue:
            print(json.dumps(r, ensure_ascii=False, indent=2))
            print()
            break

if __name__ == "__main__":
    main()
