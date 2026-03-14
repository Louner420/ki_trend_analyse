import asyncio
import json
import random
from datetime import datetime
from playwright.async_api import async_playwright

# Themen-Pool
SEARCH_TOPICS = [
    # Gastro
    "easy recipe", "food tiktok", "dinner ideas", "street food",
    # Fitness
    "gym workout", "fitness motivation", "weight loss tips", "home workout",
    # Tech
    "tech gadgets", "ai tools", "iphone tricks", "coding life",
    # Fashion
    "fashion trends 2024", "outfit ideas", "zara haul", "streetwear",
    # Business
    "business tips", "side hustle", "crypto news", "finance hacks"
]

async def get_trending_dict(count=150):
    videos_found = []
    
    # 3 Themen auswählen
    current_topics = random.sample(SEARCH_TOPICS, 3)
    
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    
    print(f"[TikTok] MULTITASKING START! Themen: {current_topics}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu", 
                "--disable-dev-shm-usage"
            ]
        )
        
        context = await browser.new_context(
            user_agent=user_agent,
            viewport={'width': 1280, 'height': 800},
            locale="de-DE",
            timezone_id="Europe/Berlin"
        )

        tasks = []
        for i, topic in enumerate(current_topics):
            # STAGGERED START: Sanftanlauf für den Raspi
            # Tab 1: sofort, Tab 2: nach 8s, Tab 3: nach 16s
            delay = i * 8 
            tasks.append(scrape_single_topic(context, topic, videos_found, start_delay=delay))
        
        # Alle Jobs starten
        await asyncio.gather(*tasks)
        
        await browser.close()

    unique_videos = list({v['video_id']: v for v in videos_found}.values())
    print(f"[TikTok] Multitasking beendet. {len(unique_videos)} Videos gesammelt.")
    return unique_videos

async def scrape_single_topic(context, topic, videos_list, start_delay=0):
    """
    Ein einzelner Worker mit Sanftanlauf.
    """
    # Hier warten wir kurz, bevor wir den Tab öffnen (CPU schonen)
    if start_delay > 0:
        await asyncio.sleep(start_delay)

    page = None
    try:
        page = await context.new_page()
        
        # Blocker für Speed
        await page.route("**/*", lambda route: route.abort() 
            if route.request.resource_type in ["image", "media", "font", "stylesheet"] 
            else route.continue_()
        )
        
        page.on("response", lambda res: handle_tiktok_response(res, videos_list))

        url = f"https://www.tiktok.com/search?q={topic.replace(' ', '%20')}"
        print(f"[Tab-Worker] Starte Suche: '{topic}' (nach {start_delay}s Pause)")
        
        # TIMEOUT ERHÖHT: 60 Sekunden Zeit geben
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(random.randint(1500, 3000))
        
        # Scrollen
        for _ in range(6):
            if not page.is_closed():
                await page.mouse.wheel(0, random.randint(800, 1500))
                await page.wait_for_timeout(random.randint(1500, 2500))
            
        await page.close()
        print(f"[Tab-Worker] '{topic}' erledigt.")
        
    except Exception as e:
        print(f"[Tab-Error] Fehler bei '{topic}': {e}")
        try: 
            if page and not page.is_closed(): await page.close()
        except: pass

def handle_tiktok_response(response, videos_list):
    if "json" in response.headers.get("content-type", ""):
        if any(x in response.url for x in ["search", "item_list", "recommend"]):
            try:
                asyncio.create_task(parse_tiktok_json(response, videos_list))
            except: pass

async def parse_tiktok_json(response, videos_list):
    try:
        data = await response.json()
        if not isinstance(data, dict): return
        
        items = data.get("data", []) or data.get("itemList", []) or data.get("item_list", [])
        if not isinstance(items, list): return
        
        for item in items:
            if "item" in item: item = item["item"]
            if not isinstance(item, dict): continue

            video_id = item.get("id") or item.get("video", {}).get("id")
            if not video_id: continue

            if any(v['video_id'] == str(video_id) for v in videos_list): continue
                
            caption = item.get("desc", "")
            stats = item.get("stats", {}) or {}
            author = item.get("author", {}) or {}
            
            hashtags = [w for w in caption.split() if w.startswith("#")]
            if "textExtra" in item and isinstance(item["textExtra"], list):
                 tags = [t.get("hashtagName") for t in item["textExtra"] if t.get("hashtagName")]
                 if tags: hashtags = tags

            video_data = {
                "video_id": str(video_id),
                "platform": "TikTok",
                "caption": caption[:300],
                "hashtags": " ".join(hashtags),
                "likes": stats.get("diggCount", 0) or 0,
                "views": stats.get("playCount", 0) or 0,
                "comments": stats.get("commentCount", 0) or 0,
                "upload_date": datetime.now().isoformat(),
                "creator": author.get("uniqueId", "unknown"),
                "region": "unknown"
            }
            
            videos_list.append(video_data)

    except: pass

if __name__ == "__main__":
    asyncio.run(get_trending_dict(100))
