# N-Gramm-Werkzeug

`scripts/ngrams.py` zählt Wörter und Wortfolgen in den OCR-Texten: häufigste N-Gramme, Verläufe über die Jahre, typische Wörter eines Jahres, Kollokationen und Belegstellen. Es braucht nur Python, keine weiteren Pakete und keine API-Schlüssel.

```bash
python scripts/ngrams.py <befehl> [optionen]
python scripts/ngrams.py <befehl> --help
```

Das Skript liest die Datalab-JSONs aus dem Scan-Ordner, den `LEAFLET_PDF_HOST_DIR` in `.env` angibt, und das Jahr jedes Bandes aus `data/volumes.json`. Neue Bände zählen also mit, sobald ihre Texterkennung vorliegt. Der erste Lauf speichert den Text im Scan-Ordner unter `.ngrams/` und dauert einige Sekunden; nach einer neuen Texterkennung wird er neu erzeugt.

Vor dem Befehl stehen zwei Optionen für alle Befehle: `--ordner PFAD` für einen anderen Scan-Ordner und `--bands 0118_0002,0118_0009` für einzelne Bände.

Die Ausgaben unten stammen aus einem Lauf über die 14 Bände vom 19.10.2026.

## Was mit dem Text passiert

Vor jeder Zählung bereitet das Skript den Text in fünf Schritten auf:

1. Kopf- und Fußzeilen, Seitenzahlen und Bilder fallen weg (Blocktypen `PageHeader`, `PageFooter`, `PageNumber`, `Picture`, `Figure`). Das betrifft 3,2 % der Token. Ohne diesen Schritt stehen die Kopfleisten der Blätter oben in jeder Liste.
2. Am Zeilenende getrennte Wörter werden zusammengezogen: `Hilfskammer-`⏎`mensch` wird `Hilfskammermensch`. `Sprach-`⏎`und` bleibt `Sprach- und`, `AStA-`⏎`Fraktion` bleibt `AStA-Fraktion`. Entschieden wird danach, wie das Wort an anderen Stellen im Bestand geschrieben ist; kommt es sonst nicht vor, nach Groß- und Kleinschreibung. Das betrifft nur 0,15 % der Token, hilft aber, lange Komposita zu finden.
3. Der Text wird in Kleinbuchstaben zerlegt, Wörter ab drei Buchstaben, ohne Ziffern. Bindestriche im Wort bleiben (`christlich-demokratisch`).
4. Steht dasselbe Wort dreimal oder öfter hintereinander, bleiben zwei. So fallen Kopfleisten wie „LSD - LSD - LSD“ weg, die als Text erkannt wurden.
5. Stoppwörter zählen nur, wo es sinnvoll ist (siehe die Befehle). Die Liste `scripts/stopwords_de.txt` hat 629 Einträge aus stopwords-iso und spaCy.

## `size`: Umfang je Jahr

```bash
python scripts/ngrams.py size
```

```
Jahr    Seiten     Token  Bände
1967        13      5462  0118_0001
1968        85     19801  0118_0002
1969       317     71845  0118_0003
1970       294     62172  0118_0004
1971       629    149818  0118_0005
1972      1608    362886  0118_0006, 0118_0007, 0118_0008, 0118_0009
1973      1518    392813  0118_0010, 0118_0011, 0118_0012, 0118_0013, 0118_0014
```

1973 hat 72-mal so viele Token wie 1967. Absolute Zahlen messen deshalb vor allem den Umfang der Bände; für Vergleiche über die Jahre `trend` nehmen. Für 1967 trägt keine Häufigkeitsaussage.

## `top`: häufigste N-Gramme

```bash
python scripts/ngrams.py top -n 3 --top 10
```

```
3-Gramme (bereinigt, 1064797 Token):
     414  der universität regensburg
     266  der verfaßten studentenschaft
     193  forschung und lehre
     161  interessen der studenten
     153  freiheit der wissenschaft
     149  mehrheit der studenten
     129  freie politische betätigung
     112  der arbeitenden bevölkerung
     108  aktionsgemeinschaft liberaler studenten
     104  organe der verfaßten
```

Einzelwörter (`-n 1`) zählen ohne Stoppwörter. Ein Zweiwort-N-Gramm braucht mindestens ein Wort, das kein Stoppwort ist, ab drei Wörtern mindestens zwei. Die Liste zeigt feste Formeln: `freiheit der wissenschaft` steht vor allem beim RCDS, `der arbeitenden bevölkerung` bei MSB und SHB.

`--raw` zählt ohne die Aufbereitung. Sieht ein Befund mit und ohne `--raw` gleich aus, hängt er nicht an der Aufbereitung:

```
3-Gramme (roh, 1096581 Token):
    1699  rcds rcds rcds
     642  der universität regensburg
     627  sprach-lit sprach-lit sprach-lit
```

Optionen: `-n` (Standard 2), `--top` (Standard 20), `--raw`.

## `trend`: Häufigkeit je Jahr

Wörter und Wortfolgen in Anführungszeichen, je 10 000 Token:

```bash
python scripts/ngrams.py trend notstand vietnam streik berufsverbot mitbestimmung "numerus clausus" "kampf gegen"
```

```
pro 10.000 Token              1967    1968    1969    1970    1971    1972    1973
  notstand                     0.0     3.0     0.0     0.2     0.0     0.0     0.3
  vietnam                      0.0     0.0     0.7     5.0     0.3     1.3     2.1
  streik                       0.0     3.5    16.6     1.0     0.3     5.9    11.5
  berufsverbot                 0.0     0.0     0.0     0.0     0.0     2.3     2.6
  mitbestimmung                0.0     2.0     1.3     2.1     3.5     5.2     5.0
  numerus clausus              0.0     1.0     0.7     5.0     1.6     1.8     2.9
  kampf gegen                  0.0     2.5     2.9     1.6     1.5     6.0     7.7
  Token je Jahr               5462   19801   71845   62172  149818  362886  392813
```

`notstand` gibt es fast nur 1968, `berufsverbot` erst ab 1972 (Radikalenerlass, Januar 1972), `mitbestimmung` steigt stetig. Gezählt werden Token, nicht Blätter: Ein langes Papier, das ein Wort zwanzigmal enthält, erzeugt einen Ausschlag. Ob ein Wert auf vielen Seiten beruht, zeigt `collocates`; nach Flugblättern zählt der Export der Anwendung.

## `keyness`: was für ein Jahr typisch ist

Vergleicht jedes Jahr mit allen übrigen (Dunnings G²). Die Suchwörter muss man dafür nicht kennen.

```bash
python scripts/ngrams.py keyness --top 6
```

```
1967: würzburg (28), stud (26), universität (48), asta (38), studenten (36)
1968: mayer (77), lsd (60), rektor (76), sds (31), universität (126), psychologie (43)
1969: hirsch (77), kraus (89), art (181), koch (55), bla (33), huber (56)
1970: schumann (121), frage (175), grant (34), onan (31), pollok (53), dow (27)
1971: grundkurse (120), ökonomie (143), marx (158), literaturwissenschaften (84), sprach (129), marxismus (79)
1972: spd (324), gups (93), csu (338), shb (415), the (159), barzel (51)
1973: mhg (274), bhg (1125), sem (472), gew (461), fsr (229), dab (144)
```

Die Liste liest sich als Chronik: 1968 Rektor Mayer, 1971 der Streit um marxistische Grundkurse in den Sprach- und Literaturwissenschaften, 1973 das Bayerische Hochschulgesetz. Sie zeigt auch Fehler der Texterkennung: `onan`, `dow` und `bla` sind keine Wörter und häufen sich in Nr. 004. `the` verrät englische Texte, `bei pustet` (mit `-n 2`) eine Anzeige der Buchhandlung in einer Fußzeile.

Optionen: `-n` (Standard 1), `--min-count` (Mindestzahl im Jahr, Standard 25), `--top` (Standard 10).

## `collocates`: Wörter in der Nähe

Welche Wörter stehen in einem Fenster von fünf Token um einen Ausdruck? Sortiert nach logDice (über 9 sehr stark, 7 bis 9 stark, unter 5 kaum bemerkenswert). Die erste Zeile zeigt, ob die Treffer über viele Seiten verteilt sind oder sich auf wenige lange Papiere bündeln; ab 50 % warnt das Skript.

```bash
python scripts/ngrams.py collocates spd --year 1972 --top 8
```

```
„spd“: 324 Treffer auf 141 von 1608 Seiten; die 10 stärksten Seiten stellen 20 %
  Kollokat                      gem.  gesamt  logDice
  fdp                             28      30     11.3
  shb                             43     418     10.9
  jungsozialisten                 20      98     10.6
  fdp-regierung                   15      15     10.5
  landtag                         15      62     10.3
  gewerkschaften                  11      67      9.8
  innerhalb                       12     190      9.6
  cdu                             11     164      9.5
```

Ein Beispiel, wie man einen Befund prüft. `keyness` zeigt `spd (324)` für 1972.

1. Die Treffer verteilen sich auf 141 Seiten in allen vier Bänden des Jahres, die zehn stärksten Seiten stellen nur 20 %.
2. `trend csu cdu barzel brandt spd` zeigt für alle fünf Wörter 1972 den höchsten Wert, `barzel` kommt fast nur 1972 vor. Die Bundespolitik reicht 1972 in die Flugblätter: das gescheiterte Misstrauensvotum im April, die vorgezogene Bundestagswahl im November.
3. Stärkster Partner ist 1972 `shb`, 1973 fehlt er (dort führen `fdp`, `csu`, `cdu`). Die Belegstellen mit `kwic` zeigen den Streit zwischen SPD und SHB: „Es geht nicht darum, ob (inhaltlich) SPD oder SHB die wahre Sozialdemokratie vertreten…“

Optionen: `--year 1972` oder `--year 1971,1972`, `-w` (Fenster, Standard 5), `--min-count` (Standard 4), `--top` (Standard 20).

## `kwic`: Belegstellen

Keine Zahl sollte in einen Text, bevor jemand ein Dutzend Belegstellen gelesen hat.

```bash
python scripts/ngrams.py --bands 0118_0009,0118_0013 kwic Berufsverbot --limit 2
```

```
[1972 0118_0009 S. 102] …it in den Räumen der Hochschule! WEG MIT DEM [BERUFSVERBOT] FÜR DEMOKRATEN UND INSBESONDERE KOMMUNISTEN …
[1972 0118_0009 S. 102] …en, müssen mit an vorderster Front gegen das [Berufsverbot] stehen. Denn genau uns, denen schon an den H…
[1973 0118_0013 S. 8] …eine Personalakte beim KuMi (zwecks späterem [Berufsverbot]). Dieses BHG zeichnet sich also v.a. dadurch…
[1973 0118_0013 S. 18] …eine Personalakte beim KUMi (zwecks späterem [Berufsverbot]). Dieses BHG zeichnet sich also v.a. dadurch…
```

Die beiden Belege von 1973 stammen aus zwei Exemplaren desselben Blatts, die die Texterkennung leicht verschieden gelesen hat (`KuMi`, `KUMi`). Gesucht wird die Zeichenfolge ohne Rücksicht auf Groß- und Kleinschreibung, `Berufsverbot` findet also auch `Berufsverbote`. `--limit` gilt je Band (Standard 10).

## Grenzen

- Wörter werden nicht auf ihre Grundform gebracht: `studenten` und `student` zählen getrennt.
- Gezählt wird nach Seiten und Token, nicht nach Flugblättern. Fragen wie „auf wie vielen Blättern steht X“ oder „welche Gruppe schreibt was“ beantwortet der Export der Anwendung (Beispiele im Notebook `vertiefung/forschungsfragen.ipynb`).
- Fehler der Texterkennung bleiben stehen. `keyness` findet sie gut.
- G² dient hier nur zum Sortieren, nicht als Test mit Schwellenwert.
