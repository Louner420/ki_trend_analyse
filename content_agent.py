"""
Content Agent – Generiert pro User eine JSON-Datei mit:
  * echten Trend-Clustern  (top_trends, rising_trends, opportunities, global_trends)
  * personalisierten AI-Video-Ideen (ai_video_ideas)

Trends = Gruppen aehnlicher Videos (nach Hashtag-Thema geclustert),
NICHT einzelne Video-Captions.
"""

import concurrent.futures
import glob
import json
import math
import os
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone

import pandas as pd

try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from main import NICHES
except Exception:
    NICHES = {
        "gastro": ["food", "essen", "recipe", "kochen", "cooking", "lecker",
                    "meal", "dinner", "lunch", "pizza", "burger", "pasta", "kitchen",
                    "streetfood", "foodtok", "restaurant", "chef"],
        "fitness": ["fitness", "gym", "workout", "sport", "training", "muscle",
                     "yoga", "health", "abnehmen", "diet", "bodybuilding"],
        "tech": ["tech", "ai", "gadget", "iphone", "android", "software",
                  "code", "programming", "computer", "laptop", "crypto"],
        "fashion": ["fashion", "style", "outfit", "ootd", "clothes", "dress",
                     "shoes", "sneaker", "model", "beauty", "makeup"],
        "business": ["business", "money", "finance", "invest", "stock",
                      "marketing", "career", "startup", "entrepreneur"],
    }

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

GENERIC_TAGS = frozenset({
    "fyp", "foryou", "viral", "trending", "xyzbca", "foryoupage", "foryour",
    "tiktok", "explore", "fypage", "toryou", "creatorsearchinsights",
    "1millionviews", "backtoschool",
})

# Hashtag -> sauberer deutscher Trend-Label-Teil
LABEL_MAP = {
    "food": "Food", "foodtok": "Food", "essen": "Essen",
    "recipe": "Rezepte", "recipes": "Rezepte", "cooking": "Kochen",
    "kochen": "Kochen", "dinner": "Dinner Ideen", "dinnerideas": "Dinner Ideen",
    "streetfood": "Street Food", "indianstreetfood": "Street Food Indien",
    "asmr": "ASMR", "mukbang": "Mukbang",
    "chicken": "Haehnchen", "beef": "Rindfleisch", "tacos": "Tacos",
    "pasta": "Pasta", "pizza": "Pizza", "burger": "Burger",
    "fitness": "Fitness", "gym": "Gym", "workout": "Workout",
    "tech": "Tech", "ai": "AI", "gadget": "Gadgets",
    "fashion": "Fashion", "style": "Style", "outfit": "Outfit",
    "beauty": "Beauty", "makeup": "Make-up",
    "business": "Business", "marketing": "Marketing",
    "eating": "Eating", "lecker": "Lecker",
    "baking": "Backen", "dessert": "Dessert",
    "healthy": "Healthy", "vegan": "Vegan",
    "restaurant": "Restaurant", "chef": "Chef",
    "nachos": "Nachos", "ramen": "Ramen", "sushi": "Sushi",
    "foodreview": "Food Review", "easyrecipe": "Einfache Rezepte",
    "easymeal": "Schnelle Gerichte", "dinnertime": "Dinner",
    "tiktokfood": "TikTok Food", "cookingtiktok": "Koch-Content",
}


def _sanitize_user_input(text, max_len=200):
    """Bereinigt User-Input bevor er in LLM-Prompts eingefuegt wird."""
    if not text or not isinstance(text, str):
        return ""
    # Entferne typische Prompt-Injection-Muster
    text = re.sub(r"(?i)(ignore|vergiss|forget|disregard)\s+(all|alle|previous|vorherige|above)", "", text)
    text = re.sub(r"(?i)(new|neue)\s+(instruction|anweisung|role|rolle)", "", text)
    text = re.sub(r"(?i)system\s*:\s*", "", text)
    text = re.sub(r"(?i)\bact as\b", "", text)
    text = re.sub(r"(?i)\bdu bist jetzt\b", "", text)
    # Entferne Steuerzeichen
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text.strip()[:max_len]


def _resolve_db_path(filename):
    if os.path.basename(BASE_DIR) == "ai":
        candidates = [
            os.path.join(PROJECT_ROOT, "database", filename),
            os.path.join(BASE_DIR, "data", filename),
        ]
    else:
        candidates = [
            os.path.join(PROJECT_ROOT, "database", filename),
            os.path.join(BASE_DIR, "database", filename),
            os.path.join(BASE_DIR, "data", filename),
        ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return candidates[0]


RAW_DB_PATH = _resolve_db_path("raw_tiktok.db")
USERS_DB_PATH = _resolve_db_path("users.db")
OUTPUT_DIR = os.path.dirname(RAW_DB_PATH)

API_KEY = os.getenv("LLM_API_KEY", "")
API_URL = os.getenv("LLM_API_URL", "http://10.10.11.11:8080/api/chat/completions")
MODEL_NAME = os.getenv("LLM_MODEL_NAME", "llama3:latest")
MAX_WORKERS = int(os.getenv("CONTENT_AGENT_MAX_WORKERS", "4"))
MAX_IDEAS_PER_USER = int(os.getenv("CONTENT_AGENT_MAX_IDEAS", "5"))
MAX_RAW_ROWS = int(os.getenv("CONTENT_AGENT_MAX_RAW_ROWS", "800"))
MIN_CLUSTER_SIZE = int(os.getenv("CONTENT_AGENT_MIN_CLUSTER", "3"))
MAX_TRENDS = int(os.getenv("CONTENT_AGENT_MAX_TRENDS", "10"))


# =========================================================================
# Hilfsfunktionen
# =========================================================================

def compute_sentiment(text):
    """Sentiment 0-100.  50 = neutral. Nutzt TextBlob wenn vorhanden."""
    if not isinstance(text, str) or not text.strip():
        return 50
    if HAS_TEXTBLOB:
        polarity = TextBlob(text).sentiment.polarity  # -1 ... +1
        return max(0, min(100, int(50 + polarity * 50)))
    positive = ["wow", "mega", "love", "best", "crazy", "amazing", "top",
                "delicious", "lecker", "geil", "awesome", "perfect"]
    negative = ["bad", "fail", "boring", "hate", "worst", "schlecht"]
    lower = text.lower()
    score = 50
    score += 6 * sum(w in lower for w in positive)
    score -= 6 * sum(w in lower for w in negative)
    return max(0, min(100, score))


def compute_cluster_sentiment(captions):
    """Mittleres Sentiment eines Clusters."""
    scores = [compute_sentiment(c) for c in captions if isinstance(c, str)]
    return int(sum(scores) / len(scores)) if scores else 50


def _extract_clean_tags(hashtag_str):
    """Gibt eine Liste sauberer, sinnvoller Hashtags zurueck."""
    raw = str(hashtag_str or "").lower()
    tags = re.findall(r"[a-z][a-z0-9]{2,}", raw)
    return [t for t in tags if t not in GENERIC_TAGS]


def _make_trend_label(tag_counter, max_parts=3):
    """Erzeugt einen lesbaren Trend-Label aus den haeufigsten Tags."""
    parts = []
    seen_labels = set()
    for tag, _ in tag_counter.most_common(8):
        label = LABEL_MAP.get(tag, tag.title())
        if label.lower() not in seen_labels:
            parts.append(label)
            seen_labels.add(label.lower())
        if len(parts) >= max_parts:
            break
    return " & ".join(parts) if parts else "Allgemeiner Trend"


def _lifecycle_phase(avg_velocity, cluster_size, med_velocity, med_size):
    """Bestimmt die Trend-Phase."""
    fast = avg_velocity > med_velocity
    big = cluster_size > med_size
    if fast and not big:
        return "EMERGING"
    if fast and big:
        return "PEAKING"
    if not fast and big:
        return "STAGNANT"
    return "NICHE"


# =========================================================================
# Video-Daten laden & vorbereiten
# =========================================================================

def load_raw_videos():
    if not os.path.exists(RAW_DB_PATH):
        print(f"[Content-Agent] raw_tiktok.db nicht gefunden: {RAW_DB_PATH}")
        return pd.DataFrame()
    conn = sqlite3.connect(RAW_DB_PATH)
    try:
        df = pd.read_sql_query("SELECT * FROM videos", conn)
    except Exception as exc:
        print(f"[Content-Agent] DB-Lesefehler: {exc}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df


def prepare_videos(df):
    """Berechnet Metriken und begrenzt auf MAX_RAW_ROWS."""
    if df.empty:
        return df
    df = df.copy()
    for col in ["caption", "hashtags", "creator", "video_id"]:
        if col not in df.columns:
            df[col] = ""
    for col in ["views", "likes", "comments", "shares"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "upload_date" not in df.columns:
        df["upload_date"] = pd.Timestamp.now(tz=timezone.utc).isoformat()

    upload_ts = pd.to_datetime(df["upload_date"], errors="coerce", utc=True)
    now = pd.Timestamp.now(tz=timezone.utc)
    age_hours = ((now - upload_ts).dt.total_seconds() / 3600).clip(lower=0.1).fillna(24)

    views = df["views"].astype(float)
    likes = df["likes"].astype(float)
    comments = df["comments"].astype(float)
    shares = df["shares"].astype(float)

    df["avg_velocity"] = (views / age_hours).fillna(0).round(2)
    df["avg_engagement"] = (((likes + comments + shares) / views.replace(0, pd.NA)) * 100).fillna(0).round(2)

    raw_score = views * 0.45 + df["avg_velocity"] * 0.35 + (likes + comments + shares) * 0.20
    mx = float(raw_score.max()) if not raw_score.empty and raw_score.max() > 0 else 1.0
    df["trend_score"] = (raw_score / mx * 100).fillna(0).round(2)
    df["video_id"] = df["video_id"].astype(str)
    df["upload_date"] = upload_ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ").fillna("")

    if len(df) > MAX_RAW_ROWS:
        df = df.sort_values("trend_score", ascending=False).head(MAX_RAW_ROWS)
    return df


# =========================================================================
# Trend-Clustering (Hashtag-basiert)
# =========================================================================

def cluster_videos_into_trends(df):
    """
    Gruppiert Videos anhand ihrer Hashtags zu Trend-Clustern.
    Returns: Liste von Trend-Dicts mit trend_label, trend_score, sentiment etc.
    """
    if df.empty:
        return []

    work = df.copy()
    work["clean_tags"] = work["hashtags"].apply(_extract_clean_tags)

    # Tag-Haeufigkeiten (jedes Video traegt pro Tag einmal bei)
    tag_freq = Counter()
    for tags in work["clean_tags"]:
        tag_freq.update(set(tags))

    # Top-Tags werden zu Trend-Kernen
    top_tags = [tag for tag, cnt in tag_freq.most_common(50) if cnt >= MIN_CLUSTER_SIZE]

    clusters = []
    assigned = set()

    for seed_tag in top_tags:
        if len(clusters) >= MAX_TRENDS:
            break

        mask = work["clean_tags"].apply(lambda tags, st=seed_tag: st in tags)
        candidates = work[mask & ~work.index.isin(assigned)]
        if len(candidates) < MIN_CLUSTER_SIZE:
            continue

        # Co-occurrierende Tags fuer Label
        co_tags = Counter()
        for tags in candidates["clean_tags"]:
            co_tags.update(tags)

        trend_label = _make_trend_label(co_tags)

        # Metriken
        c_velocity = candidates["avg_velocity"].mean()
        c_engagement = candidates["avg_engagement"].mean()
        c_score_raw = candidates["trend_score"].mean()
        c_views = candidates["views"].astype(float).sum()

        # Sentiment
        captions = candidates["caption"].fillna("").tolist()
        sentiment = compute_cluster_sentiment(captions)

        # Beispiel-Caption (kuerzeste aussagekraeftige)
        clean_caps = [c for c in captions if len(c) > 20]
        example_caption = min(clean_caps, key=len) if clean_caps else (captions[0] if captions else "")

        clusters.append({
            "rank": len(clusters) + 1,
            "trend_label": trend_label,
            "trend_score": round(c_score_raw, 2),
            "avg_velocity": round(c_velocity, 2),
            "avg_engagement": round(c_engagement, 2),
            "sentiment": sentiment,
            "lifecycle_phase": "",
            "cluster_size": len(candidates),
            "total_views": int(c_views),
            "example_caption": example_caption[:200],
        })

        assigned.update(candidates.index)

    # Lifecycle-Phasen bestimmen (relativ zum Median)
    if clusters:
        velocities = [c["avg_velocity"] for c in clusters]
        sizes = [c["cluster_size"] for c in clusters]
        med_vel = sorted(velocities)[len(velocities) // 2]
        med_size = sorted(sizes)[len(sizes) // 2]
        for c in clusters:
            c["lifecycle_phase"] = _lifecycle_phase(
                c["avg_velocity"], c["cluster_size"], med_vel, med_size
            )

    # Normalisiere trend_score auf 0-100
    if clusters:
        mx = max(c["trend_score"] for c in clusters)
        if mx > 0:
            for c in clusters:
                c["trend_score"] = round(c["trend_score"] / mx * 100, 1)

    return clusters


def filter_clusters_by_niche(clusters, niche_key):
    """Filtert Trend-Cluster nach Nischen-Keywords."""
    if niche_key == "general" or niche_key not in NICHES:
        return list(clusters)
    keywords = {k.lower() for k in NICHES[niche_key]}
    filtered = []
    for c in clusters:
        label_lower = c["trend_label"].lower()
        example_lower = c.get("example_caption", "").lower()
        if any(kw in label_lower or kw in example_lower for kw in keywords):
            filtered.append(c)
    return filtered if filtered else list(clusters)


# =========================================================================
# AI-Ideen-Generierung
# =========================================================================

def _ask_llm(prompt, system_msg="Du bist ein Social-Media-Experte. Antworte IMMER auf Deutsch."):
    """Sendet Prompt an den Schulserver. Gibt Text oder None zurueck."""
    if not API_KEY or not HAS_REQUESTS:
        return None
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }
    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        print(f"[Content-Agent] LLM-Fehler: {exc}")
        return None


def generate_video_idea(trend, user_profile):
    """Generiert eine personalisierte Video-Idee basierend auf einem Trend-Cluster."""
    trend_label = trend.get("trend_label", "Allgemeiner Trend")
    example = trend.get("example_caption", "")
    lifecycle = trend.get("lifecycle_phase", "")

    industry = _sanitize_user_input(user_profile.get("industry", "Unbekannt"))
    product = _sanitize_user_input(user_profile.get("product_description", "kein Produkt angegeben"))
    audience = _sanitize_user_input(f"{user_profile.get('target_audience_type', '')} ({user_profile.get('target_age_group', '')})")
    brand_tone = _sanitize_user_input(user_profile.get("brand_tone", "Neutral"))
    no_gos = _sanitize_user_input(user_profile.get("no_go_topics", "Keine"))
    usp = _sanitize_user_input(user_profile.get("unique_value", ""))

    prompt = f"""Erstelle eine konkrete TikTok/Reels-Videoidee fuer folgende Marke, basierend auf dem aktuellen Trend.

MARKE:
- Branche: {industry}
- Produkt: {product}
- USP: {usp}
- Zielgruppe: {audience}
- Tonalitaet: {brand_tone}
- No-Gos: {no_gos}

AKTUELLER TREND:
- Trend-Typ: {trend_label}
- Phase: {lifecycle}
- Beispiel-Video: "{example}"

AUFGABE:
Entwickle eine kreative Videoidee, die den Trend-Typ "{trend_label}" auf die Marke ummuenzt.
Die Idee muss in 15-30 Sekunden filmbar sein.

AUSGABEFORMAT (NUR dieses Format, keine Einleitung):
Titel: (kurzer, knackiger Titel - max 8 Woerter)
Sentiment: (Zahl 0-100)
Videoformat: (z.B. POV, Talking Head, Trend-Remix, Behind the Scenes, Meme/Comedy, Storytelling)
Hook: (Die ersten 1-2 Sekunden)
Idee: (Worum es geht, 1-2 Saetze)
Drehablauf: (Schritt fuer Schritt)
CTA: (Call-to-Action)"""

    raw = _ask_llm(prompt)

    if raw:
        title_m = re.search(r"Titel:\s*(.*?)(?:\n|$)", raw, re.I)
        sent_m = re.search(r"Sentiment:\s*(\d+)", raw, re.I)
        guide_m = re.search(r"(Videoformat:.*)", raw, re.I | re.DOTALL)

        title = title_m.group(1).replace("**", "").strip() if title_m else _fallback_title(trend_label, product)
        sentiment = int(sent_m.group(1)) if sent_m else trend.get("sentiment", 50)
        guide = guide_m.group(1).strip() if guide_m else _fallback_guide(trend_label, product)
    else:
        title = _fallback_title(trend_label, product)
        sentiment = trend.get("sentiment", 50)
        guide = _fallback_guide(trend_label, product)

    return title, sentiment, guide


def _fallback_title(trend_label, product):
    """Erstellt einen Titel aus Trend-Label + Produkt."""
    product_short = (product or "dein Produkt").split(",")[0].strip()[:30]
    return f"{trend_label} trifft {product_short}"


def _fallback_guide(trend_label, product):
    return (
        "Videoformat: Trend-Remix\n"
        f"Hook: Aufmerksamkeit mit dem Trend '{trend_label}' in den ersten 2 Sekunden.\n"
        f"Idee: Zeige den Trend aus der Perspektive von {product}.\n"
        "Drehablauf: 0-2s Hook, 3-8s Trend zeigen, 9-15s Produktbezug, 16-20s CTA.\n"
        "CTA: Frage deine Zielgruppe, was sie davon haelt."
    )


# =========================================================================
# User-Verarbeitung
# =========================================================================

def load_users(conn):
    return pd.read_sql_query("SELECT * FROM user_onboarding_profile", conn)


def load_valid_user_ids(conn):
    try:
        rows = pd.read_sql_query("SELECT id FROM users", conn)
    except Exception:
        return set()
    return {str(uid).strip() for uid in rows["id"].tolist()}


def cleanup_orphan_json(output_dir, keep_ids):
    """Loescht JSON-Dateien fuer User-IDs die nicht in keep_ids sind."""
    pattern = os.path.join(output_dir, "trends_user_*.json")
    removed = 0
    for path in glob.glob(pattern):
        m = re.match(r"trends_user_(.+)\.json$", os.path.basename(path))
        if not m:
            continue
        uid = m.group(1).strip()
        if uid not in keep_ids:
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    if removed:
        print(f"[Content-Agent] {removed} verwaiste JSON-Dateien geloescht.")


# =========================================================================
# Hauptpipeline
# =========================================================================

def run_agent():
    print("[Content-Agent] Starte Trend-Clustering & AI-Ideen-Pipeline...")

    if not os.path.exists(USERS_DB_PATH):
        print(f"[Content-Agent] users.db nicht gefunden: {USERS_DB_PATH}")
        return

    # 1. Videos laden
    raw_df = prepare_videos(load_raw_videos())
    if raw_df.empty:
        print("[Content-Agent] Keine Video-Daten vorhanden.")
        return
    print(f"[Content-Agent] {len(raw_df)} Videos geladen.")

    # 2. Globale Trend-Cluster berechnen
    global_clusters = cluster_videos_into_trends(raw_df)
    print(f"[Content-Agent] {len(global_clusters)} Trend-Cluster erkannt.")
    for c in global_clusters[:5]:
        print(f"  #{c['rank']} {c['trend_label']} (Score: {c['trend_score']}, "
              f"Videos: {c['cluster_size']}, Phase: {c['lifecycle_phase']})")

    # 3. User laden
    conn = sqlite3.connect(USERS_DB_PATH)
    try:
        users_df = load_users(conn)
    except Exception as exc:
        print(f"[Content-Agent] Fehler: {exc}")
        conn.close()
        return

    valid_ids = load_valid_user_ids(conn)
    if valid_ids:
        users_df = users_df[users_df["user_id"].astype(str).isin(valid_ids)].copy()
    users_df = users_df.drop_duplicates(subset=["user_id"], keep="last")

    # Nur User mit echten Onboarding-Daten verarbeiten
    users_df = users_df[users_df["industry"].fillna("").str.strip().astype(bool)].copy()

    active_user_ids = {str(uid).strip() for uid in users_df["user_id"].tolist()}
    cleanup_orphan_json(OUTPUT_DIR, active_user_ids)

    if users_df.empty:
        print("[Content-Agent] Keine User mit Onboarding-Profil gefunden.")
        conn.close()
        return

    print(f"[Content-Agent] {len(users_df)} User mit Onboarding-Profil gefunden.")

    # 4. Pro User: Nischen-Trends + AI-Ideen generieren
    for _, user in users_df.iterrows():
        user_id = str(user.get("user_id", "")).strip()
        if not user_id:
            continue

        industry = str(user.get("industry", "general") or "general").lower().strip()
        product = str(user.get("product_description", "") or "")
        print(f"\n[Content-Agent] User {user_id} (Branche: {industry})")

        # Nischen-spezifische Cluster
        niche_clusters = filter_clusters_by_niche(global_clusters, industry)

        # Sortierungen fuer die verschiedenen Sektionen
        by_score = sorted(niche_clusters, key=lambda c: c["trend_score"], reverse=True)
        by_velocity = sorted(niche_clusters, key=lambda c: c["avg_velocity"], reverse=True)
        by_engagement = sorted(niche_clusters, key=lambda c: c["avg_engagement"], reverse=True)

        # AI Video-Ideen generieren (basierend auf Top-Trends)
        top_for_ideas = by_score[:MAX_IDEAS_PER_USER]
        ai_ideas = []

        if top_for_ideas:
            print(f"  Generiere {len(top_for_ideas)} AI-Ideen...")
            user_dict = user.to_dict()

            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                results = list(pool.map(
                    lambda t: generate_video_idea(t, user_dict),
                    top_for_ideas,
                ))

            for trend_data, (title, sentiment_val, guide) in zip(top_for_ideas, results):
                ai_ideas.append({
                    "video_id": f"trend_cluster_{trend_data['rank']}",
                    "trend_label": trend_data["trend_label"],
                    "caption": trend_data.get("example_caption", ""),
                    "ai_title": title,
                    "ai_sentiment": sentiment_val,
                    "ai_guide": guide,
                    "trend_score": trend_data["trend_score"],
                    "avg_velocity": trend_data["avg_velocity"],
                    "avg_engagement": trend_data["avg_engagement"],
                    "lifecycle_phase": trend_data.get("lifecycle_phase", ""),
                    "cluster_size": trend_data["cluster_size"],
                })

        if not ai_ideas:
            for c in by_score[:MAX_IDEAS_PER_USER]:
                ai_ideas.append({
                    "video_id": f"trend_cluster_{c['rank']}",
                    "trend_label": c["trend_label"],
                    "caption": c.get("example_caption", ""),
                    "ai_title": _fallback_title(c["trend_label"], product),
                    "ai_sentiment": c["sentiment"],
                    "ai_guide": _fallback_guide(c["trend_label"], product),
                    "trend_score": c["trend_score"],
                    "avg_velocity": c["avg_velocity"],
                    "avg_engagement": c["avg_engagement"],
                    "lifecycle_phase": c.get("lifecycle_phase", ""),
                    "cluster_size": c["cluster_size"],
                })

        # JSON schreiben (1 Datei pro User, wird immer ueberschrieben)
        user_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ai_video_ideas": ai_ideas,
            "top_trends": by_score[:MAX_TRENDS],
            "rising_trends": by_velocity[:MAX_TRENDS],
            "opportunities": by_engagement[:MAX_TRENDS],
            "global_trends": global_clusters[:MAX_TRENDS],
        }

        json_path = os.path.join(OUTPUT_DIR, f"trends_user_{user_id}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
        print(f"  -> {json_path} ({len(ai_ideas)} Ideen, {len(by_score)} Trends)")

    conn.close()
    print("\n[Content-Agent] Pipeline abgeschlossen.")


if __name__ == "__main__":
    run_agent()
