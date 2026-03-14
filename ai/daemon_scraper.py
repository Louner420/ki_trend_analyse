import time
import random
import asyncio
import sys
import os
import subprocess

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
        
        new_data_available = False
        try:
            tiktok_data = asyncio.run(get_trending_dict(count=150))
            
            if tiktok_data:
                # GEÄNDERT: Nutze den absoluten Pfad zum Volume
                db_path = os.path.join(DB_DIR, "raw_tiktok.db")
                save_to_db(tiktok_data, db_path, "videos")
                
                print(f"[Daemon] ✅ TikTok: {len(tiktok_data)} Videos in {db_path} gespeichert.")
                new_data_available = True
            else:
                print("[Daemon] ⚠️ TikTok: Keine Daten in diesem Durchlauf.")
                
        except Exception as e:
            print(f"[Daemon-Error] TikTok Crash: {e}")

        if new_data_available:
            print(f"[Daemon] 🧠 Wecke den 'Koch' (KI-Analyse: {KI_SCRIPT_NAME})...")
            
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), KI_SCRIPT_NAME)
            
            if os.path.exists(script_path):
                try:
                    result = subprocess.run(
                        [sys.executable, script_path], 
                        capture_output=True, 
                        text=True,
                        check=False 
                    )
                    
                    if result.returncode == 0:
                        print("[Daemon] ✅ KI-Update erfolgreich abgeschlossen!")
                        print(f"[KI-Log] {result.stdout.strip()[-300:]}...") 
                    else:
                        print(f"[Daemon] ❌ KI-Fehler (Code {result.returncode}):")
                        print(result.stderr) 
                        
                except Exception as e:
                    print(f"[Daemon-Error] Konnte KI-Skript nicht starten: {e}")
            else:
                print(f"[Daemon] ⚠️ WARNUNG: Skript '{KI_SCRIPT_NAME}' nicht gefunden!")
        else:
            print("[Daemon] Kein KI-Update nötig (keine neuen Daten).")

        sleep_minutes = random.randint(4, 10)
        print(f"[Daemon] 💤 Schlafe für {sleep_minutes} Minuten...")
        time.sleep(sleep_minutes * 60)

if __name__ == "__main__":
    run_scraper()
