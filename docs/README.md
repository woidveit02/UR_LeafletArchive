# Dokumentation: Digitale Erschließung der Flugblattsammlung Rep. 118

Diese Dokumentation beschreibt, wie aus den Scans der Allgemeinen Flugblattsammlung der Universität Regensburg (1967–1973) ein durchsuchbares Korpus und eine Anwendung zu seiner Erkundung entstanden sind, und wie sich neue Bände einlesen lassen.

## Aufbau

| Teil | Inhalt |
|---|---|
| [`bericht/`](bericht/) | Projektbericht: Vorgehen, Entscheidungen, Evaluation. Kapitel in der Reihenfolge, in der ein Band verarbeitet wird. Ältere Fassungen liegen in `arbeitsdokumente/alte-gliederung/`. |
| [`handbuch/`](handbuch/) | Anleitungen: neuen Band einlesen, Analysewerkzeug, Betrieb. |
| [`vertiefung/`](vertiefung/) | Detailstudien, auf die der Bericht verweist. |
| [`kennzahlen.md`](kennzahlen.md) | Alle Zahlen zum Korpus mit Datum. Einzige Quelle für Zahlen im Bericht. |
| [`glossar.md`](glossar.md) | Begriffe. |
| [`literatur.bib`](literatur.bib) | Quellen. |
| [`abbildungen/`](abbildungen/) | Abbildungen für Bericht und Handbücher. |

Belege zur OCR-Evaluation liegen außerhalb dieses Ordners unter `eval/ocr/`.

## Lesepfade

- **Universitätsarchiv:** [Kurzfassung](bericht/00-kurzfassung.md), [Neuen Band einlesen](handbuch/band-einlesen.md), dann [Kapitel 8 Korpus in Zahlen](bericht/08-korpus-in-zahlen.md) und [10 Grenzen](bericht/10-grenzen-ausblick.md).
- **Forschung:** [Kapitel 2 Bestand](bericht/02-bestand.md), [8 Korpus in Zahlen](bericht/08-korpus-in-zahlen.md) und [10 Grenzen](bericht/10-grenzen-ausblick.md), dann das Notebook unter `vertiefung/`.
- **Entwicklung:** [Betrieb](handbuch/betrieb.md), Kapitel 3–7 (je Abschnitt „Für die Weiterarbeit“) und [Kapitel 9 Anwendung](bericht/09-anwendung.md).

## Bericht

0. [Kurzfassung](bericht/00-kurzfassung.md)
1. [Einleitung](bericht/01-einleitung.md)
2. [Der Bestand](bericht/02-bestand.md)
3. [Text erkennen](bericht/03-text-erkennen.md)
4. [Flugblätter trennen](bericht/04-trennen.md)
5. [Metadaten erzeugen](bericht/05-metadaten.md)
6. [Mehrfachexemplare zusammenführen](bericht/06-mehrfachexemplare.md)
7. [Themen zuordnen](bericht/07-themen.md)
8. [Das Korpus in Zahlen](bericht/08-korpus-in-zahlen.md)
9. [Die Anwendung](bericht/09-anwendung.md)
10. [Grenzen und Ausblick](bericht/10-grenzen-ausblick.md)
11. [Zusammenfassung](bericht/11-zusammenfassung.md)

## Konventionen

- **Zahlen** nur aus `kennzahlen.md` übernehmen und mit Stand angeben.
- **Modelle und Dienste** immer mit Version und Datum nennen.
- **Herstellerangaben** (z. B. Benchmark-Werte) als solche kennzeichnen und von eigenen Messungen trennen.
- **Handbücher** im selben Pull Request ändern wie den Code, den sie beschreiben.
- Hinweise zum Schreiben stehen als `<!-- Kommentar -->` in den Dateien und werden beim Zusammenfügen nicht ausgegeben.

## Bericht zusammenfügen

```bash
pandoc docs/bericht/*.md --citeproc --bibliography docs/literatur.bib -o bericht.pdf
pandoc docs/bericht/*.md --citeproc --bibliography docs/literatur.bib -o bericht.tex   # für Overleaf
```
