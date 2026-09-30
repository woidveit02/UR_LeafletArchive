# UR Leaflet Archive

Explorationswerkzeug für die Flugblattsammlung des Universitätsarchivs Regensburg (Rep. 118, 1967–1973): Flugblätter mit Scan, OCR-Transkription und automatisch extrahierten Metadaten, dazu Organisationen und Bände laut Findmittel des Archivs.

## Setup
1. Repo klonen und hineinwechseln via `cd UR_LeafletArchive`.
2. Den Ordner `UR_LeafletArchive_data` aus Drive lokal ablegen (Scans und OCR-Daten).
3. `.env.example` nach `.env` kopieren und dort den Pfad zu diesem Ordner eintragen.
4. Die Anwendung starten via `docker compose up`. Sie ist dann unter http://localhost:8000/ erreichbar; die Datenbank wird beim ersten Start angelegt und gefüllt.
5. Im Log muss „Data folder ok“ stehen (`docker compose logs backend`). Sonst nennt die Meldung, was am Pfad nicht stimmt.

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

Ohne Datenordner läuft die Anwendung auch, zeigt aber keine Scans und keinen OCR-Text.

## Ansichten

| Seite | Route | Inhalt |
|-------|-------|--------|
| Flugblätter | `/leaflets` | Liste mit Band, Datum und Herausgeber |
| Flugblatt | `/leaflets/{id}` | Scan mit OCR-Boxen neben der Transkription, Metadaten mit Fundstellen |
| Organisationen | `/organizations` | Normdatei der herausgebenden Gruppen |
| Organisation | `/organizations/{id}` | Angaben laut Findmittel, Bände, Flugblätter |
| Bände | `/volumes` | Verzeichnungseinheiten 1967–1973, gegliedert wie im Findmittel |
| Band | `/volumes/{vz}` | Findmittel-Titel, Signatur, Organisationen, Link ins Archivportal-D |

Auf der Flugblatt-Seite sind Scan und Transkription verknüpft: Fährt man über einen Textblock, wird die zugehörige Stelle im Scan markiert und umgekehrt. Bände werden über ihre Vz-Nummer adressiert (`/volumes/2` = Nr. 002), damit die Adressen beim Neuaufbau der Datenbank gleich bleiben.

## Daten

Die Datenbank wird aus den JSON-Dateien in [`data/`](data/) gebaut; sie sind maßgeblich und liegen in Git. Scans und OCR liegen in Drive.

| Datei | Inhalt | Herkunft |
|-------|--------|----------|
| [`nr002_metadata.json`](data/nr002_metadata.json) | Titel, Datum, Textsorte, Herausgeber je Flugblatt | LLM-Extraktion im Pipeline-Repo |
| [`organizations.json`](data/organizations.json) | Normdatei der Organisationen | Findmittel (Entwurf, noch nicht bereinigt) |
| [`volumes.json`](data/volumes.json) | Bände mit Titel, Signatur, Link ins Archivportal-D | Findmittel |

Bisher ist nur Nr. 002 (1968) mit Flugblättern importiert; die übrigen Bände erscheinen in der Bandliste.

Nach einem Pull mit Änderungen in `data/` oder am Datenbankschema, oder wenn der Datenordner erst nachträglich eingebunden wurde: `src/backend/leaflet_database.db` löschen und neu starten.

## Tests & Codestil

Die Tests prüfen Datenbank und Datenordner-Prüfung ([`src/backend/tests/`](src/backend/tests/)):

```bash
cd src
python -m pytest backend/tests
```

Der Codestil wird mit `pycodestyle .` geprüft. Commits folgen den `Conventional Commits`.

## Projektstruktur

```
.
├── data/                          # Quelle für die DB (siehe Daten)
├── src/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── database/
│   │   │   │   ├── createDatabase.py  # Erstellung der DB
│   │   │   │   ├── fillDatabase.py    # Füllt die DB aus den JSONs, prüft den Datenordner
│   │   │   │   ├── models.py          # DB-Struktur
│   │   │   │   └── session.py
│   │   │   ├── app.py                 # Routen (FastAPI)
│   │   │   ├── main.py                # Erstellt und füllt die DB beim Start
│   │   │   └── pdf_service.py         # Rendert Scan-Seiten aus den PDFs
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
