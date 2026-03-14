import sqlite3
import os

<<<<<<< HEAD
# PFAD-ANPASSUNG FÜR DOCKER VOLUME
# Nutzt /app/database (aus docker-compose) oder den lokalen 'data' Ordner
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.getenv("DATA_PATH", os.path.join(BASE_DIR, "data"))
=======
# Pfad zur Datenbank (Monorepo-Struktur)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DB_DIR = os.path.join(PROJECT_ROOT, "database")
>>>>>>> 746edddab3438fb87393415ad8deb9c85fbb5fa0
db_path = os.path.join(DB_DIR, "raw_tiktok.db")

def reset_result_tables():
    if not os.path.exists(db_path):
        print(f"❌ Keine Datenbank gefunden unter: {db_path}")
        return

    print(f"🔄 Verbinde mit Datenbank: {db_path}")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    try:
        # 1. Alle Top-10 Tabellen finden
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'top10_%'")
        tables = c.fetchall()
        
        if not tables:
            print("ℹ️ Keine alten Tabellen gefunden. Alles sauber.")
            return
        
        # 2. Tabellen löschen
        for table in tables:
            table_name = table[0]
            print(f"🗑️ Lösche alte Tabelle: {table_name}...")
            c.execute(f"DROP TABLE IF EXISTS {table_name}")
            
        conn.commit()
        print("✅ Alle Ergebnistabellen gelöscht. Der Weg ist frei!")
        
    except Exception as e:
        print(f"❌ Fehler beim Zurücksetzen: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    reset_result_tables()
