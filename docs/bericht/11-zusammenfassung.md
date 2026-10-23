# 11 Zusammenfassung

Trotz der ganzen bereits genannten Problemfelder erfüllt die entwickelte Anwendung ihren Zweck. Denn auch wenn kleine Fehler bleiben, hat die Anwendung einen enormen Vorteil im Vergleich zur manuellen Erfassung dieser ganzen Daten und das einleitend gesetzte Ziel wurde umgesetzt. So lässt sich mit der Import-Funktion eine PDF mit mehreren hundert Flugblättern innerhalb von kurzer Zeit zu dem Korpus hinzufügen, und die Daten der Flugblätter auslesen und verarbeiten.

Aus 4464 gescannten Seiten wurde ein recherchierbarer Bestand mit 1547 Flugblättern. Automatische Verfahren übernehmen den größten Teil der Arbeit. Beim Trennen, bei den Mehrfachexemplaren und bei den Metadaten bleibt eine Prüfung von Hand nötig, die aber durch simple Nutzeroberflächen erheblich vereinfacht werden.

| Schritt | Verfahren | Kosten je 1 000 Seiten | Handarbeit |
|---|---|---|---|
| Text erkennen | Datalab API | ca. 10 $ | keine |
| Flugblätter trennen | naiver Bayes, Vorschläge| keine | jeden Übergang bestätigen |
| Metadaten erzeugen | Claude Sonnet 4.5, mit Belegen | ca. 8 $| Korrekturen, neue Herausgeber zuordnen |
| Mehrfachexemplare | Textähnlichkeit | keine | Gruppen bestätigen, Hauptexemplar wählen |
| Themen zuordnen | bge-m3 und BERTopic | wenige Cent | Titel prüfen |

Die Anwendung erstellt mit vergleichsweise minimalem sowohl finanziellem als auch arbeitszeitlichen Aufwand ein leicht nutzbares digitales Korpus der Flugblätter. Auch wenn Fehler an vielen Stellen des Datenverarbeitungsprozesses möglich sind, ist das Korpus überwiegend gut nutzbar, und viele Fehler werden nachträglich kompensiert oder sind leicht erkennbar. Denn auch wenn Fehler im Korpus möglich sind, kann der Nutzer sie erkennen und nachprüfen, wodurch das Risiko einer Falschinformation durch eine gründliche Arbeitsweise während der Auseinandersetzung mit den Flugblättern vermeidbar ist.