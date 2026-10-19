# Entwicklung

Für alle, die am Code arbeiten. Wie die Anwendung gestartet wird, steht im [README](../../README.md), wie sie auf einem Server läuft, in [Betrieb](betrieb.md).

## Code

```
src/backend/app/
├── main.py              Start: legt die Datenbank an, füllt sie, rendert die Vorschaubilder
├── app.py               Seiten und Routen (FastAPI)
├── database/
│   ├── models.py        Tabellen
│   ├── fillDatabase.py  füllt die Datenbank aus data/ und prüft den Datenordner
│   ├── corrections.py   Handkorrekturen lesen, anhängen, anwenden
│   ├── copy_decisions.py  geprüfte Gruppen von Exemplaren
│   └── search.py        Volltextsuche (SQLite FTS5)
├── importer.py          Import eines Bandes, Schritte 1 und 2
├── ocr.py               Schritt 3: Texterkennung mit Datalab
├── segments.py          Schritt 4: Flugblätter trennen
├── boundaries.py        Vorschlag für Schritt 4 aus dem Text
├── metadata.py          Schritt 5: Metadaten mit einem Sprachmodell über OpenRouter
├── metadata_prompt.txt  Prompt dazu
├── organizations.py     neue Herausgeber dem Register zuordnen
├── copy_search.py       Mehrfachexemplare eines neuen Bandes finden
├── topics.py            Schritt 7 und Neuberechnung der Themen
├── export.py            Export als ZIP
├── keys.py              API-Schlüssel aus .env oder der Verwaltung
├── cli.py               Import in der Kommandozeile
├── pdf_service.py       Scanseiten rendern
└── warm_thumbs.py       Vorschaubilder im Hintergrund
src/frontend/            Templates (Jinja2), Stylesheet, JavaScript
```

Beim Start legt `createDatabase.py` fehlende Tabellen und Spalten an. Ist die Datenbank leer, füllt `fillDatabase.py` sie aus `data/` und wendet zuletzt die Korrekturen an; eine gefüllte Datenbank bleibt, wie sie ist. Nach Änderungen an `data/` von außen, etwa durch einen Pull, an `models.py` oder an `search.py` deshalb die Datenbank löschen und neu starten.

## Umgebungsvariablen

Was in `.env` stehen kann, erklärt `.env.example`. Die folgenden Variablen setzt `docker-compose.yml` oder der Test; ändern muss sie nur, wer ohne Docker arbeitet oder Tests schreibt.

| Variable | Standard | Wofür |
|---|---|---|
| `LEAFLET_DB` | `src/backend/leaflet_database.db` | Datei der Datenbank; die Tests legen sie in ein temporäres Verzeichnis |
| `LEAFLET_DATA_DIR` | `data/` (im Container `/app/data`) | Quelle der Datenbank |
| `LEAFLET_PDF_DIR` | `/data/pdfs` | Datenordner im Container, eingebunden aus `LEAFLET_PDF_HOST_DIR` |
| `LEAFLET_PDF_HOST_DIR` | aus `.env` | nur für Meldungen: der Pfad auf dem eigenen Rechner |
| `LEAFLET_CORRECTIONS` | `data/corrections.jsonl` | Handkorrekturen |
| `LEAFLET_COPY_DECISIONS` | `data/copy_decisions.jsonl` | geprüfte Gruppen von Exemplaren |
| `LEAFLET_CHECKED` | `data/checked.jsonl` | Prüfhinweise beim Import, die jemand mit „Passt so“ bestätigt hat |
| `LEAFLET_BUILT_DB` | nicht gesetzt | Tests mit der Markierung `built_db` laufen auf einer Kopie dieser Datei |

## Seiten

| Seite | Route | Inhalt |
|---|---|---|
| Start | `/` | Einführung, Zahlen, ausgewählte Flugblätter, Zeitleiste |
| Flugblätter | `/leaflets` | Suche und Liste mit Filtern; Ansichten Liste, Kacheln und Fundstellen |
| Flugblatt | `/leaflets/{id}` | Scan mit Textblöcken neben dem Text, Metadaten mit Belegen |
| Korrigieren | `/leaflets/{id}?bearbeiten` | Angaben von Hand ändern, mit Beleg im Scan |
| Exemplare prüfen | `/leaflets/{id}/exemplare` | Blätter einer Gruppe vergleichen, Hauptexemplar wählen, Angaben der Gruppe korrigieren |
| Exemplare | `/exemplare` | alle Gruppen mit Stand der Prüfung |
| Korrekturen | `/korrekturen` | Korrekturen und Prüfungen, die nach einer neuen Trennung nicht mehr passen |
| Themen | `/themen` | Themen mit Karte und Jahresverteilung |
| Organisationen | `/organizations`, `/organizations/{id}` | Register der Herausgeber |
| Bände | `/volumes`, `/volumes/{vz}` | Bände wie im Findmittel; die Adresse ist die Vz-Nummer und bleibt beim Neubau gleich |

Korrigieren und Exemplare prüfen teilen sich `_metadata_fields.html`, `meta-form.js` sowie `read_metadata_form` und `save_metadata` in `app.py`.

## Daten in `data/`

| Datei | Inhalt | Entsteht |
|---|---|---|
| `nr001_metadata.json`, … | Titel, Datum, Textsorte, Herausgeber je Flugblatt; jeder Band mit einer solchen Datei wird eingelesen | Nr. 001–014 im Projekt, neue Bände in Schritt 5 |
| `copies.tsv` | mögliche Exemplare desselben Blatts | Nr. 001–014 im Projekt, neue Bände beim Import |
| `corrections.jsonl` | Handkorrekturen | Korrigieren in der Anwendung |
| `copy_decisions.jsonl` | geprüfte Gruppen von Exemplaren | Exemplare prüfen in der Anwendung |
| `organizations.json` | Register der Organisationen | Findmittel, ergänzt beim Import |
| `topics.json`, `topic_map.json` | Themen, Zuordnungen, Punkte der Themenkarte | Themenmodell, Neuberechnung in der Anwendung |
| `volumes.json`, `findmittel.tsv` | Bände mit Titel, Signatur, Link ins Archivportal-D | Findmittel |

`corrections.jsonl` und `copy_decisions.jsonl` werden nur ergänzt, nie überschrieben:

- Jede Korrektur ist eine Zeile. Sie gilt nur für ein Flugblatt mit genau derselben Seitenspanne; ändert sich eine Grenze, erscheint sie unter `/korrekturen`. „Alle Handkorrekturen entfernen“ und „wiederherstellen“ hängen eine Zeile mit `"field": "revert"` an, die alle früheren Zeilen des Flugblatts aufhebt (`"value": "all"`) oder nur die eines Feldes.
- Jede geprüfte Gruppe ist eine Zeile mit Mitgliedern, ausgeschlossenen Blättern und Hauptexemplar. Blätter werden über Band und Seitenspanne angesprochen, nie über die Gruppennummer aus `copies.tsv`, denn die ändert sich bei jeder neuen Suche. „Prüfung zurücknehmen“ hängt eine Zeile mit `"revert"` an.

## Suche

Die Suche durchsucht Titel, Reihe, Herausgeber und Text mit Trigrammen (SQLite FTS5). Sie findet deshalb auch Wortteile, „versammlung“ trifft „Vo11versammlung“. Mehrere Wörter müssen alle vorkommen, Wörter in Anführungszeichen als Wortfolge. „daß“ und „dass“ finden sich gegenseitig, am Zeilenende getrennte Wörter werden zusammengezogen. Begriffe unter drei Zeichen werden nur in Titel und Reihe gesucht. Der Index entsteht beim Aufbau der Datenbank.

## Tests und Codestil

```bash
python -m pytest src/backend/tests
```

Die Tests berühren die echte Datenbank nie. Die wenigen, die eine gebaute Datenbank brauchen (Markierung `built_db`), laufen auf einer Kopie der Datei in `LEAFLET_BUILT_DB` und werden sonst übersprungen. `test_scripts.py` prüft die Werkzeuge in `scripts/`. Den Codestil prüft `pycodestyle`. Commits folgen den Conventional Commits.
