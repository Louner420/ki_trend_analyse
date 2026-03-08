# 1. Basis-Image: Schlankes Python 3.9 (Ideal für Performance)
ARG PYTHON_VERSION=3.11.9
FROM python:${PYTHON_VERSION}-slim

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
# Erst pip upgraden, dann die requirements, dann die CPU-Version von Torch
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
# 6. Das GESAMTE Projekt kopieren
# Kopiert web/, scraper/, ki_logic/ und alle anderen Ordner.
COPY . .

# 7. Port für Flask standardmäßig freigeben
EXPOSE 5000

# 8. Standard-Startbefehl (wird in docker-compose.yml pro Dienst überschrieben)
# Hier setzen wir die Web-App als Standard.
CMD ["python", "web/run.py"]
