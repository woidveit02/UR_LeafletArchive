# 6 Mehrfachexemplare zusammenführen

Etwa ein Fünftel der 1 927 Exemplare sind weitere Stücke eines Flugblatts, das schon vorliegt. Die Anwendung findet sie über Textähnlichkeit, ein Mensch bestätigt jede Gruppe und wählt ein Hauptexemplar. Alle Exemplare bleiben als eigene Datensätze erhalten.

## 6.1 Aufgabe

Ziel ist, Exemplare desselben Flugblatts zu finden, damit jedes Flugblatt nur einmal zählt. Die Mehrfachexemplare sind nach der Sammlungspraxis gewollt: Das Archiv behielt Doppelexemplare, um etwa in Ausstellungen auch die Rückseite zeigen zu können [@uar-rep118] (Kap. 2.5). Sie sind also kein Fehler der Digitalisierung.

## 6.2 Herausforderungen

Zwei Exemplare werden nie buchstabengleich erkannt, weil die Texterkennung bei jedem Scan etwas anders liest. Ein exakter Textvergleich reicht deshalb nicht. Exemplare liegen oft im selben Band, teils auch in verschiedenen; das „Theoriepapier Nr. 4“ des RCDS etwa liegt viermal in Band 007. Geänderte Nachdrucke, also Fassungen eines Flugblatts, sind inhaltlich interessant und sollen nicht verschwinden.

## 6.3 Verfahren

Für den Bestand wurden die Mehrfachexemplare über alle Bände hinweg gesucht. Kandidaten ergeben sich aus der Ähnlichkeit der bge-m3-Embeddings ab einem Kosinuswert von 0,85. Bestätigt werden sie über Zeichen-5-Gramme auf normalisiertem Text. Die Schwellen sind an der Verteilung über alle Bände kalibriert: Ab einem Jaccard-Wert von 0,75 gilt ein Paar als Exemplar, zwischen 0,5 und 0,75 als mögliche Fassung, die von Hand geprüft wird. Darunter teilen zwei Blätter meist nur Bausteine wie Formulare oder Wahllisten.

Steckt ein Flugblatt fast ganz in einem deutlich längeren, wird es als „enthalten“ markiert; das weist auf einen fehlenden Schnitt hin. Unter 150 Zeichen Text ist kein Vergleich möglich.

Beim Import neuer Bände arbeitet die Anwendung ohne Embeddings. Sie filtert Kandidaten über seltene Wörter vor und wendet dann dieselbe 5-Gramm-Schwelle an.

Mehrfachexemplare werden markiert, nicht zusammengelegt. Jedes Exemplar bleibt ein eigener Datensatz mit eigener Stelle im Karton, eigenen Stempeln und Vermerken. Auch die Metadaten werden je Exemplar erzeugt.

## 6.4 Qualität

Die Methode der Anwendung findet 309 der 310 geprüften Gruppen, ohne eine API zu nutzen. Der Vorschlag für das Hauptexemplar, das Exemplar mit dem längsten Text, wurde in 62 % der Gruppen übernommen.

## 6.5 Manuelle Prüfung

Geprüft wird in der Ansicht `/exemplare`. Dort stehen die Exemplare nebeneinander, abweichende Angaben zu Datum, Titel und Herausgeber sind markiert. Falsche Treffer werden aussortiert, und für jede Gruppe wird ein Hauptexemplar festgelegt.

Insgesamt wurden 320 Fälle geprüft. 310 davon waren echte Gruppen: 248 Paare, 55 Gruppen mit drei und 7 mit vier oder fünf Exemplaren. In 10 Fällen handelte es sich doch um verschiedene Blätter. Ein Fall dauerte etwa ein bis zwei Minuten.

Die Entscheidungen stehen in `data/copy_decisions.jsonl`. Die Datei wird nur ergänzt, nie überschrieben. Blätter werden darin über Band und Seitenbereich angesprochen, nicht über Gruppennummern.

## 6.6 Ergebnis und Kosten

Die 1 927 Exemplare ergeben 1 547 Flugblätter; 380 sind weitere Exemplare (19,7 %). Sie sind ungleich verteilt: In den Bänden von 1968 bis 1971 liegt ihr Anteil zwischen 10 und 15 %, 1972 bei 24 % und 1973 bei 23 %. Ohne diesen Schritt wäre jede Zählung um ein Fünftel zu hoch, für 1972 und 1973 um ein Viertel.

Alle Zählungen der Anwendung, also Startseite, Liste, Herausgeber, Themen und Trends, nehmen jedes Flugblatt einmal. Die Suche geht durch alle Exemplare und zeigt das Hauptexemplar an. Kosten entstehen keine.

![Anteil der Mehrfachexemplare nach Bandjahr](../abbildungen/3_mehrfachexemplare.png)

![Geprüfte Fälle von Mehrfachexemplaren](../abbildungen/7_exemplare_faelle.png)

<!-- offen: Abbildung Exemplarvergleich in der Anwendung (/exemplare), z. B. Band 006 S. 396–397 gegen S. 364–365 -->

## 6.7 Hinweise zur Weiterentwicklung

Fassungen werden bisher nicht automatisch gruppiert. Der erste Themenlauf rechnete über alle Exemplare; die Neuberechnung in der Anwendung nimmt nur die Hauptexemplare (Kap. 7).
