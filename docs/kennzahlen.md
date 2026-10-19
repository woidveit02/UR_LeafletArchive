# Kennzahlen

<!-- Der Bereich zwischen BEGIN und END wird von scripts/corpus_stats.py aus der Datenbank erzeugt.
     OCR-Qualität und Kosten sind von Hand gepflegt, bei jeder Änderung das Datum anpassen.
     Im Bericht werden Zahlen nur von hier übernommen. -->

<!-- BEGIN generiert -->
## Korpus nach Band und Jahr

Stand: 17.10.2026, Datenbank vom 17.10.2026 22:18. Erzeugt von scripts/corpus_stats.py – nicht von Hand bearbeiten.

### Je Band

| Band | Jahr | Seiten | Segmente | Exemplare | Flugblätter |
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
| **Summe** |  | **4 464** | **1 927** | **1 927** | **1 547** |

Seiten: Seiten des Bands in der Datenbank, mit Trennblättern. Segmente: alle Stücke, die beim Trennen entstanden sind. Exemplare: jedes Segment ist ein Exemplar eines Flugblatts, deshalb dieselbe Zahl wie Segmente. Flugblätter: Exemplare zusammengefasst, nur das Hauptexemplar jeder Gruppe, ohne Trennblätter und leere Seiten (sie gehören zu keinem Segment). Nur freigegebene Bände; ein Band ohne Seiten ist angelegt, aber nicht eingelesen.

### Je Bandjahr

| Bandjahr | Bände | Seiten | Segmente | Exemplare | Flugblätter | weitere Exemplare | Anteil |
|---|---|---|---|---|---|---|---|
| 1967 | 1 | 13 | 6 | 6 | 6 | 0 | 0,00 % |
| 1968 | 1 | 85 | 58 | 58 | 51 | 7 | 12,07 % |
| 1969 | 1 | 317 | 212 | 212 | 184 | 28 | 13,21 % |
| 1970 | 1 | 294 | 187 | 187 | 169 | 18 | 9,63 % |
| 1971 | 1 | 629 | 230 | 230 | 196 | 34 | 14,78 % |
| 1972 | 4 | 1 608 | 631 | 631 | 477 | 154 | 24,41 % |
| 1973 | 5 | 1 518 | 603 | 603 | 464 | 139 | 23,05 % |
| **Summe** | **14** | **4 464** | **1 927** | **1 927** | **1 547** | **380** | **19,72 %** |

Bandjahr: das Jahr, das der Band im Findmittel trägt. Weitere Exemplare: Segmente, die nicht Hauptexemplar ihrer Gruppe sind (Segmente minus Flugblätter), Anteil an den Segmenten; sie zählen im Jahr ihres eigenen Bandes, das Hauptexemplar kann in einem anderen liegen. Zählweise sonst wie oben.

### Je Datierungsjahr

| Datierungsjahr | Segmente | Exemplare | Flugblätter |
|---|---|---|---|
| 1967 | 6 | 6 | 6 |
| 1968 | 17 | 17 | 17 |
| 1969 | 108 | 108 | 101 |
| 1970 | 96 | 96 | 86 |
| 1971 | 119 | 119 | 102 |
| 1972 | 272 | 272 | 212 |
| 1973 | 242 | 242 | 181 |
| undatiert | 1 067 | 1 067 | 842 |
| **Summe** | **1 927** | **1 927** | **1 547** |

Datierungsjahr: Jahr des Datums auf dem Flugblatt. Zeile „undatiert“: Flugblätter ohne lesbares Datum (in den App-Listen zählen sie im Jahr ihres Bandes). Seiten gibt es hier nicht, sie hängen am Band. Zählweise wie oben.

## Herausgeber und Textsorten

Herausgeber mit mindestens einem Flugblatt: **169**. Flugblätter ohne erkannten Herausgeber: 241, mit einem Herausgeber, der nicht im Register steht: 24 (dieselben Flugblätter zählen bei mehreren Herausgebern mehrfach).

| Textsorte | Flugblätter | Anteil |
|---|---|---|
| Flugblatt | 1 139 | 73,63 % |
| Einladung | 187 | 12,09 % |
| Broschüre | 83 | 5,37 % |
| Zeitschrift | 42 | 2,71 % |
| Offener Brief | 41 | 2,65 % |
| unklar | 34 | 2,20 % |
| Protokoll | 21 | 1,36 % |
| **Summe** | **1 547** | **100,00 %** |

Herausgeber: Einträge des Registers, bei denen mindestens ein Flugblatt (Hauptexemplar) steht. Textsorte: Feld „Typ“ des Flugblatts (Hauptexemplar), „unklar“ ohne Angabe.

Token: nicht aufgeführt. Die Tokenisierung von scripts/ngrams.py arbeitet auf den OCR-Dateien (Blocktypen, Silbentrennung), die nicht in der Datenbank liegen; eine Zahl aus den Datenbanktexten wäre anders gezählt.
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
| OCR Gesamtbestand (Datalab, 4 464 Seiten) | August 2026 | ca. 45 $ | Hochrechnung: Listenpreis 10 $ je 1 000 Seiten |
| davon kostenloses Guthaben (Datalab) | bis 18.08.2026 | [offen] | verbraucht |
| davon abgebucht (Datalab) | 18.08.2026 | 20,11 $ (18,04 €) | Abbuchung |
| weitere Abbuchungen (Datalab) | | [offen] | Abbuchung |
| Metadaten, Testlauf 56 Flugblätter aus Band 014 | | 1,36 $ | gemessen (OpenRouter) |
| Metadaten Bände 001–014 | September/Oktober 2026 | [offen] | Abrechnung OpenRouter |
| Metadaten-Neulauf Bände 001–004 (Vergleich, nicht übernommen) | 17.10.2026 | [offen] | Abrechnung OpenRouter |
