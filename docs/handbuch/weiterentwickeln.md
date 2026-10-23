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

Was in `.env` stehen kann, erklärt `.env.example`. `docker-compose.yml` setzt die Pfade im Container (`LEAFLET_DATA_DIR`, `LEAFLET_PDF_DIR`) und bindet den Scan-Ordner aus `LEAFLET_PDF_HOST_DIR` ein. Wer ohne Docker arbeitet oder Tests schreibt, kann die Datenbank (`LEAFLET_DB`) und die Dateien der Handarbeit (`LEAFLET_CORRECTIONS`, `LEAFLET_COPY_DECISIONS`, `LEAFLET_CHECKED`) umlenken; die Standardwerte stehen in `database/session.py` und `database/fillDatabase.py`. Tests mit der Markierung `built_db` laufen auf einer Kopie der Datenbank aus `LEAFLET_BUILT_DB`.

## Seiten

Jede Seite ist eine Route in `app.py` mit eigenem Template in `templates/`. Gelesen wird unter `/`, `/leaflets`, `/volumes`, `/organizations`, `/themen` und `/trends`, gepflegt unter `/verwaltung`, `/exemplare`, `/korrekturen` und `/import/{vz}`. Die Adresse eines Bandes ist seine Vz-Nummer und bleibt beim Neubau der Datenbank gleich.

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

JavaScript ohne Build-Schritt und ohne Framework: je Seite ein Skript in `static/`, benannt nach der Seite (`leaflet-page.js`, `trends.js`, `import-split.js` …). Mehrere Seiten nutzen `field-search.js` (Suchfeld im Kopf), `run-job.js` (Fortschritt von Texterkennung, Metadaten und Themen), `evidence-pick.js` (Belege im Scan wählen, beim Korrigieren und beim Zuordnen der Herausgeber) und `keep-scroll.js` (Scrollposition beim Neuladen).

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

## Export

`src/backend/app/export.py` erzeugt das ZIP unter Verwaltung › Datensatz exportieren: `flugblaetter.jsonl` (alle Angaben und Volltext), `flugblaetter.csv` (ohne Volltext), `texte/<id>.txt`, `flugblatt_herausgeber.csv`, `herausgeber.csv`, `baende.csv`, `themen.csv` und auf Wunsch `seiten.jsonl` (Textblöcke mit Lage). Optionen: nur Hauptexemplare, ohne Unterzeichnende, ohne Seiten. Die `id` (`0118_0003_S127-128`) bleibt über Exporte gleich, solange die Seitengrenzen bleiben. Die Felder beschreibt die `README.md` im ZIP. Dazu lässt sich jede Liste der Anwendung als CSV laden.

## Suche

Die Suche durchsucht Titel, Reihe, Herausgeber und Text mit Trigrammen (SQLite FTS5). Sie findet deshalb auch Wortteile, „versammlung“ trifft „Vo11versammlung“. Mehrere Wörter müssen alle vorkommen, Wörter in Anführungszeichen als Wortfolge. „daß“ und „dass“ finden sich gegenseitig, am Zeilenende getrennte Wörter werden zusammengezogen. Begriffe unter drei Zeichen werden nur in Titel und Reihe gesucht. Der Index entsteht beim Aufbau der Datenbank.

Mit „+ Suchbedingung hinzufügen“ lassen sich bis zu acht Bedingungen mit UND, ODER und NICHT verknüpfen, jede auf alle Felder oder eines davon: Titel, Herausgeber, Unterzeichner, Reihe, Text (`FIELDS` in `search.py`, `search_row` in `app.py`).

## Verfahren

Hinweise der Kapitel 4 bis 7 des Berichts für alle, die an den Verfahren weiterarbeiten.

### Trennen

Die Implementierung der Trennvorschläge befindet sich in `src/backend/app/boundaries.py` und `src/backend/app/segments.py`. Die Gewichte lernt `scripts/learn_boundary_weights.py` aus den getrennten Bänden neu; mit `--pruefen` wiederholt es die bandweise Messung aus [Kap. 4.5](../bericht/04-trennen.md#45-qualitat-des-neuen-verfahrens). 

Bei einer wesentlichen Erweiterung des Bestandes sollte vor dem Import geprüft werden, ob eine wiederholte Anpassung der Gewichte erforderlich sein könnte. Als besondere Herausforderung für eine Weiterentwicklung erweist sich die zuverlässige Erkennung von Rückseiten. Diese weisen oftmals keinerlei eindeutigen Merkmale auf, die auf das Ende bzw. einen Anfang eines Flugblattes hindeuten.

### Metadaten

Die Verwendung von *OpenRouter* erlaubt das Austauschen des verwendeten Sprachmodells. Zudem lassen sich mithilfe der Anwendung die Kosten der einzelnen Arbeitsschritte verfolgen. Dies würde einen späteren Vergleich alternativer Modelle hinsichtlich Kosten und Ergebnisqualität ermöglichen.

Hinweise für eine schlechte Metadatenanalyse können Mehrfachexemplare geben. Weichen extrahierte Angaben innerhalb einer Gruppe von Exemplaren desselben Flugblatts voneinander ab, ist dies ein Indiz für eine fehlerhafte Informationsgewinnung (siehe [Kapitel 6](../bericht/06-mehrfachexemplare.md)).

### Mehrfachexemplare

Abweichende Fassungen eines Flugblatts werden bislang nicht automatisch gruppiert. Sie bleiben daher als eigenständige Flugblätter erhalten. Das erste Topic-Modelling wurde über alle Exemplare des Bestandes hinweg durchgeführt. Bei einer Neuberechnung innerhalb der Anwendung werden dagegen in Zukunft nur die Hauptexemplare berücksichtigt (siehe [Kapitel 7](../bericht/07-themen.md)).

### Themen

Neue Bände bekommen ihre Themen im optionalen Schritt „Themen zuordnen“ nach Schritt 6 des Imports (`src/backend/app/topics.py`). Die Anwendung holt dazu die Embeddings mit bge-m3 über OpenRouter. Jedes Flugblatt bekommt das Thema, das unter seinen fünf ähnlichsten Flugblättern überwiegt, gewichtet nach Ähnlichkeit, und einen Punkt auf der Themenkarte im Mittel dieser Nachbarn. Unsicher ist die Zuordnung, wenn weniger als 60 % des Gewichts auf das Thema fallen oder schon das ähnlichste Flugblatt weniger ähnlich ist als bei 90 % der Flugblätter ihr nächster Nachbar. Eine erste Fassung ordnete dem nächsten Themenmittelpunkt zu. Die Themen von BERTopic beruhen auf HDBSCAN und sind oft nicht rund, ihr Mittelpunkt sagt deshalb wenig. Neue Themen entstehen bei der Zuordnung nicht. Welche Bände nachträglich zugeordnet wurden und wann die Themen zuletzt berechnet wurden, steht unter Verwaltung › Themen.

Die Themen lassen sich in der Anwendung neu berechnen. Das Verfahren ist dasselbe wie beim ersten Lauf, rechnet aber nur über die Hauptexemplare; weitere Exemplare bekommen das Thema ihres Hauptexemplars. Die Ähnlichkeit berechnet immer bge-m3, wählen lässt sich nur das Sprachmodell für die Titel. Dessen Vorschläge folgen den Leitlinien, nach denen die Titel des ersten Laufs geprüft wurden. Die Titel beginnen bei jeder Neuberechnung neu; bisherige Titel werden nicht übernommen. Das Ergebnis wird erst nach einer Prüfung übernommen. Die Prüfseite zeigt die neuen Themen wie die Themenseite, mit Karte, und nennt je Thema das bisherige, aus dem die meisten seiner Flugblätter stammen. Bisherige Themen, von denen kein neues mehr als die Hälfte enthält, sind als aufgeteilt aufgeführt. Die Flugblätter eines neuen Themas lassen sich vorab in der Flugblattliste ansehen. Erst mit „Übernehmen“ ersetzt das Ergebnis die bisherigen Themen, die als Sicherung erhalten bleiben. Entwürfe zählen bei der Neuberechnung nicht mit und brauchen danach „Themen zuordnen“ noch einmal.

## Tests und Codestil

Die Tests laufen im Container. Dort liegt `src/backend` unter `/app`, die Tests importieren aber `backend.app`; der Link in `/tmp/t` gleicht das aus:

```bash
docker compose exec -T backend sh -c 'mkdir -p /tmp/t && ln -sfn /app /tmp/t/backend && cd /tmp && PYTHONPATH=/tmp/t python -m pytest /tmp/t/backend/tests -q -p no:cacheprovider --ignore=/tmp/t/backend/tests/test_scripts.py --ignore=/tmp/t/backend/tests/test_corpus_stats.py'
```

Im Container fehlt das Verzeichnis `scripts/`. `test_scripts.py` und `test_corpus_stats.py` brechen dort ab und laufen lokal: `python -m pytest src/backend/tests/test_scripts.py src/backend/tests/test_corpus_stats.py`. Die übrigen Tests scheitern lokal zu rund 30, weil dort die Templates unter `app/templates` und die Trigramm-Suche von FTS5 fehlen. Das ist kein Fehler im Code.

Die Tests berühren die echte Datenbank nie. Die wenigen, die eine gebaute Datenbank brauchen (Markierung `built_db`), laufen auf einer Kopie der Datei in `LEAFLET_BUILT_DB` und werden sonst übersprungen. `test_scripts.py` prüft die Werkzeuge in `scripts/`. Den Codestil prüft `pycodestyle`. Commits folgen den Conventional Commits.

## Dokumentation

Die Dokumentation liegt unter `docs/`: der Bericht in `bericht/`, die Handbücher in `handbuch/`, dazu `kennzahlen.md`, `glossar.md`, `literatur.bib` und `abbildungen/`. Die Navigation der Website legt `mkdocs.yml` fest; eine neue Seite muss dort eingetragen werden. Arbeitsnotizen in `docs/arbeitsdokumente/` sind nicht im Repository.

- **Zahlen** nur aus `kennzahlen.md` übernehmen und mit Stand angeben.
- **Modelle und Dienste** immer mit Version und Datum nennen.
- **Herstellerangaben** (z. B. Benchmark-Werte) als solche kennzeichnen und von eigenen Messungen trennen.
- **Handbücher** im selben Pull Request ändern wie den Code, den sie beschreiben.
- Hinweise zum Schreiben stehen als `<!-- Kommentar -->` in den Dateien und werden beim Zusammenfügen nicht ausgegeben.

```bash
pip install -r docs/requirements.txt        # einmalig, am besten in einer venv
python -m mkdocs serve -a 127.0.0.1:8001    # Vorschau beim Schreiben, Port 8000 hat die App
python scripts/build_report.py              # bericht.pdf, braucht Pandoc und XeLaTeX
python scripts/build_report.py bericht.tex  # für Overleaf
```

Das PDF beginnt mit dem Abschnitt „Kurzfassung“ der Startseite (`docs/README.md`), dann folgen die Kapitel und das Glossar.

Die Abbildungen erzeugen `scripts/scan_figures.py`, `scripts/app_screenshots.py` und danach `scripts/workflow_figure.py` (App muss laufen); die Diagramme `scripts/corpus_figures.ipynb` mit `STIL = 'doku'` (braucht pandas, matplotlib und Jupyter; liest die Datenbank der laufenden App). Die Bilder der Import-Schritte erzeugt `scripts/import_screenshots.py` an einer Testinstanz (siehe `scripts/README.md`).
