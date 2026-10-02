# UR Leaflet Archive

Eine Anwendung zum Durchsuchen der Flugblattsammlung im Universitätsarchiv Regensburg (Rep. 118, 1967–1973). Sie zeigt die Flugblätter mit Scan, OCR-Transkription und automatisch extrahierten Metadaten, außerdem die Organisationen und Bände aus dem Findmittel des Archivs.

## Setup
1. Repo klonen und mit `cd UR_LeafletArchive` hineinwechseln.
2. Den Ordner `UR_LeafletArchive_data` mit Scans und OCR-Daten aus Drive lokal ablegen.
3. `.env.example` nach `.env` kopieren und dort den Pfad zu diesem Ordner eintragen.
4. Mit `docker compose up` starten. Die Anwendung läuft dann unter http://localhost:8000/. Beim ersten Start legt sie die Datenbank an und füllt sie.
5. Im Log (`docker compose logs backend`) muss „Data folder ok“ stehen. Andernfalls sagt die Meldung, was am Pfad nicht stimmt.

Ändert ein Pull das `Dockerfile` oder `requirements.txt`, muss das Image neu gebaut werden: `docker compose up -d --build`. Beim Start rendert die Anwendung im Hintergrund die Vorschaubilder für die Kachelansicht. Das dauert beim ersten Mal einige Minuten; danach liegen sie im Datenordner unter `.thumbs/`.

Der Pfad in `.env` zeigt auf den Datenordner selbst, nicht auf einen Band darin:

```
UR_LeafletArchive_data/
├── Nr. 001 (1967)/
│   ├── 0118_0001.pdf          # Scan des Bandes
│   └── 0118_0001/
│       ├── 0118_0001.json     # OCR (Datalab)
│       └── <hash>_img.jpg     # Abbildungen aus der OCR
├── Nr. 002 (1968)/
│   └── …
└── …
```

Ohne Datenordner startet die Anwendung trotzdem, zeigt dann aber weder Scans noch OCR-Text.

## Ansichten

| Seite | Route | Inhalt |
|-------|-------|--------|
| Start | `/` | Kurze Einführung, Zahlen, ausgewählte Flugblätter, Zeitleiste |
| Flugblätter | `/leaflets` | Liste mit Band, Datum und Herausgeber |
| Flugblatt | `/leaflets/{id}` | Scan mit OCR-Boxen neben der Transkription, Metadaten mit Fundstellen |
| Organisationen | `/organizations` | Normdatei der herausgebenden Gruppen |
| Organisation | `/organizations/{id}` | Angaben laut Findmittel, Bände, Flugblätter |
| Bände | `/volumes` | Verzeichnungseinheiten 1967–1973, gegliedert wie im Findmittel |
| Band | `/volumes/{vz}` | Findmittel-Titel, Signatur, Organisationen, Link ins Archivportal-D |
| Korrigieren | `/leaflets/{id}?bearbeiten` | Titel, Datum, Textsorte, Herausgeber, Unterzeichnende sowie Reihe und Nummer von Hand korrigieren, mit Beleg im Scan |
| Korrekturen | `/korrekturen` | Korrekturen, die nach einer Änderung der Segmentgrenzen nicht mehr angewendet werden |

Jede Korrektur steht als eigene Zeile in `data/corrections.jsonl`. Beim Aufbau der Datenbank werden die Korrekturen zuletzt angewendet, und zwar nur auf ein Flugblatt mit genau derselben Seitenspanne. „Alle Handkorrekturen entfernen“ und „wiederherstellen“ hängen eine Zeile mit `"field": "revert"` an, gelöscht wird dabei nichts. Diese Zeile hebt alle früheren Zeilen des Flugblatts auf (`"value": "all"`) oder nur die eines Feldes. Die Datei gehört ins Repo.

Die Anwendung hat keine Anmeldung. Bevor sie außerhalb des eigenen Rechners erreichbar ist, muss das Bearbeiten abgesichert werden.

Auf der Flugblatt-Seite sind Scan und Transkription verknüpft: Fährt man über einen Textblock, markiert die Seite die zugehörige Stelle im Scan, und umgekehrt. Bände haben ihre Vz-Nummer als Adresse (`/volumes/2` = Nr. 002), damit die Adressen beim Neuaufbau der Datenbank gleich bleiben.

## Daten

Die Datenbank entsteht aus den JSON-Dateien in [`data/`](data/). Diese Dateien sind maßgeblich und liegen in Git, Scans und OCR dagegen in Drive.

| Datei | Inhalt | Herkunft |
|-------|--------|----------|
| `nr001_metadata.json`, `nr002_metadata.json`, … | Titel, Datum, Textsorte, Herausgeber je Flugblatt. Jeder Band mit einer solchen Datei wird importiert | LLM-Extraktion im Pipeline-Repo |
| [`copies.tsv`](data/copies.tsv) | Mögliche weitere Exemplare desselben Blatts | Textvergleich im Pipeline-Repo (`find_copies.py`) |
| `corrections.jsonl` | Handkorrekturen | Bearbeiten in der App |
| [`organizations.json`](data/organizations.json) | Normdatei der Organisationen | Findmittel (Entwurf, noch nicht bereinigt) |
| [`volumes.json`](data/volumes.json) | Bände mit Titel, Signatur, Link ins Archivportal-D | Findmittel |

Importiert sind Nr. 001 bis Nr. 014 (1967–1973). Nr. 015 ist nicht digitalisiert und erscheint nur in der Bandliste.

Ändert ein Pull etwas in `data/` oder am Datenbankschema, oder wurde der Datenordner erst nachträglich eingebunden, dann `src/backend/leaflet_database.db` löschen und neu starten.

## Tests & Codestil

Die Tests in [`src/backend/tests/`](src/backend/tests/) decken die Datenbank, die Prüfung des Datenordners, Datumsangaben, Herausgeber, Reihen, Exemplare und Korrekturen ab:

```bash
cd src
python -m pytest backend/tests
```

Den Codestil prüft `pycodestyle .`. Commits folgen den Conventional Commits.

## Projektstruktur

```
.
├── data/                          # Quelle für die DB (siehe Daten)
├── src/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── database/
│   │   │   │   ├── corrections.py     # Handkorrekturen lesen, anhängen, anwenden
│   │   │   │   ├── createDatabase.py  # Erstellung der DB
│   │   │   │   ├── fillDatabase.py    # Füllt die DB aus den JSONs, prüft den Datenordner
│   │   │   │   ├── models.py          # DB-Struktur
│   │   │   │   └── session.py
│   │   │   ├── app.py                 # Routen (FastAPI)
│   │   │   ├── main.py                # Erstellt und füllt die DB beim Start
│   │   │   ├── pdf_service.py         # Rendert Scan-Seiten aus den PDFs
│   │   │   └── warm_thumbs.py         # Erzeugt beim Start die Vorschaubilder
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── frontend/
│       ├── static/                    # Stylesheet, Favicon
│       └── templates/                 # HTML-Templates
├── .env.example                       # Vorlage für .env (Pfad zum Datenordner)
├── docker-compose.yml
└── LICENCE                            # MIT-Lizenz
```
