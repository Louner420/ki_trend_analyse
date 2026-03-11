import concurrent.futures
import json
import os
import re
import sqlite3
from datetime import datetime, timezone

import pandas as pd
import requests

try:
    from main import NICHES
except Exception:
    NICHES = {
        "gastro": ["food", "essen", "recipe", "kochen", "cooking", "lecker", "delicious", "meal", "dinner", "lunch", "frühstück", "pizza", "burger", "pasta", "kitchen"],
        "fitness": ["fitness", "gym", "workout", "sport", "training", "muscle", "run", "yoga", "health", "abnehmen", "diet", "bodybuilding", "exercise"],
        "tech": ["tech", "ai", "gadget", "iphone", "android", "software", "code", "programming", "robot", "computer", "laptop", "innovation", "crypto", "bitcoin"],
        "fashion": ["fashion", "style", "outfit", "ootd", "clothes", "wear", "dress", "shoes", "sneaker", "gucci", "zara", "model", "beauty", "makeup"],
        "business": ["business", "money", "finance", "invest", "stock", "aktien", "crypto", "marketing", "job", "career", "rich", "wealth", "startup", "entrepreneur"],
    }


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)


def resolve_db_path(filename):
    if os.path.basename(BASE_DIR) == "ai":
        candidates = [
            os.path.join(PROJECT_ROOT, "database", filename),
            os.path.join(BASE_DIR, "data", filename),
            os.path.join(BASE_DIR, filename),
        ]
    else:
        candidates = [
            os.path.join(BASE_DIR, "data", filename),
            os.path.join(PROJECT_ROOT, "database", filename),
            os.path.join(BASE_DIR, filename),
        ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


RAW_DB_PATH = resolve_db_path("raw_tiktok.db")
USERS_DB_PATH = resolve_db_path("users.db")
OUTPUT_DIR = os.path.dirname(RAW_DB_PATH)

API_KEY = os.getenv("LLM_API_KEY", "")
API_URL = os.getenv("LLM_API_URL", "http://10.10.11.11:8080/api/chat/completions")
MODEL_NAME = os.getenv("LLM_MODEL_NAME", "llama3:latest")
MAX_WORKERS = int(os.getenv("CONTENT_AGENT_MAX_WORKERS", "4"))
MAX_IDEAS_PER_USER = int(os.getenv("CONTENT_AGENT_MAX_IDEAS", "5"))
MAX_RAW_ROWS = int(os.getenv("CONTENT_AGENT_MAX_RAW_ROWS", "800"))


def compute_sentiment_fallback(caption):
    if not isinstance(caption, str):
        return 50
    positive = ["wow", "mega", "love", "best", "viral", "crazy", "amazing", "top"]
    negative = ["bad", "fail", "boring", "hate", "worst"]
    text = caption.lower()
    score = 50
    score += 8 * sum(word in text for word in positive)
    score -= 8 * sum(word in text for word in negative)
    return max(0, min(100, score))


def generate_personalized_guide(trend_caption, user_profile):
    user_id = user_profile.get("user_id", "Unbekannt")
    print(f"🤖 [Thread] Sende personalisierte Anfrage für User {user_id}...")

    brand_context = f"Branche: {user_profile.get('industry', 'Unbekannt')}. {user_profile.get('audience_description', '')}"
    product = user_profile.get("product_description", "Kein Produkt angegeben")
    usp = user_profile.get("unique_value", "Kein spezifischer USP")
    audience = f"{user_profile.get('target_audience_type', '')} ({user_profile.get('target_age_group', '')})"
    brand_tone = user_profile.get("brand_tone", "Neutral")
    no_gos = user_profile.get("no_go_topics", "Keine")

    prompt = f"""Du bist ein Experte fuer virale Social-Media Videos (Instagram Reels / TikTok).
Deine Aufgabe ist es, eine kreative Videoidee zu entwickeln, die sowohl zum aktuellen Trend als auch zur Marke passt.
Die Idee muss realistisch filmbar sein und eine hohe Chance auf Engagement haben.

--------------------------------
KONTEXT ZUR MARKE
--------------------------------
Brand Beschreibung / Kontext: {brand_context}
Produkt / Angebot: {product}
USP (Alleinstellungsmerkmal): {usp}
Zielgruppe: {audience}
Brand Tone: {brand_tone}
No-Gos: {no_gos}

--------------------------------
TREND KONTEXT
--------------------------------
Aktueller Trend: {trend_caption}

--------------------------------
AUFGABE
--------------------------------
Analysiere zuerst den Trend, die Marke und die Zielgruppe.
Entscheide danach selbst, welches Format am besten funktioniert (z.B. POV, Talking Head, Meme / Comedy, Behind the Scenes, Trend Remix, Storytelling, Reaction).

--------------------------------
WICHTIGE REGELN (Zwingend einhalten!)
--------------------------------
1. ANTWORTE AUSSCHLIESSLICH AUF DEUTSCH.
2. ADAPTION: Wenn der urspruengliche Trend inhaltlich nicht perfekt zur Firma passt, nutze nur die Mechanik des Trends und mue nze sie kreativ auf das Produkt um.
3. BERECHNUNG: Bewerte das Sentiment des rohen TikTok-Trends auf einer Skala von 0 bis 100.
4. MARKEN-TREUE: Die Idee muss authentisch wirken, in 15-30 Sekunden umsetzbar sein und darf niemals gegen die No-Gos verstossen.
5. SKRIPT-REGEL: Wenn du als Videoformat Talking Head waehlst, schreibe unter Drehablauf ein fertiges Skript.

--------------------------------
AUSGABEFORMAT
--------------------------------
Titel:
(Kurzer Titel der Videoidee - keine Hashtags)

Sentiment:
(Zahl zwischen 0 und 100)

Videoformat:
(Dein gewaehltes Format)

Hook:
(Die ersten 1-2 Sekunden des Videos)

Idee:
(Kurz erklaeren, worum es im Video geht)

Drehablauf:
(Schritt-fuer-Schritt Ablauf des Videos)

CTA:
(Call-to-Action am Ende des Videos)
"""

    if not API_KEY:
        sentiment_val = compute_sentiment_fallback(trend_caption)
        title = "Trend-Idee fuer deine Marke"
        guide = (
            "Videoformat: Trend-Remix\n"
            f"Hook: Starte mit dem staerksten Moment aus dem Trend und leite sofort auf {product} ueber.\n"
            "Idee: Nutze die Mechanik des Trends und passe sie glaubwuerdig an die Marke an.\n"
            "Drehablauf: Zeige zuerst den Hook, dann den Produktbezug, danach den konkreten Nutzen fuer die Zielgruppe.\n"
            "CTA: Fordere die Zuschauer zu einer klaren naechsten Aktion auf."
        )
        return title, sentiment_val, guide

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "Du haeltst dich strikt an das vorgegebene Ausgabeformat."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }

    title, sentiment_val, guide = (
        "KI-Titel ausstehend",
        compute_sentiment_fallback(trend_caption),
        "Leitfaden konnte nicht generiert werden.",
    )
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=300)
        response.raise_for_status()
        raw_text = response.json()["choices"][0]["message"]["content"].strip()

        title_match = re.search(r"Titel:\s*(.*?)\n", raw_text, re.IGNORECASE)
        sentiment_match = re.search(r"Sentiment:\s*(\d+)", raw_text, re.IGNORECASE)
        guide_match = re.search(r"(Videoformat:.*)", raw_text, re.IGNORECASE | re.DOTALL)

        if title_match:
            title = title_match.group(1).replace("**", "").strip()
        if sentiment_match:
            sentiment_val = int(sentiment_match.group(1))
        if guide_match:
            guide = guide_match.group(1).strip()
    except Exception as exc:
        guide = f"Fehler bei der Generierung: {exc}"

    return title, sentiment_val, guide


def load_raw_videos():
    if not os.path.exists(RAW_DB_PATH):
        print(f"❌ Fehler: raw_tiktok.db nicht gefunden unter {RAW_DB_PATH}")
        return pd.DataFrame()

    conn = sqlite3.connect(RAW_DB_PATH)
    try:
        df = pd.read_sql_query("SELECT * FROM videos", conn)
    except Exception as exc:
        print(f"❌ Fehler beim Lesen von raw_tiktok.db/videos: {exc}")
        df = pd.DataFrame()
    finally:
        conn.close()

    return df


def ensure_video_columns(df):
    if df.empty:
        return df

    df = df.copy()
    for column in ["caption", "hashtags", "creator", "video_id"]:
        if column not in df.columns:
            df[column] = ""

    for column in ["views", "likes", "comments", "shares"]:
        if column not in df.columns:
            df[column] = 0
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    if "upload_date" not in df.columns:
        df["upload_date"] = pd.Timestamp.now(tz=timezone.utc).isoformat()

    upload_ts = pd.to_datetime(df["upload_date"], errors="coerce", utc=True)
    now = pd.Timestamp.now(tz=timezone.utc)
    age_hours = ((now - upload_ts).dt.total_seconds() / 3600).clip(lower=0.1)
    age_hours = age_hours.fillna(24)

    views = df["views"].astype(float)
    likes = df["likes"].astype(float)
    comments = df["comments"].astype(float)
    shares = df["shares"].astype(float)

    df["avg_velocity"] = (views / age_hours).fillna(0)
    df["avg_engagement"] = (((likes + comments + shares) / views.replace(0, pd.NA)) * 100).fillna(0)
    raw_score = (views * 0.45) + (df["avg_velocity"] * 0.35) + ((likes + comments + shares) * 0.20)
    max_score = float(raw_score.max()) if not raw_score.empty else 0.0
    df["trend_score"] = (raw_score / max_score * 100) if max_score > 0 else 0
    df["trend_score"] = df["trend_score"].fillna(0).round(2)
    df["avg_velocity"] = df["avg_velocity"].round(2)
    df["avg_engagement"] = df["avg_engagement"].round(2)
    df["video_id"] = df["video_id"].astype(str)
    df["upload_date"] = upload_ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ").fillna("")

    if len(df) > MAX_RAW_ROWS:
        df = df.sort_values(by=["trend_score", "avg_velocity"], ascending=False).head(MAX_RAW_ROWS)

    return df


def filter_videos_by_niche(df, niche_key):
    if df.empty or niche_key == "general":
        return df.copy()

    keywords = NICHES.get(niche_key, [])
    if not keywords:
        return df.copy()

    search_text = (df["caption"].fillna("") + " " + df["hashtags"].fillna("")).str.lower()
    pattern = "|".join(keyword.lower() for keyword in keywords)
    filtered = df[search_text.str.contains(pattern, na=False, regex=True)].copy()
    return filtered if not filtered.empty else df.copy()


def select_ranked_videos(raw_df, industry):
    ranked = filter_videos_by_niche(raw_df, industry)
    ranked = ranked.sort_values(by=["trend_score", "avg_velocity", "avg_engagement"], ascending=False).reset_index(drop=True)
    ranked["rank"] = ranked.index + 1
    return ranked


def ensure_history_table(conn_users):
    conn_users.execute(
        """
        CREATE TABLE IF NOT EXISTS user_idea_history (
            user_id TEXT,
            video_id TEXT,
            generated_date TEXT,
            UNIQUE(user_id, video_id)
        )
        """
    )
    conn_users.commit()


def load_users(conn_users):
    return pd.read_sql_query("SELECT * FROM user_onboarding_profile", conn_users)


def to_records(df, limit=None):
    if df.empty:
        return []

    columns = [
        "rank",
        "video_id",
        "caption",
        "hashtags",
        "creator",
        "views",
        "likes",
        "comments",
        "shares",
        "upload_date",
        "trend_score",
        "avg_velocity",
        "avg_engagement",
    ]
    available = [column for column in columns if column in df.columns]
    records_df = df[available]
    if limit is not None:
        records_df = records_df.head(limit)
    return records_df.to_dict(orient="records")


def run_agent():
    print("[Content-Agent] Starte personalisierte KI-Pipeline auf Basis von raw_tiktok.db/videos...")
    if not os.path.exists(USERS_DB_PATH):
        print(f"❌ Fehler: users.db nicht gefunden unter {USERS_DB_PATH}")
        return

    raw_df = ensure_video_columns(load_raw_videos())
    if raw_df.empty:
        return

    conn_users = sqlite3.connect(USERS_DB_PATH)
    ensure_history_table(conn_users)

    try:
        users_df = load_users(conn_users)
    except Exception as exc:
        print(f"❌ Fehler beim Lesen der Onboarding-Daten: {exc}")
        conn_users.close()
        return

    global_ranked = select_ranked_videos(raw_df, "general")

    for _, user in users_df.iterrows():
        user_id = str(user.get("user_id", "")).strip()
        if not user_id:
            continue

        industry_raw = str(user.get("industry", "general") or "general")
        industry = industry_raw.lower().strip()
        ranked_df = select_ranked_videos(raw_df, industry)

        history_df = pd.read_sql_query(
            "SELECT video_id FROM user_idea_history WHERE user_id = ?",
            conn_users,
            params=(user_id,),
        )
        known_video_ids = history_df["video_id"].astype(str).tolist() if not history_df.empty else []

        new_videos_df = ranked_df[~ranked_df["video_id"].isin(known_video_ids)].head(MAX_IDEAS_PER_USER).copy()
        if new_videos_df.empty:
            print(f"ℹ️ User {user_id} hat bereits alle aktuellen Trends gesehen. Keine neuen Ideen generiert.")
            continue

        print(f"\n🚀 Verarbeite {len(new_videos_df)} neue Trends fuer User {user_id} (Brand: {industry_raw})...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            results = list(executor.map(lambda caption: generate_personalized_guide(caption, user.to_dict()), new_videos_df["caption"]))

        new_videos_df["ai_title"] = [result[0] for result in results]
        new_videos_df["ai_sentiment"] = [result[1] for result in results]
        new_videos_df["ai_guide"] = [result[2] for result in results]

        today = datetime.now().strftime("%Y-%m-%d")
        for video_id in new_videos_df["video_id"]:
            conn_users.execute(
                "INSERT OR IGNORE INTO user_idea_history (user_id, video_id, generated_date) VALUES (?, ?, ?)",
                (user_id, str(video_id), today),
            )
        conn_users.commit()

        user_data = {
            "ai_video_ideas": new_videos_df.to_dict(orient="records"),
            "top_trends": to_records(ranked_df, limit=10),
            "rising_trends": to_records(ranked_df.sort_values(by="avg_velocity", ascending=False), limit=10),
            "opportunities": to_records(ranked_df.sort_values(by="avg_engagement", ascending=False), limit=10),
            "global_trends": to_records(global_ranked, limit=10),
        }

        json_path = os.path.join(OUTPUT_DIR, f"trends_user_{user_id}.json")
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(user_data, handle, ensure_ascii=False, indent=4)

    conn_users.close()
    print("\n🏁 Alle personalisierten Leitfaeden fuer alle User erfolgreich generiert!")


if __name__ == "__main__":
    run_agent()