# 4 Flugblätter trennen

Ein Band ist ein Stapel Seiten ohne markierte Grenzen. Die 14 Bände wurden von Hand in 1 927 Exemplare getrennt. Für neue Bände schlägt die Anwendung Trennungen vor; etwa drei von vier Vorschlägen stimmen, deshalb bestätigt ein Mensch jeden Übergang.

## 4.1 Aufgabe

- Festlegen, welche Seiten zusammen ein Flugblatt bilden. Das bestimmt, was ein Datensatz ist.
- Die Texterkennung lief vor der Trennung, weil die Hinweise auf einen Blattanfang im Text stehen (Kopfzeilen, Stempel, Datum).

## 4.2 Herausforderungen

- Mehrseitige Hefte und Anlagen, Rückseiten ohne eigenen Kopf, Trennblätter und leere Seiten.
- In den Bänden von 1973 gibt es wenig auswertbare Kopfzeilen und Stempel.
- Regeln für Grenzfälle festhalten: mehrseitige Hefte, Anlagen, Rückseiten [aus alter Fassung 4.5].

## 4.3 Verfahren und Entscheidung

- Unsere 14 Bände: von Hand mit dem Werkzeug `flugblatt_splitter`, aufgeteilt auf drei Personen, im August abgeschlossen.
- Vergleich mit der automatischen Segmentierung von Datalab an Band 002: dort fehlten eher Schnitte, als dass falsche gesetzt wurden [aus alter Fassung 4.3 prüfen].
- Für neue Bände ein eigener Vorschlag aus dem erkannten Text (`src/backend/app/boundaries.py`): 14 Merkmale, verrechnet mit einem naiven Bayes-Klassifikator, Gewichte gelernt an den Bänden 1–14, Vorschlag ab einer Wahrscheinlichkeit von 0,5. Läuft lokal, ohne Sprachmodell.
- Für einen Blattanfang sprechen Eingangsstempel, Datum in der Kopfzeile, Kopfleiste mit Gruppenkürzeln, Impressum oder fast leere Seite davor und wenig gemeinsame Wörter mit der Vorseite.
- Dagegen sprechen eine Seitenzahl wie „- 2 -“, ein Trennstrich oder „b. w.“ am Ende der Vorseite, „Fortsetzung“ am Seitenanfang und viele gemeinsame Wörter.
- Locherkennung für die Bände 13 und 14: Sind die Abheftlöcher nur rechts zu sehen, ist die Seite eine Rückseite und beginnt kein neues Flugblatt.
- Alternativ lässt sich eine beim Scannen notierte Liste übernehmen.

## 4.4 Wie gut

- Jeder Band wurde mit Gewichten aus den übrigen 13 geprüft, so wie es bei einem neuen Band wäre.
- Statt 1 986 Trennungen von Hand bleiben 904 Korrekturen, 54 % weniger.
- Präzision 0,73: etwa jeder vierte Vorschlag ist falsch. Trefferquote 0,84: etwa jede sechste echte Trennung fehlt.
- Locherkennung: auf den Bänden 13 und 14 sinken die Korrekturen von 163 auf 120.
- Testband (Band 14 ab Seite 449, als neuer Band importiert): 50 Übergänge, 13 Korrekturen, 11 Trennungen fehlten, 2 waren zu viel.
- Grenzen der Messung: Die Referenz der Bände 1–14 ist selbst nur teilweise geprüft. Prüfung gegen die Archivtitel 1968/69 [offen, ob durchgeführt].

## 4.5 Was von Hand bleibt

- Jeder Übergang wird in der Anwendung bestätigt oder geändert (zwei benachbarte Seiten groß, Tasten für trennen und zusammen).
- Zeitaufwand für die 14 Bände [offen].

## 4.6 Ergebnis und Kosten

- 4 464 Seiten ergeben 1 927 Exemplare. 115 Seiten gehören zu keinem Flugblatt: 102 ohne Text, 8 mit wenig Text, 5 mit echtem Text, die noch geprüft werden sollten.
- Kosten: keine, das Verfahren läuft lokal.

## 4.7 Für die Weiterarbeit

- Code: `src/backend/app/boundaries.py`, `src/backend/app/segments.py`; Ursprung der Merkmale und Gewichte in `pipelines/01_pdf/` im Arbeits-Repository.
- Gewichte neu lernen, wenn der Bestand deutlich wächst.
- Rückseiten bleiben die größte Schwäche.
- Abbildung: Trennansicht der Anwendung.
