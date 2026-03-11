import sqlite3
import pandas as pd
import os

# Pfad zur DB (Monorepo-Struktur)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DB_DIR = os.path.join(PROJECT_ROOT, "database")
db_path = os.path.join(DB_DIR, "raw_tiktok.db")

def check_table(table_name):
    print(f"\n--- PRÜFE TABELLE: {table_name} ---")
    conn = sqlite3.connect(db_path)
    try:
        # Wir laden nur die Profi-Spalten
        df = pd.read_sql_query(f"SELECT caption, trend_score, sentiment, velocity FROM {table_name} LIMIT 5", conn)
        
        if df.empty:
            print("⚠️ Tabelle ist leer.")
        else:
            # Schönere Ausgabe
            print(df.to_string(index=False))
            print("\n✅ TEST BESTANDEN: Daten sind da!")
    except Exception as e:
        print(f"❌ Fehler (evtl. Spalte fehlt noch): {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    if os.path.exists(db_path):
        # Wir prüfen General und eine Nische
        check_table("top10_general")
        check_table("top10_fashion") # Oder eine andere Nische, die du hast
    else:
        print("Datenbank nicht gefunden!")
