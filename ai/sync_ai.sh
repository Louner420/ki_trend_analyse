#!/bin/bash

# --- KONFIGURATION ---
SERVER_USER="thomasortner@students.htlinn.local"
SERVER_IP="10.10.11.11"
SERVER_DIR="~/Diplomarbeit/trend-dashboard-backend-diplomarbeit-final"
# ---------------------

echo "🧹 [0/3] Bereinige Datenbank von Scraper-Duplikaten..."
source ~/projects/ai/venv/bin/activate && python3 ~/projects/ai/data/clean_db.py

echo "🚀 [1/3] Sende Datenbanken zum Schulserver..."
scp ~/projects/ai/data/raw_tiktok.db $SERVER_USER@$SERVER_IP:$SERVER_DIR/data/raw_tiktok.db
scp ~/projects/ai/data/users.db $SERVER_USER@$SERVER_IP:$SERVER_DIR/data/users.db  # NEU!

echo "🧠 [2/3] Wecke die Heavy-AI (Clustering) auf dem Server..."
# SSH-Aufruf 1: Nur das Clustering. Mit -u sehen wir es live!
ssh $SERVER_USER@$SERVER_IP "cd $SERVER_DIR && source venv/bin/activate && python3 -u daemon_ai.py"

echo "🤖 Starte LLM Content-Agent (Llama 3)..."
# SSH-Aufruf 2: Nur die Textgenerierung. Verhindert SSH-Timeouts.
ssh $SERVER_USER@$SERVER_IP "cd $SERVER_DIR && source venv/bin/activate && python3 -u content_agent.py"

echo "📥 [3/3] Lade veredelte Datenbank UND alle User-JSON-Dateien zurück..."
scp $SERVER_USER@$SERVER_IP:$SERVER_DIR/data/raw_tiktok.db ~/projects/ai/data/raw_tiktok.db
scp $SERVER_USER@$SERVER_IP:$SERVER_DIR/data/trends_user_*.json ~/projects/ai/data/  # NEU: Lädt alle User-Dateien!

echo "✅ FERTIG! Andi hat jetzt die neuesten KI-Trends (getrennt nach Titel & Leitfaden) im Dashboard."