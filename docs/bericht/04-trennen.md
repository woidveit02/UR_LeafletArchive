# 4 Flugblätter trennen

Ein Band unseres Gesamtbestandes umfasst eine Menge an Einzelseiten, deren Zugehörigkeit zu einem bestimmten Flugblatt nicht direkt vermerkt ist. Da Flugblätter sowohl aus einer einzelnen als auch aus mehreren Seiten bestehen können, ist es wichtig, die Übergänge zwischen zwei Blättern klar zu kennzeichnen. Deshalb werden die Seiten eines jeden Bandes in einzelne Flugblätter unterteilt, woraus eine Gesamtzahl von 1927 Exemplaren für den gesamten Bestand resultiert. Dieser Prozess ist auch beim Importieren neuer Bände innerhalb der Anwendung notwendig. Hier sollen Vorschläge für Trennungen dem Nutzer helfen und diesen Arbeitsschritt beschleunigen. Etwa drei von vier dieser Vorschläge können korrekt übernommen werden, weshalb eine manuelle Bestätigung notwednig ist.

## 4.1 Aufgabe

In diesem Schritt wird festgelegt, welche Bandseiten gemeinsam ein einzelnes Flugblatt bilden. Diese Bestimmung legt fest, welche Einzelseiten ein durchsuchbares Flugblattobjekt bilden. Die Texterkennung erfolgt bereits vor der Seitentrennung, da wichtige Hinweise auf den Beginn eines neuen Flugblatts, wie Kopfzeilen, Stempel oder auch Datumsangaben aus dem Text gewonnen werden. Diese Merkmale bilden zudem eine wichtige Grundlage für die automatisiert generierten Vorschläge für Trennungen während des Imports.

## 4.2 Herausforderungen

Start- und Enseite einzelner Flugblätter sind nicht immer eindeutig erkennbar. Grenzfälle, wie Hefte und Anlagen, Rückseiten ohne eigenen Kopf sowie Trennblätter sind Beispiele für entstehende Herausforderungen beim Abgrenzen der Exemplare. Insbesondere in den Bänden des Jahrgangs 1973 sind zudem nur wenige aussagekräftige Kopfzeilen und Stempel vorhanden, die zur Identifikation von Trennstellen herangezogen werden können. Daher müssen für uneindeutige Fälle einheitliche Regeln festgelegt werden, um eine Trennung des Bestandes so neutral und konsisten wie möglich zu gestalten.

Folgende Regeln ergaben sich während der manuellen Abgrenzung der Flugblattseiten am 29.09.2026:

- Zusammengehörige Hefte und Dokumentationen bleiben ein Flugblatt, auch wenn einzelne Beiträge eigene Kopfzeilen aufweisen. Ein Beispiel hierfür ist das *Fachbereichsinfo Nr. 10* in Band 005 mit den Heftseiten 1 bis 25 (S. 444–470).
- Eine Rückseite wird einem offensichtlich zugehörigen Flugblatt zugeordnet, auch wenn sie nach einem „b. w.“ ("bitte wenden") eine eigene Kopfzeile aufweist.
- Trägt eine Rückseite einen eigenständigen Text mit eigenem anderen Herausgeber als die Vorderseite, wird sie ein als separates Flugblatt gekennzeichnet. So befinden sich beispielsweise in Band 013 AStA-Informationen auf der Rückseite einer Bekanntmachung des Ältestenrats vom 22.06.1973.
- Mehrfachexemplare werden zunächst als separate Exemplare behandelt und erst im nächsten Schritt zusammengeführt (siehe Kap. 6).
- Seiten, die innerhalb eines Flugblattes eine falsche Reihenfolge aufweisen, werden in diesem Schritt nicht direkt umsortiert. Stattdessen wird der Fehler im jeweiligen Segment vermerkt.

Für angehängte Resolutionen und Pressespiegel wurden bislang keine eindeutigen Regeln festgelegt.

## 4.3 Verfahren

Die 14 Bände dieses Projekts wurden mithilfe des Werkzeugs `flugblatt_splitter` manuell abgegrenzt. Die Arbeit wurde gleichmäßig auf drei Personen verteilt und im August abgeschlossen. Für Band 002 wurde die manuelle Trennung mit einer automatischen Segmentierung durch Datalab verglichen. Während bei der händischen Trennung 59 Segmente entstanden, erkannte Datalab lediglich 13 einzelne Flugblätter. Dabei wurden alle 13 automatischen Segmentierungen auch manuell vorgenommen. Es wurden demnach keine Schnitte durch Datalab gesetzt, die zuvor nicht auch händisch festgelegt wurden. 46 der 59 manuellen Segmentierungen wurden jedoch von Datalab übersehen. Da keine der beiden Trennungen zu diesem Zeitpunkt qualitativ überprüft worden war, konnte aus diesem Schritt lediglich abgeleitet werden, inwiefern sich die Entscheidungen unterschieden. Dennoch wurde eine Vollautomatisierung aufgrund dieser Beobachtungen für weitere Segmentierungen ausgeschlossen.

Für den Import neuer Bände werden gestützt auf den erkennten Text (`src/backend/app/boundaries.py`) Vorschläge zur Segmentierung bereitgestellt. Jeder Seitenübergang wird hierbei anhand von 14 Merkmalen bewertet und einem naiven Bayes-Klassifikator verrechnet. Die zugrundeliegenden Gewichte wurden mithilfe der manuellen Segmentierung der Bände 1–14 erarbeitet. Demnach wird eine Trennung ab einer Wahrscheinlichkeit von 0,5 vorgeschlagen. Dieses Verfahren läuft lokal und ohne Zuhilfenahme eines Sprachmodells.

Als Hinweise auf den Beginn eines neuen Flugblatts dienen beispielsweise Eingangsstempel, Datumsangaben in der Kopfzeile, eine Kopfleiste mit Gruppenkürzeln und Impressen sowie eine nahezu leere vorausgehende Seite oder auch eine geringe Anzahl gemeinsamer Wörter mit der vorangegangenen Seite. Gegen eine neue Trennstelle sprechen beispielsweise Seitenzahlen wie „- 2 -“, Trennstriche oder ein „b. w.“ am Ende der vorherigen Seite. Auch wörtliche Hinweise, wie „Fortsetzung“ am Seitenanfang sowie eine große Anzahl gemeinsamer Wörter zwischen zwei aufeinanderfolgenden Seiten deuten auf ein fortlaufendes Flugblatt hin.

Für die Bände 13 und 14 wurde zusätzlich eine Locherkennung eingeführt. Sind die Abheftlöcher nur auf der rechten Seite erkennbar, wir die Seite als Rückseite eingeordnet und demnach kein Beginn eines neuen Flugblattes vermutet. 

Um den Sektionierungsvorgang zu beschleunigen, wird zusätzlich die Möglichkeit geboten, eine vorannotierte Liste während des Imports zu übergeben, welche sämtliche dokumentierte Trennstellen beinhaltet. Dadurch kann die Sektionierung sofort automaisch durchgeführt werden und eine nachträgliche manuelle Trennung kann umgangen werden. 

*TODO: Beispielbild einer Liste oder Feature hinzufügen*

## 4.4 Qualität

Um die Qualität der Vorschläge zu messen, wurde eine Simulation angestellt, wobei jeder einzelne Band mit Gewichten ausgewertet wurde, die anhand der übrigen 13 Bände erlernt wurden. Das Ergbnis zeigte, dass anstelle von ursprünglich 1 986 notwendigen Trennungen nunmehr 904 manuelle Korrekturen vorgenommen werden mussten, um den Bestand korrekt zu separieren. Dies stellt eine Reduktion des Korrekturaufwands um rund 54% dar.

Die Präzision der Trennsvorschläge entspricht laut unseres Tests 0,73. Somit ist etwa jeder vierte vorgeschlagene Schnitt fehlerhaft. Die Trefferquote konnte auf 0,84 beziffert werden, wonach ungefähr jede sechste manuell Vorgenommene Trennstelle nicht Teil der automatisierten Vorschläge war. Die zusätzliche Locherkennung konnte die Anzahl erforderlicher Korrekturen in den Bänden 13 und 14 von insgesamt 163 auf nur noch 120 reduzieren. 

Als weiterer Teil der Qualitätsübeprüfung wurde ein Teil des 14. Bandes ab Seite 449 testweise neu importiert. Von 50 untersuchten Seitenübergängen mussten 13 korrigiert werden, während elf erforderliche Trennstellen zu viel vorgeschlagen wurden.

Die genannten Ergebnisse sind nur eingeschränkt aussagekräftig. Die manuelle Trennung der Bände 1 bis 14, die bei diesen Tests als "Goldstandard" fungiert wurde bislang selbst nur teilweise validiert. Somit besteht die Möglichkeit eigener Fehler, welche die Bewertung der automatisierten Vorschläge verfälschen können. 

## 4.5 Manuelle Prüfung

In der Anwendung soll jeder Seitenübergang manuell geprüft werden. Hierbei soll die vorgeschlagene Aktion ("trennen" oder "nicht trennen") ausgewählt werden. Zwei aufeinanderfolgende Bandseiten werden hierbei nebeneinander visualisiert. Über entsprechende Schaltflächen bzw. Tastenkürzel kann bestimmt werden, ob eine Trennung zwischen diesen beiden Elementen erfolgen soll. Eine manuelle Trennung mithilfe automatisiserter Vorschläge konnte bei eigens durchgeführten Tests in der Regel innerhalb von 3 - 10 Sekunden erfolgen.

## 4.6 Ergebnis und Kosten

Die 4 464 Seiten des Gesamtbestandes wurden in 1 927 eigenständige Flugblattexemplare unterteilt. Hinzu kommen 115 Seiten, die keinem Flugblatt zugeordnet werden konnten. Hierbei handelt es sich in der Regel um Trennblätter oder leere Rückseiten. Fünf dieser Seiten wiesen dennoch potenziell relevanten Text auf und sollten daher nochmals überprüft werden.

Aufgrund der vollständig lokalen Verarbeitung entstehen für diesen Arbeitsschritt keine zusätzlichen Kosten für externe Dienste oder cloudbasierte Sprachmodelle innerhalb der Anwendung.

![Bandansicht der Anwendung um Seite 394 von Band 006](../abbildungen/app_band.png)

*Abbildung: Ergebnis der Trennung in der Bandansicht (Band 006, S. 392–397). Jede Spalte ist ein Flugblatt; Flugblatt 850 („Zur Fachschaftssatzung“, S. 394) ist markiert. Leere Rückseiten sind ausgeschlossen, S. 392 und 396–397 sind weitere Exemplare; ihr Hauptexemplar liegt in Band 008 bzw. weiter vorn in Band 006.*

## 4.7 Hinweise zur Weiterentwicklung

Die Implementierung der Trennvorschläge befindet sich in src/backend/app/boundaries.py und src/backend/app/segments.py. Die Herkunft der verwendeten Merkmale und Gewichte ist im Arbeits-Repository unter pipelines/01_pdf/ auffindbar. 

Bei einer wesentlichen Erweiterung des Bestandes sollte vor dem Import geprüft werden, ob eine wiederholte Anpassung der Gewichte erfoderlich sein könnte. Als besondere Herausfoderung für eine Weiterentwicklung erweist sich die zuverlässige Erkennung von Rückseiten. Diese weisen oftmals keinerlei eindeuiger Merkmale auf, die auf das Ende bzw. einen Anfang eines Flugblattes hindeuten.
