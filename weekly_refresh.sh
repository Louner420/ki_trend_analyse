#!/usr/bin/env bash
# weekly_refresh.sh – Wöchentliche Pipeline: Cleanup + Trend-Regenerierung
# Aufgerufen per Cron: Sonntag 03:00 Uhr
set -e

PROJ="/home/pi/projects"
VENV="/home/pi/projects/ai/venv/bin/python3"
LOG="/home/pi/projects/logs/weekly_refresh.log"

mkdir -p "$(dirname "$LOG")"

echo "=======================================" >> "$LOG"
echo "[$(date)] Wöchentliches Refresh gestartet" >> "$LOG"

# 1. Alte Videos loeschen (>7 Tage)
echo "[$(date)] Schritt 1: Cleanup alte Videos..." >> "$LOG"
$VENV "$PROJ/ai/cleanup.py" >> "$LOG" 2>&1 || echo "[WARN] cleanup.py fehlgeschlagen" >> "$LOG"

# 2. Trend-Cluster + User-JSONs via Schulserver (Heavy-AI + LLM)
echo "[$(date)] Schritt 2: Sync mit Schulserver (HDBSCAN + Content Agent)..." >> "$LOG"
bash "$PROJ/ai/run_sync.sh" >> "$LOG" 2>&1 || echo "[WARN] run_sync.sh fehlgeschlagen" >> "$LOG"

# 3. Log-DBs bereinigen (>30 Tage loeschen)
echo "[$(date)] Schritt 3: Log-DBs bereinigen..." >> "$LOG"
for db in "$PROJ/database/logs.db" "$PROJ/database/error.db"; do
    if [ -f "$db" ]; then
        sqlite3 "$db" "DELETE FROM logs WHERE timestamp < datetime('now', '-30 days');" 2>/dev/null
        sqlite3 "$db" "VACUUM;" 2>/dev/null
        echo "  Bereinigt: $(basename "$db")" >> "$LOG"
    fi
done

# 4. Log-Rotation: Nur letzte 500 Zeilen behalten
if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 500 ]; then
    tail -500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

echo "[$(date)] Refresh abgeschlossen." >> "$LOG"
echo "=======================================" >> "$LOG"
