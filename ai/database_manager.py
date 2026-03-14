import sqlite3
import os
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# PFAD-LOGIK FÜR DOCKER
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_PATH", os.path.join(BASE_DIR, "data"))

os.makedirs(DATA_DIR, exist_ok=True)

def get_db_path(db_filename):
    if os.path.isabs(db_filename):
        return db_filename
    return os.path.join(DATA_DIR, db_filename)

# ==========================================
# ROBUSTE SPEICHER- & LADE-FUNKTIONEN
# ==========================================

def save_to_db(data_list, db_filename, table_name):
    """Speichert Daten im Volume und repariert Tabellenstruktur bei Bedarf."""
    if not data_list:
        print("[DB] Keine Daten zum Speichern erhalten.")
        return

    db_path = get_db_path(db_filename)
    conn = sqlite3.connect(db_path)
    
    try:
        df = pd.DataFrame(data_list) if not isinstance(data_list, pd.DataFrame) else data_list
        
        # Sicherstellen, dass alle Spalten als Strings/Zahlen gespeichert werden (keine Dicts)
        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
                df[col] = df[col].astype(str)

        # Speichern mit 'append'. Falls Spalten fehlen, nutzt SQL-Alchemy/Pandas Schema-Evolution
        df.to_sql(table_name, conn, if_exists='append', index=False)
        conn.commit()
        print(f"[DB] ✅ {len(df)} Zeilen erfolgreich in '{table_name}' hinzugefügt. (Datei: {db_path})")
    except Exception as e:
        print(f"[DB Error] Fehler beim Speichern: {e}")
        # Notfall: Wenn Schema-Konflikt (z.B. neue Spalten), Tabelle mit 'replace' neu anlegen
        if "table" in str(e).lower() or "column" in str(e).lower():
            print("[DB] Versuche Schema-Reparatur (replace)...")
            df.to_sql(table_name, conn, if_exists='replace', index=False)
    finally:
        conn.close()

def load_recent_data(hours=48, db_filename="raw_tiktok.db", table_name="videos"):
    """Lädt Daten. Ignoriert Datum-Filter, wenn Datei alt ist."""
    db_path = get_db_path(db_filename)
    
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        print(f"[Warnung] Datenbank '{db_filename}' ist leer oder existiert nicht.")
        return pd.DataFrame()
    
    try:
        conn = sqlite3.connect(db_path)
        
        # 1. VERSUCH: Aktuelle Daten
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        try:
            query = f"SELECT * FROM {table_name} WHERE upload_date > ? ORDER BY upload_date DESC"
            df = pd.read_sql_query(query, conn, params=(cutoff,))
        except:
            df = pd.DataFrame()

        # 2. VERSUCH: Wenn 48h leer sind (wie bei dir aktuell), lade ALLES für die KI
        if df.empty:
            print("[Info] Keine aktuellen Daten gefunden. Lade stattdessen alle verfügbaren Einträge...")
            query_all = f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT 500"
            df = pd.read_sql_query(query_all, conn)
            
        conn.close()
        return df
    except Exception as e:
        print(f"[DB Error] Laden fehlgeschlagen: {e}")
        return pd.DataFrame()
