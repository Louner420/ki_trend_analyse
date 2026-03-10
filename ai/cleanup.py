import sqlite3
import os
import time

# Löscht Videos, die älter als 7 Tage sind, um die DB schnell zu halten
DB_PATH = os.path.join(os.path.dirname(__file__), "data/raw_tiktok.db")
DAYS_TO_KEEP = 7

def clean_database():
    if not os.path.exists(DB_PATH):
        return

    print("[Cleanup] Starte Datenbank-Bereinigung...")
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # SQL um alte Einträge zu löschen (basierend auf upload_date)
        # Wir nutzen SQLite's 'date' modifier
        c.execute(f"DELETE FROM videos WHERE upload_date < date('now', '-{DAYS_TO_KEEP} days')")
        deleted_count = c.rowcount
        
        conn.commit()
        conn.close()
        print(f"[Cleanup] ✅ {deleted_count} alte Videos gelöscht.")
        
        # Datenbank physisch verkleinern (VACUUM)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("VACUUM")
        conn.close()
        print("[Cleanup] Datenbank optimiert (VACUUM).")
        
    except Exception as e:
        print(f"[Cleanup Error] {e}")

if __name__ == "__main__":
    clean_database()
