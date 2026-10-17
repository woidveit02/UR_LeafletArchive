# 9 Die Anwendung

Die Webanwendung dient zum Recherchieren im Bestand und zu seiner Pflege. Sie läuft lokal in Docker. Neue Bände kommen in sieben Schritten hinein, von den Scans bis zur Freigabe.

## 9.1 Anforderungen

- Bedienbar ohne technische Kenntnisse.
- Neue Bände selbst einlesen, Angaben korrigieren, Exemplare prüfen.

## 9.2 Recherchieren

![Leseansicht von Flugblatt 850](../abbildungen/app_leseansicht.png)

*Abbildung: Leseansicht von Flugblatt 850. Oben die Angaben mit Links zum Beleg, darunter der erkannte Text neben dem Scan. Rechts stehen Modell und Datum von Texterkennung und Metadaten.*

- Leseansicht mit Scan, erkanntem Text und Metadaten samt Belegen; Tastenkürzel zum Blättern.
- Volltextsuche über Titel, Reihe, Herausgeber und Text (SQLite FTS5); findet Wortteile und Schreibvarianten wie daß/dass; Feldsuche mit UND/ODER/NICHT.
- Filter nach Jahr, Herausgeber, Thema und Textsorte.
- Trends: Anteil der Flugblätter je Jahr oder Semester für Suchbegriffe.
- Themen und Seiten je Herausgeber.

## 9.3 Pflegen

- Metadaten korrigieren, Mehrfachexemplare prüfen.
- Export als ZIP und CSV.

## 9.4 Import neuer Bände

- Sieben Schritte: Band wählen, Scans hochladen, Text erkennen, Flugblätter trennen, Metadaten erzeugen, Prüfen & freigeben, Themen zuordnen (optional, auch nach der Freigabe).
- Themen neu berechnen mit Prüfseite für die Titel; Titel lassen sich unter Verwaltung › Themen ändern (Kap. 7).
- Bis zur Freigabe ist der Band ein Entwurf und in Liste, Suche und Trends unsichtbar.
- Kostenschätzung vor der Texterkennung und den Metadaten; unterbrochene Schritte lassen sich fortsetzen.
- Anleitung: `handbuch/band-einlesen.md`.

## 9.5 Architektur und Datenmodell

- FastAPI, Jinja2, SQLAlchemy, SQLite, Docker. Grundstruktur aus dem ASE-Projekt im Wintersemester 2025/26.
- Tabellen für Bände, Seiten, Flugblätter, Organisationen, Herausgeber-Zuordnungen und Themen, dazu der Suchindex.
- Korrekturen und Exemplar-Entscheidungen liegen als JSONL-Dateien in `data/`, nur angehängt.
- Export (Verwaltung, `src/backend/app/export.py`): ZIP mit `flugblaetter.jsonl` (alle Angaben und Volltext), `flugblaetter.csv` (ohne Volltext), `texte/<id>.txt`, `flugblatt_herausgeber.csv`, `herausgeber.csv`, `baende.csv`, `themen.csv` und auf Wunsch `seiten.jsonl` (Textblöcke mit Lage). Optionen: nur Hauptexemplare, ohne Unterzeichnende, ohne Seiten. Die `id` (`0118_0003_S127-128`) bleibt über Exporte gleich, solange die Seitengrenzen bleiben. Die Felder beschreibt die `README.md` im ZIP. Dazu lässt sich jede Liste der Anwendung als CSV laden.

## 9.6 Gestaltung

- Nach den Design-Richtlinien: wenig Farbe, der Normalfall bekommt keine Markierung, Zahlen stimmen mit den Listen dahinter überein.

## 9.7 Werkzeuge außerhalb der Anwendung

- N-Gramm-Werkzeug (`ngrams.py`: Häufigkeiten, Trends, Keyness, Kollokationen, KWIC), Anleitung in `handbuch/ngrams.md`.
- Notebook `vertiefung/forschungsfragen.ipynb`: zeigt, wie sich der Export für Auswertungen nutzen lässt. Die Fragen sind Beispiele, keine Ergebnisse des Projekts.

Beispielhafte Fragen im Notebook:

1. Wer spricht, und wie stark prägen die Sonderbände das Bild?
2. Welche Gruppen sind wann aktiv?
3. Wer gibt mit wem gemeinsam heraus?
4. Wer schreibt über wen?
5. Welche Themen besetzen die Gruppen?
6. Wie unterscheidet sich das Vokabular von RCDS und sozialistischen Gruppen? [@monroe2008]
7. Wie verläuft der Konflikt um das Bayerische Hochschulgesetz?
8. Wann im Jahr wird mobilisiert?
9. Wie international ist der Protest?
10. Wer unterschreibt, und für wen?
