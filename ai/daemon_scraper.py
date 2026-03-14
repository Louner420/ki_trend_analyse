import time
import random
import asyncio
import sys
import os
import subprocess

# Pfad setzen, damit Imports funktionieren
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_manager import save_to_db
from tiktok_scraper import get_trending_dict

# WICHTIG: Hole den Pfad aus der Docker-Umgebungsvariable
# DATA_PATH ist in deiner docker-compose.yml als /app/database definiert
DB_DIR = os.getenv("DATA_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))

# Sicherstellen, dass der Ordner existiert
os.makedirs(DB_DIR, exist_ok=True)

# Name des KI-Skripts für den automatischen Start nach dem Scrape
KI_SCRIPT_NAME = "manual_ai_test.py"

def run_scraper():
    print(f"[Daemon] 🚀 Scraper gestartet. Ziel-Verzeichnis: {DB_DIR}")

    while True:
        print("\n[Daemon] " + "-"*40)
        print("[Daemon] Starte TikTok-Abfrage (Ziel: 150 Videos)...")

        try:
            # Daten von TikTok abrufen
            tiktok_data = asyncio.run(get_trending_dict(count=150))

            if tiktok_data:
                # 1. Absoluten Pfad zur Datenbank im Volume erstellen
                db_path = os.path.join(DB_DIR, "raw_tiktok.db")
                
                # 2. Speichern NUR mit dem absoluten Pfad
                # Das sorgt dafür, dass die Daten im gemounteten Volume landen
                save_to_db(tiktok_data, db_path, "videos")
                
                print(f"[Daemon] ✅ Erfolg: {len(tiktok_data)} Videos in Volume gespeichert ({db_path}).")
                
                # 3. KI-Analyse automatisch triggern
                script_path = os.path.join(os.path.dirname(__file__), KI_SCRIPT_NAME)
                if os.path.exists(script_path):
                    print("[Daemon] Triggere KI-Analyse...")
                    subprocess.run([sys.executable, script_path], check=False)
                else:
                    print(f"[Daemon] ⚠️ KI-Skript nicht gefunden unter: {script_path}")
            else:
                print("[Daemon] ⚠️ Keine Daten von TikTok empfangen.")

        except Exception as e:
            print(f"[Daemon-Error] Kritischer Fehler im Loop: {e}")

        # Wartezeit zwischen den Scrapes (zufällig zwischen 4 und 10 Minuten)
        wait_time = random.randint(4, 10) * 60
        print(f"[Daemon] Nächster Scan in {wait_time // 60} Minuten...")
        time.sleep(wait_time)

if __name__ == "__main__":
    run_scraper()
