# 7 Themen zuordnen

Ein Themenmodell gruppiert inhaltlich ähnliche Flugblätter zu 40 Themen und schafft so einen Zugang, den das Findmittel nicht bietet. Das Ergebnis ist eine Schätzung: 408 Flugblätter sind nur unsicher zugeordnet und als solche markiert.

## 7.1 Aufgabe

Die Themen sollen einen inhaltlichen Zugang zum Bestand schaffen, neben der Suche nach Wörtern und der Ordnung nach Bänden und Herausgebern.

## 7.2 Herausforderungen

Viele Flugblätter behandeln mehrere Themen, das Modell vergibt aber nur eines. Außerdem überlagern formelhafte Wörter, Gruppenkürzel und Reste der Texterkennung den eigentlichen Inhalt.

## 7.3 Verfahren

Vor der Berechnung wird der Text bereinigt. Ein Blockfilter entfernt Kopf- und Fußzeilen, Seitenzahlen und Bilder, getrennte Wörter werden zusammengeführt und Gruppenkürzel vereinheitlicht [offen: aus alter Fassung 5.3 übertragen, Quelle `handbuch/ngrams.md`].

Das Modell bge-m3 bildet dann den ganzen Text jedes Flugblatts als Vektor ab, bis zu einer Länge von 8 192 Token. BERTopic gruppiert diese Vektoren mit UMAP und HDBSCAN zu 50 Themen, die anschließend auf 40 zusammengefasst werden. Stoppwörter und Kürzel von Organisationen werden dabei nicht berücksichtigt. Flugblätter ohne klares Thema werden dem ähnlichsten zugeordnet und als unsicher markiert. Der aktuelle Lauf stammt vom 03.10.2026, mit dem Startwert 42.

Die Titel der Themen schlägt ein Sprachmodell aus Schlagwörtern und Textauszügen vor. Danach wurden alle 40 Titel von Hand nach Leitlinien geprüft und 15 davon am 13. und 14.10.2026 geändert (`docs/analyse/themen-titel-vorschlaege.md` im Arbeits-Repository).

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

Neue Bände bekommen ihre Themen in Schritt 7 des Imports (`src/backend/app/topics.py`). Die Anwendung holt dazu die Embeddings mit bge-m3 über OpenRouter und ordnet jedes Flugblatt dem Thema zu, dessen Mittelpunkt ihm am nächsten liegt. Ist es dem Mittelpunkt weniger ähnlich als drei Viertel der Flugblätter, die schon im Thema liegen, gilt die Zuordnung als unsicher. Den Punkt auf der Themenkarte bekommt es als Mittel seiner fünf nächsten Nachbarn. Neue Themen entstehen dabei nicht.

Dafür lassen sich die Themen in der Anwendung neu berechnen, unter Verwaltung › Themen. Das Verfahren ist dasselbe wie beim ersten Lauf, rechnet aber nur über die Hauptexemplare; weitere Exemplare bekommen das Thema ihres Hauptexemplars. Das Ergebnis wird nicht sofort übernommen. Eine Prüfseite zeigt zu jedem neuen Thema das bisherige mit den meisten gemeinsamen Flugblättern. Behält ein Thema mindestens die Hälfte davon, ist sein von Hand geprüfter Titel vorausgefüllt, sonst der Vorschlag des Sprachmodells, der nun den Leitlinien für die Titel folgt. Erst mit „Übernehmen“ ersetzt das Ergebnis die bisherigen Themen, die als Sicherung erhalten bleiben. Entwürfe zählen bei der Neuberechnung nicht mit und brauchen danach Schritt 7 noch einmal.

Jedes Flugblatt hat genau ein Thema. Die Neuberechnung in der Anwendung wurde bisher nicht mit dem ersten Lauf verglichen [offen].
