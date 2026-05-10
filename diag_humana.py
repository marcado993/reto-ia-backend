import asyncio
from playwright.async_api import async_playwright

async def diag():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://red.humana.med.ec/RedHumana', wait_until='networkidle', timeout=60000)
        await page.wait_for_selector('#CardviewPrestadores', timeout=30000)
        
        # Click first city to load cards
        combo = await page.query_selector('#comboboxCiudad_I')
        if combo:
            await combo.click()
            await asyncio.sleep(1)
            opt = await page.query_selector('text="Quito"')
            if opt:
                await opt.click()
                await asyncio.sleep(3)
        
        card = await page.query_selector('[id^="CardviewPrestadores_DXDataCard"]')
        if card:
            html = await card.evaluate('el => el.outerHTML')
            text = await card.evaluate('el => el.innerText')
            print('--- INNER TEXT ---')
            print(text)
            print('\n--- OUTER HTML (first 3000 chars) ---')
            print(html[:3000])
        else:
            print('No cards found')
        
        await browser.close()

asyncio.run(diag())
