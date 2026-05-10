#!/usr/bin/env python3
"""
Scraper Humana S.A. - Red de Prestadores (Red CAM / Copago)
Usa Playwright para navegar la web ASP.NET y extraer datos.
"""

import asyncio
import json
import re
from playwright.async_api import async_playwright

URL = "https://red.humana.med.ec/RedHumana"
OUTPUT_JSON = "/mnt/d/solucion-chatbot/prestadores_humana.json"
OUTPUT_DB = "/mnt/d/solucion-chatbot/prestadores_humana.db"

# Diccionario ciudad -> provincia
CIUDAD_PROVINCIA = {
    "ambato": "TUNGURAHUA",
    "atuntaqui": "IMBABURA",
    "azogues": "CAÑAR",
    "babahoyo": "LOS RÍOS",
    "cayambe": "PICHINCHA",
    "chone": "MANABÍ",
    "cuenca": "AZUAY",
    "daule": "GUAYAS",
    "durán": "GUAYAS",
    "el coca": "ORELLANA",
    "el triunfo": "GUAYAS",
    "esmeraldas": "ESMERALDAS",
    "galápagos": "GALÁPAGOS",
    "gualaquiza": "MORONA SANTIAGO",
    "guaranda": "BOLÍVAR",
    "guayaquil": "GUAYAS",
    "ibarra": "IMBABURA",
    "joya de los sachas": "ORELLANA",
    "lago agrio": "SUCUMBÍOS",
    "la libertad": "SANTA ELENA",
    "latacunga": "COTOPAXI",
    "loja": "LOJA",
    "macas": "MORONA SANTIAGO",
    "machachi": "PICHINCHA",
    "machala": "EL ORO",
    "manta": "MANABÍ",
    "marcelino maridueña": "GUAYAS",
    "milagro": "GUAYAS",
    "montecristi": "MANABÍ",
    "naranjito": "GUAYAS",
    "otavalo": "IMBABURA",
    "pelileo": "TUNGURAHUA",
    "píllaro": "TUNGURAHUA",
    "piñas": "EL ORO",
    "portoviejo": "MANABÍ",
    "pujilí": "COTOPAXI",
    "puyo": "PASTAZA",
    "quevedo": "LOS RÍOS",
    "quinindé": "ESMERALDAS",
    "quito": "PICHINCHA",
    "riobamba": "CHIMBORAZO",
    "salcedo": "COTOPAXI",
    "salinas": "SANTA ELENA",
    "samborondon": "GUAYAS",
    "san lorenzo": "ESMERALDAS",
    "santo domingo": "SANTO DOMINGO DE LOS TSÁCHILAS",
    "shushufindi": "SUCUMBÍOS",
    "tena": "NAPO",
    "tulcán": "CARCHI",
    "villamil playas": "GUAYAS",
    "yanzatza": "ZAMORA CHINCHIPE",
    "zamora": "ZAMORA CHINCHIPE",
}


def obtener_provincia(ciudad):
    if not ciudad:
        return "n/a"
    return CIUDAD_PROVINCIA.get(ciudad.strip().lower(), "n/a")


def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


async def extraer_datos_tarjeta(card_element):
    """Extrae datos de una tarjeta usando la estructura DOM de DevExpress."""
    data = await card_element.evaluate('''el => {
        const result = {};
        const groups = el.querySelectorAll('.form-group');
        groups.forEach(g => {
            const label = g.querySelector('label.control-label');
            const ctrl = g.querySelector('.dxbs-fl-ctrl');
            if (!ctrl) return;
            const txt = ctrl.textContent.trim();
            if (label) {
                const key = label.textContent.trim().replace(':', '');
                if (key) {
                    result[key] = txt;
                } else {
                    // label vacío (iconmapa) -> Ciudad
                    if (txt) result['Ciudad'] = txt;
                }
            } else {
                // sin label -> Nombre (ignorar img/botón)
                if (!ctrl.querySelector('img, button') && txt.length > 2 && txt !== 'Ver más...') {
                    result['Nombre'] = txt;
                }
            }
        });
        return result;
    }''')
    
    nombre = clean_text(data.get('Nombre', ''))
    direccion = clean_text(data.get('Dirección', ''))
    telefono = clean_text(data.get('Telefono', ''))
    tipo_atencion = clean_text(data.get('Tipo de Atención', ''))
    producto = clean_text(data.get('Producto', ''))
    ciudad = clean_text(data.get('Ciudad', ''))
    
    return {
        'nombre': nombre,
        'direccion': direccion,
        'telefono': telefono,
        'ciudad': ciudad,
        'tipo_atencion': tipo_atencion,
        'producto': producto,
    }


async def seleccionar_ciudad(page, ciudad):
    """Selecciona una ciudad en el combo de DevExpress."""
    try:
        # Hacer click en el input del combo para abrir la lista
        ciudad_input = await page.query_selector('#comboboxCiudad_I')
        if not ciudad_input:
            ciudad_input = await page.query_selector('#comboboxCiudad')
        
        if not ciudad_input:
            return False
        
        await ciudad_input.click()
        await asyncio.sleep(1)
        
        # Intentar encontrar la opción por texto exacto o parcial
        opcion = await page.query_selector(f'text="{ciudad}"')
        if not opcion:
            # Intentar case-insensitive via evaluate
            opcion = await page.evaluate_handle('''(ciudadName) => {
                const items = document.querySelectorAll('.dxbs-list-item, .dxbs-list-group-item, [id*="comboboxCiudad_L"] div, [id*="comboboxCiudad_D"] div');
                for (const item of items) {
                    if (item.textContent.trim().toLowerCase() === ciudadName) return item;
                }
                return null;
            }''', ciudad.lower())
            if opcion:
                op_element = opcion.as_element()
                if op_element:
                    await op_element.click()
                else:
                    return False
            else:
                await page.keyboard.press('Escape')
                return False
        else:
            await opcion.click()
        
        # Esperar a que termine el postback (ASP.NET UpdatePanel)
        # Usar sleep + wait_for_selector en lugar de networkidle
        await asyncio.sleep(2.5)
        try:
            await page.wait_for_selector('[id^="CardviewPrestadores_DXDataCard"]', timeout=10000)
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"    ⚠ Error seleccionando ciudad {ciudad}: {e}")
        return False


async def scrape_humana():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        print("=" * 60)
        print("SCRAPER HUMANA S.A. - Red CAM (Copago)")
        print("=" * 60)
        
        # 1. Navegar a la página
        print("\n[1/5] Cargando página...")
        await page.goto(URL, wait_until='networkidle', timeout=60000)
        await page.wait_for_selector('#CardviewPrestadores', timeout=30000)
        print("✓ Página cargada")
        
        # 2. Intentar obtener lista de ciudades del combo, si no usar diccionario
        print("\n[2/5] Obteniendo ciudades disponibles...")
        ciudades = []
        try:
            ciudad_input = await page.query_selector('#comboboxCiudad_I')
            if ciudad_input:
                await ciudad_input.click()
                await asyncio.sleep(1.5)
                
                opciones = await page.query_selector_all('.dxbs-list-item, .dxbs-list-group-item, [id*="comboboxCiudad_L"] div, [id*="comboboxCiudad_D"] div')
                for op in opciones:
                    text = await op.text_content()
                    if text and text.strip() and text.strip().lower() not in ['ciudad', 'seleccione', '']:
                        ciudades.append(text.strip())
                
                await page.keyboard.press('Escape')
                await asyncio.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ No se pudieron leer ciudades del combo: {e}")
        
        if not ciudades:
            ciudades = [c.title() for c in CIUDAD_PROVINCIA.keys()]
            print(f"  → Usando lista predefinida de {len(ciudades)} ciudades")
        else:
            print(f"✓ {len(ciudades)} ciudades encontradas en el combo")
        
        # 3. Iterar por ciudades y extraer datos
        print("\n[3/5] Extrayendo prestadores por ciudad...")
        todos_registros = []
        ciudades_procesadas = set()
        
        for ciudad in ciudades:
            if not ciudad or ciudad.lower() in ['ciudad', 'seleccione', '']:
                continue
            
            ciudad_key = ciudad.strip().lower()
            if ciudad_key in ciudades_procesadas:
                continue
            ciudades_procesadas.add(ciudad_key)
            
            print(f"\n  → Ciudad: {ciudad}")
            
            try:
                seleccionada = await seleccionar_ciudad(page, ciudad)
                if not seleccionada:
                    print(f"    ⚠ No se pudo seleccionar la ciudad")
                    continue
                
                # Verificar si hay tarjetas
                cards = await page.query_selector_all('[id^="CardviewPrestadores_DXDataCard"]')
                if not cards:
                    print(f"    → Sin prestadores para esta ciudad")
                    continue
                
                pagina = 1
                while True:
                    cards = await page.query_selector_all('[id^="CardviewPrestadores_DXDataCard"]')
                    print(f"    Página {pagina}: {len(cards)} tarjetas")
                    
                    for card in cards:
                        datos = await extraer_datos_tarjeta(card)
                        
                        if datos['nombre']:
                            tipo = datos['tipo_atencion'].lower()
                            if 'hospital' in tipo or 'clínica' in tipo:
                                categoria = "CLÍNICAS Y HOSPITALES"
                                beneficios = ["Crédito Hospitalario"]
                            else:
                                categoria = "CENTRO DE COPAGO"
                                beneficios = ["Crédito Ambulatorio"]
                            
                            ciudad_final = datos['ciudad'] or ciudad
                            registro = {
                                "provincia": obtener_provincia(ciudad_final),
                                "ciudad": ciudad_final.upper(),
                                "categoria": categoria,
                                "nombre": datos['nombre'].upper(),
                                "direccion": datos['direccion'] or "n/a",
                                "horarios": "n/a",
                                "contactos": [datos['telefono']] if datos['telefono'] else ["n/a"],
                                "pagina_web": None,
                                "beneficios": beneficios,
                            }
                            todos_registros.append(registro)
                    
                    # Buscar botón "Siguiente"
                    siguiente = await page.query_selector('a[data-args="PBN"]')
                    if not siguiente:
                        break
                    
                    # Verificar si está deshabilitado (clase disabled en el li padre)
                    is_disabled = await siguiente.evaluate('''el => {
                        const li = el.closest('li');
                        return li ? li.classList.contains('disabled') : false;
                    }''')
                    if is_disabled:
                        break
                    
                    await siguiente.click()
                    await asyncio.sleep(2.5)
                    pagina += 1
                    
            except Exception as e:
                print(f"  ⚠ Error con ciudad {ciudad}: {e}")
                continue
        
        # 4. Guardar JSON
        print(f"\n[4/5] Total registros extraídos: {len(todos_registros)}")
        
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(todos_registros, f, ensure_ascii=False, indent=2)
        print(f"✓ JSON guardado: {OUTPUT_JSON}")
        
        # 5. Crear SQLite
        print("\n[5/5] Creando base de datos SQLite...")
        import sqlite3
        conn = sqlite3.connect(OUTPUT_DB)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prestadores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provincia TEXT, ciudad TEXT, categoria TEXT,
                nombre TEXT, direccion TEXT, horarios TEXT,
                contactos TEXT, pagina_web TEXT, beneficios TEXT
            )
        ''')
        cursor.execute('DELETE FROM prestadores')
        
        for r in todos_registros:
            cursor.execute('''
                INSERT INTO prestadores (provincia, ciudad, categoria, nombre, direccion, horarios, contactos, pagina_web, beneficios)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                r['provincia'], r['ciudad'], r['categoria'], r['nombre'],
                r['direccion'], r['horarios'], json.dumps(r['contactos']),
                r['pagina_web'] or '', json.dumps(r['beneficios'])
            ))
        
        conn.commit()
        cursor.execute('SELECT COUNT(*) FROM prestadores')
        count = cursor.fetchone()[0]
        conn.close()
        print(f"✓ Base de datos creada: {OUTPUT_DB} ({count} registros)")
        
        # Resumen
        centros = [r for r in todos_registros if r['categoria'] == 'CENTRO DE COPAGO']
        hospitales = [r for r in todos_registros if r['categoria'] == 'CLÍNICAS Y HOSPITALES']
        print(f"\n📊 Resumen:")
        print(f"  - Total: {len(todos_registros)}")
        print(f"  - Centros Médicos (copago): {len(centros)}")
        print(f"  - Hospitales/Clínicas: {len(hospitales)}")
        print(f"  - Ciudades: {len(set(r['ciudad'] for r in todos_registros))}")
        print(f"  - Provincias: {len(set(r['provincia'] for r in todos_registros))}")
        
        await browser.close()
        print("\n✅ ¡Proceso completado!")


if __name__ == '__main__':
    asyncio.run(scrape_humana())
