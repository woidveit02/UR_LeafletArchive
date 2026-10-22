# UR Leaflet Archive

Die Allgemeine Flugblattsammlung des Universitätsarchivs Regensburg (Rep. 118) enthält Flugblätter aus der Studentenbewegung der Jahre 1967 bis 1973. Dieses Repository macht sie durchsuchbar: 1 927 Exemplare aus 14 Bänden mit Scan, erkanntem Text, Titel, Datum, Herausgebern und Thema. Es entstand in einem Praxisseminar im Sommersemester 2026 und enthält die Anwendung, den Projektbericht und die Werkzeuge, mit denen weitere Bände eingelesen werden.

![Leseansicht eines Flugblatts](docs/abbildungen/app_leseansicht.png)

## Schnellstart

Voraussetzung ist Docker mit Docker Compose.

1. Repository klonen und hineinwechseln: `cd UR_LeafletArchive`.
2. Den Ordner `UR_LeafletArchive_data` mit Scans und Texterkennung aus Drive lokal ablegen.
3. `.env.example` nach `.env` kopieren und dort den Pfad zu diesem Ordner eintragen.
4. `docker compose up` starten. In der Ausgabe muss „Data folder ok“ stehen. Sonst nennt die Meldung, was am Pfad nicht stimmt, und die Anwendung zeigt oben auf jeder Seite einen Hinweis.
5. http://localhost:8000/ öffnen. Beim ersten Start legt die Anwendung die Datenbank an und rendert im Hintergrund die Vorschaubilder; das dauert einige Minuten.

Nach einem Pull: Hat sich `Dockerfile` oder `requirements.txt` geändert, mit `docker compose up -d --build` neu bauen. Hat sich etwas in `data/` oder am Datenbankschema geändert, die Datenbank löschen und neu starten:

```bash
rm src/backend/leaflet_database.db      # Windows: del src\backend\leaflet_database.db
docker compose restart
```
Die Anwendung hat keine Anmeldung und ist deshalb nur auf dem eigenen Rechner erreichbar. Wie sie auf einem Server mit Passwort läuft, steht in [`docs/handbuch/installieren-und-betreiben.md`](docs/handbuch/installieren-und-betreiben.md).

## Was die Anwendung kann

Die Anwendung durchsucht den ganzen Text und zeigt die Fundstellen. Die Treffer lassen sich nach Jahr, Herausgeber, Thema und Textsorte filtern; dazu kommen Trends über die Jahre und eigene Seiten für Themen, Organisationen und Bände. Jedes Flugblatt zeigt Scan und Text nebeneinander, jede Angabe mit ihrem Beleg im Text.

Metadaten lassen sich von Hand korrigieren, Mehrfachexemplare prüfen und der Bestand als ZIP exportieren ([Anleitung](docs/handbuch/recherchieren-und-pflegen.md)). Neue Bände kommen in sechs Schritten von den Scans bis zur Freigabe dazu, im Browser oder in der Kommandozeile ([Anleitung](docs/handbuch/neue-baende-importieren.md)).

## Aufbau

```
data/           Quelle der Datenbank: Metadaten je Band, Korrekturen, Register, Themen
docs/           Projektbericht, Handbücher, Glossar (MkDocs)
scripts/        Werkzeuge neben der Anwendung: Textauswertung, Scans, Abbildungen, Bericht als PDF
src/backend/    Anwendung (FastAPI, SQLite), Import, Tests
src/frontend/   Templates, Stylesheets, Skripte im Browser
```

Die Dateien in `data/` sind maßgeblich und gehören ins Repository; die Datenbank wird aus ihnen gebaut. Scans und Texterkennung liegen wegen ihrer Größe im Datenordner außerhalb:

```
UR_LeafletArchive_data/
├── Nr. 001 (1967)/
│   ├── 0118_0001.pdf               # Scan des Bandes
│   ├── 0118_0001.segments.json     # wo ein Flugblatt endet
│   └── 0118_0001/
│       ├── 0118_0001.json          # Texterkennung (Datalab)
│       └── <hash>_img.jpg          # Abbildungen aus der Texterkennung
├── Nr. 002 (1968)/
└── …
```

Ohne Datenordner startet die Anwendung trotzdem, zeigt dann aber weder Scans noch Text.

## Dokumentation

Der Projektbericht und die Lesepfade für Archiv, Forschung und Entwicklung beginnen in [`docs/README.md`](docs/README.md). Code, Datenformate und Tests beschreibt [`docs/handbuch/weiterentwickeln.md`](docs/handbuch/weiterentwickeln.md), die Werkzeuge neben der Anwendung [`scripts/README.md`](scripts/README.md).

Als Website lässt sich die Dokumentation so ansehen:

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r docs/requirements.txt
python -m mkdocs serve -a 127.0.0.1:8001
```

Das Arbeits-Repository des Projekts mit der Evaluation der Texterkennung und den ersten Metadatenläufen ist archiviert: https://github.com/Alphazerfall/flugblatt_praxisseminarSS26

## Lizenz

MIT, siehe [`LICENSE`](LICENSE).
