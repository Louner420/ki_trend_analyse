# 1. Basis-Image: Schlankes Python 3.9 (Ideal für Performance)
FROM python:3.9-slim

# 2. Arbeitsverzeichnis im Container festlegen
WORKDIR /app

# 3. System-Tools installieren (wichtig für einige KI/Daten-Libraries)
# Wir löschen den Cache danach direkt, um das Image klein zu halten.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 4. ZUERST die globale requirements.txt kopieren
# Docker merkt sich diesen Schritt. Wenn du nur Code änderst, 
# wird dieser zeitintensive Schritt beim nächsten Mal übersprungen.
COPY requirements.txt .

# 5. Alle Libraries installieren
RUN pip install --no-cache-dir -r requirements.txt

# 6. Das GESAMTE Projekt kopieren
# Kopiert web/, scraper/, ki_logic/ und alle anderen Ordner.
COPY . .

# 7. Port für Flask standardmäßig freigeben
EXPOSE 5000

# 8. Standard-Startbefehl (wird in docker-compose.yml pro Dienst überschrieben)
# Hier setzen wir die Web-App als Standard.
CMD ["python", "web/run.py"]
