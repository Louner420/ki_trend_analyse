# KI_Trend_Analyse
Flask-basiertes Web-Dashboard für KI-gestützte Trendanalyse (Diplomarbeit 2025

Wir untersuchen, wie sich Nischentrends auf Social Media und DSGVO-konform identifizieren lassen und welche Signale (zum Beispiel: Hashtags, Audio, Caption, Wachstumsraten, Interaktionsprofile) dafür am zuverlässigsten sind. Daraus leiten wir individuelle Schwerpunkte ab:

Andreas – Webinterface & Visual Analytics:

• Interviews mit Personen aus der Branche um herauszufinden wie die Oberfläche am besten zu designen ist.

• Informationsarchitektur und UI für ein Dashboard.

• Visualisierungen von Daten zum leichten Ablesen.

Thomas – KI & Backend-Analyse:

• Aufbau einer Datenpipeline zum Übertragen von Daten.

• Untersuchung von Methoden für Trend-Erkennung.

Maximilian – Recht & Datenzugang:

• Analyse rechtlicher Rahmenbedingungen.

• Erarbeitung eines Compliance-Konzepts inkl. Datenminimierung, Speicherfristen und Einwilligungs-/Interessenabwägung.

• Ableitung technischer Vorgaben.

Übergreifend prüfen wir, wie die erkannten Trends in konkrete Content-Vorschläge, Posting-Zeitpunkte und messbare Ziele (z. B. Reichweite/CTR) übersetzt werden können und welche Grenzen/Fehlerrisiken bestehen.

## Monorepo-Betrieb

### Datenverzeichnis
Alle zentralen Datenbanken und JSON-Artefakte liegen im Ordner `database/` im Projektwurzelverzeichnis.

### Schulserver-Sync
```bash
bash ~/projects/ai/sync_ai.sh
```

Optional kann der Code-Deploy auf den Schulserver deaktiviert werden:

```bash
DEPLOY_CODE=0 bash ~/projects/ai/sync_ai.sh
```

### API-Server starten
```bash
cp ~/projects/ai/.env.example ~/projects/ai/.env
nano ~/projects/ai/.env
bash ~/projects/ai/start_api.sh
```

Die Datei `ai/.env` muss mindestens `LLM_API_KEY=...` enthalten.

### Web-App starten
```bash
cd ~/projects/web
./run.sh
```

Danach ist die Website lokal unter `http://127.0.0.1:5002/login` erreichbar.
