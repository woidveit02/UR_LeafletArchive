# room-manager-korpies: woidveits RoomManager

## Beschreibung
Eine einfache Flask-Website zum Durchsuchen und Betrachten der verschiedenen Räume der Universität Regensburg. 

Dass ganze Projekt wurde mit Visual Studio Code erstellt, dieses wurde zudem mit einigen Extensions modifiziert, darunter die `Container Tools` für Docker und einige Python-Extensions von Microsoft, der `REST Client` von Huachao Mao und der `SQLite Viewer` von Florian Klampfer.

## Getting Started - Standardnutzer
Um den Docker-Container zu starten, einfach `docker compose up` ausführen, dann ist die Anwendung unter http://localhost:8000/ verfügbar. Anfangs haben Nutzer die Gast-Rolle, dadurch nur eingschränkten Zugriff, was sich durch einen Login mit den entsprechenden Nutzerdaten ändern lässt. Läuft der Login (bzw. der beim Login generierte JWT) nach einiger Zeit aus, fällt der Nutzer auf den Gast-Zugang zurück. Alle Nutzerprofile mit den Detailinformationen sind in der Datei `userInfo.txt` dokumentiert.

## Getting Started - Admin

Um auf die Adminfunktionen zuzugreifen, muss sich der Admin zuerst mit seinem authorisierten Profil anmelden und dann ist es möglich, über http://localhost:8000/admin die Admin-Schaltfläche und deren Funktionen zu nutzen. Zudem werden in der Raum-Detailansicht zusätzliche Management-Buttons angezeigt. 

Gebäude und Standorte können nur per Import-API-Call hinzugefügt werden. Das Löschen erfolgt durch API-Calls. Das Bearbeiten ist indirekt durch das Löschen des alten Gebäudes/Standortes und Importen eines neuen, bearbeiteten Objekts möglich. Das ist zwar umständlich, aber da Gebäude/Standorte voraussichtlich nur extrem selten bearbeitet werden müssen, dürfte die bereitgestellte Funktionalität ausreichen.

## Nutzung
Die meisten Funktionen sind über das Frontend verfügbar, zudem gibt es einige Funktionen, die auch per REST-API-Call abrufbar sind.

Um die APIs leicht zu Testen gibt es auch einen Ordner `requests`, in diesem befinden sich in Form einfacher http-Dateien einige API-Requests, die sich mit der vorher genannten `REST Client` VSCode-Extension leicht ausführen lassen.  

## Projektstruktur

```
.
├── data/ # Ordner für alle vorgegebenen Testdaten
│   ├── photos/ # Fotos 1 + 2 und PDF jedes Raums
│   └── daten.json # JSON-Dateien mit Testdaten
├── requests/ # Requests zum Testen (Plugin benötigt)
├── src/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── database/
│   │   │   │   ├── base.py
│   │   │   │   ├── createDatabase.py # Erstellung der DB
│   │   │   │   ├── fillDatabase.py # Füllt DB mit Elementen aus JSONs
│   │   │   │   ├── models.py # DB-Struktur
│   │   │   │   └── session.py 
│   │   │   ├── app_decorator.py # Role-Decorator für app.py
│   │   │   ├── app_helper.py # Ausgelagerte Hilfsfunktionen für app.py
│   │   │   ├── app.py # Backend-Script (startet Anwendung im Container)
│   │   │   └── main.py # Zentrales Script zu Erstellung der DB
│   │   ├── logs/
│   │   ├── tests/ # Alle Testdateien mit Unit-Tests
│   │   ├──Dockerfile
│   │   ├──requirements.txt # Benötigte Python-Packages
│   │   └──room_database.db # Datanbank (von main.py erstellt)
│   └── frontend/
│       ├── static/ # Stylesheet & Swagger-Dokumentation
│       └── templates/ # Alle HTML-Templates für Flask
├── .gitignore
├── .gitlab-ci.yml
├── docker-compose.yml
├── LICENCE # MIT-Lizenz (Mit GitLab erstellt)
├── README.md
└── userInfo.txt # Textdatei mit Nutzerdaten zum Testen
```

## Support
Bei Rückfragen oder Unklarheiten zu Funktion oder Verwendung gern eine Mail an `veit.korpie@stud.uni-regensburg.de` oder eine Discord-Direktnachricht an `woidveit02`. 
(Die Commits im Repo sind von meinem GitHub-Profil, das noch in VS-Code eingelogged war, daher nicht wundern)
