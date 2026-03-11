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


def run_scraper():
    print("[Daemon] TikTok Scraper gestartet (KI-Analyse laeuft per Cron/Service separat)...")

    while True:
        print("\n[Daemon] ------------------------------------------------")
        print("[Daemon] Starte TikTok Multitasking (Ziel: 150 Videos)...")

        try:
            tiktok_data = asyncio.run(get_trending_dict(count=150))

            if tiktok_data:
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
