"""
tiktok_trending_dict_auto_token.py

Features:
- Holt ms_token automatisch via Playwright (Cookie 'msToken' von tiktok.com), speichert in .env
- Windows/IANA-Zeitzonen-Fix (tzdata + Fallback auf UTC)
- Region-Heuristik aus Caption/Hashtags/Account/Bio-Link/Flags/Sprache
- Gibt ein Dictionary mit den gewünschten Feldern aus

Ausgabe-Struktur:
{
  "platform": "TikTok",
  "fetched_at": "...ISO 8601...",
  "count": <int>,
  "data": [
    {
      "video_id", "platform", "caption", "hashtags", "sound_name",
      "likes", "views", "shares", "comments", "upload_date",
      "category", "creator", "region", "trend_score"
    }, ...
  ]
}
"""

import os
import re
import json
import asyncio
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

# ---------------- .env Handling ----------------
ENV_PATH = Path(__file__).with_name(".env")

def load_env():
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        os.environ.setdefault(k, v)

def set_env(k: str, v: str):
    lines, found = [], False
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{k}="):
                lines.append(f'{k}="{v}"')
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f'{k}="{v}"')
    ENV_PATH.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    os.environ[k] = v

# ------------- Dependencies sicherstellen -------------
def ensure_pkg(pkg: str):
    import importlib
    try:
        importlib.import_module(pkg)
    except ModuleNotFoundError:
        print(f"[setup] Installiere {pkg} …")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

def ensure_deps():
    ensure_pkg("TikTokApi")
    try:
        import playwright  # noqa: F401
    except ModuleNotFoundError:
        ensure_pkg("playwright")
    ensure_pkg("tzdata")       # IANA-Zeitzonen unter Windows
    ensure_pkg("langdetect")   # Sprache erkennen (Region-Heuristik)
    print("[setup] Stelle sicher, dass Playwright Chromium installiert ist …")
    subprocess.call([sys.executable, "-m", "playwright", "install", "chromium"])

# ------------- Zeitzone: robuster Vienna-Fallback -------------
def vienna_tz():
    try:
        return ZoneInfo("Europe/Vienna")
    except Exception:
        try:
            import tzdata  # noqa: F401
            return ZoneInfo("Europe/Vienna")
        except Exception:
            return ZoneInfo("UTC")

# ------------- ms_token automatisch holen -------------
async def fetch_ms_token_via_playwright(headless: bool = True, wait_seconds: int = 20) -> str | None:
    try:
        from playwright.async_api import async_playwright
    except Exception as e:
        print(f"[warn] Playwright async API nicht verfügbar: {e}")
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=os.getenv("TIKTOK_UA", None),
        )
        page = await context.new_page()
        await page.goto("https://www.tiktok.com/explore", wait_until="domcontentloaded")

        token = None
        for _ in range(max(1, wait_seconds * 2)):
            cookies = await context.cookies()
            for c in cookies:
                if c.get("name") == "msToken" and c.get("value"):
                    token = c["value"]
                    break
            if token and len(token) > 10:
                break
            await asyncio.sleep(0.5)

        await browser.close()
        return token

async def ensure_ms_token() -> str:
    existing = os.environ.get("ms_token")
    if existing and len(existing) > 10:
        return existing

    print("[info] Kein gültiger ms_token gefunden – versuche automatische Ermittlung (headless)…")
    token = await fetch_ms_token_via_playwright(headless=True, wait_seconds=20)

    if not token:
        print("[info] Headless hat keinen Token geliefert – starte sichtbaren Browser. "
              "Falls eine Challenge erscheint, kurz bestätigen/scrollen. Warte bis zu 120s …")
        token = await fetch_ms_token_via_playwright(headless=False, wait_seconds=120)

    if not token or len(token) <= 10:
        manual = input("[warn] Automatisch kein ms_token erhalten. Manuell einfügen oder leer lassen:\n> ").strip()
        if len(manual) <= 10:
            raise RuntimeError("Kein ms_token verfügbar. Erneut versuchen oder später nochmal starten.")
        token = manual

    set_env("ms_token", token)
    print(f"[ok] ms_token gespeichert in {ENV_PATH.name}.")
    return token

# ----------------- Region-Heuristik -----------------
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0  # deterministisch

COUNTRY_BY_ISO = {
    "AT": "Austria", "DE": "Germany", "CH": "Switzerland",
    "TR": "Türkiye", "IT": "Italy", "FR": "France", "ES": "Spain",
    "US": "United States", "GB": "United Kingdom", "NL": "Netherlands",
}

CITY_TO_COUNTRY = {
    "wien": "Austria", "vienna": "Austria", "innsbruck": "Austria", "salzburg": "Austria", "tirol": "Austria",
    "berlin": "Germany", "münchen": "Germany", "munich": "Germany", "hamburg": "Germany", "köln": "Germany", "cologne": "Germany",
    "zürich": "Switzerland", "zurich": "Switzerland", "bern": "Switzerland", "basel": "Switzerland",
    "istanbul": "Türkiye", "ankara": "Türkiye",
    "roma": "Italy", "rome": "Italy", "milano": "Italy", "venezia": "Italy", "venice": "Italy",
}

HASHTAG_TO_COUNTRY = {
    "österreich": "Austria", "austria": "Austria", "wien": "Austria", "vienna": "Austria",
    "deutschland": "Germany", "germany": "Germany", "berlin": "Germany", "münchen": "Germany", "munich": "Germany",
    "schweiz": "Switzerland", "switzerland": "Switzerland", "zürich": "Switzerland", "zurich": "Switzerland",
    "türkiye": "Türkiye", "turkey": "Türkiye", "istanbul": "Türkiye",
    "italia": "Italy", "italy": "Italy", "roma": "Italy", "milano": "Italy", "venezia": "Italy",
}

AUTHOR_HINT_TO_COUNTRY = {
    "_at": "Austria", "at_": "Austria", ".at": "Austria",
    "_de": "Germany", "de_": "Germany", ".de": "Germany",
    "_ch": "Switzerland", "ch_": "Switzerland", ".ch": "Switzerland",
    "_tr": "Türkiye", "tr_": "Türkiye", ".tr": "Türkiye",
    "_it": "Italy",   "it_": "Italy",   ".it": "Italy",
}

FLAG_RE = re.compile(r'[\U0001F1E6-\U0001F1FF]{2}')
URL_RE  = re.compile(r'https?://([A-Za-z0-9\.-]+)/?')
HASHTAG_RE = re.compile(r"#([\w\d_]+)", re.UNICODE)

def flag_to_iso(flag: str) -> str | None:
    if len(flag) != 2:
        return None
    base = 0x1F1E6
    return ''.join(chr(ord(ch) - base + ord('A')) for ch in flag)

def extract_flag_countries(text: str) -> list[str]:
    countries = []
    for m in FLAG_RE.findall(text or ""):
        iso = flag_to_iso(m)
        if iso and iso in COUNTRY_BY_ISO:
            countries.append(COUNTRY_BY_ISO[iso])
    return countries

def tld_country(url: str) -> str | None:
    if not url:
        return None
    m = URL_RE.search(url)
    if not m:
        return None
    host = m.group(1).lower()
    for suf, ctry in [(".at","Austria"),(".de","Germany"),(".ch","Switzerland"),
                      (".tr","Türkiye"),(".it","Italy"),(".fr","France"),
                      (".es","Spain"),(".nl","Netherlands"),(".co.uk","United Kingdom")]:
        if host.endswith(suf):
            return ctry
    return None

def score_add(scores: dict, key: str, w: float):
    scores[key] = scores.get(key, 0.0) + w

def infer_region(v: dict) -> str | None:
    """Gibt best-guess Country zurück (oder None)."""
    direct = (v.get("region")
              or (v.get("author") or {}).get("region")
              or (v.get("author") or {}).get("country"))
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    scores: dict[str,float] = {}
    def mark(ctry: str, w: float): score_add(scores, ctry, w)

    caption = (v.get("desc") or "").lower()
    author  = v.get("author") or {}
    unique  = (author.get("uniqueId") or "").lower()
    nick    = (author.get("nickname") or "").lower()
    sig     = (author.get("signature") or "").lower()
    bio_link = None
    try:
        bio_link = ((author.get("bioLink") or {}).get("link")) or None
    except Exception:
        bio_link = None

    # Flags
    for ctry in extract_flag_countries(caption + " " + nick + " " + sig):
        mark(ctry, 0.85)

    # Hashtags/Keywords/Städte
    for tag, ctry in HASHTAG_TO_COUNTRY.items():
        if f"#{tag}" in caption or tag in caption.split():
            mark(ctry, 0.70)
    for city, ctry in CITY_TO_COUNTRY.items():
        if city in caption or city in nick or city in sig:
            mark(ctry, 0.75)

    # Account-Hints
    for hint, ctry in AUTHOR_HINT_TO_COUNTRY.items():
        if hint in unique or hint in nick:
            mark(ctry, 0.55)

    # Bio-Link TLD
    c_from_tld = tld_country(bio_link) if bio_link else None
    if c_from_tld:
        mark(c_from_tld, 0.80)

    # Sprache
    try:
        lang = detect((v.get("desc") or "")[:4000])
        if lang == "de":
            for ctry in ["Germany","Austria","Switzerland"]:
                mark(ctry, 0.25)
        elif lang == "tr":
            mark("Türkiye", 0.40)
        elif lang == "it":
            mark("Italy", 0.40)
        elif lang in ("fr","es","nl","en"):
            map_lang = {"fr":"France","es":"Spain","nl":"Netherlands","en":"United Kingdom"}
            mark(map_lang[lang], 0.25)
    except Exception:
        pass

    if not scores:
        return None
    return max(scores.items(), key=lambda kv: kv[1])[0]

# ----------------- Utils & Score -----------------
def get_nested(d, path, default=None):
    cur = d
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur

def extract_hashtags(vdict: dict) -> list[str]:
    tags = []
    for item in get_nested(vdict, ["textExtra"], []) or []:
        name = item.get("hashtagName")
        if name:
            tags.append(name.strip())
    if not tags:
        caption = vdict.get("desc") or ""
        tags = HASHTAG_RE.findall(caption)
    return sorted({t.strip() for t in tags if t})

def compute_trend_score(likes: int, shares: int, views: int) -> float | None:
    if not views or views <= 0:
        return None
    return round((likes + shares) / views, 6)

def to_vienna_iso(ts_seconds: int | str | None) -> str | None:
    if ts_seconds is None:
        return None
    try:
        ts = int(ts_seconds)
        dt = datetime.fromtimestamp(ts, tz=vienna_tz())
        return dt.isoformat()
    except Exception:
        return None

# ----------------- Normalisierung → gewünschtes Schema -----------------
def normalize(v: dict) -> dict:
    video_id   = v.get("id") or v.get("video_id")
    caption    = v.get("desc") or ""
    hashtags   = extract_hashtags(v)
    music_title = get_nested(v, ["music", "title"]) or ""
    sound_name  = music_title or (get_nested(v, ["music", "authorName"]) or "")
    likes      = int(get_nested(v, ["stats", "diggCount"], 0) or 0)
    views      = int(get_nested(v, ["stats", "playCount"], 0) or 0)
    shares     = int(get_nested(v, ["stats", "shareCount"], 0) or 0)
    comments   = int(get_nested(v, ["stats", "commentCount"], 0) or 0)
    upload_iso = to_vienna_iso(v.get("createTime"))
    creator    = get_nested(v, ["author", "uniqueId"]) or get_nested(v, ["author", "nickname"]) or None

    # Region via Heuristik
    country = infer_region(v)

    # Kategorie: wird später von eurer KI gesetzt
    category = None

    return {
        "video_id": video_id,
        "platform": "TikTok",
        "caption": caption,
        "hashtags": ", ".join(hashtags) if hashtags else "",
        "sound_name": sound_name,
        "likes": likes,
        "views": views,
        "shares": shares,
        "comments": comments,
        "upload_date": upload_iso,
        "category": category,          # <- wird später von ML gefüllt
        "creator": creator,
        "region": country,
        "trend_score": compute_trend_score(likes, shares, views),
    }

# ----------------- Main: Dictionary ausgeben -----------------
async def get_trending_dict(count: int = 20) -> dict:
    from TikTokApi import TikTokApi

    ms_token = await ensure_ms_token()
    browser_choice = os.getenv("TIKTOK_BROWSER", "chromium")

    items = []
    async with TikTokApi() as api:
        await api.create_sessions(
            ms_tokens=[ms_token],
            num_sessions=1,
            sleep_after=3,
            browser=browser_choice
        )
        async for video in api.trending.videos(count=count):
            items.append(normalize(video.as_dict))

    return {
        "platform": "TikTok",
        "fetched_at": datetime.now(vienna_tz()).isoformat(),
        "count": len(items),
        "data": items,
    }

def main():
    load_env()
    ensure_deps()
    try:
        result = asyncio.run(get_trending_dict(count=20))
        # Nur noch „schönes“ JSON ausgeben – kein rohes Python-Dict mehr
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        print("\n[info] Abgebrochen.")
    except Exception as e:
        print(f"[error] {e}")
        print("Hinweise:")
        print("- Bei 429/403: kurz warten, Script neu starten (Token wird automatisch aktualisiert).")
        print("- Wenn eine TikTok-Challenge erscheint: Beim nächsten Lauf öffnet sich ein sichtbarer Browser.")
        sys.exit(1)

if __name__ == "__main__":
    main()