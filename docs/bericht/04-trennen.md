# 4 Flugblätter trennen

In den Bänden liegen die Seiten aller Flugblätter hintereinander, ohne Vermerk, wo eines endet und das nächste beginnt. Dieser Schritt legt die Grenzen fest. Für die Bände 1 bis 14 haben wir das von Hand getan; daraus sind 1927 Exemplare entstanden. Beim Import neuer Bände schlägt die Anwendung die Trennungen vor. Etwa fünf von sechs Vorschlägen stimmen, bestätigen muss sie aber weiterhin ein Mensch.

## 4.1 Aufgabe

Festzulegen ist, welche Seiten eines Bandes gemeinsam ein Flugblatt bilden. Für die Vorschläge beim Import läuft die Texterkennung vor der Trennung, weil ein Teil der Hinweise auf ein neues Flugblatt, etwa Kopfzeilen und Datumsangaben, aus dem Text stammt. Andere Hinweise wie Papierfarbe, Abheftlöcher und Stempel liest die Anwendung aus dem Scan (4.4).

## 4.2 Herausforderungen

Anfang und Ende eines Flugblatts sind nicht immer eindeutig zu erkennen. Grenzfälle sind Hefte und Anlagen, Rückseiten ohne eigenen Kopf und Trennblätter. Vor allem in den Bänden von 1973 gibt es zudem nur wenige aussagekräftige Kopfzeilen und Stempel. Für unklare Fälle braucht es deshalb einheitliche Regeln, damit die Trennung über den ganzen Bestand gleich ausfällt.

Beim zweiten Durchgang über die Handtrennung am 29.09.2026 haben wir folgende Regeln festgelegt:

- Zusammengehörige Hefte und Dokumentationen bleiben ein Flugblatt, auch wenn einzelne Beiträge eigene Kopfzeilen haben. Ein Beispiel ist das *Fachbereichsinfo Nr. 10* in Band 005 mit den Heftseiten 1 bis 25 (S. 444–470).
- Eine Rückseite gehört zu einem offensichtlich zugehörigen Flugblatt, auch wenn sie nach einem „b. w.“ („bitte wenden“) eine eigene Kopfzeile hat.
- Trägt eine Rückseite einen eigenständigen Text eines anderen Herausgebers als die Vorderseite, wird sie ein eigenes Flugblatt. So stehen in Band 013 AStA-Informationen auf der Rückseite einer Bekanntmachung des Ältestenrats vom 22.06.1973.
- Mehrfachexemplare bleiben zunächst getrennte Exemplare und werden erst im nächsten Schritt zusammengeführt (Kap. 6).
- Seiten in falscher Reihenfolge werden nicht umsortiert, sondern beim Flugblatt vermerkt.

Für angehängte Resolutionen und Pressespiegel gibt es bislang keine eindeutige Regel.

## 4.3 Altes Verfahren

Die 14 Bände haben wir bis zum 22.08.2026 von Hand mit dem Werkzeug `flugblatt_splitter` getrennt, einem Vorläufer der Trennansicht, die heute in der Anwendung steckt. Ob sich dieser Schritt automatisieren lässt, haben wir an Band 002 geprüft und die Handtrennung mit der automatischen Trennung durch Datalab verglichen. Von Hand entstanden 59 Exemplare, Datalab erkannte nur 13. Alle 13 Schnitte von Datalab hatten wir auch von Hand gesetzt, 46 der 59 hat Datalab aber übersehen. Da keine der beiden Trennungen damals geprüft war, zeigt der Vergleich nur, wie stark sich die Entscheidungen unterschieden. Er reichte aber, um eine vollständige Automatisierung vorerst auszuschließen.

Mit dem Import kam später eine erste Fassung der Vorschläge in die Anwendung. Sie stützte sich nur auf den erkannten Text: Jeder Seitenwechsel wurde anhand von 14 Merkmalen bewertet und mit einem naiven Bayes-Klassifikator verrechnet, dessen Gewichte aus der Handtrennung der Bände 1–14 stammen. Ab einer Wahrscheinlichkeit von 0,5 schlug die Anwendung eine Trennung vor. Das Verfahren läuft lokal und ohne Sprachmodell.

Für ein neues Flugblatt sprechen etwa Eingangsstempel, Datumsangaben in der Kopfzeile, eine Kopfleiste mit Gruppenkürzeln, ein Impressum, eine nahezu leere vorausgehende Seite oder wenige gemeinsame Wörter mit der Seite davor. Gegen eine Trennung sprechen Seitenzahlen wie „- 2 -“, Trennstriche oder ein „b. w.“ am Ende der vorherigen Seite, ein „Fortsetzung“ am Seitenanfang und viele gemeinsame Wörter zwischen zwei aufeinanderfolgenden Seiten.

Für die Bände 13 und 14 kam eine Locherkennung hinzu. Sind die Abheftlöcher nur rechts zu sehen, gilt die Seite als Rückseite, und die Anwendung vermutet dort keinen Beginn eines neuen Flugblatts.

Liegt die Einteilung eines Bandes schon vor, lässt sie sich beim Import als Liste übergeben. Die Anwendung übernimmt dann alle Trennungen, und die Prüfung von Hand entfällt. Die Liste enthält eine Zeile je Flugblatt mit erster und letzter Seite; ein „x“ davor markiert eine Leerseite:

```
1-2
3
x 4
5-9
```

## 4.4 Neues Verfahren

Kurz vor Projektende haben wir die Vorschläge erweitert. Zu den 14 Merkmalen aus dem Text kommen eine Wortliste mit Wörtern, die ein Ende oder einen Anfang anzeigen können, und neun Merkmale aus dem Scan. Die Erkennung der Abheftlöcher funktioniert jetzt in allen Bänden und bei jedem Import, für schwarze wie für weiße Löcher.

Der naive Bayes-Klassifikator selbst ist geblieben. Jeder Hinweis hat ein Gewicht, positiv für ein neues Flugblatt und negativ dagegen; Wortliste und Scan liefern Hinweise in beide Richtungen. Die Anwendung summiert alle Gewichte und schlägt eine Trennung vor, wenn die Summe über Null liegt. Ohne jeden Hinweis trennt sie nicht; der Grundwert entspricht dem Anteil der Seitenwechsel mit Trennung in den Bänden 1–14 (1797 von 4219 Seitenwechseln ohne Leerseiten, 42,6 %). Gelernt sind die Gewichte an der Handtrennung der Bände 1–14.

Für die Wortliste haben wir die letzten 250 Zeichen der Seite davor und die ersten 250 Zeichen jeder Seite verglichen, an Seitenwechseln mit und ohne Trennung. Übrig blieben etwa 90 Wörter. Namen, Orte und Wörter einzelner Gruppen haben wir herausgenommen, alle Monate und Wochentage hinzugenommen. Je Seitenwechsel zählt nur das stärkste Wort dafür und das stärkste dagegen. Für eine Trennung sprechen etwa „Eigendruck“ am Ende der Seite davor oder „eingelaufen“ und „Ablage“ am Seitenanfang. Dagegen sprechen Wörter, die mitten im Gedankengang stehen, wie „natürlich“, „jedoch“ und „deshalb“.

Die Merkmale aus dem Scan gewinnt die Anwendung aus einer verkleinerten Fassung jeder Seite, im Hintergrund und parallel zur Texterkennung. Mit der Seite davor vergleicht sie Papierfarbe, Format, Ränder und Tintenmenge. Sind die Abheftlöcher nur rechts zu sehen, ist die Seite eine Rückseite. Das blaue „F“ und die blauen Stempel des Archivs erkennt sie an der Farbe: Blaue Tinte schluckt mehr Rot als Blau, graue Schreibmaschinenschrift alle Farben gleich. Graue oder blasse Stempel bleiben im Bild deshalb unsichtbar, meist findet sie aber die Texterkennung. Leerseiten mit fast keinen dunklen Kanten bekommen kein Gewicht; der Vorschlag lässt sie als „Leerseite / Trennblatt“ aus, sie gehören zu keinem Flugblatt.

![Hinweise und ihre Gewichte](../abbildungen/trennmerkmale.png)

*Abbildung: Hinweise auf einen Flugblattwechsel und ihre Gewichte. Grün spricht für ein neues Flugblatt, rot dagegen. Die Summe mit dem Grundwert ergibt den Wert, der in der Anwendung zwischen den Knöpfen steht.*

![Zwei Seitenwechsel aus Band 006 mit ihren Hinweisen](../abbildungen/trennbeispiel.png)

*Abbildung: Zwei knappe Seitenwechsel aus Band 006 mit den Hinweisen, die die Anwendung dort findet. Oben beginnt mit S. 442 ein neues Flugblatt („Was ist ein Strauzel???“), obwohl das Papier gleich ist und „deshalb“ unter den ersten 250 Zeichen des erkannten Texts steht. Den Ausschlag gibt das Impressum unten auf S. 441, die Summe ist +1,3. Unten endet S. 454 ebenfalls mit einem Impressum, doch S. 455 hat die Abheftlöcher rechts und ist damit eine Rückseite. Mit −1,7 schlägt die Anwendung richtig keine Trennung vor.*

## 4.5 Qualität des neuen Verfahrens

Die erste Fassung nutzte nur den Text, die neue zusätzlich Wortliste und Scan:

| Vorschlag | Fehler je 100 Seitenwechsel | Präzision | Trefferquote |
|---|---|---|---|
| nur Text (bisher) | 20,2 | 0,79 | 0,72 |
| Text + Wortliste + Scan (jetzt) | **11,8** | **0,84** | **0,89** |

Ohne Vorschlag müsste man 1797 Trennungen selbst setzen. Mit Vorschlag sind noch 496 Stellen zu ändern (302 zu viel, 194 fehlen), also 72 % weniger als ohne Vorschlag. Bei einer Präzision von 0,84 ist etwa jeder sechste vorgeschlagene Schnitt falsch, bei einer Trefferquote von 0,89 fehlt etwa jeder neunte echte Anfang.

Die Zahlen sind leicht optimistisch, weil wir Merkmale und Wörter mit Blick auf alle 14 Bände ausgewählt haben; nur die Gewichte sind sauber getrennt gelernt. Leerseiten und die Seitenwechsel an ihnen sind nicht enthalten, weil die Anwendung sie vor dem Vorschlag auslässt (Stand 23.10.2026). Wie gut das Verfahren auf neue Bände übertragbar ist, haben wir nicht getestet; das muss nach Erhalt neuer Bände geschehen.

## 4.6 Manuelle Prüfung

Weil die Vorschläge Fehler enthalten, prüft beim Import ein Mensch jeden Seitenwechsel. Die Trennansicht zeigt die beiden Seiten groß nebeneinander, dazu den Wert des Vorschlags und die Hinweise, aus denen er sich zusammensetzt; mit einer Taste wird die Trennung bestätigt oder geändert. Die Bedienung beschreibt das Handbuch [Import neuer Bände](../handbuch/neue-baende-importieren.md#4-flugblatter-trennen). Für die Bände 1 bis 14 gab es den Vorschlag noch nicht. Sie wurden ganz von Hand getrennt und in einem zweiten Durchgang anhand einer Liste verdächtiger Stellen geprüft (Kap. 12.5).

![Trennansicht beim Import](../abbildungen/import_trennen.png)

*Abbildung: Trennansicht beim Import an einem vorgeschlagenen Seitenwechsel, mit geöffneter Erklärung des Werts.*

## 4.7 Ergebnis und Kosten

Die 4464 Seiten des Bestands ergeben 1927 Exemplare. Hinzu kommen 115 Seiten, die zu keinem Flugblatt gehören, meist Trennblätter oder leere Rückseiten. Fünf davon enthalten dennoch möglicherweise relevanten Text und sollten noch einmal geprüft werden.

Die Auswertung der Scans für die Vorschläge dauert je Band höchstens wenige Minuten, der Vorschlag selbst kommt danach sofort. Weil alles lokal läuft, entstehen für diesen Schritt keine Kosten für externe Dienste.

Hinweise für die Weiterentwicklung stehen im Handbuch [Weiterentwicklung](../handbuch/weiterentwickeln.md#trennen).
