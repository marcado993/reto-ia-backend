#!/usr/bin/env python3
"""
Scraper para API de Salud S.A. - Redes CAPS
Extrae Centros Médicos y Hospitales/Clínicas con cobertura directa.
Genera prestadores_saludsa.json en formato compatbile con prestadores_bmi.json
"""

import requests
import json
import time
import sys
from urllib.parse import urlencode

# ─── Config ──────────────────────────────────────────────────────
BASE_URL = "https://back.saludsa.com"
TOKEN_URL = f"{BASE_URL}/api/oauth/token"
CITIES_URL = f"{BASE_URL}/api/microsites/cities/{{plan}}"
SPECIALS_URL = f"{BASE_URL}/api/microsites/specials-providers"
MEDICAL_URL = f"{BASE_URL}/api/microsites/medical-providers"

PLAN = "STAR30-NP"  # Red Star - plan más común
TAKE = 100  # items por página (máximo razonable)

# ─── Diccionario Ciudad → Provincia ─────────────────────────────
CIUDAD_PROVINCIA = {
    "ambato": "TUNGURAHUA",
    "atuntaqui": "IMBABURA",
    "azogues": "CAÑAR",
    "babahoyo": "LOS RÍOS",
    "cayambe": "PICHINCHA",
    "chone": "MANABÍ",
    "coca": "ORELLANA",
    "cuenca": "AZUAY",
    "daule": "GUAYAS",
    "durán": "GUAYAS",
    "el carmen": "MANABÍ",
    "el empalme": "GUAYAS",
    "esmeraldas": "ESMERALDAS",
    "guaranda": "BOLÍVAR",
    "guayaquil": "GUAYAS",
    "ibarra": "IMBABURA",
    "jipijapa": "MANABÍ",
    "la libertad": "SANTA ELENA",
    "latacunga": "COTOPAXI",
    "loja": "LOJA",
    "macas": "MORONA SANTIAGO",
    "machala": "EL ORO",
    "manta": "MANABÍ",
    "milagro": "GUAYAS",
    "montecristi": "MANABÍ",
    "nueva loja": "SUCUMBÍOS",
    "otavalo": "IMBABURA",
    "pasaje": "EL ORO",
    "portoviejo": "MANABÍ",
    "playas": "GUAYAS",
    "puyo": "PASTAZA",
    "quevedo": "LOS RÍOS",
    "quito": "PICHINCHA",
    "riobamba": "CHIMBORAZO",
    "samborondón": "GUAYAS",
    "salinas": "SANTA ELENA",
    "santa elena": "SANTA ELENA",
    "santo domingo": "SANTO DOMINGO DE LOS TSÁCHILAS",
    "tena": "NAPO",
    "tulcan": "CARCHI",
    "yaguachi": "GUAYAS",
    "zamora": "ZAMORA CHINCHIPE",
}


def obtener_provincia(ciudad):
    """Infiere provincia desde nombre de ciudad."""
    if not ciudad:
        return "n/a"
    return CIUDAD_PROVINCIA.get(ciudad.strip().lower(), "n/a")


def get_token():
    """Obtiene token OAuth2 de la API."""
    payload = {
        "grant_type": "client_credentials",
        "client_id": "4",
        "client_secret": "6b1Ln7kBzw2gTkZZoyJcVrFfoWxh5Gx6QmOoK4EL",
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post(TOKEN_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_cities(token):
    """Obtiene lista de ciudades disponibles para el plan."""
    headers = {"Authorization": f"Bearer {token}"}
    url = CITIES_URL.format(plan=PLAN)
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_all_pages(token, code_city, type_provider, specialities=""):
    """
    Obtiene TODOS los items de un tipo de proveedor en una ciudad,
    manejando paginación automática y reintentos ante 429.
    """
    headers = {"Authorization": f"Bearer {token}"}
    all_items = []
    page = 1
    max_retries = 5

    while True:
        params = {
            "codeCity": code_city,
            "page": page,
            "take": TAKE,
            "typeProvider": type_provider,
            "query": "",
            "specialities": specialities,
            "nombreRed": PLAN,
        }

        for attempt in range(max_retries):
            try:
                resp = requests.get(SPECIALS_URL, headers=headers, params=params, timeout=60)
                if resp.status_code == 429:
                    wait = 2 ** attempt + 1
                    print(f"    ⚠ 429 detectado. Esperando {wait}s antes de reintentar...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** attempt + 1
                print(f"    ⚠ Error de red: {e}. Esperando {wait}s...")
                time.sleep(wait)
        else:
            # Si salimos del for por 429 persistente
            raise Exception(f"No se pudo obtener datos para ciudad {code_city} tras {max_retries} intentos")

        data = resp.json()

        items = data.get("items", [])
        if not items:
            break

        all_items.extend(items)

        total_pages = data.get("totalPages", 1)
        print(f"  [{type_provider}] Ciudad {code_city} - Página {page}/{total_pages} - {len(items)} items")

        if page >= total_pages:
            break
        page += 1
        time.sleep(0.8)  # Pausa entre páginas para evitar 429

    return all_items


def mapear_registro(item, categoria_bmi, tipo):
    """
    Mapea un item de la API al formato prestadores_bmi.json.
    tipo: 'centro_medico' o 'hospital'
    """
    ciudad = item.get("Ciudad", "") or ""
    provincia = obtener_provincia(ciudad)

    nombre = item.get("NombreComercial", "") or item.get("RazonSocial", "") or "n/a"
    direccion = item.get("Direccion", "") or "n/a"
    horario = item.get("HorarioAtencion", "") or "n/a"

    # Contactos
    contactos = []
    for campo in ["Telefono", "Telefono2", "Celular"]:
        val = item.get(campo, "")
        if val and str(val).strip():
            contactos.append(str(val).strip())
    if not contactos:
        contactos = ["n/a"]

    pagina_web = item.get("PaginaWeb", "")
    pagina_web = pagina_web if pagina_web and pagina_web.strip() else None

    # Beneficios según tipo
    if tipo == "centro_medico":
        beneficios = ["Crédito Ambulatorio"]
    else:
        beneficios = ["Crédito Hospitalario"]

    return {
        "provincia": provincia,
        "ciudad": ciudad.upper() if ciudad else "n/a",
        "categoria": categoria_bmi,
        "nombre": nombre.upper() if nombre else "n/a",
        "direccion": direccion,
        "horarios": horario,
        "contactos": contactos,
        "pagina_web": pagina_web,
        "beneficios": beneficios,
    }


def main():
    print("=" * 60)
    print("SCRAPER SALUD S.A. - Redes CAPS")
    print("=" * 60)

    # 1. Token
    print("\n[1/5] Obteniendo token OAuth2...")
    token = get_token()
    print("✓ Token obtenido")

    # 2. Ciudades
    print("\n[2/5] Obteniendo lista de ciudades...")
    cities = get_cities(token)
    print(f"✓ {len(cities)} ciudades encontradas")

    # 3. Extraer datos
    print("\n[3/5] Extrayendo Centros Médicos...")
    registros = []

    for city in cities:
        code = city["Codigo"]
        name = city["Nombre"]

        # --- Centros Médicos ---
        items = fetch_all_pages(token, code, "Centro de Médicos")
        for item in items:
            registros.append(mapear_registro(item, "CENTRO DE COPAGO", "centro_medico"))

        # --- Hospitales / Clínicas ---
        # Solo incluir si EsRedCeroTramites=True o EmiteOdas=True
        hosp_items = fetch_all_pages(token, code, "Clínica/Hospital")
        for item in hosp_items:
            if item.get("EsRedCeroTramites") or item.get("EmiteOdas"):
                registros.append(mapear_registro(item, "CLÍNICAS Y HOSPITALES", "hospital"))

        # Pausa entre ciudades para no saturar la API
        time.sleep(1.5)

    # 4. Guardar
    print(f"\n[4/5] Total de registros extraídos: {len(registros)}")

    output_path = "/mnt/d/solucion-chatbot/prestadores_saludsa.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)

    print(f"✓ Archivo guardado: {output_path}")

    # 5. Resumen
    print("\n[5/5] Resumen:")
    print(f"  - Total registros: {len(registros)}")
    centros = [r for r in registros if r["categoria"] == "CENTRO DE COPAGO"]
    hospitales = [r for r in registros if r["categoria"] == "CLÍNICAS Y HOSPITALES"]
    print(f"  - Centros Médicos (copago): {len(centros)}")
    print(f"  - Hospitales/Clínicas (cobertura directa): {len(hospitales)}")

    print("\n¡Proceso completado!")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
