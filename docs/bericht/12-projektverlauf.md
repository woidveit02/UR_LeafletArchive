# 12 Projektverlauf und Organisation

<!-- Fassung von Sebastian vom 23.10.2026 (Commit 44af357), ergänzt um Punkte aus Felix' Fassung; Stichpunkte mit Quellen: arbeitsdokumente/kap12-stichpunkte.md.
     Alle Daten ohne Jahr sind aus 2026. -->

Dieses Kapitel beschreibt, wer im Projekt was gemacht hat, wie der tatsächliche Verlauf vom Plan aus dem Antrittsvortrag abwich und wie wir die Arbeit organisiert haben. Danach folgen Aufwand und Kosten, unsere Erfahrungen und zum Schluss welche KI-Werkzeuge eingesetzt wurden.

## 12.1 Team und Betreuung

Im Team waren Veit Korpies, Felix Lindner und Sebastian Simbeck. Betreut wurde es in erster Linie von Thomas Schmidt, und Prof. Christian Wolff, Jakob Fehle und Niklas Donhauser waren zusätzliche Ansprechpartner. Ansprechpartner im Universitätsarchiv war Dr. Andreas Becker.

Feste Rollen haben wir nicht vergeben, aus den Aufgaben ergaben sich aber Schwerpunkte, die über das Projekt weitgehend stabil blieben. Felix testete sechs der acht OCR-Systeme (Datalab, Mistral OCR 4, Claude Sonnet 5, Gemini 3.5 Flash, Qwen3-VL und MinerU), erkannte den Text aller Bände (Kap. 3.9), baute die eigenen Werkzeuge OCR-Viewer und Splitter, trennte die Bände 001–003 (von Veit geprüft) und erzeugte die Metadaten (Kap. 5). In der Anwendung entwickelte er Datenmodell, Import neuer Bände, Verwaltung und Export. Sebastian testete GLM-OCR, trennte die Bände 004–008, prüfte die Mehrfachexemplare (Kap. 6) und baute in der Anwendung Filter und Suche. Veit hielt den Kontakt zum Archiv, erstellte das Testkorpus (Kap. 3.3), testete PaddleOCR, trennte die Bände 009–014, berechnete die Themen mit einem ersten Versuch zur Named Entity Recognition (Kap. 7) und baute die Themenansicht. Repository, Grundgerüst und Datenbank der Anwendung entstanden bei Veit und Sebastian. Alle drei haben gemeinsam die Seiten von Datalab und Mistral verglichen und den Goldstandard erstellt, jeweils mit einem Drittel der Seiten (Kap. 3.6 und 3.7), und die Felder der Metadaten festgelegt.

Die Kapitel dieses Berichts haben Veit (1, 2, 3, 7, 10), Sebastian (4, 5, 6) und Felix (Übersicht, 8, 9, 11, Kennzahlen, Handbücher, Glossar) geschrieben, Kapitel 12 alle gemeinsam. Alle Kapitel wurden mehrmals von verschiedenen Teammitgliedern überarbeitet. Felix hat außerdem die Texte in der Anwendung und die READMEs verfasst.

## 12.2 Zeitlicher Verlauf

Im Antrittsvortrag am 09.06.2026 hatten wir den Ablauf so geplant: Evaluation der Methoden, Flugblätter trennen, Text erkennen, ein Datenmodell entwickeln und schließlich eine Anwendung zur Datenanalyse bauen, etwa für Topic Modelling, Sentiment-Analyse und N-Gramme.

Tatsächlich verlief das Projekt in drei Phasen. In der Vorbereitung von Mai bis Juni haben wir den Bestand gewählt und das Vorgehen abgestimmt. In der Phase „Rohdaten“ von Ende Juni bis August haben wir den Umfang auf die 14 bis dahin gescannten Bände festgelegt, ein OCR-System ausgewählt und geprüft, alle Bände erkannt und von Hand getrennt. Anders als geplant liefen Trennen und Texterkennung dabei parallel, weil das Trennen von Hand nur die Scans brauchte; Felix konnte die Texterkennung abschließen, während Sebastian und Veit trennten. Die Phase „Erschließung und Anwendung“ begann mit den Sprechstunden am 25.08.2026. Im September haben wir das Findmittel ausgewertet, die Metadatenextraktion entwickelt und das Topic Modelling aufgebaut. Das Datenmodell konnten wir erst festlegen, als am 22.09.2026 die Felder der Metadaten feststanden; zwei Tage später entstand das Repository der Anwendung. Metadaten aller Bände und Themen folgten Ende September und Anfang Oktober, die Prüfung der Mehrfachexemplare vom 05.10. bis 11.10.2026.

Die größte Abweichung vom Plan betrifft die Anwendung. Statt einer Anwendung zur Datenanalyse entstand eine zum Erschließen und Pflegen des Bestands, mit Import neuer Bände. Sie zeigt unter „Trends“, welcher Anteil der Flugblätter eines Jahres einen Suchbegriff enthält; weitergehende Analysen liegen außerhalb, im N-Gramm-Werkzeug und im Notebook (Kap. 9.6).

Für die Rohdaten und die Erschließung hatten wir uns feste Termine gesetzt. Die Tabelle stellt sie dem Erreichten gegenüber:

| Meilenstein | geplant | erreicht |
|---|---|---|
| Goldstandard erstellt und ausgewertet | 09.08. | 04.08. |
| Texterkennung aller Bände | 16.08. | 19.08. |
| Trennen aller Bände von Hand | 30.08. | 22.08. |
| Metadaten für alle Bände | 30.08. | 30.09. (Bände 001–004) und 02.10. (Bände 005–014) |
| Topic Modelling | 30.09. | 03.10. |
| Vorschläge für Trennungen in der Trennansicht | 11.10. | 09.10. |
| Alle Flugblätter in der Anwendung durchsuchbar | 11.10. | 12.10. |

Am weitesten zurück lagen die Metadaten: Ihre Felder standen erst am 22.09. fest, und das zuerst eingeplante Modell lieferte zu ungenaue Ergebnisse (Kap. 12.8).

Alle Daten in den folgenden Tabellen sind aus 2026.

Vorbereitung (Mai bis Juni):

| Datum | Was geschah |
|---|---|
| 12.05. | Erste Projektsprechstunde mit Prof. Wolff und Thomas Schmidt |
| 20.05. | Termin mit Andreas Becker im Archiv: Allgemeine Flugblattsammlung statt Sammlung Reisner; danach Sprechstunde mit Prof. Wolff und Jakob Fehle zum weiteren Vorgehen |
| **09.06.** | **Antrittsvortrag** |

Rohdaten (Ende Juni bis August):

| Datum | Was geschah |
|---|---|
| Ende Juni | Aufgabenplanung auf einem Kanban-Board beginnt; erster Test der Datalab API am 23.06. |
| 30.06. | Testkorpus aus 100 Seiten für den Vergleich der OCR-Systeme |
| 08.07.–09.07. | Acht OCR-Systeme auf das Testkorpus angewendet, Ergebnisse im OCR-Viewer nebeneinander |
| **14.07.** | **Zwischenpräsentation** |
| 20.07. | Nachfrage beim Archiv: keine weiteren Bände gescannt; Korpus auf die Bände 001–014 festgelegt |
| 21.07. | Seitenvergleich Datalab und Mistral, Entscheidung für Datalab |
| 23.07. | Erste Fassung des Splitters (eigenes Werkzeug zum Trennen); Beginn des Trennens von Hand |
| 28.07. | Modus für den Goldstandard (von Hand korrigierter Text des Testkorpus) im OCR-Viewer; Annotationen bis 03.08., Auswertung am 04.08. |
| 17.08.–19.08. | Texterkennung aller 14 Bände (geplant war der 16.08.) |
| 20.08. | Splitter erhält eine Notizfunktion für Vermerke beim Trennen |
| 22.08. | Trennen von Hand abgeschlossen |

Erschließung und Anwendung (Ende August bis Oktober):

| Datum | Was geschah |
|---|---|
| 25.08. | Sprechstunden mit Prof. Wolff und Niklas Donhauser (Texterkennung) und mit Thomas Schmidt (Metadaten, Topic Modelling, Named Entity Recognition) |
| Anfang September | Findmittel des Archivs erhalten und ausgewertet: 127 Einträge als Grundlage des Herausgeber-Registers |
| 17.09. | Erste Pipeline für die Themen (Topic Modelling) |
| 22.09. | Konzept der Anwendung mit Import neuer Bände, Felder der Metadaten, Wahl von FastAPI und SQLAlchemy; Sprechstunde mit Prof. Wolff und Niklas Donhauser |
| 24.09. | Repository der Anwendung angelegt, Datenmodell festgelegt |
| 29.09. | Zweite Prüfung der Trennung anhand einer Liste verdächtiger Stellen |
| 30.09., 02.10. | Metadaten für alle Bände erzeugt und in die Anwendung übernommen |
| 02.10.–12.10. | Filter, Themen, Suche und Trends in der Anwendung |
| 03.10. | Themen für den ganzen Bestand berechnet (40 Themen) |
| 05.10.–11.10. | Prüfung der Mehrfachexemplare |
| 07.10. | Vorführung der Anwendung in der Sprechstunde |
| 08.10. | Erste Seite für den Import neuer Bände |
| 09.10. | Erste Vorschläge für Trennungen in der Trennansicht, aus dem erkannten Text |
| **14.10.** | **Abschlusspräsentation** |
| 20.10. | Vorführung im Archiv mit Import des ersten Teils von Band 15 |

## 12.3 Entscheidungen

Fünf Entscheidungen haben den Verlauf des Projekts geändert:

| Datum | Entscheidung | Grund | Kapitel |
|---|---|---|---|
| 20.05. | Allgemeine Flugblattsammlung (Rep. 118) statt Sammlung Reisner | Die Sammlung Reisner ist nicht digitalisiert und enthält fast nur Blätter linker Gruppen | 2 |
| 20.07. | Korpus auf die Bände 001–014 begrenzt | Laut Archiv waren keine weiteren Bände gescannt; wir wollten den Umfang für die weitere Arbeit festlegen | 2 |
| Juli/August | Trennen von Hand mit eigenem Werkzeug, parallel zur Texterkennung | Die automatische Trennung von Datalab fand nur einen Bruchteil der Grenzen; das Trennen brauchte den erkannten Text nicht | 4 |
| 22.09. | Metadaten mit Claude Sonnet 4.5 über OpenRouter statt Gemini 2.5 Flash | Gemini 2.5 Flash lieferte zu ungenaue Metadaten; im Test an Band 002 verarbeitete nur Claude Sonnet 4.5 den ganzen Band | 5 |
| 22.09. | Anwendung mit Import neuer Bände | Das Archiv soll neue Bände selbst einlesen können | 9 |

## 12.4 Arbeitsweise

### Interne Besprechungen

Über das ganze Projekt haben wir uns wöchentlich getroffen, an der Universität oder online über Discord. Meist moderierte Felix. Jede Person berichtete ihren Stand, danach haben wir die Aufgaben bis zum nächsten Treffen verteilt. Ab dem 19.08.2026 haben wir dazu ein Protokoll mit dem Stand jeder Person und den offenen Aufgaben geführt. Zwischen den Treffen haben wir uns über WhatsApp abgestimmt. Als Sebastian vom 07.09. bis 17.09.2026 abwesend war, haben wir die Aufgaben für diese Zeit vorher fest verteilt.

Wo wir die Aufgaben zwischen den Treffen festgehalten haben, änderte sich mit den Phasen: zuerst auf einem Kanban-Board, nach der Texterkennung aller Bände in den Protokollen und ab dem 24.09.2026 in GitHub-Issues.

### Trello

In der Phase „Rohdaten“ ließen sich die Aufgaben gut voneinander abgrenzen, deshalb haben wir sie auf einem Kanban-Board geplant. Das Board „Praxisseminar-OCR“ hatte die Spalten „Backlog“, „Diese Woche“, „Review“, „Fertig“ und „Fragen“. In der wöchentlichen Besprechung zogen wir Karten nach „Diese Woche“. Erledigte Aufgaben kamen nach „Review“, wurden dort geprüft und dann nach „Fertig“ verschoben. Unter „Fragen“ sammelten wir, was wir in der nächsten Sprechstunde oder im Archiv besprechen wollten. Labels ordneten die Karten den Arbeitsbereichen zu: Rohdaten aufbereiten, OCR-Vergleich und OCR-Validierung. Jede Karte hatte eine verantwortliche Person; gemeinsame Aufgaben wie der Seitenvergleich waren als eigene Karten je Drittel angelegt. Insgesamt haben wir 17 Karten angelegt und erledigt.

### GitHub

Ab dem 24.09.2026 lagen Code, Aufgaben und Dokumentation im Repository der Anwendung an einem Ort, und die Arbeit verlagerte sich weitgehend in den Code. Deshalb haben wir die Aufgaben nun vor allem über Issues auf GitHub verwaltet. Die meisten Issues legte Felix an, weil er am meisten im Code gearbeitet hat. Labels kennzeichneten die Arbeitsbereiche „Daten“, „neue Funktionen“, „Änderungen an der Oberfläche“ und „Topic Modelling“. Für die Arbeit am Code haben wir eigene Branches je Issue oder Aufgabenblock angelegt. Felix war für den Hauptzweig verantwortlich: Er hat die Pull Requests lokal getestet, Konflikte gelöst und zusammengeführt. Kleinere Änderungen gingen bei ihm direkt in den Hauptzweig. Commit-Nachrichten folgen den Conventional Commits. Bis zum 23.10.2026 sind im Repository der Anwendung rund 150 Commits entstanden.

### Sprechstunden und Archiv

In den Sprechstunden haben wir Zwischenstände vorgestellt und die nächsten Schritte abgestimmt. Vor dem Antrittsvortrag und der Zwischenpräsentation haben wir außerdem Inhalte und Folien mit Thomas Schmidt besprochen. Aus der Sprechstunde am 25.08.2026 ergaben sich die Schwerpunkte „Metadaten“ und „Topic Modelling“. Den Import neuer Bände haben wir nach der Sprechstunde am 22.09.2026 in das Konzept der Anwendung aufgenommen. Bei der Vorführung am 07.10.2026 fragten Prof. Wolff und Jakob Fehle, ob sich neue Flugblätter hochladen und Fehler in der Datenbank nachträglich korrigieren lassen. Außerdem betonten sie, dass die Anwendung auch ohne technisches Vorwissen bedienbar sein soll.

## 12.5 Qualitätssicherung

Für den Goldstandard haben wir vor der Korrektur gemeinsam festgelegt, wann eine Stelle im OCR-Text als fehlerhaft gilt, und diese Regeln nach einigen Testseiten präzisiert. Die Seiten 1 bis 5 haben alle drei bearbeitet, um die Übereinstimmung zu vergleichen (Kap. 3.7).

Beim Trennen hat Felix die Bände 001–003 zunächst mit einer frühen Fassung des Splitters getrennt. Ihr fehlte noch die Notizfunktion, die erst am 20.08.2026 hinzukam, um etwa Fehler in der Reihenfolge fortlaufender Flugblätter festzuhalten. Veit hat diese Bände danach geprüft.

In einem zweiten Durchgang am 29.09.2026 haben wir alle Bände anhand einer automatisch erstellten Liste verdächtiger Trennstellen erneut geprüft und dabei 30 Trennungen geändert. Daraus entstanden die Regeln für Grenzfälle (Kap. 4.2).

## 12.6 Werkzeuge und Repositories

Für Treffen und Abstimmung haben wir Discord und WhatsApp genutzt, für die Aufgaben Trello und später GitHub (Kap. 12.4), für Scans, Protokolle und Notizen Google Drive und Google Docs. Die Literatur steht in einer gemeinsamen Zotero-Sammlung. Die eigenen Werkzeuge OCR-Viewer (Vergleich der OCR-Ausgaben, Goldstandard) und Splitter (Trennen von Hand) liegen im Arbeits-Repository, den Einsatz von KI-Werkzeugen beschreibt Kap. 12.9.

Bevor die Anwendung entstand, lag die Arbeit in einem eigenen Arbeits-Repository: <https://github.com/Alphazerfall/flugblatt_praxisseminarSS26>. Dort liegen die Skripte für den Vergleich der OCR-Systeme und den Goldstandard, die Metadatenläufe mit allen Prompt-Fassungen, der erste Themenlauf und die Suche nach Mehrfachexemplaren über alle Bände, außerdem OCR-Viewer und Splitter. Dort entstanden auch die Bausteine der Anwendung: die Ansicht zum Vergleich der OCR-Ausgaben (09.07.2026), der OCR-Viewer mit dem erkannten Text samt Bounding Boxes neben dem Scan, der Splitter (23.07.2026), der Modus für den Goldstandard (28.07.2026) und die Topic-Modelling-Pipeline (17.09.2026). Screenshots von OCR-Viewer und Splitter stehen in den READMEs der Ordner `ocr_viewer/` und `flugblatt_splitter/`. Das Repository der Anwendung vom 24.09.2026 hat sie übernommen; das Arbeits-Repository haben wir danach nicht weiter gepflegt. Was für Betrieb und Weiterentwicklung wichtig ist, steht im Repository der Anwendung, die Werkzeuge sind unter `scripts/` dokumentiert.

Die Form der Dokumentation durften wir laut einer Ankündigung im Kurs selbst wählen. Zunächst planten wir ein Overleaf-Projekt mit einer Vorlage für Abschlussarbeiten. Weil unsere Dokumentation viele Abbildungen und Tabellen enthalten sollte und sich eine Website für Anwenderinnen und Anwender besser nutzen lässt, entschieden wir uns schließlich für eine Website mit MkDocs. Sie steht als Markdown im Repository der Anwendung und ist in der Anwendung unter „Doku“ zu lesen. Für die Abgabe erzeugt Pandoc hieraus ein PDF.

## 12.7 Aufwand und Kosten

Zeiten haben wir während des Projekts nicht laufend erfasst. Die folgenden Angaben stammen aus Protokollen und Zeitstempeln in Dateien und Repositories oder sind im Nachhinein aus der Erinnerung geschätzt. Den Aufwand der Arbeitsschritte haben wir zu Beginn zwar geschätzt, aber nur für die Präsentationen im Kurs beziffert; eine dokumentierte Aufwandsplanung gibt es deshalb nicht. 

| Arbeitsschritt | Aufwand | Anmerkung |
|---|---|---|
| Seitenvergleich Datalab und Mistral | ein Tag | je Person ein Drittel der Seiten mit Notizen je Seite, abends Besprechung und Entscheidung |
| Goldstandard | ca. 2,5 Stunden je Person für ein Drittel | in Blöcken von etwa 15 Minuten über mehrere Tage, weil die Arbeit viel Konzentration braucht; dazu Besprechungen zu den Regeln |
| Trennen von Hand | Sebastian ca. 6 Stunden für 1926 Seiten, Veit ca. 4,5 Stunden für 2123 Seiten | 7 bis 11 Sekunden je Seite; Felix trennte Nr. 001–003 (415 Seiten) nebenbei, während er den Splitter entwickelte und die Texterkennung betreute |
| Zweite Prüfung der Trennung | ca. 1,5 Stunden | Stellen der Verdachtsliste, über den Tag verteilt |
| Prüfung der Mehrfachexemplare | Sebastian ca. 8 Stunden für 320 vorgeschlagene Gruppen | etwa 1,5 Minuten je Gruppe, mit Korrektur der Metadaten |
| Anwendung | Felix etwa in Vollzeit vom 24.09. bis 22.10. | Veit und Sebastian arbeiteten mit; ihren Anteil haben wir nicht erfasst |

Für die übrigen Schritte, etwa den Test der OCR-Systeme, die Entwicklung des Splitters, die Metadaten und die Themen, haben wir keinen Aufwand erfasst.

Wie lange das Trennen dauerte, hing stark vom Band ab. Weil die Bände innerhalb eines Jahrgangs nach herausgebenden Gruppen sortiert sind, zeigten sich schnell Muster: Flugblätter von Gruppen, die ihre Blätter streng durchnummerierten, ließen sich deutlich schneller trennen als andere. Zwei der drei Bände, die laut Findmittel überwiegend eine einzige Gruppe enthalten, hat Veit getrennt (Nr. 011 Demokratische Front, Nr. 013 AStA), den dritten Sebastian (Nr. 007 RCDS). Das könnte das unterschiedliche Tempo teilweise erklären.

Für externe Dienste haben wir insgesamt etwa 95 \$ bezahlt. Bei Datalab lagen wir rund 30 \$ über dem monatlichen Gratisguthaben von 20 \$. Bei OpenRouter, wo es für Claude kein Gratiskontingent gibt, kosteten alle Tests und Läufe zusammen rund 65 \$. Fast alles davon entfiel auf die Metadaten, kleine Teile auf die OCR-Tests mit Claude Sonnet 5 und Qwen3-VL und auf Embeddings und Titel der Themen. Die Beträge sind gerundet; eine vollständige Aufstellung aus den Abrechnungen der Dienste haben wir nicht.

## 12.8 Erfahrungen

### Bewährtes

Bewährt hat sich beim Goldstandard, vor der Korrektur gemeinsam Regeln festzulegen und einige Seiten von allen bearbeiten zu lassen. So ließ sich die Übereinstimmung messen (Kap. 3.7).

Bewährt hat sich auch, die Werkzeuge während der Nutzung weiterzuentwickeln. Mit der Notizfunktion im Splitter haben wir in 36 Notizen unter anderem 18 doppelte Flugblätter und 10 Seiten ohne Inhalt vermerkt. Dadurch fiel auf, dass der Bestand viele Mehrfachexemplare und leere Seiten enthält, und daraus ergaben sich eigene Arbeitsschritte (Kap. 4 und 6).

Schließlich haben wir das OCR-System nach eigenen Tests gewählt, nicht allein nach öffentlichen Benchmarks. Die Texterkennung aller Bände war so am 19.08.2026 fertig, drei Tage nach dem geplanten Termin.

### Fehleinschätzungen

Am stärksten verschätzt haben wir uns beim Umfang der Anwendung. Verwaltung und Import neuer Bände schienen zunächst nur zu verlangen, die vorhandene Pipeline in eine Oberfläche einzubinden. Tatsächlich brauchte jeder Schritt des Imports eigene Zustände, Fehlerfälle, das Fortsetzen nach Abbrüchen, Kostenanzeigen und Prüfungen, und jede Vorführung brachte neue Anforderungen. Die erste Fassung der Import-Oberfläche entstand am 08.10.2026, am Tag nach der Vorführung in der Sprechstunde und sechs Tage vor der Abschlusspräsentation. Bis zum 22.10.2026 folgten 19 Commits an Import und Verwaltung, dazu die Änderungen nach der Vorführung im Archiv.

Auch bei den Metadaten und beim Topic Modelling lagen die ersten Ansätze daneben. Für die Metadaten hatten wir zuerst *Gemini 2.5 Flash* im Gratiskontingent eingeplant. Die Ergebnisse waren zu ungenau, und im Test an Band 002 brach der Lauf nach Seite 36 ab (Kap. 5.3). Für *Claude Sonnet 4.5* über *OpenRouter* fiel dann der größte Teil der rund 65 $ bei OpenRouter an (Kap. 12.7). Beim Topic Modelling ergab der erste Versuch mit *MiniLM* auf einzelnen Textblöcken 234 Themen und ließ 42 % der Blöcke ohne Thema, weil der Kontext des Modells für ganze Flugblätter zu klein war. Erst *bge-m3* auf ganzen Flugblättern führte zu brauchbaren Themen (Kap. 7).

### Lehren

Die Import-Oberfläche würden wir bei einem neuen Projekt früh als einfachen Prototyp bauen und mit dem Archiv testen, statt sie in den letzten Wochen zu entwickeln. Die Anforderungen, die erst bei den Vorführungen sichtbar wurden, wären so früher aufgefallen.

Unsere Notizen lagen lange unsortiert in einem Google-Drive-Ordner, ein Protokoll haben wir erst am 19.08.2026 angelegt. Hätten wir alle Aufzeichnungen von Anfang an an einem Ort gesammelt, hätten wir wichtige Informationen nicht erst am Ende für die Dokumentation zusammentragen müssen.

Regeln für Grenzfälle beim Trennen würden wir vor dem Trennen festlegen. Beim ersten Durchgang fehlten sie, sie entstanden erst bei der zweiten Prüfung (Kap. 4.2).

Den Zeitaufwand würden wir von Beginn an mitschreiben (Kap. 12.7). Gerade für die Arbeitsschritte, bei denen wir uns am stärksten verschätzt haben, vor allem die Anwendung, fehlen uns Zahlen, um die Abweichung im Nachhinein nachzuvollziehen.

Branches würden wir regelmäßig mit dem Hauptzweig abgleichen, statt sie lange getrennt zu lassen. Sebastians Umbau der Flugblattliste mit htmx lag am Ende zu weit hinter dem Hauptzweig zurück und ließ sich nicht mehr übernehmen.

Die Genauigkeit der Metadaten würden wir früher und systematisch prüfen. Geplant war ein Gold-Set aus 50 bis 60 Flugblättern. Wir haben es fallen lassen, weil das Findmittel für 1968 und 1969 Titel nennt; der Abgleich zeigte dann aber, dass diese Titel keine verlässliche Referenz sind (Kap. 5.4 und 10). Eine frühe Messung hätte die Qualität besser einschätzen und Fehler gezielter finden lassen.

### Offene Vorhaben

Einige Vorhaben haben wir bewusst zurückgestellt, um uns auf Metadaten und Anwendung zu konzentrieren: Named Entity Recognition und Sentiment-Analyse, mehrere Themen je Flugblatt aus einer festen Liste, Wort-Boxen in der Texterkennung, eine Annotationsrichtlinie für das Trennen, eine unabhängige zweite Trennung einer Stichprobe, um die Übereinstimmung zu messen, und eine Liste der damaligen Professorinnen und Professoren als Referenz für OCR-Fehler bei Eigennamen. Die Prüfung der Trennung mit einem Sprachmodell hat der lokale Trennvorschlag aus Text und Scan ersetzt (Kap. 4).

Aus der Verdachtsliste beim Trennen sind Stellen unbearbeitet geblieben, vor allem aus der Stufe „prüfen“, und Nr. 003 S. 38–41, die wir für den Abgleich mit dem Findmittel zurückgestellt haben (Kap. 12.5). Für die Metadaten haben wir außerdem kein neueres Modell getestet, auch nicht Claude Sonnet 5. Offen ist auch der dauerhafte Betrieb: Das Gespräch mit dem Rechenzentrum über Zugriffsschutz, Updates und Betreuung steht noch aus (Kap. 9.7). Was davon für eine Weiterentwicklung lohnt, steht in Kapitel 10.

## 12.9 Einsatz von KI-Werkzeugen

Nach den KI-Richtlinien der Medieninformatik legen wir offen, welche Werkzeuge wir wofür eingesetzt haben und was sie beigetragen haben ([KI-Richtlinien der Medieninformatik](https://www.uni-regensburg.de/informatik-data-science/fakultaet/einrichtungen/medieninformatik/studium/ki-richtlinien)). Die Tabelle folgt den Anwendungsfeldern der Richtlinie. Nach Auskunft der Betreuenden durften KI-Werkzeuge beim Programmieren eingesetzt werden, laut einer Ankündigung im Kurs auch, um Notizen in eine strukturierte Form zu bringen.

KI-Modelle und -Dienste, die Teil des Verfahrens sind, beschreiben die jeweiligen Kapitel: die Datalab API für die Texterkennung (Kap. 3), Claude Sonnet 4.5 für die Metadaten (Kap. 5), bge-m3 für die Ähnlichkeit der Texte und GPT-4.1 mini für die Titel der Themen (Kap. 7).

| Anwendungsfeld | Werkzeug | Wofür und mit welchem Beitrag | Wie geprüft |
|---|---|---|---|
| Programmieren | Claude Code, GitHub Copilot (automatische Modellwahl im Chat von VS Code), von allen dreien genutzt | Teile von Pipeline, OCR-Viewer, Splitter und Anwendung nach unseren Vorgaben, vor allem Oberflächen, einfache Skripte, Tests und erste Fassungen, um einen Ansatz auszuprobieren; das Stylesheet wurde mit KI überarbeitet | Anforderungen von uns, jeder Stand ausprobiert, Pull Requests, automatische Tests, Stichproben gegen die Scans |
| Prompts entwickeln | Claude, Gemini; für die Metadaten Claude Code | Prompts für die Coding-Assistenten, oft schrittweise verbessert; Fassungen des Metadaten-Prompts | Welche Fassung wir übernommen haben, haben wir entschieden; eine Messung gegen eine Referenz gab es für die Metadaten nicht (Kap. 5.4) |
| Texte schreiben | Claude Code | erste Entwürfe aus unseren Notizen, Protokollen, Daten und dem Code, vor allem für Kap. 8, 9 und 12, die Handbücher und die Kennzahlen | gegen Code und Daten geprüft, im Team gegengelesen, mehrfach überarbeitet |
| Texte überarbeiten | Claude | sprachliche Überarbeitung aller Kapitel im Oktober 2026: kürzere Sätze, einheitliche Begriffe, Kürzungen, Prüfung auf Widersprüche zwischen den Kapiteln; Inhalte nur aus Code, Daten und unseren Notizen | Änderungen von Felix durchgesehen, Zahlen gegen Daten und Kennzahlen geprüft |
| Bildgenerierung | Claude Code | Favicon der Anwendung als SVG-Code | von Felix durchgesehen |
