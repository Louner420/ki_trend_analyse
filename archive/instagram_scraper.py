import asyncio
import random
from datetime import datetime
from playwright.async_api import async_playwright

async def get_instagram_feed(count=30, hashtag=None):
    """
    Holt Instagram Reels via Mobile Browser Emulation (iPhone).
    Umgeht oft API-Sperren.
    """
    # Wir zielen auf Profile, die garantiert Reels haben.
    # Das ist stabiler als Hashtags.
    TARGETS = ["pubity", "memezar", "9gag", "wealth"]
    target = random.choice(TARGETS)
    
    found_posts = []
    print(f"[Insta-Mobile] Starte iPhone-Simulation für @{target}...")

    async with async_playwright() as p:
        # Wir laden ein vorgefertigtes iPhone 13 Profil
        iphone = p.devices['iPhone 13']
        
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        context = await browser.new_context(
            **iphone, # Hier wird die komplette Handy-Tarnung geladen
            locale='de-DE',
            timezone_id='Europe/Berlin'
        )
        
        page = await context.new_page()

        # Turbo-Modus: Bilder weg
        await page.route("**/*", lambda route: route.abort() 
            if route.request.resource_type in ["image", "font", "stylesheet"] 
            else route.continue_()
        )
        
        # Listener für Netzwerk-Traffic (JSON abfangen)
        page.on("response", lambda res: handle_response(res, found_posts))

        try:
            # Wir gehen direkt auf den Reels-Tab des Profils
            url = f"https://www.instagram.com/{target}/reels/"
            print(f"[Insta-Mobile] Lade {url}")
            
            await page.goto(url, timeout=60000)
            await page.wait_for_timeout(random.randint(3000, 5000))

            # Cookie Banner wegklicken (Mobile Version)
            try:
                await page.click('button:has-text("Decline")', timeout=2000)
            except: 
                try: await page.click('button:has-text("Ablehnen")', timeout=2000)
                except: pass

            # Scroll Loop
            for i in range(10):
                if len(found_posts) >= count: break
                
                # Wischen statt Scrollen (Touch Simulation)
                await page.mouse.wheel(0, random.randint(300, 600))
                await page.wait_for_timeout(random.randint(2000, 4000))
                print(f"[Insta-Mobile] Wische... ({len(found_posts)} Posts)")

        except Exception as e:
            print(f"[Insta-Error] {e}")

        await browser.close()

    # Daten normalisieren
    return {
        "platform": "Instagram",
        "fetched_at": datetime.now().isoformat(),
        "count": len(found_posts),
        "data": found_posts
    }

def handle_response(response, found_posts):
    """Sucht nach Reels in den Hintergrund-Daten"""
    try:
        # Instagram Mobile nutzt oft GraphQL im Hintergrund
        if "graphql" in response.url or "api/v1" in response.url:
             # Da wir async sind, starten wir den Parser als Task
             asyncio.create_task(parse_mobile_json(response, found_posts))
    except: pass

async def parse_mobile_json(response, found_posts):
    try:
        data = await response.json()
        
        # Rekursive Suche nach Items, da die Struktur oft wechselt
        items = extract_items_recursive(data)
        
        for item in items:
            # Prüfen ob Video
            if not item.get("is_video") and not item.get("video_duration"):
                continue

            # ID finden
            vid_id = item.get("id") or item.get("pk") or item.get("shortcode")
            if not vid_id: continue
            
            # Duplikate check
            if any(p['video_id'] == str(vid_id) for p in found_posts): continue

            # Caption finden
            caption = ""
            if "edge_media_to_caption" in item:
                edges = item["edge_media_to_caption"].get("edges", [])
                if edges: caption = edges[0]["node"]["text"]
            elif "caption" in item:
                if isinstance(item["caption"], dict): caption = item["caption"].get("text", "")
                else: caption = str(item["caption"])

            post_data = {
                "video_id": str(vid_id),
                "platform": "Instagram",
                "caption": caption[:200],
                "hashtags": " ".join([w for w in caption.split() if w.startswith("#")]),
                "sound_name": "Original Audio",
                "likes": item.get("like_count") or item.get("edge_liked_by", {}).get("count") or 0,
                "views": item.get("view_count") or item.get("video_view_count") or item.get("play_count") or 0,
                "comments": item.get("comment_count") or item.get("edge_media_to_comment", {}).get("count") or 0,
                "upload_date": datetime.now().isoformat(),
                "creator": "unknown", # Bei Mobile API oft schwer zu finden, egal
                "region": "unknown"
            }
            
            found_posts.append(post_data)
            print(f"[Insta-Mobile] Treffer: {caption[:20]}...")
            
    except: pass

def extract_items_recursive(data):
    """Hilfsfunktion zum Durchsuchen von verschachtelten JSONs"""
    items = []
    if isinstance(data, dict):
        if "edges" in data and isinstance(data["edges"], list):
            for e in data["edges"]: 
                if "node" in e: items.append(e["node"])
        if "items" in data and isinstance(data["items"], list):
            items.extend(data["items"])
        for v in data.values():
            if isinstance(v, (dict, list)): items.extend(extract_items_recursive(v))
    elif isinstance(data, list):
        for i in data: items.extend(extract_items_recursive(i))
    return items

if __name__ == "__main__":
    print(asyncio.run(get_instagram_feed(5)))
