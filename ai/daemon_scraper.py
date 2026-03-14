import time
import random
import asyncio
import sys
import os

# Pfad setzen
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importe
from database_manager import save_to_db
from tiktok_scraper import get_trending_dict

# NEU: Hole den Pfad aus der Docker-Umgebungsvariable
# Falls lokal ausgeführt, wird das aktuelle Verzeichnis genutzt.
DB_DIR = os.getenv("DATA_PATH", os.path.dirname(os.path.abspath(__file__)))

# KONFIGURATION: Das Skript, das die KI steuert
KI_SCRIPT_NAME = "manual_ai_test.py"

def run_scraper():
    print(f"[Daemon] High-Performance Scraper gestartet (Pfad: {DB_DIR})...")

    while True:
        print("\n[Daemon] ------------------------------------------------")
        print("[Daemon] Starte TikTok Multitasking (Ziel: 150 Videos)...")

        try:
            tiktok_data = asyncio.run(get_trending_dict(count=150))

            if tiktok_data:
                # GEÄNDERT: Nutze den absoluten Pfad zum Volume
                db_path = os.path.join(DB_DIR, "raw_tiktok.db")
                save_to_db(tiktok_data, db_path, "videos")
                
                print(f"[Daemon] ✅ TikTok: {len(tiktok_data)} Videos in {db_path} gespeichert.")
                new_data_available = True
                save_to_db(tiktok_data, "raw_tiktok.db", "videos")
                print(f"[Daemon] ✅ {len(tiktok_data)} neue Videos gespeichert.")
            else:
                print("[Daemon] ⚠️ Keine Daten in diesem Durchlauf.")

        except Exception as e:
            print(f"[Daemon-Error] TikTok Crash: {e}")

        sleep_minutes = random.randint(4, 10)
        print(f"[Daemon] 💤 Schlafe für {sleep_minutes} Minuten...")
        time.sleep(sleep_minutes * 60)

if __name__ == "__main__":
    run_scraper()
