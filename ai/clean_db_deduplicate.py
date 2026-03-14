import sqlite3
import pandas as pd
import os

# PFAD-ANPASSUNG FÜR DOCKER VOLUME
# Nutzt /app/database (aus docker-compose) oder den lokalen 'database' Ordner
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Wir prüfen erst DATA_PATH, dann einen Standard-Ordner relativ zum Skript
DB_DIR = os.getenv("DATA_PATH", os.path.join(os.path.dirname(BASE_DIR), "database"))
db_path = os.path.join(DB_DIR, 'raw_tiktok.db')

def clean_database():
    print(f"🔍 Starte smarte Datenbank-Bereinigung in: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Lade die rohe Videos-Tabelle
        df = pd.read_sql_query("SELECT * FROM videos", conn)
        
        if df.empty:
            print("⚠️ Tabelle 'videos' ist leer. Nichts zu tun.")
            conn.close()
            return
            
        start_len = len(df)
        
        # 🚀 DER FIX: Wir suchen Duplikate anhand von Text und Creator.
        # keep='last' behält den aktuellsten Scrape (neueste Metriken)
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
        
    except Exception as e:
        print(f"❌ Fehler bei der Bereinigung: {e}")

if __name__ == "__main__":
    if os.path.exists(db_path):
        clean_database()
    else:
        print(f"⚠️ Fehler: Datenbank nicht gefunden unter {db_path}")