import sqlite3
import pandas as pd
import os

# Pfad zur DB (Monorepo-Struktur)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DB_DIR = os.path.join(PROJECT_ROOT, "database")
db_path = os.path.join(DB_DIR, 'raw_tiktok.db')

def clean_database():
    print("🔍 Starte smarte Datenbank-Bereinigung...")
    conn = sqlite3.connect(db_path)
    
    # Lade die rohe Videos-Tabelle
    df = pd.read_sql_query("SELECT * FROM videos", conn)
    start_len = len(df)
    
    # 🚀 DER FIX: Wir suchen Duplikate anhand von Text und Creator, nicht nach der ID!
    # keep='last' sorgt dafür, dass wir den aktuellsten Scrape (mit den neuesten Views) behalten
    df_clean = df.drop_duplicates(subset=['creator', 'caption'], keep='last')
    
    # Speichere die saubere Version zurück
    df_clean.to_sql('videos', conn, if_exists='replace', index=False)
    
    end_len = len(df_clean)
    geloescht = start_len - end_len
    
    print(f"🧹 Bereinigung abgeschlossen!")
    print(f"📊 Vorher: {start_len} Videos")
    print(f"🗑️ Gelöschte Spam-Duplikate: {geloescht}")
    print(f"✨ Nachher: {end_len} echte, einzigartige Videos für die KI.")
    
    conn.close()

if __name__ == "__main__":
    if os.path.exists(db_path):
        clean_database()
    else:
        print("Fehler: Datenbank nicht gefunden.")