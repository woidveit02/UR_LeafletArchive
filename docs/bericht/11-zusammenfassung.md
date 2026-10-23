# 11 Zusammenfassung

Aus 4464 gescannten Seiten der Bände 1 bis 14 ist ein Korpus mit 1926 Exemplaren entstanden, davon 1546 verschiedene Flugblätter, jedes mit Volltext und Metadaten. Gemessen an den Zielen aus Kap. 1.2 und den Anforderungen aus Kap. 9.1 ergibt sich folgendes Bild:

| Ziel | Stand |
|---|---|
| Erschließen | Erreicht. Jede Seite hat Volltext; die Texterkennung liegt an einer Stichprobe gemessen bei etwa 6 falschen Zeichen von 1000 (Kap. 3). Jedes Flugblatt hat von Hand bestätigte Grenzen und automatisch erzeugte Metadaten, Mehrfachexemplare sind von Hand geprüft (Kap. 4 bis 6). |
| Nachprüfbar machen | Erreicht, mit Einschränkung. Fast jeder Wert der Metadaten nennt seine Belegstelle im Scan, und Korrekturen bleiben bei einer Neuberechnung erhalten (Kap. 9). Wie oft die Metadaten selbst richtig sind, ist nicht gemessen (Kap. 5). |
| Recherche ohne Technikwissen | Umgesetzt, nicht mit Nutzern geprüft. Suche, Filter, Leseansicht, Trends und Themen stehen in einer Weboberfläche (Kap. 9); einen Nutzertest gab es nicht (Kap. 10). |
| Fortführen | Technisch erreicht. Ein neuer Band lässt sich in sechs Schritten einlesen, die Kosten nennt die Anwendung vorher, und der Testimport mit dem ersten Teil von Band 15 hat funktioniert. Ob das Archiv den Import ohne uns bewältigt, zeigt erst der Betrieb (Kap. 9). |

Von Hand bestätigt sind dabei die Grenzen und die Gruppen von Mehrfachexemplaren. Die Metadaten stammen vom Sprachmodell und sind nur dort korrigiert, wo uns Fehler aufgefallen sind (Kap. 5.5). Alles Übrige übernehmen automatische Verfahren, und die Anwendung zeigt bei jeder Prüfung den Scan.

| Schritt | Verfahren | Kosten je 1000 Seiten | Handarbeit |
|---|---|---|---|
| Text erkennen | Datalab API | ca. 10 $ | keine |
| Flugblätter trennen | Vorschläge aus gewichteten Hinweisen | keine | jeden Seitenwechsel bestätigen |
| Metadaten erzeugen | Claude Sonnet 4.5, mit Belegen | ca. 9 $ | Korrekturen, neue Herausgeber zuordnen |
| Mehrfachexemplare | Textähnlichkeit | keine | Gruppen bestätigen, Hauptexemplar wählen |
| Themen zuordnen | bge-m3 und BERTopic | wenige Cent | Titel prüfen |

Texterkennung und Metadaten kosten zusammen etwa 19 $ je 1000 Seiten, gemessen am Testimport. Die meiste Zeit braucht das Prüfen der Seitenwechsel. Beim Trennen der Bände 1 bis 14 von Hand waren es 7 bis 11 Sekunden je Seite, für einen Band von rund 300 Seiten also 35 bis 55 Minuten; mit dem Vorschlag beim Import haben wir die Zeit nicht gemessen. Dazu kommen etwa 1,5 Minuten je Gruppe von Mehrfachexemplaren.

Auswertungen zur politischen Kommunikation haben wir zugunsten der Erschließung zurückgestellt (Kap. 1.2); die Werkzeuge dafür liegen bereit (Kap. 9.6).

Fehlerfrei ist das Korpus nicht (Kap. 10). Für Recherchen heißt das: Es findet Flugblätter und zeigt Zusammenhänge, Zitate und Zahlen sollten aber am Scan geprüft werden. Die Belege machen das mit einem Klick möglich (Kap. 9.2).
