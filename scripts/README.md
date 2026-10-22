# Skripte

Werkzeuge, die neben der Anwendung auf dem eigenen Rechner laufen. Aufruf immer aus dem Repository, zum Beispiel `python scripts/ngrams.py size`. Jedes Skript erklärt seine Optionen mit `--help`.

Skripte, die den Scan-Ordner lesen, nehmen den Pfad aus `LEAFLET_PDF_HOST_DIR` in `.env`; mit `--ordner` lässt sich ein anderer angeben.

## Scans und Pflege

| Skript | Wofür | Braucht |
|---|---|---|
| `tiff_to_pdf.py ORDNER` | TIFF-Scans zu einem PDF zusammenfügen, wie Schritt 2 des Imports | PyMuPDF |
| `learn_boundary_weights.py` | Die Gewichte des Trennvorschlags aus allen getrennten Bänden neu lernen und mit denen in `src/backend/app/boundaries.py` vergleichen. Lohnt sich, wenn deutlich mehr Bände dazugekommen sind. | nur Python |

## Auswertung

| Skript | Wofür | Braucht |
|---|---|---|
| `ngrams.py` | N-Gramme, Trends, Kollokationen und Belegstellen auf den OCR-Texten; Handbuch: `docs/handbuch/ngramme-auswerten.md` | nur Python |
| `stopwords_de.txt` | Stoppwortliste für `ngrams.py` | |

## Bericht

| Skript | Wofür | Braucht |
|---|---|---|
| `corpus_stats.py` | Zahlen zum Korpus nach `docs/kennzahlen.md` schreiben | Pakete der App, gebaute Datenbank |
| `corpus_figures.ipynb` | Diagramme für Kapitel 8 und Präsentationen | pandas, matplotlib, Jupyter |
| `scan_figures.py`, `app_screenshots.py`, `workflow_figure.py` | Abbildungen für Bericht und Handbücher | laufende App; `app_screenshots.py` zusätzlich playwright |
| `import_screenshots.py` | Abbildungen der Import-Schritte für `docs/handbuch/neue-baende-importieren.md`; nur gegen eine Testinstanz mit kopierten Daten auf Port 8002, weil die Trennansicht Seitenwechsel als geprüft markiert | playwright, Band 015 als Entwurf in Schritt 6 |
| `boundary_figure.py` | Abbildung der Hinweise und Gewichte des Trennvorschlags für Kapitel 4, direkt aus `boundaries.py` | matplotlib |
| `boundary_example.py` | Zwei echte Seitenwechsel aus Band 006 mit den Gründen des Trennvorschlags, für Kapitel 4 | PyMuPDF, numpy, scipy, Pillow, gebaute Datenbank, Scan-Ordner |
| `build_report.py` | Bericht als PDF | pandoc, xelatex |

`scan_folder.py` ist kein eigenes Werkzeug: Es findet den Scan-Ordner und die Bände darin für die anderen Skripte.

Die Tests liegen in `src/backend/tests/test_scripts.py`.
