from app import create_app, socketio
import sqlite3
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.getenv("DATA_PATH", os.path.join(PROJECT_ROOT, "database"))

def init_log_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(os.path.join(DATA_DIR, "logs.db"))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ip TEXT,
            method TEXT,
            path TEXT,
            status_code INTEGER,
            response_time REAL,
            error TEXT
        )
    """)
    conn.commit()
    conn.close()

app = create_app()

if __name__ == "__main__":
    init_log_db()
    debug_mode = os.getenv("FLASK_DEBUG", "0") in ("1", "true", "True")
    # host="0.0.0.0" = von allen Schnittstellen erreichbar (für Raspi/Zugriff im Netz + Port-Weiterleitung)
    # Wenn Port 5000 rumspinnt, kannst du hier z.B. 5001 eintragen.
    socketio.run(app, debug=debug_mode, host="0.0.0.0", port=5002, allow_unsafe_werkzeug=True)
