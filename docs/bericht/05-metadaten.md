# 5 Metadaten erzeugen

Ein Sprachmodell liest Titel, Datum, Herausgeber und weitere Angaben aus dem erkannten Text. Zu jedem Wert muss es die wörtliche Textstelle nennen, aus der er stammt. Wie genau die Angaben sind, wurde noch nicht gemessen.

## 5.1 Aufgabe und Felder

Das Modell erfasst für jedes Exemplar die folgenden Felder. Zu jedem Wert außer Textsorte und Selbsteinschätzung gehören die wörtliche Belegstelle und die Nummern der OCR-Blöcke, aus denen er stammt (5.3).

| Feld | Inhalt | Beispiel: Flugblatt 850 |
|---|---|---|
| Titel | Überschrift, sonst der Textanfang | „Zur Fachschaftssatzung“ |
| Reihe und Heft | Name einer Reihe oder Zeitschrift mit Nummer | – |
| Herausgeber | Name wie auf dem Blatt, Funktion, Vermerk; Zuordnung zum Register | „MSB Spartakus“ |
| Unterzeichnende | Name wie auf dem Blatt, Funktion, Vermerk wie „V.i.S.d.P.“ | „Fred Karl“, Vermerk „verantw.“ |
| Datum | Wortlaut, normalisiertes Datum und Art (Erscheinen, Veranstaltung, undatiert) | „8.2.72“, 1972-02-08, Erscheinen |
| Eingangsstempel | Datum des Archivstempels, getrennt vom Datum auf dem Blatt | „10. FEB. 1972“, 1972-02-10 |
| Textsorte | Flugblatt im engeren Sinn, Einladung, Broschüre, Zeitschrift, offener Brief, Protokoll, unklar | Flugblatt |
| Selbsteinschätzung | Sicherheit des Modells zwischen 0 und 1 | 0,85 |

Die Kernfelder entsprechen dem, was Sammlungen von Hand erfassen: Die Frankfurter Sammlung verzeichnet je Flugblatt Datum, Urheber, Thema und Art [@frankfurt-flugblaetter]. Neu sind die Belegstelle je Wert und die Trennung von Herausgebern und Unterzeichnenden.

## 5.2 Herausforderungen

Ab 1969 tragen manche Blätter einen Eingangsstempel auf der Vorderseite; bis 2007 war das in der Sammlung üblich [@uar-rep118]. Auf diesen Blättern stehen dann zwei Daten, etwa das Erscheinungsdatum „8.2.72“ und der Eingangsstempel „10. FEB. 1972“. Das Modell muss sie auseinanderhalten. Schwierig sind auch die Herausgeber: Sie erscheinen als Kürzel in Kopfleisten und in vielen verschiedenen Schreibweisen.

## 5.3 Verfahren

Am 22.09.2026 wurden zuerst vier Modelle an Band 002 getestet: Gemini 2.5 Flash, GPT-5 mini, Qwen3 235B und Claude Sonnet 4.5. Für die Bände 1–14 kam danach Claude Sonnet 4.5 (`anthropic/claude-sonnet-4.5`) zum Einsatz. Es wurde über OpenRouter mit Prompt v2 und 20 Flugblättern je Anfrage aufgerufen. Die Nummern 001–004 stammen aus Läufen vom 30.09.2026 (Kennungen `claude-r9`, `claude-r11`, `claude-r11a2`), die Nummern 005–014 aus einem Lauf vom 02.10.2026 (`claude-r12`). Zwischen diesen Läufen wurde der Prompt weiter überarbeitet. Die einzelnen Fassungen liegen im Arbeits-Repository (Kap. 12.5).

Das Modell antwortet mit JSON nach einem festen Schema. Der Prompt, den die Anwendung verwendet, steht in `src/backend/app/metadata_prompt.txt`. Für jedes Feld gilt eine Belegpflicht: Das Modell nennt zuerst die wörtliche Textstelle und die OCR-Blöcke und erst danach den Wert. Die Pipeline prüft anschließend, ob die genannte Stelle tatsächlich im OCR-Text steht.

Die Herausgeber werden einem Register zugeordnet, das aus dem Findmittel aufgebaut wurde. Es enthält zu jeder Organisation einen kanonischen Namen, das Kürzel und die Schreibvarianten. Einen Abgleich mit der GND gibt es nicht, weil nur sehr wenige Gruppen einen GND-Eintrag haben. Das Jahr wird aus dem Datum auf dem Blatt genommen. Fehlt es, wird das Jahr des Bandes verwendet.

![Flugblatt 850 mit den Belegstellen der Metadaten](../abbildungen/metadaten_belege.png)

*Abbildung: Belegstellen der Metadaten für Flugblatt 850 (Band 006, S. 394). Das Modell trennt das Datum auf dem Blatt (8.2.72) vom Eingangsstempel des Archivs (10. Feb. 1972) und nennt für jeden Wert den Block, aus dem er stammt.*

<!-- Abbildungen aus scripts/scan_figures.py (App muss laufen); anderes Flugblatt: python scripts/scan_figures.py <id> -->

## 5.4 Qualität

Die Belegprüfung der Pipeline bestehen 1 731 von 2 000 Segmenten (86,5 %) ohne Beanstandung. Sie ist in `check_grounding` in `extract_metadata_v2.py` umgesetzt, die Ergebnisse stehen unter `grounding` in `data/nr0XX_metadata.json`. Die Prüfung zeigt allerdings nur, ob die Angaben belegt sind, nicht, ob sie stimmen.

Um die Prompt-Fassungen zu vergleichen, wurden die Bände 002–004 am 17.10.2026 noch einmal mit dem Prompt der Bände 005–014 verarbeitet (`claude-r12`). Gegenüber den früheren Fassungen änderten sich bei 464 Flugblättern das Datum in 25 Fällen (5 %), die Textsorte in 24 (5 %), die Herausgeber in 58 (13 %, teils nur andere Schreibweisen) und der Titel in 115 (25 %, meist Länge und Zeichensetzung). Die Belegprüfung fiel leicht schlechter aus (86,2/90,6/89,2 % gegenüber 84,5/87,7/85,1 %). Die App behält deshalb die früheren Läufe. Die neuen Läufe liegen im Arbeits-Repository (Kap. 12.5). In den Unterschieden mischen sich Zufall und Prompt-Änderung.

Wie gut sich die Ergebnisse bei gleichem Prompt wiederholen lassen, ist noch offen: [offen: zweiter Lauf mit `claude-r12` über dieselben Bände, dann Vergleich r12 gegen r12].

[offen] Wenn die Prüfung gegen Archivtitel an der Referenzstrecke 1968/69 gemacht wurde, gehört ihr Ergebnis hierher, je Feld. Sonst die fehlende Messung in Kap. 10 benennen.

Zum Bestand lassen sich folgende Zahlen festhalten: 169 Herausgeber haben mindestens ein Flugblatt, 24 Flugblätter nennen einen Herausgeber ohne Registereintrag. Wie viele Flugblätter die einzelnen Felder füllen, vor und nach den Korrekturen, zeigt 5.5.

## 5.5 Manuelle Prüfung

Korrekturen werden in der Leseansicht über „Beleg wählen“ vorgenommen und in `data/corrections.jsonl` gespeichert. Felder, die dort geändert wurden, gelten als von Hand korrigiert.

Bis zum 12.10.2026 wurden 142 der 1 547 Flugblätter in mindestens einem Feld korrigiert. Die Tabelle zeigt für jedes Feld, wie viele Flugblätter nach der Extraktion einen Wert hatten, wie viele nach den Korrekturen und bei wie vielen das Feld korrigiert wurde. Gezählt sind die Hauptexemplare (Datenbank vom 17.10.2026).

| Feld | automatisch | nach Korrektur | korrigiert |
|---|---|---|---|
| Titel | 1 520 (98 %) | 1 520 (98 %) | 10 |
| Reihe und Heft | 404 (26 %) | 415 (27 %) | 13 |
| Datum auf dem Blatt | 722 (47 %) | 705 (46 %) | 38 |
| Eingangsstempel | 255 (16 %) | 353 (23 %) | 105 |
| Herausgeber | 1 300 (84 %) | 1 306 (84 %) | 13 |
| Unterzeichnende | 695 (45 %) | 697 (45 %) | 8 |
| Textsorte (nicht „unklar“) | 1 513 (98 %) | 1 513 (98 %) | 1 |

Die meisten Korrekturen betreffen den Eingangsstempel. In 98 Fällen hatte das Modell keinen Stempel erkannt, obwohl einer auf dem Blatt steht. In 24 Fällen wurde ein Datum entfernt, bei 22 davon wurde es zugleich als Eingangsstempel eingetragen: Das Modell hatte den Stempel als Erscheinungsdatum gelesen. Wie die korrigierten Flugblätter ausgewählt wurden, ist offen [offen]. Die Zahlen erlauben deshalb keinen Schluss auf die Genauigkeit der übrigen Flugblätter.

Neue Herausgeber werden im Import-Schritt „Prüfen & freigeben“ einmal dem Register zugeordnet. Danach erkennt die Anwendung sie in späteren Bänden.

## 5.6 Kosten

Die Kosten liegen bei ca. 8 $ je 1 000 Seiten. Dieser Wert ist aus einem einzigen Lauf mit 56 Flugblättern hochgerechnet. Der Lauf mit Claude Opus 5.5 kostete gemessen 1,36 $. Mit denselben Tokens und dem Listenpreis von Sonnet 4.5 ergeben sich etwa 0,018 $ je Flugblatt, bei rund 430 Exemplaren je 1 000 Seiten.

Der Lauf war ein Test für die Demo. Von Einheit 15 gibt es keine Scans, deshalb wurde ein Teil der PDF von Band 14 als Nr. 015 eingelesen. Die Kosten beruhen also auf echtem Material des Bestands, aber nicht auf Einheit 15.

## 5.7 Hinweise zur Weiterentwicklung

Über OpenRouter lässt sich das Modell austauschen, und die Anwendung zeigt die Kosten je Lauf an. Weichen die Angaben innerhalb einer Gruppe von Mehrfachexemplaren voneinander ab, ist das ein Hinweis auf Fehler der Extraktion (Kap. 6).
