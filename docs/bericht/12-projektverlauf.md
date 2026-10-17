# 12 Projektverlauf und Organisation

Wer hat was gemacht, wie wurde gearbeitet, wann fiel welche Entscheidung. Das Kapitel hilft einzuordnen, warum der Bestand heute so erschlossen ist, und wen man fragen kann.

## 12.1 Team und Betreuung

Das Projekt wurde im Praxisseminar [Name des Seminars] im Sommersemester 2026 von drei Studierenden durchgeführt. Betreut wurde es von [Namen der Betreuenden]; Ansprechpartner im Universitätsarchiv war Andreas Becker.

Aufgabenverteilung im Team: [offen: wer war wofür zuständig, z. B. OCR-Evaluation, Trennen, Metadaten, Anwendung, Themen].

## 12.2 Arbeitsweise

Das Team hat sich mindestens einmal wöchentlich besprochen, im Wechsel in Präsenz an der Universität und online. Hinzu kamen regelmäßige Sprechstunden mit den Betreuenden, in denen Zwischenstände vorgestellt und das weitere Vorgehen abgestimmt wurden.

Während der OCR-Evaluation [Zeitraum] wurden die Aufgaben auf einem Kanban-Board in Trello organisiert. Mit Beginn der Entwicklung der Anwendung im September 2026 wurde die Arbeit über GitHub-Issues und Pull Requests koordiniert; die Pull Requests hat Felix [offen: Nachname] geprüft. Code und Dokumentation liegen im Git-Repository, die Scans und OCR-Rohdaten wegen ihrer Größe auf einem gemeinsamen Laufwerk.

## 12.3 Verlauf

| Datum | Meilenstein |
|---|---|
| Mai 2026 | Gespräch im Universitätsarchiv, Entscheidung für Rep. 118 statt Sammlung Reisner |
| Juni 2026 | Erste Zwischenpräsentation |
| Juli 2026 | Vergleich der OCR-Systeme am 100-seitigen Testkorpus |
| August 2026 | OCR des Gesamtbestands, Abschluss des manuellen Splittens |
| September 2026 | Findmitteldaten des Archivs, Metadatenextraktion, Beginn der Anwendung |
| Oktober 2026 | Import-Ablauf für neue Bände, Abschlusspräsentation |

## 12.4 Entscheidungen im Überblick

| Datum | Entscheidung | Kapitel |
|---|---|---|
| Mai 2026 | Rep. 118 statt Sammlung Reisner | 2 |
| Juli 2026 | Datalab API, Modus accurate | 3 |
| August 2026 | Texterkennung vor der Trennung | 4 |
| September 2026 | FastAPI, Jinja2 und SQLAlchemy | 9 |

<!-- Daten auf den Tag genau ergänzen. -->

## 12.5 Erfahrungen für ein Folgeprojekt

- [offen: was hat gut funktioniert, was würde das Team anders machen; z. B. früher eine Referenzstrecke für die Metadaten festlegen, Prompt-Fassungen von Anfang an versionieren]
