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

# 2. Trend-Cluster + User-JSONs neu generieren
echo "[$(date)] Schritt 2: Content Agent (Trend-Clustering + AI-Ideen)..." >> "$LOG"
$VENV "$PROJ/content_agent.py" >> "$LOG" 2>&1 || echo "[WARN] content_agent.py fehlgeschlagen" >> "$LOG"

# 3. Log-Rotation: Nur letzte 500 Zeilen behalten
if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 500 ]; then
    tail -500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

echo "[$(date)] Refresh abgeschlossen." >> "$LOG"
echo "=======================================" >> "$LOG"
