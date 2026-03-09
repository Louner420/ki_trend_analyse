from app import create_app
import sqlite3

def init_log_db():
    conn = sqlite3.connect('/app/database/logs.db')
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
    # host="0.0.0.0" = von allen Schnittstellen erreichbar (für Raspi/Zugriff im Netz + Port-Weiterleitung)
    # Wenn Port 5000 rumspinnt, kannst du hier z.B. 5001 eintragen.
    app.run(debug=True, host="0.0.0.0", port=5002)
