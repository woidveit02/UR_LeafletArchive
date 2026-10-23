# Übersicht

Diese Dokumentation beschreibt, wie aus den Scans der Allgemeinen Flugblattsammlung der Universität Regensburg (1967–1973) ein durchsuchbares Korpus entstanden ist, wie Sie damit arbeiten und wie Sie neue Bände einlesen.

## Kurzfassung

Grundlage sind 14 Bände der Allgemeinen Flugblattsammlung (Universitätsarchiv, Rep. 118) aus den Jahren 1967–1973, zusammen 4464 Seiten Fotoscans. Daraus sind 1926 Exemplare entstanden, davon 1546 verschiedene Flugblätter, jedes mit Volltext und Metadaten.

Die Anwendung läuft lokal in Docker. Darin können Sie recherchieren, mit Suche, Filtern, Trends und Themen, und den Bestand pflegen: Metadaten korrigieren, Mehrfachexemplare prüfen, neue Bände importieren und alles exportieren.

Wie verlässlich die Daten sind, hängt vom Schritt ab. Im Text sind etwa 6 von 1000 Zeichen falsch, eher eine Untergrenze. Trennung und Mehrfachexemplare haben wir von Hand geprüft. Fast jeder Wert der Metadaten hat eine Belegstelle, ihre Genauigkeit ist aber noch nicht gemessen (Kap. 5.4). Die Themen sind eine automatische Schätzung, 407 Flugblätter sind nur unsicher zugeordnet.

Ein neuer Band kostet etwa 19 $ je 1000 Seiten, rund 10 $ für die Texterkennung und 9 $ für die Metadaten, beides am Testimport gemessen. Dazu kommt Handarbeit beim Trennen und Prüfen.

## Aufbau der Dokumentation

Der Bericht folgt einem Band durch die Verarbeitung, vom Bestand über Texterkennung, Trennen, Metadaten, Mehrfachexemplare und Themen bis zur Anwendung, und endet mit Grenzen, Zusammenfassung und Projektverlauf. Die Handbücher sind Anleitungen zum Nachschlagen. Im Anhang stehen alle Kennzahlen mit Datum und die Begriffe.

Wo Sie anfangen, hängt davon ab, was Sie vorhaben:

- Im Universitätsarchiv: [Recherche](handbuch/recherchieren.md), [Pflege](handbuch/pflegen.md) und [Import neuer Bände](handbuch/neue-baende-importieren.md), danach [Kapitel 8](bericht/08-korpus-in-zahlen.md) und [Kapitel 10](bericht/10-grenzen-ausblick.md).
- Für die Forschung: [Kapitel 2](bericht/02-bestand.md), [8](bericht/08-korpus-in-zahlen.md) und [10](bericht/10-grenzen-ausblick.md), dann [Textauswertung](handbuch/ngramme-auswerten.md) und das Notebook `scripts/forschungsfragen.ipynb`.
- Für die Weiterentwicklung: [Weiterentwicklung](handbuch/weiterentwickeln.md), [Installation und Betrieb](handbuch/installieren-und-betreiben.md) und [Kapitel 9](bericht/09-anwendung.md).

Die Belege zur Evaluation der Texterkennung liegen im Arbeits-Repository ([Kapitel 12.6](bericht/12-projektverlauf.md#126-werkzeuge-und-repositories)).
