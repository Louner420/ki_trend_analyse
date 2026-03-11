# Website QA Checkliste (Visuell + Funktion)

Datum: __________
Tester: __________
Build/Stand: __________

## 1) Basis & Erreichbarkeit
- [ ] Website lädt unter http://127.0.0.1:5002 ohne 5xx-Fehler.
- [ ] Login-Seite ist erreichbar und vollständig gerendert.
- [ ] Keine kaputten Assets (CSS/JS/Icons) im Browser sichtbar.
- [ ] Browser-Konsole hat keine roten Fehler beim ersten Laden.

## 2) Auth Flow
- [ ] Registrierung mit neuem Testuser funktioniert.
- [ ] Nach Registrierung erfolgt Weiterleitung zum Onboarding.
- [ ] Onboarding speichern funktioniert ohne Fehlermeldung.
- [ ] Nach Onboarding landet man im Dashboard.
- [ ] Logout funktioniert und schützt private Seiten.
- [ ] Nicht eingeloggter Zugriff auf /, /trends, /tasks, /planner leitet auf Login um.

## 3) Dashboard (Visuell)
- [ ] Header, Titel, Cards und Abstände wirken sauber und konsistent.
- [ ] Keine abgeschnittenen Texte in Trend-Cards.
- [ ] Zahlenformate wirken korrekt (Hype, Velocity, Engagement, Sentiment).
- [ ] Keine Platzhalter-Artefakte (None/null) im sichtbaren UI.
- [ ] Modal/Overlays öffnen und schließen sauber (inkl. ESC/Close-Button falls vorhanden).

## 4) Trends Seite (Daten + UX)
- [ ] Seite /trends lädt ohne Fehler.
- [ ] Sektionen werden angezeigt:
  - Top Trends deiner Nische
  - Rising Trends
  - Content Opportunities
  - Globale Trends
- [ ] Trend-Karten sind klickbar und zeigen Details.
- [ ] Sortierung wirkt plausibel (Top Trends nach Hype, Rising nach Velocity).
- [ ] Keine leeren Karten bei vorhandener Datenbank.
- [ ] Bei fehlenden Daten: Seite zeigt Fallback ohne 500.

## 5) AI Ideen & Refine
- [ ] AI Ideen sind sichtbar und öffnen korrekt Detail-Interaktion.
- [ ] Refine/Verbessern Aktion funktioniert aus der Website heraus.
- [ ] Erfolgsantwort zeigt sinnvollen verfeinerten Text.
- [ ] Fehlerfall (AI API aus) zeigt verständliche Fehlermeldung statt Absturz.

## 6) Datenaktualität
- [ ] Nach Sync sind neue Daten sichtbar (nicht nur alte Trends).
- [ ] Stichprobe: Werte auf Dashboard/Trends entsprechen aktueller trend_results.db.
- [ ] User-spezifische Ideen entsprechen aktuellem Nutzerkontext (falls relevant).

## 7) Navigation & Funktionen
- [ ] Navigation zwischen Dashboard, Trends, Planner, Tasks, Settings funktioniert.
- [ ] Zurück/Vorwärts im Browser erzeugt keine kaputten Zustände.
- [ ] Formulare behalten erwartetes Verhalten (Validierung, Fehlermeldungen, Erfolgsmeldung).

## 8) Responsive Check
- [ ] Desktop (>= 1280px): Layout stabil, keine Überlappungen.
- [ ] Tablet (~768px): Cards umbrechen sinnvoll, Navigation bleibt nutzbar.
- [ ] Mobile (~390px): Keine horizontalen Scrollbalken, Buttons ausreichend groß.
- [ ] Modals sind auf Mobile komplett bedienbar.

## 9) Performance (kurzer Smoke-Test)
- [ ] Erste Seite lädt subjektiv schnell (< 3s lokal).
- [ ] Seitenwechsel zwischen Kernseiten ohne spürbare Hänger.
- [ ] Kein dauerhaftes Spinner-Hängenbleiben.

## 10) Regression Quick Checks nach jedem Sync
- [ ] Register + Login + Onboarding mit neuem User funktioniert.
- [ ] /trends lädt und zeigt Trend-Karten.
- [ ] Refine Endpoint aus UI funktioniert.
- [ ] Keine 500er in Web-Logs während des Tests.

## 11) Abnahme
- [ ] Visuell freigegeben.
- [ ] Funktional freigegeben.
- [ ] Keine Blocker offen.

Offene Punkte / Bugs:
- ______________________________________________
- ______________________________________________
- ______________________________________________
