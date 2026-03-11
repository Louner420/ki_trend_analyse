#!/bin/bash
set -euo pipefail

# --- KONFIGURATION ---
SERVER_USER="thomasortner@students.htlinn.local"
SERVER_IP="10.10.11.11"
SERVER_PORT="${SERVER_PORT:-22}"
SERVER_DIR_REL="Diplomarbeit/trend-dashboard-backend-diplomarbeit-final"
DEPLOY_CODE="${DEPLOY_CODE:-1}"
STOP_AFTER_VERIFY="${STOP_AFTER_VERIFY:-0}"
# ---------------------

# Passwort aus auth.txt lesen (Zeile 2), nicht im Script hardcoden
AUTH_FILE="$HOME/projects/auth.txt"
if [[ ! -f "$AUTH_FILE" ]]; then
	echo "❌ auth.txt fehlt: $AUTH_FILE"
	exit 1
fi
export SSHPASS
SSHPASS="$(sed -n '2p' "$AUTH_FILE")"
if [[ -z "$SSHPASS" ]]; then
	echo "❌ Kein Passwort in Zeile 2 von $AUTH_FILE"
	exit 1
fi

SSH_OPTS=(
	-o Port="$SERVER_PORT"
	-o ConnectTimeout=10
	-o StrictHostKeyChecking=accept-new
	-o ServerAliveInterval=30
	-o ServerAliveCountMax=6
	-o User="$SERVER_USER"
)

_ssh()  { sshpass -e ssh  "${SSH_OPTS[@]}" "$SERVER_IP" "$@"; }
_scp()  { sshpass -e scp  "${SSH_OPTS[@]}" "$@"; }

require_file() {
	if [[ ! -f "$1" ]]; then
		echo "❌ Datei fehlt: $1"
		exit 1
	fi
}

deploy_remote_file() {
	local source_path="$1"
	local target_rel_path="$2"
	if [[ -f "$source_path" ]]; then
		_ssh "mkdir -p '$REMOTE_DIR/$(dirname "$target_rel_path")'"
		_scp "$source_path" "$SERVER_IP:$REMOTE_DIR/$target_rel_path"
	else
		echo "⚠️ Deploy übersprungen, Datei fehlt lokal: $source_path"
	fi
}

deploy_dir_py() {
	local source_dir="$1"
	local target_dir_rel="$2"
	if [[ ! -d "$source_dir" ]]; then
		echo "⚠️ Deploy übersprungen, Ordner fehlt lokal: $source_dir"
		return
	fi
	_ssh "mkdir -p '$REMOTE_DIR/$target_dir_rel'"
	while IFS= read -r -d '' file; do
		local rel_path="${file#$source_dir/}"
		local target_rel_path="$target_dir_rel/$rel_path"
		_ssh "mkdir -p '$REMOTE_DIR/$(dirname "$target_rel_path")'"
		_scp "$file" "$SERVER_IP:$REMOTE_DIR/$target_rel_path"
	done < <(find "$source_dir" -type f -name '*.py' -print0)
}

verify_remote_file() {
	local source_path="$1"
	local target_rel_path="$2"
	local local_size remote_size
	if [[ ! -f "$source_path" ]]; then
		echo "⚠️ Verify übersprungen, lokal fehlt: $source_path"
		return 1
	fi
	if ! _ssh "test -f '$REMOTE_DIR/$target_rel_path'"; then
		echo "❌ Verify fehlgeschlagen, remote fehlt: $target_rel_path"
		return 1
	fi
	local_size="$(wc -c < "$source_path" | tr -d ' ')"
	remote_size="$(_ssh "wc -c < '$REMOTE_DIR/$target_rel_path'" | tr -d ' ')"
	if [[ "$local_size" != "$remote_size" ]]; then
		echo "❌ Verify Size-Mismatch: $target_rel_path (lokal=$local_size, remote=$remote_size)"
		return 1
	fi
	echo "✅ Verify ok: $target_rel_path ($remote_size bytes)"
	return 0
}

verify_deploy_batch() {
	local failed=0
	verify_remote_file "$HOME/projects/ai/database_manager.py" "database_manager.py" || failed=1
	verify_remote_file "$HOME/projects/ai/main.py" "main.py" || failed=1
	verify_remote_file "$HOME/projects/content_agent.py" "content_agent.py" || failed=1
	verify_remote_file "$HOME/projects/ai/advanced_ai/daemon_ai.py" "daemon_ai.py" || failed=1
	verify_remote_file "$HOME/projects/ai/advanced_ai/feature_pipeline.py" "feature_pipeline.py" || failed=1
	verify_remote_file "$HOME/projects/ai/advanced_ai/trend_scoring.py" "trend_scoring.py" || failed=1
	verify_remote_file "$HOME/projects/ai/advanced_ai/clustering_model.py" "clustering_model.py" || failed=1
	if [[ "$failed" -ne 0 ]]; then
		echo "❌ Deploy-Verify fehlgeschlagen. Abbruch, damit kein alter Remote-Code läuft."
		exit 1
	fi
}

echo "🔎 Preflight: Prüfe VPN/SSH-Verbindung..."
if ! ip -brief a | grep -q '^tun'; then
	echo "❌ Kein VPN-Tunnel aktiv (kein tun-Interface gefunden)."
	echo "   Bitte OpenVPN mit schule.ovpn starten und erneut ausführen."
	exit 1
fi

if ! timeout 5 bash -lc "cat < /dev/null > /dev/tcp/$SERVER_IP/$SERVER_PORT"; then
	echo "❌ Schulserver $SERVER_IP:$SERVER_PORT ist nicht erreichbar."
	echo "   VPN aktiv, aber keine Route/Firewall/Server erreichbar."
	echo "   Tipp: Wenn VPN nur am PC läuft, nutze Reverse-Tunnel und setze SERVER_IP=127.0.0.1 SERVER_PORT=10022"
	exit 1
fi

REMOTE_HOME="$(_ssh 'printf %s "$HOME"')"
if [[ -z "$REMOTE_HOME" ]]; then
	echo "❌ Konnte Remote-HOME nicht ermitteln."
	exit 1
fi
REMOTE_DIR="$REMOTE_HOME/$SERVER_DIR_REL"
_ssh "mkdir -p '$REMOTE_DIR/data'"

require_file "$HOME/projects/database/raw_tiktok.db"
require_file "$HOME/projects/database/users.db"

echo "🧹 [0/3] Bereinige Datenbank von Scraper-Duplikaten..."
cd "$HOME/projects/ai"
source venv/bin/activate
python3 clean_db_deduplicate.py

if [[ "$DEPLOY_CODE" == "1" ]]; then
	echo "📦 [0.5/3] Synchronisiere aktuelle KI-Skripte auf den Schulserver..."
	deploy_remote_file "$HOME/projects/ai/database_manager.py" "database_manager.py"
	deploy_remote_file "$HOME/projects/ai/main.py" "main.py"
	deploy_remote_file "$HOME/projects/content_agent.py" "content_agent.py"
	deploy_dir_py "$HOME/projects/ai/advanced_ai" "advanced_ai"
	deploy_remote_file "$HOME/projects/ai/advanced_ai/daemon_ai.py" "daemon_ai.py"
	deploy_remote_file "$HOME/projects/ai/advanced_ai/trend_scoring.py" "trend_scoring.py"
	deploy_remote_file "$HOME/projects/ai/advanced_ai/feature_pipeline.py" "feature_pipeline.py"
	deploy_remote_file "$HOME/projects/ai/advanced_ai/clustering_model.py" "clustering_model.py"
	echo "🔍 [0.6/3] Verifiziere Deploy auf dem Schulserver..."
	verify_deploy_batch
fi

if [[ "$STOP_AFTER_VERIFY" == "1" ]]; then
	echo "🧪 Dry-Run abgeschlossen: Deploy + Verify erfolgreich (Heavy-AI übersprungen)."
	exit 0
fi

echo "🚀 [1/3] Sende Datenbanken zum Schulserver..."
_scp "$HOME/projects/database/raw_tiktok.db" "$SERVER_IP:$REMOTE_DIR/data/raw_tiktok.db"
_scp "$HOME/projects/database/users.db" "$SERVER_IP:$REMOTE_DIR/data/users.db"

echo "🧠 [2/3] Wecke die Heavy-AI (Clustering) auf dem Server..."
_ssh "cd '$REMOTE_DIR' && source venv/bin/activate && AI_RUN_ONCE=1 python3 -u daemon_ai.py"

echo "🤖 Starte LLM Content-Agent (Llama 3)..."
_ssh "cd '$REMOTE_DIR' && source venv/bin/activate && python3 -u content_agent.py"

echo "📥 [3/3] Lade veredelte Datenbank UND alle User-JSON-Dateien zurück..."
_scp "$SERVER_IP:$REMOTE_DIR/data/raw_tiktok.db" "$HOME/projects/database/raw_tiktok.db"
if _ssh "test -f '$REMOTE_DIR/data/trend_results.db'"; then
	_scp "$SERVER_IP:$REMOTE_DIR/data/trend_results.db" "$HOME/projects/database/trend_results.db"
elif _ssh "test -f '$REMOTE_HOME/database/trend_results.db'"; then
	_scp "$SERVER_IP:$REMOTE_HOME/database/trend_results.db" "$HOME/projects/database/trend_results.db"
else
	echo "⚠️ trend_results.db nicht gefunden (weder $REMOTE_DIR/data noch $REMOTE_HOME/database)."
fi
rm -f "$HOME/projects/database/trends_user_"*.json
_scp "$SERVER_IP:$REMOTE_DIR/data/trends_user_*.json" "$HOME/projects/database/"

echo "✅ FERTIG! Andi hat jetzt die neuesten KI-Trends (getrennt nach Titel & Leitfaden) im Dashboard."