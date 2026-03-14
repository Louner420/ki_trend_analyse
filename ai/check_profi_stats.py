import sqlite3
import pandas as pd
import os

# PFAD-ANPASSUNG FÜR DOCKER VOLUME
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.getenv("DATA_PATH", os.path.join(BASE_DIR, "data"))
db_path = os.path.join(DB_DIR, "raw_tiktok.db")

def check_table(table_name):
    print(f"\n--- PRÜFE TABELLE: {table_name} ---")
    if not os.path.exists(db_path):
        print(f"❌ Datenbank-Datei fehlt unter: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    try:
        # Erst prüfen, welche Spalten existieren, um Fehler zu vermeiden
        check_cols = pd.read_sql_query(f"PRAGMA table_info({table_name})", conn)
        existing_cols = check_cols['name'].tolist()
        
        # Nur Spalten wählen, die auch wirklich existieren
        target_cols = [c for c in ['caption', 'trend_score', 'sentiment', 'velocity'] if c in existing_cols]
        
        if not target_cols:
            print(f"⚠️ Tabelle {table_name} existiert, hat aber keine der gesuchten Spalten.")
            return

        query = f"SELECT {', '.join(target_cols)} FROM {table_name} LIMIT 5"
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print(f"⚠️ Tabelle '{table_name}' ist leer.")
        else:
            print(df.to_string(index=False))
            print(f"\n✅ TEST BESTANDEN: {len(df)} Zeilen gefunden.")
            
    except Exception as e:
        print(f"❌ Fehler bei Tabelle {table_name}: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # Prüfe verschiedene mögliche Tabellen
    check_table("videos")          # Die Rohdaten vom Scraper
    check_table("top10_general")   # KI-Ergebnisse
    check_table("top10_fashion")   # Nischen-Ergebnisse