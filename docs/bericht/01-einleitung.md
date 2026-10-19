# 1 Einleitung

Ziel des Projekts war, die Scans der Allgemeinen Flugblattsammlung so zu erschließen, dass jedes Flugblatt einzeln auffindbar ist und das Archiv neue Bände selbst einlesen kann. Dafür durchläuft jeder Band fünf Arbeitsschritte, die jeweils so weit automatisiert sind, wie es die Qualität erlaubt. Wo ein Mensch prüfen muss, sagt das jeweilige Kapitel.

## 1.1 Motivation und Ausgangslage

Die Allgemeine Flugblattsammlung des Universitätsarchivs Regensburg (Rep. 118) bewahrt, was Studierende und Hochschulgruppen zwischen 1967 und 1973 selbst geschrieben, vervielfältigt und verteilt haben: Aufrufe zu Streiks und Vollversammlungen, Wahlprogramme, Stellungnahmen zum Hochschulgesetz, Satire. Die Akten der Universität zeigen diese Jahre aus Sicht der Verwaltung, die Flugblätter aus Sicht derer, die sich zu Wort meldeten. Sie geben Einblick in die Mentalitäten der Studierenden, und sie richten sich „stets an eine Öffentlichkeit“ [@hamburg-flugblaetter].

Regensburg war damals eine junge Universität, der Vorlesungsbetrieb begann am 6. November 1967. Harte Auseinandersetzungen im Sinne der 68er-Bewegung gab es zunächst nicht. Scharfe Proteste mit Massendemonstrationen setzten erst ein, als bekannt wurde, dass der Freistaat mit dem neuen Bayerischen Hochschulgesetz die Drittelparität in den Gremien und die verfasste Studierendenschaft abschaffen wollte. Andreas Becker nennt die Jahre 1971 bis 1973 in seinem Lexikonartikel „die eigentlich revolutionäre Zeit“ der Universität, auch wegen der Wahl des Physikers Gustav Obermair zum Rektor, der damals als Marxist verschrien war [@becker2021]. In der Sammlung handeln die beiden größten Themen vom Hochschulgesetz (Kap. 7).

Bis zu diesem Projekt lagen die 4 464 Seiten nur als Fotos vor, die das Archiv seit Herbst 2025 anfertigt. Es gab keinen Volltext, keine Grenzen zwischen den Flugblättern und keine Angaben zu Titel, Datum oder Herausgeber. Wer wissen wollte, welche Gruppen sich zum Hochschulgesetz äußerten, musste die Bände Seite für Seite durchsehen. Heute findet eine Suche 304 der 1 547 Flugblätter, die das Gesetz nennen, von 71 verschiedenen Herausgebern (Export vom 17.10.2026).

Andere Universitäten haben ihre Flugblätter aus dieser Zeit ebenfalls digitalisiert. Die TU Berlin zeigt rund 1 800 Flugblätter der Jahre 1965 bis 1972 in Kitodo, mit Volltextsuche [@tub-flugblaetter]. In Frankfurt verzeichnet eine private Sammlung 403 Flugblätter von 1967 bis 1969 von Hand nach Datum, Urheber, Thema und Art [@frankfurt-flugblaetter]. Die Sammlung der Universität Hamburg mit über 10 000 Flugblättern ist nach Anton F. Guhl und Alexandra Jaeger kaum erschlossen [@hamburg-flugblaetter]; ihr Blogbeitrag erschien 2013 überarbeitet und erweitert im Druck [@guhl2013]. Soweit wir sehen, wurden die Angaben je Flugblatt überall von Hand erfasst [offen: für TU Berlin prüfen]. Eine Flugblattsammlung einer deutschen Universität, die ähnlich automatisch erschlossen wird und die das Archiv selbst fortführen kann, kennen wir nicht (Stand Oktober 2026).

Guhl und Jaeger nennen für die Hamburger Sammlung drei Hürden, die auch in Regensburg bestehen:

| Hürde nach Guhl und Jaeger | Arbeitsschritt | Stand in Regensburg |
|---|---|---|
| Dubletten machen die Zahl der Flugblätter unsicher | Mehrfachexemplare zusammenführen (Kap. 6) | 1 927 Exemplare ergeben 1 547 Flugblätter |
| Viele Blätter nennen keine Verantwortlichen | Herausgeber mit Beleg und Register (Kap. 5) | 241 Flugblätter bleiben ohne erkannten Herausgeber |
| Ohne Parallelüberlieferung ist das Datieren schwer | Datum mit Beleg, sonst Jahr des Bandes (Kap. 5) | 46 % tragen ein Datum auf dem Blatt |

Der größte Teil der Arbeit läuft automatisch (Kap. 1.5). Für jeden Wert, den das Sprachmodell ausliest, nennt es die Textstelle, auf die er sich stützt; so lässt sich jede Angabe am Scan nachprüfen. Von Hand bestätigt ein Mensch nur die Grenzen zwischen den Flugblättern und die Gruppen von Mehrfachexemplaren. Texterkennung und Metadaten kosten zusammen rund 18 $ je 1 000 Seiten (hochgerechnet, Kap. 11), und neue Bände liest das Archiv in der Anwendung selbst ein (Kap. 9).

## 1.2 Ziele

- Durchsuchbares Korpus mit einem Datensatz je Flugblatt.
- Anwendung zum Erkunden.
- Import neuer Bände durch das Archiv.

## 1.3 Projekt

Das Projekt entstand im Praxisseminar [offen: Name des Seminars] im Sommersemester 2026; drei Studierende haben es durchgeführt, Ansprechpartner im Universitätsarchiv war Andreas Becker. Organisation, Verlauf und die wichtigsten Entscheidungen beschreibt Kapitel 12.

## 1.4 Lesepfade

- Archiv: Kurzfassung, Kap. 8, Kap. 10, Handbücher.
- Weiterentwicklung: Kap. 4–7 (je Abschnitt „Hinweise zur Weiterentwicklung“), Kap. 9, Handbuch Betrieb.
- Forschung: Kap. 2, 8 und 10.

## 1.5 Gesamtablauf

Jeder Band durchläuft dieselben Schritte. Ein OCR-Dienst erkennt den Text der Scans. Danach wird der Band in einzelne Flugblätter geteilt: Die Anwendung schlägt die Grenzen vor, ein Mensch bestätigt jede. Ein Sprachmodell liest Titel, Datum und Herausgeber aus. Mehrfachexemplare schlägt die Anwendung wieder nur vor, entschieden wird von Hand. Zuletzt ordnet ein Themenmodell jedem Flugblatt ein Thema zu.

![Ablauf vom Scan zur Anwendung](../abbildungen/ablauf.png)

*Abbildung: Flugblatt 850 in den einzelnen Schritten. Bild 5 zeigt das Nachbarblatt auf S. 396, weil 850 kein weiteres Exemplar hat.*

<!-- Abbildung aus scripts/workflow_figure.py, nach scan_figures.py und app_screenshots.py -->

Die Kapitel 3 bis 7 behandeln je einen dieser Schritte. Kapitel 3 beschreibt ausführlich, wie wir das OCR-System ausgewählt haben. Die Kapitel 4 bis 7 sind gleich aufgebaut: Sie beschreiben die Aufgabe und ihre Schwierigkeiten, das gewählte Verfahren und wie gut es arbeitet, was von Hand geprüft wird und was es kostet. Am Ende steht jeweils, was für die Weiterentwicklung offen ist. Als Beispiel zieht sich ein Flugblatt durch alle Kapitel: „Zur Fachschaftssatzung“ des MSB Spartakus vom 8. Februar 1972 (Band 006, S. 394).
