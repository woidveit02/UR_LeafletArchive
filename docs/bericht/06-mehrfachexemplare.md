# 6 Mehrfachexemplare zusammenführen

Etwa ein Fünftel der 1 927 Exemplare sind weitere identische Versionen eines bereits im Bestand vorhandenen Flugblatts. Potenzielle Mehrfachexemplare werden zunächst in der Anwendung anhand von Textähnlichkeit gekennzeichnet. Mithilfe eines integrierten Tools kann die Zuordnung anschließend manuell überprüft und bestätigt werden. Bei diesem Schritt wird ein sogenanntes Hauptexemplar bestimmt. Alle Exemplare bleiben auch nach der Kontrolle als eigenständige Datensätze vorhanden.

## 6.1 Aufgabe

Ziel ist es, Mehrfachexemplare eines einzigen Flugblatts zu identifizieren, um bei späteren Auswertungen bzw. Datenanalysen jeden Inhalt nur einfach zu behandeln. Das Auftreten dieser Mehrfachexemplare ist Teil der Sammlungspraxis: Nach Möglichkeit bewahrt das Archiv bewusst mehrere Versionen des gleichen Flugblatts auf, um bspw. bei Ausstellungen auch die Rückseite präsentieren zu können [@uar-rep118] (Kap. 2.5). Es handelt sich dabei also nicht um einen Digitalisierungsfehler, welcher behoben werden muss, sondern um eine Eigenschaft des Bestandes, die bei einer Auswertung Berücksichtigung erfodert.

## 6.2 Herausforderungen

Selbst bei identischen Inhalten unterscheiden sich die erkannten Texte mehrerer Exemplare oft geringfügig, da bei jedem Scan unterschiedliche OCR-Fehler auftreten können. Für eine zuverlässige Erkennung von Mehrfachexemplaren ist ein ausschließlicher direkter Textvergleich somit nicht ausreichend. Zusätzlich konnte beobachtet werden, dass identische Exemplare sowohl innerhalb desselben Bandes als auch über mehrere Bände hinweg vorkommen können. So liegt das "Theoriepapier Nr. 4 " des RCDS bspw. viermal in Band 7 vor. Gleichzeitig müssen Nachdrucke, die den Inhalt verändern, als eigene Fassungen erkennbar bleiben, um inhaltliche Untersuchungen aufgrund ihrer Unterschiede anstellen zu können.

*TODO: Ein Beispiel raussuchen, wo sich Mehrfachexemplare über mehrere Bände hinweg verteilen.*

## 6.3 Verfahren

Die Suche nach Mehrfachexemplaren wurde über alle Bände des Bestands hinweg durchgeführt. Kandidaten ergeben sich aus der Ähnlichkeit der bge-m3-Embeddings ab einem Kosinuswert von 0,85. Bestätigt werden sie über Zeichen-5-Gramme auf normalisiertem Text. Die Schwellen sind an der Verteilung über alle Bände kalibriert: Ab einem Jaccard-Wert von 0,75 gilt ein Paar als Exemplar, zwischen 0,5 und 0,75 als mögliche Fassung, die von Hand geprüft wird. Darunter teilen zwei Blätter meist nur Bausteine wie Formulare oder Wahllisten.

Enthält ein deutlich längerer Text nahezu vollständig den Text eines kürzeren Flugblatts, wird dies als „enthalten“ markiert. Ein derartiger Fall kann auf einen nicht erkannten Schnitt zwischen zwei Flugblättern hinweisen. Bei Texten mit weniger als 150 Zeichen ist kein Vergleich möglich.

Beim Import neuer Bände werden keine Embeddings verwendet. In diesem Fall grenzt die Anwendung zunächst mögliche Kandidaten anhand seltener Wörter ein. Anschließend wird die Textähnlichkeit mit derselben 5-Gramm-Methode wie zuvor und den beschriebenen Schwellenwerten bewertet.

Mehrfachexemplare werden als solche markiert, jedoch nicht direkt zusammengeführt. Jedes Exemplar bleibt ein eigständiger Datensatz mit eigener Stelle im Karton, individuellen Stempeln und Vermerken. Auch die Metadaten werden für jedes Exemplar einzeln erzeugt. In Listen, bei Asuwertungen und Exporten vertritt das Hauptexemplar die Gruppe der Mehrfachexemplare. Informationen der übrigen Versionen bleiben erhalten.

## 6.4 Qualität

Die Methode der Anwendung findet 309 der 310 geprüften Gruppen, ohne eine API zu nutzen. Der Vorschlag für das Hauptexemplar, das Exemplar mit dem längsten Text, wurde in 62 % der Gruppen übernommen.

## 6.5 Manuelle Prüfung

Die manuelle Prüfung findet in der Ansicht `/exemplare` statt. Hier werden die Exemplare einer Gruppe nebeneinander angezeigt. Abweichungen bei Datum, Titel und Herausgeber werden in einer eigenen Metadaten-Tabelle hervorgehoben. Fehlerhaft erkannte Mehrfachexemplare werden verfworden, während bei einer korrekten Annahme ein Hauptexemplar ausgewählt werden muss. Hiernach können die Metadaten der repräsentativen Version überprüft und bearbeitet werden. Dabei werden auch wesentliche Informationen der anderen Exemplare der Gruppe angezeigt und können samt Beleg (falls vorhanden) übernommen werden. 

Insgesamt wurden 320 Fälle geprüft. Bei 310 dieser Gruppen konnten tatsächlich Mehrfachexemplare festgestellt werden: Darunter sind 248 Duplikate, 55 Gruppen mit jeweils drei Exemplaren und sieben Gruppen mit vier oder fünf Versionen. Bei den übrigen 10 Fällen handelt es sich um unterschiedliche Flugblätter, deren Inhalt fälschlicherweise als identisch erkannt wurde. jede Prüfung dauerte von der Auswahl des Hauptexemplares bis zum Abgleichen der Metadaten ca. 1 - 2 Minuten. 

Die Entscheidungen werden in `data/copy_decisions.jsonl` dokumentiert. Hierbei wird die Datei fortlaufend ergänzt, bestehende Einträge werden nicht überschrieben. Einzelne Blätter werden anhand ihres Bandes und Seitenbereichs identifiziert. Die Gruppennummern spielen hierbei keine Rolle. Somit können Entscheidungen auch bei Änderungen an der Gruppierung nachvollzogen werden. 

## 6.6 Ergebnis und Kosten

Die 1 927 Exemplare ergeben 1 547 Flugblätter; 380 sind weitere Exemplare (19,7 %). Sie sind ungleich verteilt: In den Bänden von 1968 bis 1971 liegt ihr Anteil zwischen 10 und 15 %, 1972 bei 24 % und 1973 bei 23 %. Ohne diesen Schritt wäre jede Zählung um ein Fünftel zu hoch, für 1972 und 1973 um ein Viertel.

Alle Zählungen der Anwendung, also Startseite, Liste, Herausgeber, Themen und Trends, nehmen jedes Flugblatt einmal. Die Suche geht durch alle Exemplare und zeigt das Hauptexemplar an. Kosten entstehen keine.

![Anteil der Mehrfachexemplare nach Bandjahr](../abbildungen/3_mehrfachexemplare.png)

![Geprüfte Fälle von Mehrfachexemplaren](../abbildungen/7_exemplare_faelle.png)

<!-- offen: Abbildung Exemplarvergleich in der Anwendung (/exemplare), z. B. Band 006 S. 396–397 gegen S. 364–365 -->

## 6.7 Hinweise zur Weiterentwicklung

Fassungen werden bisher nicht automatisch gruppiert. Der erste Themenlauf rechnete über alle Exemplare; die Neuberechnung in der Anwendung nimmt nur die Hauptexemplare (Kap. 7).
