# 4 Flugblätter trennen

Ein Band ist ein Stapel Seiten ohne markierte Grenzen. Die 14 Bände wurden von Hand in 1 927 Exemplare getrennt. Für neue Bände schlägt die Anwendung Trennungen vor. Etwa drei von vier Vorschlägen stimmen, deshalb bestätigt ein Mensch jeden Übergang.

## 4.1 Aufgabe

In diesem Schritt wird festgelegt, welche Seiten zusammen ein Flugblatt bilden. Davon hängt ab, was später ein Datensatz ist. Die Texterkennung lief vor der Trennung, weil die Hinweise auf den Anfang eines Blatts im Text stehen: Kopfzeilen, Stempel und Datumsangaben.

## 4.2 Herausforderungen

Nicht jedes Flugblatt ist ein einzelnes Blatt. Es gibt mehrseitige Hefte und Anlagen, Rückseiten ohne eigenen Kopf sowie Trennblätter und leere Seiten. In den Bänden von 1973 finden sich zudem wenige auswertbare Kopfzeilen und Stempel. Für die Grenzfälle braucht es feste Regeln. Sie ergaben sich bei der Durchsicht der Grenzen am 29.09.2026:

- Hefte und Dokumentationen bleiben ein Flugblatt, auch wenn einzelne Beiträge eigene Kopfleisten tragen. Ein Beispiel ist das Fachbereichsinfo Nr. 10 in Band 005 mit den Heftseiten 1 bis 25 (S. 444–470).
- Eine Rückseite gehört zum Blatt, auch wenn sie nach einem „b. w.“ einen eigenen Kopf trägt.
- Trägt die Rückseite einen anderen Text mit eigenem Herausgeber, wird sie ein eigenes Flugblatt. So liegen in Band 013 AStA-Infos auf der Rückseite einer Bekanntmachung des Ältestenrats vom 22.06.1973, vermutlich auf schon bedrucktes Papier gedruckt.
- Mehrfachexemplare bleiben eigene Exemplare und werden erst im nächsten Schritt zusammengeführt (Kap. 6).
- Vertauschte Seiten werden nicht umsortiert, sondern im Segment vermerkt.

Für angehängte Resolutionen und für Pressespiegel wurde keine Regel festgelegt.

## 4.3 Verfahren

Die 14 Bände dieses Projekts wurden von Hand mit einem eigenen Werkzeug getrennt, dessen Aufgabe heute Schritt 4 der Anwendung übernimmt. Die Arbeit war auf drei Personen aufgeteilt und im August abgeschlossen. An Band 002 wurde die Trennung von Hand mit der automatischen Segmentierung von Datalab verglichen. Von Hand entstanden 59 Segmente, automatisch 13. Alle 13 automatischen Schnitte stehen auch in der Trennung von Hand, keiner kommt nur automatisch vor. Die automatische Segmentierung setzt also kaum falsche Schnitte, lässt aber die meisten aus: 46 von 59. Sie wurde deshalb nicht verwendet. Keine der beiden Trennungen war zu diesem Zeitpunkt geprüft, der Vergleich zeigt also nur die Art der Abweichung.

Für neue Bände berechnet die Anwendung einen eigenen Vorschlag aus dem erkannten Text (`src/backend/app/boundaries.py`). Sie bewertet jeden Seitenübergang anhand von 14 Merkmalen und verrechnet sie mit einem naiven Bayes-Klassifikator. Die Gewichte wurden an den Bänden 1–14 gelernt, eine Trennung wird ab einer Wahrscheinlichkeit von 0,5 vorgeschlagen. Das Verfahren läuft lokal und braucht kein Sprachmodell.

Für den Anfang eines neuen Blatts sprechen ein Eingangsstempel, ein Datum in der Kopfzeile, eine Kopfleiste mit Gruppenkürzeln, ein Impressum oder eine fast leere Seite davor und wenige gemeinsame Wörter mit der vorigen Seite. Dagegen sprechen eine Seitenzahl wie „- 2 -“, ein Trennstrich oder „b. w.“ am Ende der vorigen Seite, „Fortsetzung“ am Seitenanfang und viele gemeinsame Wörter.

Für die Bände 13 und 14 kommt eine Locherkennung hinzu. Sind die Abheftlöcher nur rechts zu sehen, ist die Seite eine Rückseite und beginnt kein neues Flugblatt. Alternativ lässt sich eine Liste übernehmen, die beim Scannen notiert wurde.

## 4.4 Qualität

Gemessen wurde so, wie es bei einem neuen Band wäre: Jeder Band wurde mit Gewichten geprüft, die nur aus den übrigen 13 Bänden gelernt waren. Statt 1 986 Trennungen von Hand bleiben dann 904 Korrekturen, 54 % weniger. Die Präzision liegt bei 0,73, etwa jeder vierte Vorschlag ist also falsch. Die Trefferquote liegt bei 0,84, etwa jede sechste echte Trennung fehlt. Mit der Locherkennung sinken die Korrekturen auf den Bänden 13 und 14 von 163 auf 120.

Zusätzlich wurde ein Teil von Band 14 ab Seite 449 als neuer Band importiert. Von 50 Übergängen mussten 13 korrigiert werden: 11 Trennungen fehlten, 2 waren zu viel.

Die Messung hat Grenzen. Die Referenz, also die Trennung der Bände 1–14, ist selbst nur teilweise geprüft. Ob zusätzlich gegen die Archivtitel 1968/69 geprüft wurde, ist offen (siehe 5.4).

## 4.5 Manuelle Prüfung

In der Anwendung wird jeder Übergang bestätigt oder geändert. Dazu zeigt sie zwei benachbarte Seiten groß nebeneinander, mit Tasten zum Trennen und Zusammenfügen. Wie lange das Trennen der 14 Bände gedauert hat, ist noch offen [offen].

## 4.6 Ergebnis und Kosten

Die 4 464 Seiten ergeben 1 927 Exemplare. 115 Seiten gehören zu keinem Flugblatt: 102 davon haben keinen Text, 8 wenig Text und 5 echten Text; diese fünf sollten noch geprüft werden. Kosten entstehen keine, weil das Verfahren lokal läuft.

![Bandansicht der Anwendung um Seite 394 von Band 006](../abbildungen/app_band.png)

*Abbildung: Ergebnis der Trennung in der Bandansicht (Band 006, S. 392–397). Jede Spalte ist ein Flugblatt; Flugblatt 850 („Zur Fachschaftssatzung“, S. 394) ist markiert. Leere Rückseiten sind ausgeschlossen, S. 392 und 396–397 sind weitere Exemplare; ihr Hauptexemplar liegt in Band 008 bzw. weiter vorn in Band 006.*

## 4.7 Hinweise zur Weiterentwicklung

Der Code liegt in `src/backend/app/boundaries.py` und `src/backend/app/segments.py`. Wächst der Bestand deutlich, sollten die Gewichte neu gelernt werden; das übernimmt `scripts/learn_boundary_weights.py`. Rückseiten bleiben die größte Schwäche des Verfahrens.
