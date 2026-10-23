# 6 Mehrfachexemplare zusammenführen

Etwa ein Fünftel der 1927 Exemplare sind weitere Exemplare eines Flugblatts, das schon im Bestand liegt. Dieser Schritt findet solche Mehrfachexemplare, lässt sie von Hand bestätigen und bestimmt für jede Gruppe ein Hauptexemplar. Am Ende stehen 1547 Flugblätter; alle Exemplare bleiben als eigene Datensätze erhalten.

## 6.1 Aufgabe

Mehrfachexemplare müssen erkannt werden, damit jeder Inhalt bei Auswertungen nur einmal zählt. Sie gehören zur Sammlungspraxis: Das Archiv bewahrt bewusst mehrere Exemplare auf, etwa um in Ausstellungen auch die Rückseite zeigen zu können [@uar-rep118] (Kap. 2.5).

## 6.2 Herausforderungen

Ein einfacher Textvergleich genügt nicht, weil die Texterkennung auf jedem Scan andere Fehler macht. Auch bei identischem Inhalt unterscheiden sich die erkannten Texte deshalb oft geringfügig. Zudem liegen Mehrfachexemplare an verschiedenen Stellen. Sie kommen innerhalb eines Bandes vor, das „Theoriepapier Nr. 4“ des RCDS etwa viermal in Band 7, und über Bände hinweg: 59 der 310 Gruppen verteilen sich auf zwei Bände. „Zulassungs-Stop im Fach Psychologie“ vom 08.01.1969 liegt zweimal in Band 002 (1968) und ein weiteres Mal in Band 003 (1969). Gleichzeitig müssen Nachdrucke mit verändertem Inhalt als eigene Fassungen erkennbar bleiben, damit man ihre Unterschiede untersuchen kann.

## 6.3 Verfahren

Für die Bände 1 bis 14 haben wir über alle Bände hinweg gesucht. Kandidaten ergeben sich aus der Ähnlichkeit der bge-m3-Embeddings ab einem Kosinuswert von 0,85. Bestätigt werden sie über Zeichen-5-Gramme auf normalisiertem Text. Die Schwellen sind an der Verteilung über alle Bände kalibriert: Ab einem Jaccard-Wert von 0,75 gilt ein Paar als Exemplar desselben Flugblatts, zwischen 0,5 und 0,75 als mögliche Fassung, die von Hand geprüft wird. Darunter teilen zwei Flugblätter meist nur Bausteine wie Formulare oder Wahllisten.

Enthält ein deutlich längerer Text fast vollständig den Text eines kürzeren Flugblatts, markiert das Verfahren den Fall als „enthalten“. Das kann auf eine übersehene Trennung zwischen zwei Flugblättern hinweisen. Texte mit weniger als 150 Zeichen lassen sich nicht vergleichen.

Beim Import neuer Bände verwendet die Anwendung keine Embeddings. Sie grenzt die Kandidaten zunächst über seltene Wörter ein und bewertet die Ähnlichkeit dann mit derselben 5-Gramm-Methode und denselben Schwellen.

Gefundene Mehrfachexemplare werden markiert, aber nicht verschmolzen. Jedes Exemplar bleibt ein eigener Datensatz mit eigener Stelle im Karton, eigenen Stempeln und Vermerken, und auch die Metadaten entstehen für jedes Exemplar einzeln. In Listen, Auswertungen und Exporten vertritt das Hauptexemplar die Gruppe; die Angaben der übrigen Exemplare bleiben erhalten.

## 6.4 Qualität

Von 320 vermuteten Gruppen haben sich 310 bestätigt; falsche Treffer machen 3,13 % aus. Den Vorschlag für das Hauptexemplar, das Exemplar mit dem längsten Text, haben wir bei 62 % der Gruppen übernommen.

## 6.5 Manuelle Prüfung

Geprüft haben wir in einer eigenen Vergleichsansicht. Sie zeigt die Exemplare einer Gruppe nebeneinander und hebt Abweichungen bei Datum, Titel und Herausgeber in einer Tabelle hervor. Falsch erkannte Gruppen werden verworfen; bei richtigen wählt man ein Hauptexemplar. Danach lassen sich dessen Metadaten prüfen und bearbeiten. Die Ansicht zeigt dabei die Angaben der anderen Exemplare, die sich samt Beleg übernehmen lassen.

![Drei Exemplare eines Flugblatts aus Band 006 nebeneinander](../abbildungen/nutzen_exemplare.png)

*Abbildung: Prüfung einer Gruppe in der Anwendung. Drei Exemplare desselben Flugblatts aus Band 006 (S. 364–365, 376–377 und 396–397) stehen nebeneinander; markiert ist die abweichende Angabe zum Eingangsstempel, den nur das gewählte Hauptexemplar trägt.*

Unter den 310 bestätigten Gruppen sind 248 Paare, 55 Gruppen mit drei Exemplaren und sieben Gruppen mit vier oder fünf Exemplaren. Die übrigen 10 Fälle waren unterschiedliche Flugblätter, deren Inhalt fälschlich als identisch erkannt wurde. Jede Prüfung dauerte von der Wahl des Hauptexemplars bis zum Abgleich der Metadaten etwa 1 bis 2 Minuten.

Die Anwendung speichert die Entscheidungen getrennt von den Gruppen. So bleiben sie erhalten, wenn sich die Gruppierung ändert.

## 6.6 Ergebnis und Kosten

Aus den 1927 Exemplaren ergeben sich 1547 Flugblätter. Die übrigen 380 Exemplare machen rund 19,7 % des Bestands aus. Ihr Anteil schwankt zwischen den Jahrgängen: In den Bänden von 1968 bis 1971 liegt er zwischen 10 und 15 %, 1972 bei 24 % und 1973 bei 23 %.

Alle Zahlen in der Anwendung, etwa zu Herausgebern, Themen, Trends, Umfang des Korpus oder Veröffentlichungen je Jahr, zählen jedes Flugblatt nur einmal. Die Suche bezieht weiterhin alle Exemplare ein, zeigt bei Treffern aber nur das Hauptexemplar. Externe Dienste braucht dieser Schritt nicht, Kosten entstehen also keine.

![Anteil der Mehrfachexemplare nach Bandjahr](../abbildungen/3_mehrfachexemplare.png)

![Geprüfte Fälle von Mehrfachexemplaren](../abbildungen/7_exemplare_faelle.png)

Hinweise für die Weiterentwicklung stehen im Handbuch [Weiterentwicklung](../handbuch/weiterentwickeln.md#mehrfachexemplare).
