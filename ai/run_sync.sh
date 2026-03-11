#!/bin/bash
# run_sync.sh – VPN sicherstellen & sync_ai.sh ausfuehren
# Aufruf per Cron oder manuell
set -euo pipefail

LOG="/home/pi/projects/logs/sync.log"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

log "=== Sync gestartet ==="

# 1. VPN prüfen / starten
if ! ip -brief a 2>/dev/null | grep -q '^tun'; then
	log "VPN nicht aktiv, starte OpenVPN..."
	cd /home/pi/projects
	sudo openvpn --config schule.ovpn --daemon --log /tmp/openvpn_cron.log
	sleep 8
	if ! ip -brief a 2>/dev/null | grep -q '^tun'; then
		log "❌ VPN konnte nicht gestartet werden. Abbruch."
		exit 1
	fi
	log "VPN gestartet."
fi

# 2. Sync ausfuehren
log "Starte sync_ai.sh..."
cd /home/pi/projects/ai
if bash sync_ai.sh >> "$LOG" 2>&1; then
	log "✅ Sync erfolgreich abgeschlossen."
else
	log "❌ sync_ai.sh fehlgeschlagen (Exit $?)."
	exit 1
fi

# 3. Log-Rotation (max 2000 Zeilen)
if [[ -f "$LOG" ]] && [[ "$(wc -l < "$LOG")" -gt 2000 ]]; then
	tail -1000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

log "=== Sync beendet ==="
