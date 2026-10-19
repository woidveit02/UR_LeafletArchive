# 7 Themen zuordnen

Ein Themenmodell gruppiert inhaltlich ähnliche Flugblätter zu 40 Themen und schafft so einen Zugang, den das Findmittel nicht bietet. Das Ergebnis ist eine Schätzung: 408 Flugblätter sind nur unsicher zugeordnet und als solche markiert.

## 7.1 Aufgabe

Die Themen sollen einen inhaltlichen Zugang zum Bestand schaffen, neben der Suche nach Wörtern und der Ordnung nach Bänden und Herausgebern.

## 7.2 Herausforderungen

Viele Flugblätter behandeln mehrere Themen, das Modell vergibt aber nur eines. Außerdem überlagern formelhafte Wörter, Gruppenkürzel und Reste der Texterkennung den eigentlichen Inhalt.

## 7.3 Verfahren

Vor der Berechnung wird der Text bereinigt. Aus der Texterkennung bleiben nur die Textblöcke; Bilder, Kopf- und Fußzeilen fallen weg. Vermerke des Archivs wie „Ablage“ mit Eingangsstempel, „z. K.“ oder „Erbitte Rückgabe“ werden entfernt. Flugblätter mit weniger als 50 Zeichen Text gehen nicht ein, längere Texte werden nach 16 000 Zeichen abgeschnitten. Silbentrennungen werden hier nicht zusammengeführt und Gruppenkürzel nicht vereinheitlicht; das tut nur das N-Gramm-Werkzeug (`handbuch/ngrams.md`). Die Anwendung bereitet den Text beim Zuordnen neuer Bände und bei der Neuberechnung genauso auf.

Das Modell bge-m3 bildet dann den ganzen Text jedes Flugblatts als Vektor ab, bis zu einer Länge von 8 192 Token. BERTopic gruppiert diese Vektoren mit UMAP und HDBSCAN zu 50 Themen, die anschließend auf 40 zusammengefasst werden. Für die Schlagwörter eines Themas zählen nur Substantive in ihrer Grundform (spaCy, Modell `de_core_news_lg`). Stoppwörter und Kürzel von Organisationen werden dabei nicht berücksichtigt. Flugblätter ohne klares Thema werden dem ähnlichsten zugeordnet und als unsicher markiert. Der aktuelle Lauf stammt vom 03.10.2026, mit dem Startwert 42.

Die Titel der Themen schlägt ein Sprachmodell aus Schlagwörtern und Textauszügen vor. Danach wurden alle 40 Titel von Hand nach Leitlinien geprüft und 15 davon am 13. und 14.10.2026 geändert.

## 7.4 Qualität

Die Qualität der Zuordnung wurde nicht gemessen. 1 078 Flugblätter sind sicher zugeordnet, 408 unsicher und 61 haben kein Thema. Die größten Themen sind „Streiks und Vollversammlungen gegen das Hochschulgesetz“ (136 Flugblätter), „Debatte um Hochschulgesetz und Hochschulreform“ (71) und „Hochschulwahlen: Kandidaten, Listen und Ergebnisse“ (47).

Fehlzuordnungen kommen vor. Das Flugblatt zum Streik gegen die Notstandsgesetze vom 29.05.1968 etwa liegt im Thema zum Hochschulgesetz, weil es in beiden um Streiks geht.

![Themenkarte und Themenliste der Anwendung](../abbildungen/app_themen.png)

*Abbildung: Themenkarte der Anwendung. Jeder Punkt ist ein Flugblatt, nahe Punkte haben ähnliche Texte. Flugblatt 850 gehört zum Thema „Fachschaftssatzungen und Urabstimmungen“ (25 Flugblätter).*

## 7.5 Manuelle Prüfung

Von Hand werden die Titel der Themen geprüft und bei Bedarf umbenannt. Das geht in der Anwendung unter Verwaltung › Themen; die Titel stehen in `data/topics.json`.

## 7.6 Kosten

Ein Lauf über den ganzen Bestand kostet wenige Cent.

## 7.7 Hinweise zur Weiterentwicklung

Neue Bände bekommen ihre Themen in Schritt 7 des Imports (`src/backend/app/topics.py`). Die Anwendung holt dazu die Embeddings mit bge-m3 über OpenRouter. Jedes Flugblatt bekommt das Thema, das unter seinen fünf ähnlichsten Flugblättern überwiegt, gewichtet nach Ähnlichkeit, und einen Punkt auf der Themenkarte im Mittel dieser Nachbarn. Unsicher ist die Zuordnung, wenn weniger als 60 % des Gewichts auf das Thema fallen oder schon das ähnlichste Flugblatt weniger ähnlich ist als bei 90 % der Flugblätter ihr nächster Nachbar. Eine erste Fassung ordnete dem nächsten Themenmittelpunkt zu. An Band 015, dessen Seiten aus Band 14 stammen, traf sie bei 5 von 9 Flugblättern das Thema des Gegenstücks in Band 14, die Nachbarn bei 8 von 9. Die Themen von BERTopic beruhen auf HDBSCAN und sind oft nicht rund, ihr Mittelpunkt sagt deshalb wenig. Neue Themen entstehen bei der Zuordnung nicht. Welche Bände nachträglich zugeordnet wurden und wann die Themen zuletzt berechnet wurden, steht unter Verwaltung › Themen.

Die Themen lassen sich in der Anwendung neu berechnen. Das Verfahren ist dasselbe wie beim ersten Lauf, rechnet aber nur über die Hauptexemplare; weitere Exemplare bekommen das Thema ihres Hauptexemplars. Die Ähnlichkeit berechnet immer bge-m3, wählen lässt sich nur das Sprachmodell für die Titel. Dessen Vorschläge folgen den Leitlinien, nach denen die Titel des ersten Laufs geprüft wurden. Die Titel beginnen bei jeder Neuberechnung neu; bisherige Titel werden nicht übernommen. Das Ergebnis wird erst nach einer Prüfung übernommen. Die Prüfseite zeigt die neuen Themen wie die Themenseite, mit Karte, und nennt je Thema das bisherige, aus dem die meisten seiner Flugblätter stammen. Bisherige Themen, von denen kein neues mehr als die Hälfte enthält, sind als aufgeteilt aufgeführt. Die Flugblätter eines neuen Themas lassen sich vorab in der Flugblattliste ansehen. Erst mit „Übernehmen“ ersetzt das Ergebnis die bisherigen Themen, die als Sicherung erhalten bleiben. Entwürfe zählen bei der Neuberechnung nicht mit und brauchen danach Schritt 7 noch einmal.

Jedes Flugblatt hat genau ein Thema. Die Neuberechnung in der Anwendung wurde bisher nicht mit dem ersten Lauf verglichen [offen].
