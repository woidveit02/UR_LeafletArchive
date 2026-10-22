# 12 Projektverlauf und Organisation

<!-- Stand 22.10.2026: Stichpunkte als Gerüst. Anlass: Die Betreuenden möchten Methoden, Werkzeuge, Aufgabenplanung,
     Meilensteine, Aufwände, positive wie negative Erfahrungen und Fehleinschätzungen deutlicher sehen.
     Quellen: Google-Doc „Notizen“ (Besprechungen und Sprechstunden), Trello-Board „Praxisseminar-OCR“ (Screenshot
     vom Endstand), git beider Repositories, Antritts- und Abschlussvortrag, Angaben des Teams vom 22.10.
     Sammelstelle der Antworten: arbeitsdokumente/offene-punkte.md, Abschnitt „Projektmanagement“.
     [offen: …] = muss das Team noch klären oder ausformulieren. Am Ende im Stil der übrigen Kapitel ausformulieren. -->

Dieses Kapitel dokumentiert den zeitlichen Verlauf sowie wesentliche Entscheidungen des Projekts. Es zeigt, wie die Arbeit im Team organisiert und koordiniert wurde, welche Arbeits- und Entwicklungsschritte aufeinanderfolgten und wo die für das Projekt relevanten Informationen und Ansprechpartner zu finden sind.

## 12.1 Team, Rollen und Betreuung

Das Projekt wurde im Rahmen des Praxisseminars des Masterstudiengangs Medieninformatik im Sommersemester 2026 von drei Studierenden durchgeführt. Betreut wurde das Projekt in erster Instanz von Thomas Schmidt sowie von Prof. Dr. Christian Wolff, Niklas Donhauser und Jakob Fehle.  Andreas Becker war als Archivar der Universität der zentrale Ansprechpartner auf Seiten des Archivs und damit ein wesentlicher Stakeholder des Projekts.

Die Schwerpunkte der Arbeit sind in folgender Tabelle aufgelistet:

  | Bereich | Wer |
  |---|---|
  | Testkorpus für die OCR (Ziehung der 100 Seiten) | Veit |
  | OCR-Tests: Datalab, Mistral OCR 4, Claude Sonnet 5, Gemini 3.5 Flash, Qwen3-VL | Felix |
  | OCR-Tests: GLM-OCR | Sebastian |
  | OCR-Tests: MinerU (über die API), PaddleOCR | [offen: wer] |
  | Seitenvergleich Datalab gegen Mistral, Goldstandard | alle drei, je ein Drittel |
  | Werkzeuge: OCR-Viewer, Splitter, OCR-Pipeline für alle Bände | Felix |
  | Trennen von Hand | Felix Nr. 001–003 (danach von Veit geprüft), Sebastian Nr. 004–008, Veit Nr. 009–014 |
  | Metadatenextraktion (Prompt, Pipeline, Läufe) | Felix; Felder vom Team gemeinsam festgelegt |
  | Topic Modelling, erster Versuch NER | Veit |
  | Mehrfachexemplare prüfen (320 Fälle, mit Korrektur der Metadaten) | Sebastian |
  | App: Repository, Grundgerüst und Datenbank | Veit und Sebastian |
  | App: Filter, Suche | Sebastian [offen: prüfen] |
  | App: Themen in der App | Veit |
  | App: Datenmodell, Import und Verwaltung, Export, Zusammenführung auf `main` | Felix |
  | Kommunikation mit dem Archiv (Findmittel, Rückfragen) | Veit |

Das Ausformulieren der einzelnen Kapitel der Dokumentation wurde wie folgt aufgeteilt: Veit, Kapitel 1, 2, 3, 7, 10; Sebastian, Kapitel 4, 5, 6; Felix, Kapitel 0, 8, 9, 11, Kennzahlen, Handbücher, Glossar, READMEs und Texte in der Anwendung; Kapitel 12 wurde gemeinsam erarbeitet

- [offen: Tabelle mit dem Team abgleichen, v. a. die App-Zeilen und wer Trends, Exemplarprüfung und Suche gebaut hat.]

## 12.2 Arbeitsweise und Werkzeuge

**Phasen.** Das Projekt lief in zwei Phasen mit unterschiedlicher Organisation:

- Phase 1 (Ende Juni bis Mitte August): Bestand aufbereiten, OCR auswählen und prüfen, alle Bände erkennen. Organisiert als Kanban in Trello.
- Phase 2 (ab September): Metadaten, Mehrfachexemplare, Themen und die Anwendung. Organisiert über GitHub-Issues, Branches und Pull Requests im App-Repository.

**Kanban in Trello (Phase 1).**

- Board „Praxisseminar-OCR“, genutzt ab Ende Juni (vor der Ziehung des Testkorpus am 30.06.) bis zur OCR aller Bände.
- Spalten: Backlog, Diese Woche, Review, Fertig, Fragen. „Diese Woche“ war die Wochenplanung aus dem Treffen, „Review“ die gegenseitige Prüfung, „Fragen“ die Sammlung für Sprechstunden und Archiv.
- Labels nach Arbeitsbereich: Rohdaten aufbereiten (PDF, TIFF), OCR-Vergleich (Pipelines für die Systeme, Einbindung in den OCR-Viewer), OCR-Validierung (Goldstandard, CER).
- Jede Karte mit verantwortlicher Person, gemeinsame Arbeit als eigene Karten je Person (z. B. „OCR-Vergleich S. 1–33 / 34–66 / 67–100“). Am Ende 17 Karten erledigt, Fälligkeitsdatum z. B. für „OCR aller Bände mit Datalab“ am 30.08.
- Vom Board gibt es nur einen Screenshot des Endstands. [offen: JSON-Export des Boards versuchen, er enthält jede Verschiebung mit Datum.]

**GitHub (Phase 2).**

- Grund für den Wechsel: Mit dem neuen Repository lag alles an einem Ort, und die Arbeit fand vor allem im Code statt.
- Issues meist von Felix angelegt; Labels `data`, `feature`, UI-Änderungen und `topic modelling`.
- Alle arbeiteten auf eigenen Branches (`dev-search`, `dev-topics`, `dev-trends`, `dev-copy-review`, `dev-import` oder aus einem Issue benannt). Felix verwaltete `main`, testete Pull Requests lokal, löste Konflikte und führte zusammen. Kleinere Änderungen gingen direkt auf `main`.
- Commit-Nachrichten nach Conventional Commits.

**Besprechungen.**

- Wöchentliches Treffen, meist von Felix moderiert: Jede Person berichtet ihren Stand, dann werden die Aufgaben bis zum nächsten Treffen verteilt. Ab 19.08. mit Protokoll (Stand je Person, TODOs).
- Kein fester Wochentag, am häufigsten dienstags. Teils in Präsenz an der Universität, teils online auf Discord.
- Während Sebastians Abwesenheit (08.–16.09.) wurden die Aufgaben vorher fest verteilt.
- Dazwischen Abstimmung über WhatsApp.

**Sprechstunden und Archiv** (Termine siehe 12.3): Vorstellung der Zwischenstände und Abstimmung der nächsten Schritte, je vor den Präsentationen eine Sprechstunde mit Thomas Schmidt. Rückmeldungen der Betreuung haben die Richtung mitbestimmt, z. B. der Wunsch nach Import und Korrektur in der Anwendung, bedienbar ohne technische Kenntnisse (07.10.).

**Qualitätssicherung bei der Handarbeit.**

- Goldstandard: Regeln, was als Fehler gilt, vorher gemeinsam festgelegt und danach nachgeschärft; die Seiten 1–5 von allen dreien bearbeitet, um die Übereinstimmung zu prüfen (Kap. 3.7).
- Trennen: zweiter Durchgang am 29.09. mit einer automatischen Verdachtsliste (`check_boundaries.py`, 254 Fälle, 77 entschieden, 30 Schnitte geändert); dabei die Regeln für Grenzfälle festgehalten (Kap. 4.2).
- Mehrfachexemplare: jede vorgeschlagene Gruppe von Hand bestätigt oder verworfen (Kap. 6.5).

**Werkzeuge.**

| Werkzeug | Wofür |
|---|---|
| Trello | Aufgabenplanung in Phase 1 (Kanban) |
| GitHub | Code, Issues, Branches, Pull Requests; zwei Repositories (Pipeline bis September, danach die Anwendung) |
| Google Drive und Google Docs | Scans und OCR-Ergebnisse (wegen der Größe), Besprechungsnotizen, Seitenvergleich |
| Zotero | gemeinsame Bibliothek, u. a. Working Papers und Blogbeiträge zu den OCR-Modellen |
| Discord, WhatsApp | Online-Treffen, Abstimmung zwischen den Treffen |
| Eigene Werkzeuge | OCR-Viewer (Vergleich der Systeme, Goldstandard), Splitter (Trennen von Hand, Prüfmodus) |
| MkDocs, Pandoc | Dokumentation als Website und PDF aus Markdown im Repository |
| Claude Code | Programmieren und Schreiben, siehe 12.8 |

- Eine Overleaf-Vorlage für Abschlussarbeiten (Notiz 31.08.) wurde verworfen: Bei vielen Abbildungen und Tabellen und für Anwenderinnen und Anwender ist eine Dokumentation als Website näher an der Struktur der Anwendung. Sie liegt deshalb als Markdown im Repository (MkDocs); das PDF entsteht daraus mit Pandoc.

## 12.3 Verlauf und Meilensteine

| Datum | Ereignis |
|---|---|
| 12.05. | Erste Projektsprechstunde (Prof. Wolff, Thomas Schmidt): Ziele, zunächst Sammlung Reisner |
| 20.05. | Termin mit Andreas Becker, Besichtigung des Archivs; dabei wird klar: Allgemeine Flugblattsammlung statt Sammlung Reisner. Danach Sprechstunde mit Prof. Wolff und Jakob Fehle zum weiteren Vorgehen |
| 27.05. | Erste Teambesprechung (Discord) |
| 08.06. | Sprechstunde Thomas Schmidt zur ersten Präsentation |
| **09.06.** | **Antrittsvortrag** |
| Ende Juni | Start des Trello-Boards; 23.06. erster Test der Datalab API |
| 30.06. | Testkorpus aus 100 Seiten |
| 08.07. | Sprechstunde Thomas Schmidt zur zweiten Präsentation |
| 08./09.07. | Acht OCR-Systeme auf dem Testkorpus; Vergleichswerkzeug (OCR-Viewer) |
| **14.07.** | **Zwischenpräsentation** |
| 21.07. | Seitenvergleich Datalab gegen Mistral, Entscheidung für Datalab [offen: Tag bestätigen] |
| 23.07. | Splitter; Trennen von Hand beginnt [offen: Beginn bestätigen] |
| 28.07. | Ergebnisse des Goldstandards; Auswertung am 04.08. (CER 0,60 %) |
| 17.–19.08. | OCR aller 14 Bände (geplant bis 30.08.) |
| 22.08. | Trennen von Hand abgeschlossen |
| 23.08. | Sprechstunde Prof. Wolff und Niklas Donhauser (OCR) |
| 25.08. | Sprechstunde Thomas Schmidt (online): Metadaten, Themen, NER |
| September | Findmittel des Archivs (Export aus ACTApro); Andreas Becker bis 02.09. im Urlaub |
| 17.09. | Topic-Modelling-Pipeline (Veit) |
| 22.09. | Konzept der Anwendung, Wahl von FastAPI und SQLAlchemy; Sprechstunde Prof. Wolff und Niklas Donhauser |
| 24.09. | App-Repository angelegt |
| 29.09. | Zweiter Durchgang Trennen mit Verdachtsliste |
| 30.09., 02.10. | Metadatenläufe; Bände 005–014 in der Anwendung |
| 02.–12.10. | Filter, Themen, Suche, Exemplarprüfung, Trends, Import und Export auf `main` |
| 07.10. | Vorführung der Anwendung in der Sprechstunde (Prof. Wolff, Jakob Fehle) |
| 08.10. | Erste Seite für den Import neuer Bände |
| **14.10.** | **Abschlusspräsentation** |
| 20.10. | Vorführung im Archiv mit Live-Import eines Teils von Band 15 |
| 22.10. | Dokumentation auf `main` |

**Plan und tatsächlicher Ablauf.** Der Antrittsvortrag plante: Evaluation der Methoden → Trennen → OCR → Datenmodell → Anwendung zur Datenanalyse (Sentiment, Keywords, Topic Modelling, N-Gramme).

- Trennen und OCR liefen parallel, weil das Trennen von Hand die OCR nicht brauchte.
- Das Datenmodell entstand erst, als die Metadatenextraktion gut genug lief (Ende September).
- Aus der Anwendung zur Datenanalyse wurde eine Anwendung zum Erschließen und Pflegen, mit Import neuer Bände; die Analysen liegen als N-Gramm-Werkzeug und Notebook außerhalb (Kap. 9.7).

## 12.4 Entscheidungen im Überblick

| Datum | Entscheidung | Kapitel |
|---|---|---|
| Mai 2026 | Allgemeine Flugblattsammlung (Rep. 118) statt Sammlung Reisner | 2 |
| 21.07.2026 | Datalab API, Modus accurate | 3 |
| Juli/August 2026 | Trennen von Hand mit eigenem Werkzeug, parallel zur OCR | 4 |
| 22.09.2026 | Anwendung mit FastAPI, Jinja2 und SQLAlchemy, auf Basis eines früheren Projekts | 9 |
| September 2026 | Metadaten mit Claude Sonnet 4.5 über OpenRouter, mit Belegpflicht | 5 |
| Oktober 2026 | Import neuer Bände in der Anwendung, bedienbar ohne technische Kenntnisse | 9 |
| Oktober 2026 | NER nicht umsetzen, Fokus auf Metadaten und Anwendung | 10 |

## 12.5 Arbeits-Repository

Bevor die Anwendung entstand, lag die Arbeit in einem eigenen Repository. Dort liegen die Skripte für den Vergleich der OCR-Systeme und den Goldstandard, die Metadatenläufe mit allen Prompt-Fassungen, der erste Themenlauf und die Suche nach Mehrfachexemplaren über alle Bände. Auch die beiden Werkzeuge, mit denen die Bände von Hand getrennt und die Texterkennung geprüft wurden, sind dort abgelegt. Das Repository ist archiviert und wird nicht weiter gepflegt: <https://github.com/Alphazerfall/flugblatt_praxisseminarSS26>. Was für Betrieb und Weiterentwicklung nötig ist, steht in diesem Repository, in der Anwendung oder unter `scripts/`.

- [offen: Das Repository ist noch privat; vor der Abgabe öffentlich stellen oder für das Archiv freigeben und die Skripte in `pipelines/01_pdf/` committen.]
- Bausteine der Anwendung, die dort zuerst entstanden: Vergleichsansicht der OCR-Ausgaben (09.07.), OCR-Viewer mit Text neben dem Scan samt Bounding Boxes und Vorschaubildern, Splitter (23.07.), Goldstandard-Modus (28.07.), NER-Übersicht (Veit, 07.09.), Topic-Modelling-Pipeline (Veit, 17.09.). Das App-Repository vom 24.09. hat diese Bausteine übernommen.

## 12.6 Aufwände

Zeiten wurden nicht laufend erfasst. Die Angaben beruhen auf Erinnerung des Teams und auf Zeitstempeln in Dateien und Protokollen.

| Arbeit | Aufwand | Anmerkung |
|---|---|---|
| Seitenvergleich Datalab gegen Mistral | ein Tag, je Person ein Drittel, abends Besprechung | Notizen je Seite |
| Goldstandard | ca. 2,5 h je Person für ein Drittel (rund 4,5 min je Seite) | in Blöcken von etwa 15 min über mehrere Tage, weil sehr konzentrationsintensiv; dazu Besprechungen zu den Regeln |
| OCR aller Bände | wenige Minuten Rechenzeit je Band | über drei Tage verteilt, wegen Guthaben und Wiederholungen |
| Trennen von Hand | Sebastian ca. 6 h (1 926 Seiten), Veit ca. 4,5 h (2 123 Seiten), Felix nicht beziffert (415 Seiten) | 7–11 s je Seite; nach Herausgeber sortierte Bände gingen schneller. Felix trennte Nr. 001–003 nebenbei, während er den Splitter baute |
| Splitter entwickeln | ca. eine Woche für die erste Fassung (ab 21.07.) | danach iterativ weiterentwickelt, während getrennt wurde (Kommentare 20.08., Prüfmodus 29.09.) |
| Zweiter Durchgang Trennen | ca. 1,5 h Entscheidungszeit | am 29.09., verteilt über den Tag |
| Mehrfachexemplare | Sebastian ca. 8 h für 320 Fälle | rund 1,5 min je Fall, inklusive Metadatenkorrektur |
| Anwendung | Felix etwa Vollzeit vom 24.09. bis 22.10. | Anteil von Veit und Sebastian [offen] |

- Kosten externer Dienste: ca. 30 $ bei Datalab über das monatliche Gratisguthaben (20 $ bei Anmeldung mit Uni-Adresse) hinaus; ca. 65 $ bei OpenRouter, fast ganz für Tests und Läufe der Metadaten, ein sehr kleiner Teil für Embeddings. [offen: Beträge aus den Dashboards in `kennzahlen.md` übernehmen.]
- [offen: Gab es zu Beginn eine Aufwandsplanung (Stunden je Person, ECTS)? Falls nein, so festhalten.]

## 12.7 Erfahrungen

**Was gut lief** [offen: vom Team bestätigen, ergänzen oder streichen]

- Gemeinsame Arbeit in Dritteln, mit Kalibrierungsseiten, die alle bearbeitet haben.
- Regeln vor der Arbeit festlegen (Fehler im Goldstandard, Grenzfälle beim Trennen).
- Werkzeuge beim Benutzen weiterentwickeln: Die Kommentarfunktion im Splitter machte das Trennen zugleich zur Erkundung des Materials. So fielen die vielen Mehrfachexemplare und die Trennblätter auf, aus denen eigene Arbeitsschritte wurden (Kap. 6, Leerseiten in Kap. 4).
- Schnelle Entscheidung für die OCR mit eigenem Testkorpus statt nur nach Benchmarks.
- OCR früh und parallel zum Trennen; sie war elf Tage vor dem geplanten Termin fertig.
- Regelmäßige Sprechstunden und Vorführungen bei Betreuung und Archiv; ihre Fragen haben die Anwendung geprägt.

**Was wir anders machen würden**

- Notizen früh systematisch an einem Ort sammeln. Sie lagen verstreut in Google Drive; besser von Anfang an als Markdown im Repository mit Git-Versionierung. Dadurch wurde die Dokumentation erst am Ende gebündelt.
- Aufwände von Anfang an mitschreiben, vor allem bei der Entwicklung der Anwendung. Dort fehlen Zahlen gerade an der Stelle, an der wir uns am stärksten verschätzt haben.
- Branches nicht lange getrennt laufen lassen. Sebastians Umbau der Flugblattliste mit htmx (03./04.10.) lag am Ende zu weit hinter `main` zurück und wurde nicht übernommen; auch der Branch der Dokumentation brauchte zum Schluss Konfliktlösungen.
- Die Genauigkeit der Metadaten früh messen. Geplant waren ein Gold-Set aus 50–60 Flugblättern und später ein Abgleich mit den Archivtiteln 1968/69; beides ist nicht passiert (Kap. 5.4, 10).
- [offen: weitere Punkte des Teams]

**Fehleinschätzungen**

- Umfang der Anwendung: Die Funktionen wurden immer mehr. Vor allem Verwaltung und Import neuer Bände schienen zunächst nur „die fertige Pipeline in eine Oberfläche bringen“, brauchten aber viele Iterationen: eigene Zustände je Schritt, Fehlerfälle, Wiederaufnahme, Kostenanzeigen, Prüfungen. Die erste Import-Seite entstand am 08.10., danach folgten 19 Commits an Import und Verwaltung bis 22.10., dazu die Änderungen nach der Vorführung im Archiv.
- Themen: viel Versuch und Irrtum. Der erste Lauf mit MiniLM auf einzelnen Textblöcken ergab 234 Themen und 42 % ohne Thema, weil der Kontext des Modells für ganze Flugblätter zu klein war; erst bge-m3 auf ganzen Flugblättern trug.
- Kosten: Für die Metadaten war ein Lauf im kostenlosen Kontingent geplant („2 Tage“); tatsächlich lief er bezahlt (ca. 65 $). Insgesamt gering, aber höher als gedacht.
- [offen: weitere Fehleinschätzungen des Teams]

**Bewusste Planänderungen** (keine Fehler, aber Abweichungen vom ersten Plan)

- Sammlung Reisner verworfen: nicht digitalisiert und politisch einseitig (Kap. 2.1).
- OCR und Trennen parallel statt nacheinander.
- Datenmodell erst nach der Metadatenextraktion.
- Analyse-App zu Erschließungs- und Pflege-App, angestoßen durch die Sprechstunden.
- NER nicht umgesetzt, um sich auf Metadaten und Anwendung zu konzentrieren (Ausblick in 10.4).

**Geplant, aber nicht umgesetzt**

- Annotationsrichtlinie für das Trennen (19.08.).
- OCR mit Wort-Boxen für Treffer im Scan (19.08.).
- Prüfung der Trennung mit einem Sprachmodell (19.08.); stattdessen später der lokale Trennvorschlag aus Text und Scan (Kap. 4).
- Sentiment-Analyse (Antrittsvortrag, Sprechstunde 25.08.).
- Ein bis vier Themen je Flugblatt aus einer festen Liste (25.08.); umgesetzt ist ein Thema je Flugblatt.
- Namensliste der Professoren als Referenz für OCR-Fehler bei Eigennamen (22.09.).
- Unabhängige doppelte Annotation der Trennung einer Stichprobe.

## 12.8 Einsatz von KI-Werkzeugen

Nach den KI-Richtlinien der Medieninformatik ist offenzulegen: Werkzeug oder Modell, Zweck, betroffene Teile der Arbeit und der konkrete Beitrag der KI ([KI-Richtlinien der Medieninformatik](https://www.uni-regensburg.de/informatik-data-science/fakultaet/einrichtungen/medieninformatik/studium/ki-richtlinien)). Im Praxisseminar war auch das Erzeugen wesentlicher Codeteile und der Einsatz von Agenten erlaubt.

- Sprachmodelle als Teil des Verfahrens stehen in den jeweiligen Kapiteln: Datalab API (Kap. 3), Claude Sonnet 4.5 für die Metadaten (Kap. 5), bge-m3 und ein Sprachmodell für Thementitel (Kap. 7).
- Werkzeuge bei der Arbeit:
  - Claude Code: [offen: je Bereich angeben, was es beigetragen hat und wie wir es geprüft haben: OCR-Pipeline, OCR-Viewer und Splitter, Metadaten-Prompt, Anwendung, Skripte, Dokumentation und Texte in der Anwendung]
  - [offen: weitere Werkzeuge der Teammitglieder, z. B. für Recherche oder Übersetzung]
- Früher stand ein Hinweis zum KI-Einsatz im Stylesheet und beim Favicon der Anwendung; er wurde am 30.09.2026 aus dem Code entfernt und gehört hierher.
- [offen: Eintrag `ur-ki-richtlinien` in `literatur.bib` anlegen: https://www.uni-regensburg.de/informatik-data-science/fakultaet/einrichtungen/medieninformatik/studium/ki-richtlinien]

## Noch zu schreiben

Zusammengefasst, was das Team noch klären oder ausformulieren muss:

1. Rollen (12.1): App-Zeilen der Tabelle prüfen; wer MinerU und PaddleOCR getestet hat.
2. Besprechungen (12.2): Trello-JSON-Export versuchen.
3. Termine (12.3): Tag des Seitenvergleichs, Beginn des Trennens, Datum der Sprechstunde mit Jakob Fehle.
4. Aufwände (12.6): Anteil von Veit und Sebastian an der Anwendung; Beträge aus den Dashboards; ob es eine Aufwandsplanung gab.
5. Erfahrungen (12.7): „Was gut lief“ bestätigen; weitere Fehleinschätzungen und Lehren aus Sicht von Veit und Sebastian.
6. KI-Einsatz (12.8): je Bereich ausformulieren; Quelle in `literatur.bib`.
7. Danach alles im Stil der übrigen Kapitel als Fließtext ausformulieren und gegen `offene-punkte.md` abgleichen.
