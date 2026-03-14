import sqlite3
import os
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# PFAD-LOGIK FÜR DOCKER ANPASSEN
# ==========================================
# 1. Hole DATA_PATH aus der Umgebungsvariable (in deiner YAML: /app/database)
# 2. Fallback auf den lokalen "data" Ordner, falls man es ohne Docker testet.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_PATH", os.path.join(BASE_DIR, "data"))

# Sicherstellen, dass der Ordner existiert (erstellt /app/database im Container)
os.makedirs(DATA_DIR, exist_ok=True)

def get_db_path(db_filename):
    # Verhindert, dass Pfade doppelt verkettet werden, falls db_filename schon ein Pfad ist
    if os.path.isabs(db_filename):
        return db_filename
    return os.path.join(DATA_DIR, db_filename)

# ==========================================
# REST DES CODES BLEIBT GLEICH
# ==========================================

def save_to_db(data_list, db_filename, table_name):
    """
    Speichert Daten (vom Scraper) in die DB.
    Nutzt intelligente Upsert-Logik und automatische Tabellen-Erweiterung (Schema Evolution).
    """
    if not data_list:
        return

    db_path = get_db_path(db_filename)
    # Ab hier bleibt die Logik identisch...
    conn = sqlite3.connect(db_path)
    # ... (Rest der Funktion unverändert)