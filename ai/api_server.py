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
API_KEY = "sk-eea92dcb4a3e4ec0a1dcba12ddaead0a"  
API_URL = "http://10.10.11.11:8080/api/chat/completions" 
MODEL_NAME = "llama3:latest" 
# ---------------------

def get_user_profile(user_id):
    """Holt den Kontext des Users aus der Datenbank für maßgeschneiderte Antworten."""
    if not os.path.exists(USERS_DB_PATH):
        return None
    try:
        conn = sqlite3.connect(USERS_DB_PATH)
        query = f"SELECT * FROM user_onboarding_profile WHERE user_id = '{user_id}'"
        df = pd.read_sql_query(query, conn)
        conn.close()
        if not df.empty:
            return df.iloc[0].to_dict()
    except Exception as e:
        print(f"DB Error: {e}")
    return None

def ask_llama(prompt):
    """Schickt den Prompt live an den Schulserver."""
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "Du bist ein Social-Media-Experte. Antworte immer auf Deutsch und halte dich strikt an die Vorgaben."},
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
    
    new_idea = ask_llama(prompt)
    return jsonify({"refined_idea": new_idea})

# ==========================================
# ENDPUNKT 2: Spontane Idee generieren
# ==========================================
@app.route('/api/spontaneous', methods=['POST'])
def spontaneous_idea():
    data = request.json
    user_id = data.get('user_id')
    topic = data.get('topic') # z.B. "Wir haben heute einen neuen Pizzaofen bekommen"

    if not all([user_id, topic]):
        return jsonify({"error": "Fehlende Daten"}), 400

    profile = get_user_profile(user_id)
    if not profile:
        return jsonify({"error": "User Profil nicht gefunden"}), 404
        
    brand_context = f"{profile.get('industry', '')}. {profile.get('audience_description', '')}"
    product = profile.get('product_description', '')
    
    prompt = f"""Du bist ein Social Media Manager. Dein Kunde (Branche: {brand_context}, Produkt: {product}) hat gerade folgende spontane Idee / Situation geäußert:
    
    "{topic}"
    
    Mach daraus ein fertiges, kurzes TikTok-Skript.
    Antworte im Format:
    Titel: ...
    Videoformat: ...
    Hook: ...
    Idee: ...
    Drehablauf: ...
    CTA: ...

    "WICHTIG: Antworte AUSSCHLIESSLICH in dem vorgegebenen Format. Nutze keine Einleitungs- oder Schlusssätze."
    """
    
    idea = ask_llama(prompt)
    return jsonify({"idea": idea})

if __name__ == '__main__':
    # Startet den Server auf Port 5000, erreichbar im ganzen Netzwerk
    app.run(host='0.0.0.0', port=5000)