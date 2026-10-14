# 1 Einleitung

Ziel des Projekts war, die Scans der Allgemeinen Flugblattsammlung so zu erschließen, dass jedes Flugblatt einzeln auffindbar ist und das Archiv neue Bände selbst einlesen kann. Dafür durchläuft jeder Band fünf Arbeitsschritte, die jeweils so weit automatisiert sind, wie es die Qualität erlaubt. Wo ein Mensch prüfen muss, sagt das jeweilige Kapitel.

## 1.1 Gegenstand und Ausgangslage

- Studentische Flugblätter der Universität Regensburg 1967–1973, vor allem Hochschulpolitik, Hochschulwahlen und Streiks, dazu bundespolitische und internationale Themen.
- Die Scans lagen vor, aber nur als Bilder: kein Volltext, keine Grenzen zwischen den Flugblättern, keine Angaben je Blatt.
- Erst ein erschlossener Bestand macht Fragen stellbar wie: Wer äußert sich wann wozu, was fehlt, wie verläuft ein Konflikt über die Semester [knapp halten, keine Ergebnisse].

## 1.2 Ziele

- Durchsuchbares Korpus mit einem Datensatz je Flugblatt.
- Anwendung zum Erkunden.
- Import neuer Bände durch das Archiv.

## 1.3 Projektorganisation

Das Projekt wurde im Praxisseminar [Name des Seminars] im Sommersemester 2026 von drei Studierenden durchgeführt. Betreut wurde es von [Namen der Betreuenden]; Ansprechpartner im Universitätsarchiv war Andreas Becker.

Das Team hat sich mindestens einmal wöchentlich besprochen, im Wechsel in Präsenz an der Universität und online. Hinzu kamen regelmäßige Sprechstunden mit den Betreuenden, in denen Zwischenstände vorgestellt und das weitere Vorgehen abgestimmt wurden.

Während der OCR-Evaluation [Zeitraum] wurden die Aufgaben auf einem Kanban-Board [Werkzeug] organisiert. [Mit Beginn der Entwicklung der Anwendung im September 2026 wurde die Arbeit über GitHub-Issues und Pull Requests mit gegenseitigem Review koordiniert.] Code und Dokumentation liegen im Git-Repository, die Scans und OCR-Rohdaten wegen ihrer Größe auf einem gemeinsamen Laufwerk.

<!-- Platzhalter in eckigen Klammern ergänzen; den Satz zu GitHub prüfen. -->

### Meilensteine

| Datum | Meilenstein |
|---|---|
| Mai 2026 | Gespräch im Universitätsarchiv, Entscheidung für Rep. 118 statt Sammlung Reisner |
| Juni 2026 | Erste Zwischenpräsentation |
| Juli 2026 | Vergleich der OCR-Systeme am 100-seitigen Testkorpus |
| August 2026 | OCR des Gesamtbestands, Abschluss des manuellen Splittens |
| September 2026 | Findmitteldaten des Archivs, Metadatenextraktion, Beginn der Anwendung |
| Oktober 2026 | Import-Ablauf für neue Bände, Abschlusspräsentation |

### Entscheidungen im Überblick

| Datum | Entscheidung | Kapitel |
|---|---|---|
| Mai 2026 | Rep. 118 statt Sammlung Reisner | 2 |
| Juli 2026 | Datalab API, Modus accurate | 3 |
| August 2026 | Texterkennung vor der Trennung | 4 |
| September 2026 | FastAPI, Jinja2 und SQLAlchemy | 9 |

<!-- Daten auf den Tag genau ergänzen. -->

<!-- Daten auf den Tag genau ergänzen. Beleg für „Chandra OCR 2“ siehe Kap. 3. -->

## 1.4 Lesepfade

- Archiv: Kurzfassung, Kap. 8, Kap. 10, Handbücher.
- Weiterentwicklung: Kap. 3–7 (je Abschnitt „Für die Weiterarbeit“), Kap. 9, Handbuch Betrieb.
- Forschung: Kap. 2, 8 und 10.

## 1.5 Gesamtablauf

- Abbildung: Scan → Text → Flugblätter → Metadaten → Mehrfachexemplare → Themen → Anwendung, je Schritt markiert als automatisch oder von Hand geprüft.
- Kapitel 3–7 folgen diesem Ablauf und haben denselben Aufbau: Aufgabe, Herausforderungen, Verfahren und Entscheidung, Wie gut, Was von Hand bleibt, Kosten, Für die Weiterarbeit.
