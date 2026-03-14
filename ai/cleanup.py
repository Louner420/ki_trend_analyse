import sqlite3
import os

# PFAD-ANPASSUNG FÜR DOCKER VOLUME
# Nutzt /app/database (aus docker-compose) oder den lokalen 'data' Ordner
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.getenv("DATA_PATH", os.path.join(BASE_DIR, "data"))
DB_PATH = os.path.join(DB_DIR, "raw_tiktok.db")

DAYS_TO_KEEP = 7

def clean_database():
    if not os.path.exists(DB_PATH):
        print(f"[Cleanup] ⚠️ Datenbank nicht gefunden unter: {DB_PATH}")
        return

    print(f"[Cleanup] Starte Bereinigung in: {DB_PATH}")
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Lösche Einträge, die älter als X Tage sind
        c.execute(f"DELETE FROM videos WHERE upload_date < date('now', '-{DAYS_TO_KEEP} days')")
        deleted_count = c.rowcount
        
        conn.commit()
        conn.close()
        print(f"[Cleanup] ✅ {deleted_count} alte Videos gelöscht.")
        
        # Datenbank physisch verkleinern
        conn = sqlite3.connect(DB_PATH)
        conn.execute("VACUUM")
        conn.close()
        print("[Cleanup] Datenbank optimiert (VACUUM).")
        
    except Exception as e:
        print(f"[Cleanup Error] {e}")

if __name__ == "__main__":
    clean_database()