# 6 Mehrfachexemplare zusammenführen

Etwa ein Fünftel der 1 927 Exemplare sind weitere Stücke eines Flugblatts, das schon vorliegt. Die Anwendung findet sie über Textähnlichkeit, ein Mensch bestätigt jede Gruppe und wählt ein Hauptexemplar. Alle Exemplare bleiben als eigene Datensätze erhalten.

## 6.1 Aufgabe

- Exemplare desselben Flugblatts finden, damit jedes Flugblatt nur einmal zählt.
- Die Doppelstücke sind nach der Sammlungspraxis gewollt (Kap. 2.5), kein Fehler der Digitalisierung.

## 6.2 Herausforderungen

- Zwei Exemplare werden nie buchstabengleich erkannt (OCR-Rauschen), ein exakter Textvergleich reicht nicht.
- Exemplare liegen oft im selben Band, teils in verschiedenen; Beispiel: das RCDS-„Theoriepapier Nr. 4“ liegt viermal in Band 007.
- Geänderte Nachdrucke (Fassungen) sind inhaltlich interessant und sollen nicht verschwinden.

## 6.3 Verfahren und Entscheidung

- Pipeline (`pipelines/01_pdf/find_copies.py`, Arbeits-Repository): Kandidaten über die Ähnlichkeit der bge-m3-Embeddings (Kosinus ab 0,85), bestätigt über Zeichen-5-Gramme auf normalisiertem Text.
- Einstufung, kalibriert an der Verteilung über alle Bände: Jaccard ab 0,75 Exemplar, 0,5–0,75 mögliche Fassung (von Hand prüfen), darunter meist nur gemeinsame Bausteine wie Formulare oder Wahllisten.
- „Enthalten“: ein Flugblatt steckt fast ganz in einem deutlich längeren, Hinweis auf einen fehlenden Schnitt.
- Unter 150 Zeichen Text ist kein Vergleich möglich.
- Anwendung beim Import: ohne Embeddings, Vorfilter über seltene Wörter, dann dieselbe 5-Gramm-Schwelle.
- Markieren statt zusammenlegen: Jedes Exemplar bleibt ein eigener Datensatz mit eigener Stelle im Karton, eigenen Stempeln und Vermerken. Metadaten werden je Exemplar extrahiert.

## 6.4 Wie gut

- Die Methode der Anwendung findet 309 der 310 geprüften Gruppen, ohne API.
- Der Vorschlag für das Hauptexemplar (längster Text) wurde in 62 % der Gruppen übernommen.

## 6.5 Was von Hand bleibt

- Prüfung in der Ansicht `/exemplare`: Exemplare nebeneinander, abweichende Angaben (Datum, Titel, Herausgeber) markiert; falsche Treffer aussortieren, Hauptexemplar festlegen.
- 320 Fälle geprüft: 310 echte Gruppen (248 Paare, 55 mit drei, 7 mit vier oder fünf Exemplaren), 10 doch verschiedene Blätter. Etwa 1–2 Minuten je Fall.
- Entscheidungen in `data/copy_decisions.jsonl`, nur angehängt, nie überschrieben; Blätter werden über Band und Seitenbereich angesprochen, nicht über Gruppennummern.

## 6.6 Ergebnis und Kosten

- 1 927 Exemplare ergeben 1 547 Flugblätter; 380 weitere Exemplare (19,7 %).
- Ungleich verteilt: 1968–1971 zwischen 10 und 15 %, 1972 24 %, 1973 23 %. Ohne diesen Schritt wäre jede Zählung um ein Fünftel zu hoch, für 1972/73 um ein Viertel.
- Zählungen (Startseite, Liste, Herausgeber, Themen, Trends) nehmen jedes Flugblatt einmal; die Suche geht durch alle Exemplare und zeigt das Hauptexemplar.
- Kosten: keine.

## 6.7 Für die Weiterarbeit

- Fassungen werden nicht automatisch gruppiert.
- Das Themenmodell rechnet noch über alle Exemplare statt nur über die Hauptexemplare (Kap. 7).
- Abbildung: Exemplarvergleich in der Anwendung.
