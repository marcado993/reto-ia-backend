#!/usr/bin/env python3
"""
Scraper Humana S.A. usando Playwright
Extrae prestadores de la Red de Prestadores
"""

import asyncio
from playwright.async_api import async_playwright
import json

URL = "https://red.humana.med.ec/RedHumana"

async def scrape_humana():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        print("Navegando a Humana Red de Prestadores...")
        await page.goto(URL, wait_until='networkidle', timeout=60000)
        
        # Esperar a que cargue el CardView
        await page.wait_for_selector('#CardviewPrestadores', timeout=30000)
        print("Página cargada.")
        
        # Contar tarjetas iniciales
        cards = await page.query_selector_all('[id^="CardviewPrestadores_DXDataCard"]')
        print(f"Tarjetas visibles: {len(cards)}")
        
        if cards:
            # Extraer datos de la primera tarjeta
            card = cards[0]
            texts = await card.evaluate('el => Array.from(el.querySelectorAll("*")).map(e => e.textContent.trim()).filter(t => t.length > 0)')
            print(f"\nPrimera tarjeta:\n{texts}")
            
            # Intentar hacer click en "Ver más"
            ver_mas = await card.query_selector('text=Ver más')
            if ver_mas:
                print("\nHaciendo click en 'Ver más'...")
                await ver_mas.click()
                await asyncio.sleep(2)
                
                # Buscar popup de detalle
                popup = await page.query_selector('#popupDetallePrestador')
                if popup:
                    popup_texts = await popup.evaluate('el => Array.from(el.querySelectorAll("*")).map(e => e.textContent.trim()).filter(t => t.length > 0)')
                    print(f"\nPopup detalle:\n{popup_texts}")
                else:
                    print("Popup no encontrado")
        
        await browser.close()

if __name__ == '__main__':
    asyncio.run(scrape_humana())
