# Übersicht

Diese Dokumentation beschreibt, wie aus den Scans der Allgemeinen Flugblattsammlung der Universität Regensburg (1967–1973) ein durchsuchbares Korpus und eine Anwendung zu seiner Erkundung entstanden sind, und wie sich neue Bände einlesen lassen.

## Kurzfassung

- Bestand: Allgemeine Flugblattsammlung der Universität Regensburg (Universitätsarchiv, Rep. 118), 14 Bände aus den Jahren 1967–1973, 4464 Seiten als Fotoscans.
- Ergebnis: 1927 Exemplare, davon 1547 verschiedene Flugblätter, jedes mit Volltext und Metadaten.
- Anwendung zum Recherchieren (Suche, Filter, Trends, Themen) und Pflegen (Korrekturen, Exemplare, Import, Export), läuft lokal in Docker.
- Verlässlichkeit: Der Text ist sehr genau, etwa 6 falsche Zeichen von 1000, eher eine Untergrenze. Trennung und Mehrfachexemplare sind von Hand geprüft. Metadaten haben je Wert eine Belegstelle, ihre Genauigkeit ist aber noch nicht gemessen (Kap. 5.4). Themen sind eine automatische Schätzung, 408 Flugblätter sind nur unsicher zugeordnet.
- Ein neuer Band kostet etwa 19 $ je 1000 Seiten (Texterkennung ca. 10 $, Metadaten ca. 9 $, beides am Testimport gemessen), dazu Handarbeit beim Trennen und Prüfen.

## Aufbau der Dokumentation

Der **Bericht** folgt einem Band durch die Verarbeitung, vom Bestand über Texterkennung, Trennen, Metadaten, Mehrfachexemplare und Themen bis zur Anwendung, und endet mit Grenzen, Zusammenfassung und Projektverlauf. Die **Handbücher** sind Anleitungen zum Nachschlagen. Im **Anhang** stehen alle Kennzahlen mit Datum und die Begriffe.

- **Universitätsarchiv:** [Recherche](handbuch/recherchieren.md), [Pflege](handbuch/pflegen.md), [Import neuer Bände](handbuch/neue-baende-importieren.md), dann [Kapitel 8 Korpus in Zahlen](bericht/08-korpus-in-zahlen.md) und [10 Grenzen](bericht/10-grenzen-ausblick.md).
- **Forschung:** [Kapitel 2 Bestand](bericht/02-bestand.md), [8 Korpus in Zahlen](bericht/08-korpus-in-zahlen.md) und [10 Grenzen](bericht/10-grenzen-ausblick.md), dann [Textauswertung](handbuch/ngramme-auswerten.md) und das Notebook `scripts/forschungsfragen.ipynb`.
- **Entwicklung:** [Weiterentwicklung](handbuch/weiterentwickeln.md), [Installation und Betrieb](handbuch/installieren-und-betreiben.md) und [Kapitel 9 Anwendung](bericht/09-anwendung.md).

Die Belege zur OCR-Evaluation liegen im archivierten Arbeits-Repository ([Kapitel 12.6](bericht/12-projektverlauf.md#126-werkzeuge-und-repositories)).
