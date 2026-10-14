# 11 Zusammenfassung

Aus 4 464 gescannten Seiten wurde ein recherchierbarer Bestand mit 1 547 Flugblättern. Automatische Verfahren übernehmen den größten Teil der Arbeit; beim Trennen, bei den Mehrfachexemplaren und bei den Metadaten bleibt eine Prüfung von Hand nötig.

| Schritt | Verfahren | Kosten je 1 000 Seiten | Handarbeit |
|---|---|---|---|
| Text erkennen | Datalab API, Modus accurate | ca. 10 $ | keine |
| Flugblätter trennen | naiver Bayes, Vorschläge | keine | jeden Übergang bestätigen |
| Metadaten erzeugen | Claude Sonnet 4.5, mit Belegen | ca. 8 $ (hochgerechnet) | Korrekturen, neue Herausgeber zuordnen |
| Mehrfachexemplare | Textähnlichkeit | keine | Gruppen bestätigen, Hauptexemplar wählen |
| Themen zuordnen | bge-m3 und BERTopic | wenige Cent je Lauf | Titel prüfen |
| Zusammen | | ca. 18 $ | |

- Je Zeile ein Satz, wofür die Handarbeit nötig ist und wie lange sie dauert [Zeitaufwände offen].
- Für Band 15 mit etwa 200 Seiten wären das rund 4 $.
- Schluss: Die Anwendung erleichtert den Zugang zum Bestand und zeigt zugleich, wo fachliche Prüfung nötig bleibt.

<!-- Listenpreise Stand August 2026. -->
