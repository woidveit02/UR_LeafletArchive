# Kennzahlen

<!-- Der Bereich zwischen BEGIN und END wird von scripts/kennzahlen.py aus der Datenbank erzeugt.
     OCR-Qualität und Kosten sind von Hand gepflegt, bei jeder Änderung das Datum anpassen.
     Im Bericht werden Zahlen nur von hier übernommen. -->

<!-- BEGIN generiert -->
## Korpus nach Band und Jahr

Stand: 13.10.2026, Datenbank vom 13.10.2026 09:12. Erzeugt von scripts/kennzahlen.py – nicht von Hand bearbeiten.

### Je Band

| Band | Jahr | Seiten | Segmente | Exemplare | Dokumente |
|---|---|---|---|---|---|
| 001 | 1967 | 13 | 6 | 6 | 6 |
| 002 | 1968 | 85 | 58 | 58 | 51 |
| 003 | 1969 | 317 | 212 | 212 | 184 |
| 004 | 1970 | 294 | 187 | 187 | 169 |
| 005 | 1971 | 629 | 230 | 230 | 196 |
| 006 | 1972 | 455 | 184 | 184 | 143 |
| 007 | 1972 | 223 | 69 | 69 | 43 |
| 008 | 1972 | 325 | 144 | 144 | 94 |
| 009 | 1972 | 605 | 234 | 234 | 197 |
| 010 | 1973 | 217 | 75 | 75 | 60 |
| 011 | 1973 | 255 | 92 | 92 | 58 |
| 012 | 1973 | 286 | 131 | 131 | 100 |
| 013 | 1973 | 261 | 137 | 137 | 104 |
| 014 | 1973 | 499 | 168 | 168 | 142 |
| 015 | 1973 | 0 | 0 | 0 | 0 |
| **Summe** |  | **4 464** | **1 927** | **1 927** | **1 547** |

Seiten: Seiten des Bands in der Datenbank, mit Trennblättern. Segmente: alle Flugblätter, die beim Splitten entstanden sind. Exemplare: jedes Segment ist ein Exemplar eines Dokuments, deshalb dieselbe Zahl wie Segmente. Dokumente: Exemplare zusammengefasst, nur das Hauptexemplar jeder Gruppe, ohne Trennblätter und leere Seiten (sie gehören zu keinem Segment). Nur freigegebene Bände; ein Band ohne Seiten ist angelegt, aber nicht eingelesen.

### Je Bandjahr

| Bandjahr | Bände | Seiten | Segmente | Exemplare | Dokumente | weitere Exemplare | Anteil |
|---|---|---|---|---|---|---|---|
| 1967 | 1 | 13 | 6 | 6 | 6 | 0 | 0,00 % |
| 1968 | 1 | 85 | 58 | 58 | 51 | 7 | 12,07 % |
| 1969 | 1 | 317 | 212 | 212 | 184 | 28 | 13,21 % |
| 1970 | 1 | 294 | 187 | 187 | 169 | 18 | 9,63 % |
| 1971 | 1 | 629 | 230 | 230 | 196 | 34 | 14,78 % |
| 1972 | 4 | 1 608 | 631 | 631 | 477 | 154 | 24,41 % |
| 1973 | 6 | 1 518 | 603 | 603 | 464 | 139 | 23,05 % |
| **Summe** | **15** | **4 464** | **1 927** | **1 927** | **1 547** | **380** | **19,72 %** |

Bandjahr: das Jahr, das der Band im Findmittel trägt. Weitere Exemplare: Segmente, die nicht Hauptexemplar ihrer Gruppe sind (Segmente minus Dokumente), Anteil an den Segmenten; sie zählen im Jahr ihres eigenen Bandes, das Hauptexemplar kann in einem anderen liegen. Zählweise sonst wie oben.

### Je Datierungsjahr

| Datierungsjahr | Segmente | Exemplare | Dokumente |
|---|---|---|---|
| 1967 | 6 | 6 | 6 |
| 1968 | 17 | 17 | 17 |
| 1969 | 108 | 108 | 101 |
| 1970 | 96 | 96 | 86 |
| 1971 | 119 | 119 | 102 |
| 1972 | 279 | 279 | 219 |
| 1973 | 243 | 243 | 182 |
| undatiert | 1 059 | 1 059 | 834 |
| **Summe** | **1 927** | **1 927** | **1 547** |

Datierungsjahr: Jahr des Datums auf dem Dokument. Zeile „undatiert“: Dokumente ohne lesbares Datum (in den App-Listen zählen sie im Jahr ihres Bandes). Seiten gibt es hier nicht, sie hängen am Band. Zählweise wie oben.

## Herausgeber und Textsorten

Herausgeber mit mindestens einem Dokument: **170**. Dokumente ohne erkannten Herausgeber: 242, mit einem Herausgeber, der nicht im Register steht: 24 (dieselben Dokumente zählen bei mehreren Herausgebern mehrfach).

| Textsorte | Dokumente | Anteil |
|---|---|---|
| Flugblatt | 1 140 | 73,69 % |
| Einladung | 186 | 12,02 % |
| Broschüre | 83 | 5,37 % |
| Zeitschrift | 42 | 2,71 % |
| Offener Brief | 41 | 2,65 % |
| unklar | 34 | 2,20 % |
| Protokoll | 21 | 1,36 % |
| **Summe** | **1 547** | **100,00 %** |

Herausgeber: Einträge des Registers, bei denen mindestens ein Dokument (Hauptexemplar) steht. Textsorte: Feld „Typ“ des Dokuments (Hauptexemplar), „unklar“ ohne Angabe.

Token: nicht aufgeführt. Die Tokenisierung von pipelines/06_analysis/ngrams.py arbeitet auf den OCR-Dateien (Blocktypen, Silbentrennung), die nicht in der Datenbank liegen; eine Zahl aus den Datenbanktexten wäre anders gezählt.
<!-- END generiert -->

## OCR-Qualität

Goldstandard aus 105 bewerteten Seiten des Testkorpus (Datalab-Ausgabe, siehe bericht/03-ocr.md, 3.7)

| Maß | Wert |
|---|---|
| CER, längengewichtet | 0,60 % |
| WER, längengewichtet | 2,53 % |
| Seiten mit Layout-Fehlern | 18 (17 %) |
| Seiten mit Fehlern in der Lesereihenfolge | 8 (8 %) |

<!-- Vorbehalt zur Entstehung des Goldstandards in bericht/03-ocr.md, Abschnitt 3.10. -->

## Kosten

<!-- Tatsächliche Abbuchungen getrennt von Hochrechnungen eintragen. -->

| Posten | Datum | Betrag | Art |
|---|---|---|---|
| OCR Gesamtbestand (Datalab) | 18.08.2026 | 18,04 € | Abbuchung |
| | | | |
