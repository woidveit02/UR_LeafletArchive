# UR_LeafletArchive: UR Flugblattsammlung

## Beschreibung

Eine einfache FastAPI-Website zum Durchsuchen und Betrachten der verschiedenen Flugblätter der Flugblattsammlung des Archivs der Universität Regensburg. 

Dass ganze Projekt wurde mit Visual Studio Code erstellt, dieses wurde zudem mit einigen Extensions modifiziert, darunter die `Container Tools` für Docker und einige Python-Extensions von Microsoft, der `REST Client` von Huachao Mao und der `SQLite Viewer` von Florian Klampfer.

## Getting Started / Bedienung

Um den Docker-Container und damit die Anwendung zu starten, einfach `docker compose up` ausführen, dann ist die Anwendung unter http://localhost:8000/ verfügbar.
Zum Erstellen & Füllen der Datenbank einfach die `main.py` ausführen (vorher ggf. die bestehende Datenbank löschen). Das ist nach jedem `git pull` nötig, wenn sich die Daten in `data/` geändert haben (siehe nächster Abschnitt).

## Daten & Synchronisation

Rohdaten (PDFs) liegen in Drive, nicht in Git. `data/*.json` ist maßgeblich und liegt in Git. Die generierte `leaflet_database.db` liegt nicht in Git – nach jedem Pull mit Änderungen in `data/`: alte `.db` löschen, `main.py` neu ausführen.

## Git Commits

Möglichst an `Conventional Commits`-Richtlinien halten.

## PyTest & PyCodeStyle

Es gibt eine Datei für Tests mit `PyTest`, dazu einfach `pytest` in der Konsole ausführen.
Die Korrektheit der Code-Formatierung erfolgt mittels `PyCodeStyle`, dazu einfach `pycodestyle .` für alle Dateien oder `pycodestyle <Name der Datei>.py` ausführen.

## Projektstruktur

```
.
├── data/ # Ordner für alle vorgegebenen Testdaten
│   └── leaflets.json # JSON-Dateien mit Testdaten
├── src/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── database/
│   │   │   │   ├── base.py
│   │   │   │   ├── createDatabase.py # Erstellung der DB
│   │   │   │   ├── fillDatabase.py # Füllt DB mit Elementen aus JSONs
│   │   │   │   ├── models.py # DB-Struktur
│   │   │   │   └── session.py 
│   │   │   ├── app_helper.py # Ausgelagerte Hilfsfunktionen für app.py
│   │   │   ├── app.py # Backend-Script (startet Anwendung im Container)
│   │   │   └── main.py # Zentrales Script zu Erstellung der DB
│   │   ├── logs/
│   │   ├── tests/ # Alle Testdateien mit Unit-Tests
│   │   ├──Dockerfile
│   │   ├──requirements.txt # Benötigte Python-Packages
│   │   └──leaflet_database.db # Datenbank (von main.py erstellt, nicht in Git)
│   └── frontend/
│       ├── static/ # Stylesheet
│       └── templates/ # Alle HTML-Templates für FastAPI
├── .gitignore
├── docker-compose.yml
├── LICENCE # MIT-Lizenz
└── README.md
```