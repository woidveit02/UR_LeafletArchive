# UR_LeafletArchive: UR Flugblattsammlung

## Beschreibung

Eine einfache Flask-Website zum Durchsuchen und Betrachten der verschiedenen Flugblätter der Flugblattsammlung des Archivs der Universität Regensburg. 

Dass ganze Projekt wurde mit Visual Studio Code erstellt, dieses wurde zudem mit einigen Extensions modifiziert, darunter die `Container Tools` für Docker und einige Python-Extensions von Microsoft, der `REST Client` von Huachao Mao und der `SQLite Viewer` von Florian Klampfer.

## Getting Started / Bedienung

Um den Docker-Container und damit die Anwendung zu starten, einfach `docker compose up` ausführen, dann ist die Anwendung unter http://localhost:8000/ verfügbar.
Zum Erstellen & Füllen der Datenbank einfach die `main.py` ausführen (vorher ggf. die bestehende Datenbank löschen).

## Git Commits

Möglichst an `Conventional Commits`-Richtlinien halten.

## PyTest & PyCodeStyle

Es gibt eine Datei für Tests mit `PyTest`, dazu einfach `pytest` in der Konsole ausführen.
Die Korrektheit der Code-Formatierung erfolgt mittels `PyCodeStyle`, dazu einfach `pycodestyle .` für alle Dateien oder `pycodestyle <Name der Datei>.py` ausführen.

## Projektstruktur

```
.
├── data/ # Ordner für alle vorgegebenen Testdaten
│   └── daten.json # JSON-Dateien mit Testdaten
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
│   │   └──leaflet_database.db # Datanbank (von main.py erstellt)
│   └── frontend/
│       ├── static/ # Stylesheet
│       └── templates/ # Alle HTML-Templates für Flask
├── .gitignore
├── docker-compose.yml
├── LICENCE # MIT-Lizenz
└── README.md
```