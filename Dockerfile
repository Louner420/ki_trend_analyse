# 1. Basis-Image direkt definieren (vermeidet Parse-Fehler)
FROM python:3.11.9-slim

# 2. Arbeitsverzeichnis im Container festlegen
WORKDIR /app

# 3. System-Tools und Playwright-Abhängigkeiten installieren
# Diese Bibliotheken sind zwingend erforderlich, damit der Browser im Container startet.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/* 

# 4. Requirements kopieren und Python-Pakete installieren
COPY requirements.txt . 

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu 

# 5. Playwright Browser-Installation
# Wir nutzen 'python -m', um den "Command not found" Fehler (127) zu umgehen.
RUN python -m playwright install chromium --with-deps

# 6. Das gesamte Projekt kopieren
COPY . . 

# 7. Standard-Startbefehl (wird in docker-compose überschrieben)
CMD ["python", "-u", "web/run.py"]