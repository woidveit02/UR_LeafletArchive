# 5 Metadaten erzeugen

Damit sich die Flugblätter suchen und filtern lassen, ergänzen wir jedes Exemplar um Metadaten wie Titel, Datum und Herausgeber. Ein Sprachmodell liest sie aus dem erkannten Text und nennt für die meisten Werte die Textstelle, auf die sie sich stützen. Diese Belege machen jeden Wert nachprüfbar. Wie oft die Werte richtig sind, haben wir aber noch nicht gemessen (5.4).

## 5.1 Aufgabe und Felder

Für jedes Exemplar ermitteln wir die Felder der folgenden Tabelle. Außer Textsorte und Selbsteinschätzung muss jedes Feld durch mindestens eine wörtliche Belegstelle im Text und die Nummern der zugehörigen OCR-Blöcke gestützt sein (5.3). Bei einem Sprachmodell ist das nötig, um Fehldeutungen und erfundene Angaben (Halluzinationen) erkennen zu können.

| Feld | Inhalt | Beispiel: Flugblatt 850 |
|---|---|---|
| Titel | Überschrift oder Textanfang (sofern keine Überschrift erkennbar) | „Zur Fachschaftssatzung“ |
| Reihe und Heft | Name einer Reihe oder Zeitschrift mit Nummer | – |
| Herausgeber | auf dem Blatt angegebener Name, gegebenenfalls mit Funktion oder Vermerk; Zuordnung zum (Herausgeber-)Register | „MSB Spartakus“ |
| Unterzeichnende | auf dem Blatt angegebener Name, gegebenenfalls mit Funktion oder Vermerk wie „V.i.S.d.P.“ | „Fred Karl“, Vermerk „verantw.“ |
| Datum | Datum in Wortlaut, normalisiertes Datum und Art der Angabe (Erscheinen, Veranstaltung, undatiert) | „8.2.72“, 1972-02-08, Erscheinen |
| Eingangsstempel | Datum des Archivstempels, getrennt vom Datum auf dem Blatt | „10. FEB. 1972“, 1972-02-10 |
| Textsorte | Flugblatt im engeren Sinn, Einladung, Broschüre, Zeitschrift, offener Brief, Protokoll oder unklar | Flugblatt |
| Selbsteinschätzung | Vom Modell selbst angegebener Wert zwischen 0 und 1, der seine Sicherheit bei der Extraktion einschätzt | 0,85 |

Die Felder orientieren sich an vergleichbaren Sammlungen. Die Frankfurter Sammlung etwa führt für ihre Flugblätter Datum, Urheber, Thema und Art des Dokuments auf [@frankfurt-flugblaetter]. Zusätzlich nennen wir Belegstellen, damit die Angaben nachvollziehbar sind. Herausgeber und Unterzeichnende erfassen wir getrennt, um die herausgebende Organisation von der verantwortlichen oder unterzeichnenden Person zu unterscheiden.

## 5.2 Herausforderungen

Zwei Felder sind besonders schwer. Das erste ist das Datum. Viele Flugblätter tragen ab 1969 den Eingangsstempel des Archivs, bis 2007 bei vielen Exemplaren der Sammlung (Kap. 2.3, [@uar-rep118]). Ein Blatt hat dann mehrere Datumsangaben, etwa „08.02.1972“ als Erscheinungsdatum und „10.02.1972“ als Eingangsdatum. Das Sprachmodell muss beide auseinanderhalten.

Das zweite sind die Herausgeber. Ihre Namen erscheinen oft als Kürzel in der Kopfleiste und in wechselnden Schreibweisen. Damit dieselbe Gruppe immer gleich erkannt wird, muss jede Angabe einer Organisation aus einem gemeinsamen Herausgeber-Register zugeordnet werden.

## 5.3 Verfahren

Am 22.09.2026 haben wir zunächst vier Modelle an Band 002 getestet: *Gemini 2.5 Flash*, *GPT-5 mini*, *Qwen3 235B* und *Claude Sonnet 4.5*. Für die Bände 1–14 haben wir danach *Claude Sonnet 4.5* gewählt und über OpenRouter aufgerufen, mit mehreren Flugblättern je Anfrage. Die Bände 001–004 liefen am 30.09.2026, die Bände 005–014 am 02.10.2026 mit einer angepassten Fassung des Prompts.

Das Modell antwortet nach einem festen Schema im JSON-Format; der Prompt steht in `src/backend/app/metadata_prompt.txt`. Für jedes Feld gilt eine Belegpflicht: Das Modell nennt zuerst die wörtliche Textstelle und die OCR-Blöcke und erst danach den Wert. Die Pipeline prüft anschließend, ob die genannte Stelle tatsächlich im erkannten Text steht. Nur wenn diese Prüfung gelingt, übernimmt sie den Wert, damit keine Angabe ohne Stütze im Text in die Metadaten gelangt.

Die Herausgeber ordnet die Pipeline einem Register zu, das wir aus dem Findmittel aufgebaut haben (Kap. 2.4). Jede Organisation steht darin unter einem kanonischen Namen, mit Kürzel und bekannten Schreibweisen. Einen Abgleich mit der Gemeinsamen Normdatei (GND) gibt es nicht, weil dort nur sehr wenige der Gruppen eingetragen sind. Das Jahr eines Flugblatts leiten wir aus dem Datum auf dem Blatt ab; fehlt es, gilt das Jahr des Bandes.

![Flugblatt 850 mit den Belegstellen der Metadaten](../abbildungen/metadaten_belege.png)

*Abbildung: Belegstellen der Metadaten für Flugblatt 850 (Band 006, S. 394). Das Modell trennt das Datum auf dem Blatt (8.2.72) vom Eingangsstempel des Archivs (10. Feb. 1972) und nennt für jeden Wert den Block, aus dem er stammt.*

## 5.4 Qualität

Gemessen haben wir bisher nur, ob die Werte belegt sind, nicht, ob sie stimmen. Die Belegprüfung lief beim Erzeugen über 2000 Segmente, nach der Einteilung zum Zeitpunkt der Läufe; darunter sind Leerseiten und Trennungen, die wir danach noch geändert haben. Bei 1731 davon (86,5 %) fand sie keine Beanstandung.

Um zu sehen, wie stark die Ergebnisse vom Prompt abhängen, haben wir am 17.10.2026 die Bände 002–004 erneut mit dem Prompt der Bände 005–014 verarbeitet. Bei den 464 Flugblättern unterschied sich 25-mal (5 %) das Datum, 24-mal (5 %) die Textsorte, 58-mal (13 %, teils nur in der Schreibweise) der Herausgeber und 115-mal (25 %, meist in Länge und Zeichensetzung) der Titel. Die Belegprüfung fiel im zweiten Lauf etwas schlechter aus, mit 84,5 %, 87,7 % und 85,1 % statt 86,2 %, 90,6 % und 89,2 %. Weil sich die Angaben teilweise änderten, behält die Anwendung die Ergebnisse der ursprünglichen Läufe. Als Grund für die Unterschiede vermuten wir sowohl den geänderten Prompt als auch einen Zufallsanteil. Um beides zu trennen, müsste man dieselben Bände mit denselben Einstellungen wie am 02.10.2026 erneut verarbeiten und die Ergebnisse vergleichen.

Eine Messung der Richtigkeit haben wir mit den Titeln des Findmittels für 1968 und 1969 versucht. Als Referenz taugen sie aber nicht: Das Archiv kürzt und vereinheitlicht seine Titel, nennt nur eine Auswahl der Blätter („u. a.“), und schon die Zuordnung eines Archivtitels zu einem unserer Flugblätter ist unsicher. Eine Messung gegen eine verlässliche Referenz fehlt deshalb (Kap. 10.1).

Für den Bestand lassen sich folgende Zahlen festhalten: 169 Herausgeber werden auf mindestens einem Flugblatt genannt, und bei 24 Flugblättern tritt ein Herausgeber auf, der nicht im Register steht. Wie oft die einzelnen Felder gefüllt sind und was die Korrekturen daran geändert haben, zeigt 5.5.

## 5.5 Manuelle Prüfung

Fehler, die beim Lesen auffallen, lassen sich in der Leseansicht von Hand korrigieren, samt neuem Beleg über „Beleg wählen“. Die Anwendung speichert Korrekturen getrennt von den erzeugten Metadaten, sodass sie bei einer Neuberechnung erhalten bleiben. Geänderte Felder gelten als von Hand korrigiert.

Bis zum 12.10.2026 haben wir 142 der 1547 Flugblätter in mindestens einem Feld korrigiert. Gezählt sind nur die Hauptexemplare (Datenbank vom 17.10.2026).

| Feld | automatisch | nach Korrektur | korrigiert |
|---|---|---|---|
| Titel | 1520 (98 %) | 1520 (98 %) | 10 |
| Reihe und Heft | 404 (26 %) | 415 (27 %) | 13 |
| Datum auf dem Blatt | 722 (47 %) | 705 (46 %) | 38 |
| Eingangsstempel | 255 (16 %) | 353 (23 %) | 105 |
| Herausgeber | 1300 (84 %) | 1306 (84 %) | 13 |
| Unterzeichnende | 695 (45 %) | 697 (45 %) | 8 |
| Textsorte (nicht „unklar“) | 1513 (98 %) | 1513 (98 %) | 1 |

Die meisten Korrekturen betreffen den Eingangsstempel, also genau die Schwierigkeit aus 5.2. In 98 Fällen hatte das Modell einen vorhandenen Stempel nicht erkannt. In 24 Fällen haben wir ein erkanntes Datum entfernt, 22-mal davon zugleich als Eingangsstempel eingetragen; das Modell hatte den Stempel also für das Erscheinungsdatum gehalten. Die Korrekturen entstanden größtenteils bei der Prüfung der Mehrfachexemplare vom 05.10. bis 11.10.2026 (Kap. 6.5): Von den 146 Exemplaren, die bis zum 12.10. korrigiert wurden, gehören 131 zu einer Gruppe von Mehrfachexemplaren. Die Auswahl ist also keine Stichprobe, und die Zahlen erlauben keinen Schluss auf die Genauigkeit der übrigen Flugblätter.

Neue Herausgeber ordnet man beim Import im Schritt „Prüfen & freigeben“ dem Register zu. Danach erkennt die Anwendung sie auch in späteren Bänden.

## 5.6 Kosten

Für den Testimport am 20.10.2026 hatten wir die ersten 230 Seiten von Band 15 (Kap. 2.5). Mit *Claude Sonnet 4.5*, dem Modell der Bände 1–14, kostet die Metadatenextraktion danach etwa 9 \$ je 1000 Seiten (2,11 \$ für die 230 Seiten), mit *Claude Opus 5.5* etwa 10 \$ (hochgerechnet aus einem Testlauf mit 56 Flugblättern aus Band 014: 1,36 \$).

Hinweise für die Weiterentwicklung stehen im Handbuch [Weiterentwicklung](../handbuch/weiterentwickeln.md#metadaten).
