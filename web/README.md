# TrendDash

## Setup
```bash
cd ~/projects/web
./run.sh
```

`run.sh` erstellt bei Bedarf automatisch eine lokale virtuelle Umgebung unter `.venv_local`, installiert die Abhaengigkeiten und startet die Website auf Port `5002`.

## Aufruf
```text
http://127.0.0.1:5002/login
```

## Wichtige Routen
- `/login`
- `/register`
- `/`
- `/trends`
- `/tasks`
- `/planner`
- `/planner/month`
- `/settings`

## Datenhaltung
Die Web-App liest ihre SQLite-Dateien standardmaessig aus dem zentralen Monorepo-Ordner `~/projects/database`.
In Docker kann stattdessen `DATA_PATH` gesetzt werden.
