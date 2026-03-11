from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import pandas as pd
import requests
import os

app = Flask(__name__)
CORS(app) # Erlaubt Andis Frontend den Zugriff

# --- KONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DB_DIR = os.path.join(PROJECT_ROOT, "database")
USERS_DB_PATH = os.path.join(DB_DIR, "users.db")
API_KEY = os.getenv("LLM_API_KEY", "")
API_URL = "http://10.10.11.11:8080/api/chat/completions" 
MODEL_NAME = "llama3:latest" 
REQUIRE_LLM = os.getenv("AI_REQUIRE_LLM", "0").lower() in ("1", "true", "yes", "on")
SPONTANEOUS_REQUIRE_LLM = os.getenv("AI_SPONTANEOUS_REQUIRE_LLM", "1").lower() in ("1", "true", "yes", "on")
# ---------------------


def fallback_refine_idea(original_idea, feedback, profile=None):
    """Lokaler Fallback, falls School-LLM nicht erreichbar ist."""
    tone = (profile or {}).get("brand_tone") or "klar"
    return (
        f"Titel: Überarbeitet ({tone})\n"
        f"Videoformat: Short-Form\n"
        f"Hook: {feedback.strip().capitalize()} – sofort in den ersten 2 Sekunden.\n"
        f"Idee: {original_idea[:220].strip()}\n"
        "Drehablauf: 0-2s Hook einblenden, 3-8s Kernbotschaft, 9-15s klare Demo/Proof, 16-20s Abschluss.\n"
        "CTA: Schreib 'MEHR' in die Kommentare für die nächste Version."
    )


def fallback_spontaneous_idea(topic, profile=None):
    """Lokaler Fallback für spontane Ideen."""
    industry = (profile or {}).get("industry") or "Business"
    return (
        f"Titel: {industry}-Quick Idea\n"
        "Videoformat: Talking + B-Roll\n"
        f"Hook: Heute spontan: {topic}\n"
        f"Idee: Zeige in 20 Sekunden, warum das für deine Zielgruppe relevant ist.\n"
        "Drehablauf: 0-2s Hook, 3-10s Kontext, 11-17s Nutzen, 18-20s CTA.\n"
        "CTA: Folge für mehr tägliche Kurzideen."
    )


def ensure_spontaneous_format(raw_text, topic, requested_format=None):
    text = str(raw_text or "").strip()
    if not text:
        return ""

    fields = {
        "Titel": "",
        "Videoformat": "",
        "Hook": "",
        "Idee": "",
        "Drehablauf": "",
        "CTA": "",
    }
    current = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key_clean = key.strip().lower()
            for canonical in fields:
                if key_clean == canonical.lower():
                    current = canonical
                    fields[canonical] = value.strip()
                    break
            else:
                if current:
                    fields[current] = (fields[current] + " " + line).strip()
        elif current:
            fields[current] = (fields[current] + " " + line).strip()

    expected_topic_snippet = topic.strip()[:80]
    if not fields["Titel"]:
        fields["Titel"] = f"Idee zu: {expected_topic_snippet}" if expected_topic_snippet else "Neue Trend-Idee"
    if requested_format:
        fields["Videoformat"] = requested_format
    elif not fields["Videoformat"]:
        fields["Videoformat"] = "Talking + B-Roll"
    if not fields["Hook"]:
        fields["Hook"] = f"Heute geht es konkret um: {expected_topic_snippet}" if expected_topic_snippet else "Heute gibt es eine neue Content-Idee."
    if expected_topic_snippet and expected_topic_snippet.lower() not in fields["Hook"].lower() and expected_topic_snippet.lower() not in fields["Idee"].lower():
        fields["Idee"] = (fields["Idee"] + f" Fokus: {expected_topic_snippet}.").strip()
    if not fields["Idee"]:
        fields["Idee"] = f"Erklaere den Nutzen von '{expected_topic_snippet}' fuer die Zielgruppe in einem klaren Beispiel." if expected_topic_snippet else "Erklaere den Nutzen fuer die Zielgruppe mit einem klaren Beispiel."
    if not fields["Drehablauf"]:
        fields["Drehablauf"] = "0-2s Hook, 3-8s Problem, 9-15s Loesung, 16-20s CTA."
    if not fields["CTA"]:
        fields["CTA"] = "Schreibe 'MEHR' in die Kommentare fuer die naechste Idee."

    return "\n".join([
        f"Titel: {fields['Titel']}",
        f"Videoformat: {fields['Videoformat']}",
        f"Hook: {fields['Hook']}",
        f"Idee: {fields['Idee']}",
        f"Drehablauf: {fields['Drehablauf']}",
        f"CTA: {fields['CTA']}",
    ])

def get_user_profile(user_id):
    """Holt den Kontext des Users aus der Datenbank für maßgeschneiderte Antworten."""
    if not os.path.exists(USERS_DB_PATH):
        return None
    try:
        conn = sqlite3.connect(USERS_DB_PATH)
        query = "SELECT * FROM user_onboarding_profile WHERE user_id = ?"
        df = pd.read_sql_query(query, conn, params=(user_id,))
        conn.close()
        if not df.empty:
            return df.iloc[0].to_dict()
    except Exception as e:
        print(f"DB Error: {e}")
    return None

def ask_llama(prompt, system_msg=None):
    """Schickt den Prompt live an den Schulserver."""
    if not API_KEY:
        return "Fehler: LLM_API_KEY ist nicht gesetzt."
    if system_msg is None:
        system_msg = "Du bist ein erfahrener Social-Media-Manager. Antworte IMMER auf Deutsch. Halte dich strikt ans vorgegebene Ausgabeformat. Keine Einleitungen, keine Erklaerungen ausserhalb des Formats."
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Fehler bei der KI-Verbindung: {str(e)}"

# ==========================================
# ENDPUNKT 1: Idee überarbeiten
# ==========================================
@app.route('/api/refine', methods=['POST'])
def refine_idea():
    data = request.json
    user_id = data.get('user_id')
    original_idea = data.get('original_idea')
    feedback = data.get('feedback') # z.B. "Mach es witziger" oder "Kürzer"

    if not all([user_id, original_idea, feedback]):
        return jsonify({"error": "Fehlende Daten"}), 400

    profile = get_user_profile(user_id)
    brand_tone = profile.get('brand_tone', 'Neutral') if profile else 'Neutral'

    prompt = f"""Hier ist eine bestehende Video-Idee für unseren Kunden (Brand Tone: {brand_tone}):
    
    {original_idea}
    
    DER KUNDE HAT FOLGENDES FEEDBACK GEGEBEN: "{feedback}"
    
    Bitte überarbeite die Idee basierend auf dem Feedback. Behalte das ursprüngliche Format (Titel, Hook, Idee, Drehablauf, CTA) bei, aber passe den Inhalt an die Wünsche an.
    """
    
    if REQUIRE_LLM and not API_KEY:
        return jsonify({"error": "AI_REQUIRE_LLM=1, aber LLM_API_KEY fehlt."}), 503

    if not API_KEY:
        return jsonify({
            "refined_idea": fallback_refine_idea(original_idea, feedback, profile),
            "source": "fallback"
        })

    new_idea = ask_llama(prompt)
    if new_idea.startswith("Fehler bei der KI-Verbindung:"):
        if REQUIRE_LLM:
            return jsonify({"error": new_idea}), 502
        return jsonify({
            "refined_idea": fallback_refine_idea(original_idea, feedback, profile),
            "source": "fallback"
        })
    return jsonify({"refined_idea": new_idea, "source": "llm"})

# ==========================================
# ENDPUNKT 2: Spontane Idee generieren
# ==========================================
@app.route('/api/spontaneous', methods=['POST'])
def spontaneous_idea():
    data = request.json
    user_id = data.get('user_id')
    topic = data.get('topic') # z.B. "Wir haben heute einen neuen Pizzaofen bekommen"
    requested_format = (data.get('requested_format') or '').strip()

    if not all([user_id, topic]):
        return jsonify({"error": "Fehlende Daten"}), 400

    profile = get_user_profile(user_id)
    if not profile:
        return jsonify({"error": "User Profil nicht gefunden"}), 404

    industry = profile.get('industry', 'Unbekannt')
    product = profile.get('product_description', '')
    audience = profile.get('audience_description', '')
    brand_tone = profile.get('brand_tone', 'Neutral')
    no_gos = profile.get('no_go_topics', 'Keine')

    format_line = f"Videoformat: {requested_format}" if requested_format else "Videoformat: (waehle das passendste Format: POV, Talking Head, Trend-Remix, Behind the Scenes, Meme/Comedy, Storytelling)"

    prompt = f"""Erstelle ein kurzes TikTok/Reels-Skript zum Thema "{topic}".

MARKE: {industry}, Produkt: {product}
ZIELGRUPPE: {audience}
TONALITAET: {brand_tone}
NO-GOs: {no_gos}

Antworte NUR in diesem Format:
Titel: (kurzer Titel, max 8 Woerter, bezieht sich auf "{topic}")
{format_line}
Hook: (erste 1-2 Sek, macht neugierig auf "{topic}")
Idee: (worum es konkret geht, 1-2 Saetze)
Drehablauf: (Schritt fuer Schritt, 15-30 Sek Video)
CTA: (Call-to-Action)"""
    
    if (REQUIRE_LLM or SPONTANEOUS_REQUIRE_LLM) and not API_KEY:
        return jsonify({"error": "LLM_API_KEY fehlt. Spontane Ideen muessen vom Schulserver generiert werden."}), 503

    if not API_KEY:
        return jsonify({"idea": fallback_spontaneous_idea(topic, profile), "source": "fallback"})

    idea = ask_llama(prompt)
    if idea.startswith("Fehler bei der KI-Verbindung:"):
        if REQUIRE_LLM or SPONTANEOUS_REQUIRE_LLM:
            return jsonify({"error": idea}), 502
        return jsonify({"idea": fallback_spontaneous_idea(topic, profile), "source": "fallback"})
    normalized = ensure_spontaneous_format(idea, topic, requested_format)
    if not normalized:
        if REQUIRE_LLM or SPONTANEOUS_REQUIRE_LLM:
            return jsonify({"error": "Leere Antwort vom LLM."}), 502
        return jsonify({"idea": fallback_spontaneous_idea(topic, profile), "source": "fallback"})
    return jsonify({"idea": normalized, "source": "llm"})

if __name__ == '__main__':
    # Startet den Server auf Port 5000, erreichbar im ganzen Netzwerk
    app.run(host='0.0.0.0', port=5000)