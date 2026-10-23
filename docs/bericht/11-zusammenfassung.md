# 11 Zusammenfassung

Aus 4464 gescannten Seiten der Bände 1 bis 14 ist ein Korpus mit 1927 Exemplaren entstanden, davon 1547 verschiedene Flugblätter, jedes mit Volltext und Metadaten. Gemessen an den Zielen aus Kap. 1.2 und den Anforderungen aus Kap. 9.1 ergibt sich folgendes Bild:

| Ziel | Stand |
|---|---|
| Erschließen | Erreicht. Jede Seite hat Volltext; die Texterkennung liegt bei etwa 6 falschen Zeichen von 1000 (Kap. 3). Jedes Flugblatt hat von Hand bestätigte Grenzen und Metadaten, Mehrfachexemplare sind von Hand geprüft (Kap. 4 bis 6). |
| Nachprüfbar machen | Erreicht, mit Einschränkung. Jeder Wert der Metadaten nennt seine Belegstelle im Scan, und Korrekturen bleiben bei einer Neuberechnung erhalten (Kap. 9). Wie oft die Metadaten selbst richtig sind, ist nicht gemessen (Kap. 5). |
| Recherche ohne Technikwissen | Erreicht. Suche, Filter, Leseansicht, Trends und Themen stehen in einer Weboberfläche (Kap. 9). Einen Nutzertest gab es nicht (Kap. 10). |
| Fortführen | Technisch erreicht. Ein neuer Band lässt sich in sechs Schritten einlesen, die Kosten nennt die Anwendung vorher, und der Testimport mit dem ersten Teil von Band 15 hat funktioniert. Ob das Archiv den Import ohne uns bewältigt, zeigt erst der Betrieb (Kap. 9). |

Den größten Teil der Arbeit übernehmen automatische Verfahren. Von Hand bleiben das Bestätigen der Seitenwechsel, die Prüfung der Mehrfachexemplare und Korrekturen an den Metadaten. Die Anwendung führt durch diese Prüfung und zeigt dabei jeweils den Scan.

| Schritt | Verfahren | Kosten je 1000 Seiten | Handarbeit |
|---|---|---|---|
| Text erkennen | Datalab API | ca. 10 $ | keine |
| Flugblätter trennen | Vorschläge aus gewichteten Hinweisen | keine | jeden Seitenwechsel bestätigen |
| Metadaten erzeugen | Claude Sonnet 4.5, mit Belegen | ca. 9 $ | Korrekturen, neue Herausgeber zuordnen |
| Mehrfachexemplare | Textähnlichkeit | keine | Gruppen bestätigen, Hauptexemplar wählen |
| Themen zuordnen | bge-m3 und BERTopic | wenige Cent | Titel prüfen |

Texterkennung und Metadaten kosten zusammen etwa 19 $ je 1000 Seiten, gemessen am Testimport. Die meiste Zeit braucht das Prüfen der Seitenwechsel, bei einem Band von rund 300 Seiten etwa 35 bis 55 Minuten, dazu etwa 1,5 Minuten je Gruppe von Mehrfachexemplaren.

Den Schwerpunkt haben wir auf die Erschließung gelegt. Auswertungen zur politischen Kommunikation, die die Themenstellung ebenfalls nennt, sind über Export, N-Gramm-Werkzeug und Notebook möglich (Kap. 9). Sie werden aussagekräftiger, je mehr Jahrgänge das Archiv mit der Anwendung erschließt.

Fehlerfrei ist das Korpus nicht (Kap. 10). Für Recherchen heißt das: Es findet Flugblätter und zeigt Zusammenhänge, Zitate und Zahlen sollten aber am Scan geprüft werden. Die Belege machen das mit einem Klick möglich.
