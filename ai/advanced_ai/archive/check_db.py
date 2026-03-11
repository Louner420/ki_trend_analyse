import sqlite3
import os

# Pfade (Monorepo-Struktur)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_BASE_DIR)))
DB_DIR = os.path.join(_PROJECT_ROOT, "database")
DB_TIKTOK = os.path.join(DB_DIR, "raw_tiktok.db")
DB_INSTA = os.path.join(DB_DIR, "raw_instagram.db")
DB_RESULTS = os.path.join(DB_DIR, "trend_results.db")

def check_db(name, path, table):
    if not os.path.exists(path):
        print(f"❌ {name}: Datei fehlt!")
        return
    
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT count(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"✅ {name}: {count} Einträge in Tabelle '{table}'")
        
        # Zeige das neueste Datum
        if count > 0:
            cursor.execute(f"SELECT scraped_at FROM {table} ORDER BY scraped_at DESC LIMIT 1")
            last = cursor.fetchone()[0]
            print(f"   Letztes Update: {last}")
            
        conn.close()
    except Exception as e:
        print(f"⚠️ {name}: Fehler - {e}")

print("--- DATENBANK CHECK ---")
check_db("TikTok Raw", DB_TIKTOK, "videos")
check_db("Instagram Raw", DB_INSTA, "posts")

print("\n--- ERGEBNIS CHECK (KI) ---")
# Prüfen wir mal die Gastro-Nische
try:
    conn = sqlite3.connect(DB_RESULTS)
    cursor = conn.cursor()
    # List all tables to see which niches exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for t in tables:
        table_name = t[0]
        cursor.execute(f"SELECT count(*) FROM {table_name}")
        c = cursor.fetchone()[0]
        print(f"📊 {table_name}: {c} Trends gefunden")
    conn.close()
except:
    print("Trend DB noch nicht bereit.")
