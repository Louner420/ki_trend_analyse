import asyncio
from playwright.async_api import async_playwright

async def debug_insta():
    async with async_playwright() as p:
        print("Starte Browser...")
        browser = await p.chromium.launch(headless=False) # Headless False ist wichtig für Insta
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()

        # 1. Seite laden
        print("Lade Instagram...")
        await page.goto("https://www.instagram.com/reels/", timeout=60000)
        await page.wait_for_timeout(5000)

        # 2. Screenshot VOR Klick
        await page.screenshot(path="debug_1_vorher.png")
        print("Screenshot 1 gespeichert.")

        # 3. Cookies klicken
        try:
            await page.get_by_role("button", name="Decline optional cookies").click(timeout=3000)
            print("Cookie Button geklickt.")
            await page.wait_for_timeout(3000)
        except:
            print("Kein Cookie Button gefunden.")

        # 4. Screenshot NACH Klick
        await page.screenshot(path="debug_2_nachher.png")
        print("Screenshot 2 gespeichert.")

        # 5. Versuch zu Scrollen
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(3000)
        
        # 6. Screenshot NACH Scrollen
        await page.screenshot(path="debug_3_scrolling.png")
        print("Screenshot 3 gespeichert.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_insta())
