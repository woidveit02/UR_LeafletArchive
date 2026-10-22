# Weiterentwickeln

Für alle, die am Code arbeiten. Wie die Anwendung gestartet wird, steht in der README im Hauptverzeichnis des Repositorys, wie sie auf einem Server läuft, in [Installieren und betreiben](installieren-und-betreiben.md).

## Code

```
src/backend/app/
├── main.py              Start: legt die Datenbank an, füllt sie, rendert die Vorschaubilder
├── app.py               Seiten und Routen (FastAPI)
├── database/
│   ├── models.py        Tabellen
│   ├── createDatabase.py  legt fehlende Tabellen und Spalten an
│   ├── fillDatabase.py  füllt die Datenbank aus data/ und prüft den Datenordner
│   ├── corrections.py   Handkorrekturen lesen, anhängen, anwenden
│   ├── copy_decisions.py  geprüfte Gruppen von Exemplaren
│   └── search.py        Volltextsuche (SQLite FTS5)
├── importer.py          Import eines Bandes, Schritte 1 und 2
├── ocr.py               Schritt 3: Texterkennung mit Datalab
├── segments.py          Schritt 4: Flugblätter trennen
├── boundaries.py        Vorschlag für Schritt 4 aus Text und Scan
├── looks.py             Merkmale des Scans je Seite (Papier, Lochung, Stempel, Leerseite)
├── metadata.py          Schritt 5: Metadaten mit einem Sprachmodell über OpenRouter
├── metadata_prompt.txt  Prompt dazu
├── organizations.py     Herausgeber dem Register zuordnen (Import und Verwaltung)
├── copy_search.py       Mehrfachexemplare eines neuen Bandes finden
├── topics.py            Themen zuordnen und Neuberechnung der Themen
├── export.py            Export als ZIP
├── keys.py              API-Keys aus .env oder der Verwaltung
├── cli.py               Import in der Kommandozeile
├── pdf_service.py       Scanseiten rendern
└── warm_thumbs.py       Vorschaubilder im Hintergrund
src/frontend/            Templates (Jinja2), Stylesheet, JavaScript
```

Beim Start legt `createDatabase.py` fehlende Tabellen und Spalten an. Ist die Datenbank leer, füllt `fillDatabase.py` sie aus `data/` und wendet zuletzt die Korrekturen an; eine gefüllte Datenbank bleibt, wie sie ist. Nach Änderungen an `data/` von außen, etwa durch einen Pull, an `models.py` oder an `search.py` deshalb die Datenbank löschen und neu starten. Ob ein Band Entwurf ist, steht dafür auch in `volumes.json`; `set_status` in `fillDatabase.py` hält Datenbank und Datei gleich.

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
| Korrigieren | `/leaflets/{id}?bearbeiten` | Metadaten von Hand ändern, mit Beleg im Scan |
| Exemplare prüfen | `/leaflets/{id}/exemplare` | Blätter einer Gruppe vergleichen, Hauptexemplar wählen, Metadaten der Gruppe korrigieren |
| Exemplare | `/exemplare` | alle Gruppen mit Stand der Prüfung |
| Korrekturen | `/korrekturen` | Korrekturen und Prüfungen, die nach einer neuen Trennung nicht mehr passen |
| Themen | `/themen` | Themen mit Karte und Jahresverteilung |
| Organisationen | `/organizations`, `/organizations/{id}` | Register der Herausgeber |
| Bände | `/volumes`, `/volumes/{vz}` | Bände wie im Findmittel; die Adresse ist die Vz-Nummer und bleibt beim Neubau gleich |
| Trends | `/trends` | Anteil der Flugblätter je Jahr für Suchbegriffe |
| Verwaltung | `/verwaltung` | Entwürfe und freigegebene Bände, Zugang zu Exemplaren, Herausgebern, Korrekturen, Themen, Export und API-Keys |
| Herausgeber zuordnen | `/verwaltung/herausgeber` | Flugblätter mit unbekannter Schreibweise oder ohne Herausgeber, über alle freigegebenen Bände |
| Export | `/verwaltung/export` | ZIP mit Flugblättern, Texten und Tabellen |
| Import | `/import/{vz}` | die Schritte des Imports eines Bandes |

Korrigieren und Exemplare prüfen teilen sich `_metadata_fields.html`, `meta-form.js` sowie `read_metadata_form` und `save_metadata` in `app.py`.

## Oberfläche

Alle Seiten erben von `base.html`. Ein Stylesheet (`static/styles.css`) für alles; Farben und Schriftgrößen stehen als Variablen in `:root` (`--accent`, `--suggest`, `--text-sm` …), neue Regeln verwenden nur diese. Wiederkehrende Teile liegen in Makros:

| Datei | Makros |
|---|---|
| `_ui.html` | `step_link` (Blättern), `review_bar` (Leiste „← Schritt 6“ über den Seiten, auf die Schritt 6 des Imports verweist), `sort_select`, `sort_link`, `view_switch`, `excerpt` |
| `_leaflets.html` | Trefferliste, Kacheln, Titel, Herausgeber |
| `_metadata_fields.html` | Formularfelder beim Korrigieren, mit Belegen |
| `_topics.html` | Themenzeilen und Themenkarte |
| `_keys.html`, `_models.html` | API-Key-Feld, Modellwahl |

JavaScript ohne Build-Schritt und ohne Framework, je Seite ein Skript in `static/`:

| Skript | Seite |
|---|---|
| `field-search.js` | Suchfeld im Kopf jeder Seite |
| `home.js`, `leaflet-list.js`, `leaflet-page.js`, `volume-page.js`, `organization-list.js`, `trends.js` | Start, Flugblattliste, Flugblatt, Band, Herausgeber, Trends |
| `meta-form.js`, `evidence-pick.js` | Korrigieren: Felder, Belege im Scan wählen |
| `copy-review.js` | Exemplare prüfen |
| `topic-map.js`, `topics-admin.js` | Themenkarte, Verwaltung › Themen |
| `import-upload.js`, `import-split.js`, `import-check.js`, `page-pair.js` | Import: Hochladen, Trennansicht, Texterkennung ansehen (Scan neben Text) |
| `run-job.js` | Fortschritt laufender Hintergrundaufgaben (Texterkennung, Metadaten, Themen) |
| `issuer-search.js` | Herausgeber zuordnen |
| `export.js` | Export |
| `keep-scroll.js` | Scrollposition beim Neuladen halten |

`chart.umd.min.js` und `chartjs-plugin-zoom.min.js` (Chart.js) zeichnen Trends und Themenverläufe.

## Daten in `data/`

| Datei | Inhalt | Entsteht |
|---|---|---|
| `nr001_metadata.json`, … | Titel, Datum, Textsorte, Herausgeber je Flugblatt; jeder Band mit einer solchen Datei wird eingelesen | Nr. 001–014 im Projekt, neue Bände in Schritt 5 |
| `copies.tsv` | mögliche Exemplare desselben Blatts | Nr. 001–014 im Projekt, neue Bände beim Import |
| `corrections.jsonl` | Handkorrekturen | Korrigieren in der Anwendung |
| `copy_decisions.jsonl` | geprüfte Gruppen von Exemplaren | Exemplare prüfen in der Anwendung |
| `organizations.json` | Register der Organisationen | Findmittel, ergänzt beim Import |
| `topics.json`, `topic_map.json` | Themen, Zuordnungen, Punkte der Themenkarte | Themenmodell, Neuberechnung in der Anwendung |
| `volumes.json`, `findmittel.tsv` | Bände mit Titel, Signatur, Link ins Archivportal-D; bei Entwürfen `"status": "entwurf"` | Findmittel, ergänzt beim Import |
| `checked.jsonl` | Prüfhinweise, die jemand mit „Passt so“ bestätigt hat, und Entscheidungen zu Flugblättern ohne Herausgeber | Import und Verwaltung |

Neben dem Scan eines Bandes im Scan-Ordner liegen außerdem `<stem>.segments.json` (die Trennung), `<stem>.looks.json` (Merkmale des Scans je Seite) und `<stem>.reasons.json` (Gründe des letzten Trennvorschlags).

`corrections.jsonl` und `copy_decisions.jsonl` werden nur ergänzt, nie überschrieben:

- Jede Korrektur ist eine Zeile. Sie gilt nur für ein Flugblatt mit genau derselben Seitenspanne; ändert sich eine Grenze, erscheint sie unter `/korrekturen`. „Alle Handkorrekturen entfernen“ und „wiederherstellen“ hängen eine Zeile mit `"field": "revert"` an, die alle früheren Zeilen des Flugblatts aufhebt (`"value": "all"`) oder nur die eines Feldes.
- Jede geprüfte Gruppe ist eine Zeile mit Mitgliedern, ausgeschlossenen Blättern und Hauptexemplar. Blätter werden über Band und Seitenspanne angesprochen, nie über die Gruppennummer aus `copies.tsv`, denn die ändert sich bei jeder neuen Suche. „Prüfung zurücknehmen“ hängt eine Zeile mit `"revert"` an.

## Suche

Die Suche durchsucht Titel, Reihe, Herausgeber und Text mit Trigrammen (SQLite FTS5). Sie findet deshalb auch Wortteile, „versammlung“ trifft „Vo11versammlung“. Mehrere Wörter müssen alle vorkommen, Wörter in Anführungszeichen als Wortfolge. „daß“ und „dass“ finden sich gegenseitig, am Zeilenende getrennte Wörter werden zusammengezogen. Begriffe unter drei Zeichen werden nur in Titel und Reihe gesucht. Der Index entsteht beim Aufbau der Datenbank.

Mit „+ Suchbedingung hinzufügen“ lassen sich bis zu acht Bedingungen mit UND, ODER und NICHT verknüpfen, jede auf alle Felder oder eines davon: Titel, Herausgeber, Unterzeichner, Reihe, Text (`FIELDS` in `search.py`, `search_row` in `app.py`).

## Tests und Codestil

Die Tests laufen im Container. Dort liegt `src/backend` unter `/app`, die Tests importieren aber `backend.app`; der Link in `/tmp/t` gleicht das aus:

```bash
docker compose exec -T backend sh -c 'mkdir -p /tmp/t && ln -sfn /app /tmp/t/backend && cd /tmp && PYTHONPATH=/tmp/t python -m pytest /tmp/t/backend/tests -q -p no:cacheprovider --ignore=/tmp/t/backend/tests/test_scripts.py --ignore=/tmp/t/backend/tests/test_corpus_stats.py'
```

Im Container fehlt das Verzeichnis `scripts/`. `test_scripts.py` und `test_corpus_stats.py` brechen dort ab und laufen lokal: `python -m pytest src/backend/tests/test_scripts.py src/backend/tests/test_corpus_stats.py`. Die übrigen Tests scheitern lokal zu rund 30, weil dort die Templates unter `app/templates` und die Trigramm-Suche von FTS5 fehlen. Das ist kein Fehler im Code.

Die Tests berühren die echte Datenbank nie. Die wenigen, die eine gebaute Datenbank brauchen (Markierung `built_db`), laufen auf einer Kopie der Datei in `LEAFLET_BUILT_DB` und werden sonst übersprungen. `test_scripts.py` prüft die Werkzeuge in `scripts/`. Den Codestil prüft `pycodestyle`. Commits folgen den Conventional Commits.
