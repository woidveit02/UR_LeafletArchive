# 9 Die Anwendung

Am Ende des Projekts steht eine Webanwendung, mit der sich das Korpus durchsuchen, lesen, auswerten und pflegen lässt und mit der das Archiv neue Bände selbst einlesen kann. Sie läuft lokal in Docker und braucht Internetzugang nur für die Texterkennung und die Metadaten neuer Bände und für die Themen. Die Bedienung beschreiben die Handbücher [Recherche](../handbuch/recherchieren.md), [Pflege](../handbuch/pflegen.md) und [Import neuer Bände](../handbuch/neue-baende-importieren.md).

## 9.1 Anforderungen

Aus den Zielen in Kap. 1.2 folgen drei Anforderungen. Für die Recherche muss das Korpus über eine Oberfläche durchsuchbar sein, die ohne technische Kenntnisse bedienbar ist. Zum Fortführen müssen sich neue Bände einpflegen lassen, ohne dass dafür jemand aus dem Projekt nötig ist; danach fragten auch die Betreuenden bei der Vorführung am 07.10.2026 (Kap. 12.4). Die dritte, alles nachprüfbar zu machen, ergibt sich auch aus den Verfahren: Text, Trennung und Metadaten entstehen größtenteils automatisch und sind nicht fehlerfrei (Kap. 10). Jede Angabe soll sich deshalb am Scan prüfen und von Hand korrigieren lassen, und Korrekturen dürfen nicht verloren gehen, wenn Daten neu erzeugt werden.

## 9.2 Recherchieren

Einstieg in die Recherche ist die Flugblattliste. Ein Suchfeld durchsucht Titel, Reihe, Herausgeber, Unterzeichnende und den erkannten Text. Die Suche findet auch Wortteile und alte Schreibweisen (daß und dass), und über weitere Suchbedingungen lassen sich Felder mit UND, ODER und NICHT verknüpfen. Links stehen Filter nach Jahr, Herausgeber, Thema und Textsorte. Die Zahlen an den Filtern beziehen sich immer auf die aktuelle Trefferliste, sodass man sieht, wie sich ein Begriff über Jahre und Gruppen verteilt, bevor man ein einziges Flugblatt öffnet.

![Flugblattliste mit der Suche nach „berufsverbot“](../abbildungen/nutzen_suche.png)

*Abbildung: Die Suche nach „berufsverbot“ ergibt 129 Treffer, fast alle aus 1972 und 1973. Die Filter links zählen die Treffer je Jahr, Herausgeber und Thema; jeder Treffer zeigt die Fundstellen im Text.*

Die Leseansicht eines Flugblatts zeigt den Scan und den erkannten Text nebeneinander, Block für Block verbunden: Zeigt man auf einen Absatz, leuchtet er in Text und Scan zugleich auf, und ein Klick in den Scan springt zur Stelle im Text. Darüber stehen die Metadaten. Neben jedem Wert führt „Beleg“ zu der Stelle im Scan, aus der er stammt. Wie diese Belege entstehen, beschreibt Kap. 5. In der Anwendung machen sie jede Angabe in einem Klick überprüfbar. Unsichere Werte sind als solche gekennzeichnet, etwa ein Datum ohne Jahr oder ein automatisch zugeordnetes Thema.

![Leseansicht von Flugblatt 850](../abbildungen/app_leseansicht.png)

*Abbildung: Leseansicht von Flugblatt 850. Oben die Metadaten mit Links zum Beleg, darunter der erkannte Text neben dem Scan. Rechts stehen Modell und Datum von Texterkennung und Metadaten.*

Über einzelne Flugblätter hinaus führen drei weitere Zugänge zu Fragen über das ganze Korpus. Die Seiten der Herausgeber und Bände zeigen, wann eine Gruppe aktiv war und was ein Band enthält. Die Themenkarte ordnet die Flugblätter nach Ähnlichkeit ihrer Texte (Kap. 7). Die Trends zeigen für bis zu vier Begriffe, welcher Anteil der Flugblätter eines Jahres oder Semesters sie enthält. Gezählt werden Flugblätter, nicht Wörter, und Mehrfachexemplare nur einmal, damit ein langes Papier oder ein oft gesammeltes Flugblatt das Bild nicht verzerrt. Unter jedem Jahr steht die Zahl der Flugblätter, auf die sich der Anteil bezieht.

![Trends für Notstand, Berufsverbot und Numerus](../abbildungen/nutzen_trends.png)

*Abbildung: Trends für „Notstand“, „Berufsverbot“ und „Numerus“. Die Notstandsgesetze prägen 1967/68, die Berufsverbote 1972 und 1973. Die dünn belegten ersten Jahre sind zusammengefasst.*

## 9.3 Pflegen

Fehler lassen sich dort beheben, wo man sie findet. „Metadaten korrigieren“ auf der Seite eines Flugblatts öffnet ein Formular, in dem zu jedem Wert auch der Beleg neu gewählt werden kann, indem man Blöcke im Scan anklickt. Korrigierte Felder sind danach als „von Hand korrigiert“ gekennzeichnet, der automatisch erkannte Wert lässt sich wiederherstellen.

![Formular „Metadaten korrigieren“ für Flugblatt 850](../abbildungen/nutzen_korrigieren.png)

*Abbildung: Metadaten korrigieren, am Beispiel von Flugblatt 850. Zu jedem Wert gehört ein Beleg, der sich über „Beleg wählen“ im Scan neu setzen lässt.*

Mehrfachexemplare prüft man in einer Ansicht, die die Exemplare einer Gruppe nebeneinander zeigt (Kap. 6.5). Dort wählt man das Hauptexemplar, nimmt Exemplare heraus, die nicht dazugehören, und korrigiert die gemeinsamen Metadaten einmal für alle. Herausgeber, die das Register noch nicht kennt, ordnet man unter Verwaltung › Herausgeber zuordnen einer Organisation zu oder legt sie neu an. Die Anwendung merkt sich die Schreibweise und erkennt sie in späteren Bänden.

Damit keine Handarbeit verloren geht, speichert die Anwendung Korrekturen und Prüfentscheidungen außer in der Datenbank auch in Dateien, an die sie nur anhängt. Beim Neuaufbau der Datenbank werden sie wieder angewendet. Sie hängen an den Seiten eines Flugblatts: Wird ein Band neu getrennt und passt eine Korrektur nicht mehr, erscheint sie unter Verwaltung › Korrekturen, statt stillschweigend zu verschwinden. Für Auswertungen außerhalb lässt sich der Bestand als ZIP mit Volltexten und Tabellen exportieren.

## 9.4 Import neuer Bände

Ein neuer Band kommt in sechs Schritten in die Anwendung: Band wählen, Scans hochladen, Text erkennen, Flugblätter trennen, Metadaten erzeugen, prüfen und freigeben. Die Schritte führen nacheinander durch die Verfahren aus Kap. 3 bis 6. Danach lassen sich die neuen Flugblätter den bestehenden Themen zuordnen.

Damit Anwenderinnen und Anwender ohne technische Kenntnisse damit zurechtkommen, haben wir drei Entscheidungen getroffen. Erstens ist ein Band bis zur Freigabe ein Entwurf: Er fehlt in Liste, Suche und Trends, sodass Zwischenstände den Bestand nicht verfälschen. Zweitens speichert jeder Schritt sein Ergebnis; ein abgebrochener Import lässt sich später fortsetzen, und vor den kostenpflichtigen Schritten nennt die Anwendung den geschätzten Preis. Drittens bündelt Schritt 6 alles, was ein Mensch ansehen sollte, in drei Aufgaben: Mehrfachexemplare, unbekannte Herausgeber und Hinweise, wo die Metadaten nicht zum erkannten Text passen. Jede Aufgabe führt direkt zu den betroffenen Flugblättern.

![Schritt 6 des Imports](../abbildungen/import_pruefen.png)

*Abbildung: Schritt 6 beim Testimport. Jede der drei Aufgaben nennt die Zahl offener Fälle und führt zu ihnen; freigeben lässt sich der Band auch, wenn noch etwas offen ist.*

Die meiste Zeit kostet das Prüfen der Seitenwechsel beim Trennen; Texterkennung und Metadaten brauchen nur einige Minuten Wartezeit. Vorgeführt haben wir den Import im Archiv (Kap. 9.8).

## 9.5 Architektur und Datenmodell

Die Anwendung ist mit FastAPI, Jinja2 und SQLAlchemy gebaut und speichert in SQLite. Die Grundstruktur stammt aus dem ASE-Projekt im Wintersemester 2025/26; deshalb fiel die Wahl auf diese Systeme. Die Seiten werden auf dem Server erzeugt. JavaScript ohne Framework und ohne Build-Schritt ergänzt einzelne Ansichten wie die Trennansicht. Die Datenbank enthält Bände, Seiten, Flugblätter, Organisationen, Herausgeber-Zuordnungen und Themen, dazu einen Volltextindex (SQLite FTS5). Seiten und Flugblätter sind getrennt gespeichert, deshalb lässt sich ein Band neu trennen, ohne den Text neu zu erkennen. Die Datenbank lässt sich jederzeit aus den Dateien in `data/` und im Scan-Ordner neu aufbauen. Einzelheiten für die Weiterentwicklung stehen in [Weiterentwicklung](../handbuch/weiterentwickeln.md).

## 9.6 Gestaltung

Die Oberfläche folgt wenigen Regeln: wenig Farbe, Markierungen nur für das, was Aufmerksamkeit braucht, und Zahlen, die mit den Listen dahinter übereinstimmen.

## 9.7 Werkzeuge außerhalb der Anwendung

Für Auswertungen, die über die Anwendung hinausgehen, gibt es zwei Werkzeuge. `scripts/ngrams.py` berechnet auf den erkannten Texten Häufigkeiten, Trends, typische Wörter je Jahr, Kollokationen und Belegstellen ([Textauswertung](../handbuch/ngramme-auswerten.md)). Das Notebook `scripts/forschungsfragen.ipynb` ([als Webseite](../forschungsfragen.html)) zeigt am Export, wie sich Fragen wie „Welche Gruppen sind wann aktiv?“, „Wer gibt mit wem gemeinsam heraus?“ oder „Wie unterscheidet sich das Vokabular von RCDS und sozialistischen Gruppen?“ [@monroe2008] beantworten lassen. Die zehn Fragen im Notebook sind Beispiele, keine Ergebnisse des Projekts. Weitere Skripte, etwa zum Zusammenfügen von TIFF-Scans und zum Neulernen der Gewichte des Trennvorschlags, beschreibt `scripts/README.md`.

Warum eigene Auswertungen hinter der Erschließung zurückstanden, erklärt Kap. 1.2. Die Werkzeuge zeigen, dass das Korpus solche Auswertungen trägt.

## 9.8 Einsatz im Archiv

Für das Universitätsarchiv, unseren Kooperationspartner, ist die Anwendung ein Werkzeug für die weitere Erschließung des Bestands. Das Archiv wollte vor allem zweierlei: im Korpus recherchieren und neu gescannte Bände selbst einlesen, ohne dass dafür jemand aus dem Projekt nötig ist. Daraus stammen die Anforderungen in 9.1 und der Aufbau des Imports in 9.4.

Am 20.10.2026 haben wir die Anwendung im Archiv vorgeführt und dabei den ersten Teil von Band 15 eingelesen (230 Seiten), den das Archiv inzwischen gescannt hat (Kap. 2.5). [offen: Rückmeldung des Archivs: was gefragt wurde, was gut ankam, was danach geändert wurde.]

Für den dauerhaften Betrieb haben wir mit dem Archiv verabredet, dass das Rechenzentrum der Universität die Anwendung als Docker-Container betreibt, wie andere Software des Archivs auch. [offen: Datum der Verabredung.] Dafür sind noch drei Fragen zu klären [offen: prüfen, was davon schon geklärt ist].

Die erste betrifft den Zugriff. Die Anwendung hat keine eigene Anmeldung. Bevor sie im Netz der Universität erreichbar ist, braucht sie einen Zugriffsschutz, etwa ein Passwort über einen vorgeschalteten Webserver; die Einrichtung beschreibt das Handbuch [Installation und Betrieb](../handbuch/installieren-und-betreiben.md#auf-einem-server-des-archivs). Wer Zugang bekommt und wie mit Personennamen umzugehen ist, entscheidet das Archiv (Kap. 10.3).

Die zweite betrifft Konten und Kosten. Für neue Bände braucht die Anwendung API-Keys für Datalab und OpenRouter, und offen ist, auf wessen Konto sie laufen. Ein Band mit 300 Seiten kostet etwa 6 $ ([Kosten](../handbuch/neue-baende-importieren.md#kosten)).

Die dritte betrifft Sicherung und Betreuung. Welche Dateien zu sichern sind, steht im Handbuch; wer Updates einspielt und bei Fehlern hilft, ist noch festzulegen.
