import sqlite3
import os
import pandas as pd
from datetime import datetime, timedelta

# Pfad zum Daten-Ordner
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

def get_db_path(db_filename):
    return os.path.join(DATA_DIR, db_filename)

# ==========================================
# 1. HAUPTFUNKTIONEN
# ==========================================

def save_to_db(data_list, db_filename, table_name):
    """
    Speichert Daten (vom Scraper) in die DB.
    Nutzt intelligente Upsert-Logik und automatische Tabellen-Erweiterung (Schema Evolution).
    """
    if not data_list:
        return

    db_path = get_db_path(db_filename)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    first_item = data_list[0]
    columns = list(first_item.keys())
    
    # 1. Tabelle erstellen (falls sie noch gar nicht existiert)
    create_cols = []
    for col in columns:
        if col == "video_id":
            create_cols.append(f"{col} TEXT PRIMARY KEY")
        else:
            create_cols.append(f"{col} TEXT")
            
    create_query = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(create_cols)})"
    c.execute(create_query)

    # 2. Prüfen, ob neue Spalten (wie 'shares') dazu gekommen sind und vollautomatisch hinzufügen!
    c.execute(f"PRAGMA table_info({table_name})")
    existing_cols = [row[1] for row in c.fetchall()]
    
    for col in columns:
        if col not in existing_cols:
            try:
                c.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} TEXT")
                print(f"[DB-Manager] 🆕 Neue Spalte '{col}' zur Tabelle hinzugefügt.")
            except Exception as e:
                pass

    neu_count = 0
    update_count = 0

    for item in data_list:
        creator = str(item.get('creator', ''))
        caption = str(item.get('caption', ''))
        
        # 3. Prüfen, ob das Video (Creator + Caption) schon existiert
        c.execute(f"SELECT video_id FROM {table_name} WHERE creator = ? AND caption = ?", (creator, caption))
        existiert = c.fetchone()

        if existiert:
            # 4a. UPDATE: Dynamischen Update-Befehl bauen
            update_cols = []
            update_values = []
            for col in columns:
                if col not in ['creator', 'caption']: # Diese zwei als Suchkriterien auslassen
                    update_cols.append(f"{col} = ?")
                    update_values.append(str(item.get(col, "")))
            
            # Suchkriterien ans Ende der Werte-Liste hängen
            update_values.extend([creator, caption])
            
            update_query = f"UPDATE {table_name} SET {', '.join(update_cols)} WHERE creator = ? AND caption = ?"
            
            try:
                c.execute(update_query, update_values)
                update_count += 1
            except Exception as e:
                print(f"[DB-Error] Fehler beim Update: {e}")
        else:
            # 4b. INSERT: Echtes neues Video
            values = [str(item.get(col, "")) for col in columns]
            placeholders = ", ".join(["?"] * len(columns))
            col_names = ", ".join(columns)
            insert_query = f"INSERT OR REPLACE INTO {table_name} ({col_names}) VALUES ({placeholders})"
            
            try:
                c.execute(insert_query, values)
                neu_count += 1
            except Exception as e:
                print(f"[DB-Error] Fehler beim Insert: {e}")

    conn.commit()
    conn.close()
    print(f"[DB-Manager] 📊 {neu_count} neue Videos | 🔄 {update_count} Updates")

def load_recent_data(db_filename="raw_tiktok.db", table_name="videos", hours=48):
    """
    Lädt Daten für die KI. Akzeptiert 'hours' Parameter.
    """
    db_path = get_db_path(db_filename)
    if not os.path.exists(db_path):
        return pd.DataFrame()

    conn = sqlite3.connect(db_path)
    try:
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql_query(query, conn)
    except:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def save_niche_results(arg1, arg2):
    """
    Speichert KI-Ergebnisse.
    INTELLIGENT: Erkennt automatisch die Reihenfolge der Argumente.
    """
    # Automatische Erkennung: Was ist DataFrame, was ist Name?
    if isinstance(arg1, pd.DataFrame):
        df = arg1
        niche_name = arg2
    elif isinstance(arg2, pd.DataFrame):
        df = arg2
        niche_name = arg1
    else:
        print("[DB-Error] Kein DataFrame zum Speichern gefunden!")
        return

    # Fallback, falls Name kein String ist
    if not isinstance(niche_name, str):
        niche_name = "general"

    db_path = get_db_path("raw_tiktok.db")
    conn = sqlite3.connect(db_path)
    table_name = f"top10_{niche_name}"
    
    try:
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"[DB] Trends für '{niche_name}' gespeichert.")
    except Exception as e:
        print(f"[DB-Error] Fehler beim Speichern: {e}")
    finally:
        conn.close()

# ==========================================
# 2. LEGACY SUPPORT
# ==========================================

def init_dbs():
    pass

def save_raw_data(data, platform):
    if platform == "TikTok":
        save_to_db(data, "raw_tiktok.db", "videos")
    elif platform == "Instagram":
        save_to_db(data, "raw_instagram.db", "posts")
