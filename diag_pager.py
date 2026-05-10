import asyncio
from playwright.async_api import async_playwright

async def diag():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://red.humana.med.ec/RedHumana', wait_until='networkidle', timeout=60000)
        await page.wait_for_selector('#CardviewPrestadores', timeout=30000)
        
        # Click a city with many results
        combo = await page.query_selector('#comboboxCiudad_I')
        if combo:
            await combo.click()
            await asyncio.sleep(1)
            opt = await page.query_selector('text="Quito"')
            if opt:
                await opt.click()
                await asyncio.sleep(3)
        
        pager = await page.query_selector('#CardviewPrestadores_DXPagerBottom')
        if pager:
            html = await pager.evaluate('el => el.outerHTML')
            text = await pager.evaluate('el => el.innerText')
            print('--- PAGER INNER TEXT ---')
            print(text)
            print('\n--- PAGER HTML ---')
            print(html)
        else:
            print('No pager found')
        
        await browser.close()

asyncio.run(diag())
