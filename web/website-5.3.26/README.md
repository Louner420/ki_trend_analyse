# TrendDash (MVP)

## Setup (macOS/Linux)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

## Setup (Windows)
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

## Start
python run.py
# auf dem Raspberry Pi:
# python run.py  (oder in run.py host='0.0.0.0' setzen)

## Struktur
- Topbar, Sidebar, KPI-Row, Chart-Platzhalter, Tabelle
- Route "/" (Dashboard), "/trends" (Platzhalter)
