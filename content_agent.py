import sqlite3
import pandas as pd
import requests
import json
import os
import re
import concurrent.futures
from datetime import datetime

# --- KONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DB_PATH = os.path.join(BASE_DIR, "data", "raw_tiktok.db")
USERS_DB_PATH = os.path.join(BASE_DIR, "data", "users.db")
API_KEY = "sk-eea92dcb4a3e4ec0a1dcba12ddaead0a"  
API_URL = "http://10.10.11.11:8080/api/chat/completions" 
MODEL_NAME = "llama3:latest" 
MAX_WORKERS = 4
# ---------------------

def generate_personalized_guide(trend_caption, user_profile):
    user_id = user_profile.get('user_id', 'Unbekannt')
    print(f"🤖 [Thread] Sende personalisierte Anfrage für User {user_id}...")
    
    # 🧠 CONTEXT INJECTION (Daten aus der users.db)
    brand_context = f"Branche: {user_profile.get('industry', 'Unbekannt')}. {user_profile.get('audience_description', '')}"
    product = user_profile.get('product_description', 'Kein Produkt angegeben')
    usp = user_profile.get('unique_value', 'Kein spezifischer USP')
    audience = f"{user_profile.get('target_audience_type', '')} ({user_profile.get('target_age_group', '')})"
    brand_tone = user_profile.get('brand_tone', 'Neutral')
    no_gos = user_profile.get('no_go_topics', 'Keine')
    
    # 🔥 ANDIS MASTER-PROMPT (leicht modifiziert für Code-Kompatibilität & Sentiment)
    prompt = f"""Du bist ein Experte für virale Social-Media Videos (Instagram Reels / TikTok).

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
1. ANTWORTE AUSSCHLIESSLICH AUF DEUTSCH! Übersetze alle Gedanken und Ideen ins Deutsche, egal in welcher Sprache der Trend-Inhalt ist.
2. ADAPTION: Wenn der ursprüngliche Trend inhaltlich nicht perfekt zur Firma passt, nutze nur die Mechanik des Trends (z.B. den Hook, Sound oder Stil) und münze es kreativ so um, dass es perfekt zum Produkt '{product}' passt.
3. BERECHNUNG: Bewerte das Sentiment (die Stimmung) des rohen TikTok-Trends auf einer Skala von 0 (sehr negativ) bis 100 (sehr positiv).
4. MARKEN-TREUE: Die Idee muss authentisch wirken (nicht wie platte Werbung), in 15-30 Sekunden umsetzbar sein und darf NIEMALS gegen die No-Gos verstoßen.
5. SKRIPT-REGEL: Wenn du als Videoformat "Talking Head" wählst, schreibe unter "Drehablauf" kein abstraktes Konzept, sondern ein fertiges, wortwörtliches Skript, das der Kunde 1:1 vom Teleprompter ablesen kann!

--------------------------------
AUSGABEFORMAT
--------------------------------
Antworte ausschließlich in dieser Struktur (kein Fließtext davor oder danach!):

Titel:
(Kurzer Titel der Videoidee - KEINE Hashtags)

Sentiment:
(Zahl zwischen 0 und 100)

Videoformat:
(Dein gewähltes Format)

Hook:
(Die ersten 1-2 Sekunden des Videos - maximal aufmerksamkeitsstark)

Idee:
(Kurz erklären, worum es im Video geht)

Drehablauf:
(Schritt-für-Schritt Ablauf des Videos)

CTA:
(Call-to-Action am Ende des Videos)
"""
    
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "Du hältst dich strikt an das vorgegebene Ausgabeformat."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    
    title, sentiment_val, guide = "KI-Titel ausstehend", 50, "Leitfaden konnte nicht generiert werden."
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=300)
        response.raise_for_status()
        raw_text = response.json()['choices'][0]['message']['content'].strip()
        
        # ✂️ DAS NEUE SKALPELL: Schneidet Titel, Sentiment und den gesamten Rest (als Guide) aus
        t_match = re.search(r'Titel:\s*(.*?)\n', raw_text, re.IGNORECASE)
        s_match = re.search(r'Sentiment:\s*(\d+)', raw_text, re.IGNORECASE)
        g_match = re.search(r'(Videoformat:.*)', raw_text, re.IGNORECASE | re.DOTALL)
        
        if t_match: title = t_match.group(1).replace("**", "").strip()
        if s_match: sentiment_val = int(s_match.group(1))
        if g_match: guide = g_match.group(1).strip()
    except Exception as e:
        guide = f"Fehler bei der Generierung: {e}"
        
    return title, sentiment_val, guide

def run_agent():
    print(f"[Content-Agent] Starte personalisierte KI-Pipeline (Max 5 Videos/Woche)...")
    
    if not os.path.exists(USERS_DB_PATH):
        print(f"❌ Fehler: Keine Onboarding-Datenbank unter {USERS_DB_PATH} gefunden.")
        return
        
    conn_users = sqlite3.connect(USERS_DB_PATH)
    
    # 🆕 1. Historien-Tabelle anlegen (falls sie nicht existiert)
    conn_users.execute("""
        CREATE TABLE IF NOT EXISTS user_idea_history (
            user_id TEXT,
            video_id TEXT,
            generated_date TEXT,
            UNIQUE(user_id, video_id)
        )
    """)
    conn_users.commit()
    
    try:
        users_df = pd.read_sql_query("SELECT * FROM user_onboarding_profile", conn_users)
    except Exception as e:
        print(f"❌ Fehler beim Lesen der Onboarding-Daten: {e}")
        conn_users.close()
        return

    conn_trends = sqlite3.connect(RAW_DB_PATH)
    
    # 🚀 Wir iterieren über jeden einzelnen Benutzer!
    for index, user in users_df.iterrows():
        user_id = str(user.get('user_id'))
        industry_raw = user.get('industry', 'general')
        industry = str(industry_raw).lower().strip()
        table_name = f"top10_{industry}"
        
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn_trends)
        except:
            print(f"⚠️ Keine Trends für Nische '{industry}' (User {user_id}) gefunden. Überspringe...")
            continue
            
        if df.empty or 'caption' not in df.columns:
            continue

        # 🆕 2. Historie laden: Welche Videos kennt der User schon?
        history_df = pd.read_sql_query(f"SELECT video_id FROM user_idea_history WHERE user_id = '{user_id}'", conn_users)
        bekannte_videos = history_df['video_id'].astype(str).tolist()
        
        # Sicherstellen, dass die video_id Spalte im Trend-DataFrame ein String ist
        df['video_id'] = df['video_id'].astype(str)
        
        # 🆕 3. Alte Videos herausfiltern und auf exakt 5 limitieren!
        df_neu = df[~df['video_id'].isin(bekannte_videos)].head(5)
        
        if df_neu.empty:
            print(f"ℹ️ User {user_id} hat bereits alle aktuellen Trends gesehen. Keine neuen Ideen generiert.")
            continue
            
        print(f"\n🚀 Verarbeite {len(df_neu)} NEUE Trends für User {user_id} (Brand: {industry_raw})...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Lambda übergibt Caption und das User-Dictionary
            results = list(executor.map(lambda cap: generate_personalized_guide(cap, user.to_dict()), df_neu['caption']))
            
        df_neu['ai_title'] = [r[0] for r in results]
        df_neu['ai_sentiment'] = [r[1] for r in results]
        df_neu['ai_guide'] = [r[2] for r in results]
        
        # 🆕 4. Die neuen Videos in die Historie eintragen
        heute = datetime.now().strftime("%Y-%m-%d")
        for vid in df_neu['video_id']:
            conn_users.execute("INSERT OR IGNORE INTO user_idea_history (user_id, video_id, generated_date) VALUES (?, ?, ?)", 
                               (user_id, vid, heute))
        conn_users.commit()
        
        # Globale Trends laden (für Andis Reiter "Global Trends")
        try:
            global_df = pd.read_sql_query("SELECT * FROM top10_general", conn_trends)
        except:
            global_df = pd.DataFrame()

        # 📂 Das ultimative Daten-Paket für Andis Frontend!
        user_data = {
            "ai_video_ideas": df_neu.to_dict(orient='records'), # Die 5 fertigen KI-Ideen der Woche
            "top_trends": df.sort_values(by="trend_score", ascending=False).to_dict(orient='records'),
            "rising_trends": df.sort_values(by="avg_velocity", ascending=False).to_dict(orient='records'),
            "opportunities": df.sort_values(by="avg_engagement", ascending=False).to_dict(orient='records'),
            "global_trends": global_df.to_dict(orient='records') if not global_df.empty else []
        }
        
        json_path = os.path.join(os.path.dirname(RAW_DB_PATH), f"trends_user_{user_id}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=4)

    conn_trends.close()
    conn_users.close()
    print("\n🏁 Alle personalisierten Leitfäden für alle User erfolgreich generiert!")

if __name__ == "__main__":
    run_agent()