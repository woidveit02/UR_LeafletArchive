# 5 Metadaten erzeugen

Ein Sprachmodell liest Titel, Datum, Herausgeber und weitere Angaben aus dem erkannten Text. Zu jedem Wert muss es die wörtliche Textstelle nennen, aus der er stammt. Wie genau die Angaben sind, wurde noch nicht gemessen.

## 5.1 Aufgabe und Felder

- Titel (Überschrift oder, wenn keine vorhanden, der Textanfang), Reihe und Heftnummer.
- Herausgeber und Unterzeichnende: Name wie auf dem Blatt, Rolle (Organisation oder Einzelperson), Funktion, Vermerk wie „V.i.S.d.P.“.
- Datum: wie auf dem Blatt, normalisiert, und seine Art (Erscheinen, Veranstaltung, undatiert); dazu der Eingangsstempel.
- Textsorte (Flugblatt im engeren Sinn, Einladung, Broschüre, Zeitschrift, offener Brief, Protokoll, unklar) und eine Selbsteinschätzung des Modells.

## 5.2 Herausforderungen

- Auf einem Blatt stehen oft mehrere Daten, etwa Erscheinungsdatum „8.2.72“ und Eingangsstempel „10. FEB. 1972“.
- Herausgeber erscheinen als Kürzel in Kopfleisten und in vielen Schreibweisen.

## 5.3 Verfahren und Entscheidung

- Zuerst Gemini 2.5 Flash, dann Claude Sonnet 4.5 über OpenRouter für die Bände 1–14 [Versionen, Daten, Bündelung ergänzen].
- Antwort als JSON nach festem Schema; Prompt in `pipelines/04_metadata/prompt_v2.py` (Arbeits-Repository).
- Belegpflicht: Das Modell nennt zu jedem Feld zuerst die wörtliche Textstelle und die OCR-Blöcke, dann den Wert. Die Pipeline prüft, ob die Stelle im OCR-Text steht.
- Herausgeber-Register aus dem Findmittel mit kanonischem Namen, Kürzel und Schreibvarianten; Zuordnung mit `pipelines/04_metadata/org_match.py` [GND-Abgleich: gemacht?].
- Jahr: aus dem Datum auf dem Blatt, sonst das Jahr des Bandes.
- Abbildung: Flugblatt 850 mit beschrifteten Belegstellen (Folie 8 der Abschlusspräsentation).

## 5.4 Wie gut

- [offen] Wenn die Prüfung gegen Archivtitel an der Referenzstrecke 1968/69 gemacht wurde, gehört ihr Ergebnis hierher, je Feld. Sonst mindestens die Belegquote angeben und die fehlende Messung in Kap. 10 benennen.
- Ein Datum auf dem Blatt haben 713 von 1 547 Flugblättern (46 %).
- 170 Herausgeber haben mindestens ein Flugblatt; 242 Flugblätter haben keinen erkannten Herausgeber, 24 einen Namen ohne Registereintrag.
- Bekannter Fehler: Eingangsstempel als Erscheinungsdatum gelesen.

## 5.5 Was von Hand bleibt

- Korrekturen in der Leseansicht („Beleg wählen“), gespeichert in `data/corrections.jsonl`; geänderte Felder gelten als von Hand korrigiert.
- Neue Herausgeber werden im Import-Schritt „Prüfen & freigeben“ einmal dem Register zugeordnet; danach erkennt die Anwendung sie in späteren Bänden.

## 5.6 Kosten

- Ca. 8 $ je 1 000 Seiten, hochgerechnet aus einem einzigen Lauf mit 56 Flugblättern: Claude Opus 5.5 kostete gemessen 1,36 $; mit denselben Tokens und dem Listenpreis von Sonnet 4.5 ergeben sich etwa 0,018 $ je Flugblatt und rund 430 Exemplare je 1 000 Seiten.
- [klären, welche Seiten bei diesem Lauf in Nr. 015 lagen]

## 5.7 Für die Weiterarbeit

- Das Modell ist über OpenRouter austauschbar; die Anwendung zeigt die Kosten je Lauf.
- Abweichende Angaben innerhalb einer Exemplargruppe weisen auf Fehler der Extraktion hin (Kap. 6).
