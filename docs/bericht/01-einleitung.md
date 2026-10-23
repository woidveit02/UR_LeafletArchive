# 1 Einleitung

Das Universitätsarchiv Regensburg bewahrt in seiner Allgemeinen Flugblattsammlung die Flugblätter, die an der jungen Universität zwischen 1967 und 1973 verteilt wurden. Bis zu diesem Projekt lagen davon nur Fotos vor, ohne Volltext, ohne Grenzen zwischen den Flugblättern und ohne Angaben zu Titel, Datum oder Herausgeber. Wir haben daraus ein durchsuchbares Korpus mit 1547 Flugblättern gemacht und eine Anwendung gebaut, mit der das Archiv weitere Bände selbst erschließen kann.

## 1.1 Motivation und Ausgangslage

Die Allgemeine Flugblattsammlung (Rep. 118) enthält, was Studierende, Hochschulgruppen, Parteien, Unternehmen und andere Akteure selbst geschrieben, vervielfältigt und verteilt haben: Aufrufe zu Streiks und Vollversammlungen, Wahlprogramme, Stellungnahmen, Satire, Werbung und Einladungen.

Warum diese Jahre ergiebig sind, zeigt die Geschichte der Universität. Der Vorlesungsbetrieb begann am 06.11.1967. Harte Auseinandersetzungen wie an anderen Universitäten um 1968 gab es zunächst nicht. Scharfe Proteste mit Massendemonstrationen setzten erst ein, als bekannt wurde, dass der Freistaat mit dem neuen Bayerischen Hochschulgesetz (BHG) die Drittelparität in den Gremien und die verfasste Studierendenschaft abschaffen wollte. Andreas Becker nennt die Jahre 1971 bis 1973 in seinem Lexikonartikel „die eigentlich revolutionäre Zeit“ der Universität, auch wegen der Wahl des Physikers Gustav Obermair zum Rektor, der damals als Marxist verschrien war [@becker2021]. Das Hochschulgesetz ist deshalb eines der häufigsten Themen der Flugblätter.

Darüber hinaus zeigt die Sammlung die Anfänge noch heute bestehender Hochschulgruppen, das beginnende Nachtleben der Studentenstadt, das politische Engagement später bekannter Personen und die Sprache der Studierenden jener Jahre.

Genutzt werden konnte das bisher kaum. Im Herbst 2025 begann das Archiv, die Flugblätter zu digitalisieren; bis zum Beginn des Projekts im Sommer 2026 waren 4464 Seiten fotografiert. Wer etwa wissen wollte, welche Gruppen sich zum Hochschulgesetz äußerten, musste die Bände Seite für Seite durchsehen. In der Anwendung liefert eine Suche danach in wenigen Sekunden 310 Flugblätter von 67 Herausgebern.

Andere Universitäten haben ihre Flugblätter aus dieser Zeit ebenfalls digitalisiert. Die TU Berlin zeigt rund 1800 Flugblätter der Jahre 1965 bis 1972 in Kitodo, mit Volltextsuche [@tub-flugblaetter]. In Frankfurt verzeichnet eine private Sammlung 403 Flugblätter von 1967 bis 1969 von Hand nach Datum, Urheber, Thema und Art [@frankfurt-flugblaetter]. Die Sammlung der Universität Hamburg mit über zehntausend Flugblättern ist nach Anton F. Guhl und Alexandra Jaeger kaum erschlossen [@hamburg-flugblaetter]. Eine Flugblattsammlung einer deutschen Universität, die ähnlich automatisch erschlossen wird und die das Archiv selbst fortführen kann, ist uns nicht bekannt (Stand Oktober 2026).

Guhl und Jaeger nennen für die Hamburger Sammlung drei Hürden, die auch in Regensburg bestehen:

| Hürde nach Guhl und Jaeger | Arbeitsschritt | Stand in Regensburg |
|---|---|---|
| Dubletten machen die Zahl der Flugblätter unsicher | Mehrfachexemplare zusammenführen (Kap. 6) | 1927 Exemplare ergeben 1547 Flugblätter |
| Viele Blätter nennen keine Verantwortlichen | Herausgeber mit Beleg und Register (Kap. 5) | 241 Flugblätter bleiben ohne erkannten Herausgeber |
| Ohne Parallelüberlieferung ist das Datieren schwer | Datum mit Beleg, sonst Jahr des Bandes (Kap. 5) | 46 % tragen ein Datum auf dem Blatt |

Die meisten dieser Schritte laufen automatisch (Kap. 3 bis 7). Die Texterkennung (OCR, optische Zeichenerkennung) macht aus den Fotos Text, ein Sprachmodell liest daraus die Metadaten und nennt für jeden Wert die Textstelle, auf die er sich stützt; so lässt sich jede Angabe am Scan nachprüfen. Von Hand bestätigen wir die Grenzen zwischen den Flugblättern, unterstützt durch Vorschläge der Anwendung, und die Gruppen von Mehrfachexemplaren. Texterkennung und Metadaten kosten zusammen etwa 19 $ je 1000 Seiten (Kap. 11), und neue Bände liest das Archiv in der Anwendung selbst ein (Kap. 9).

![Der Weg von Flugblatt 850 durch die Arbeitsschritte](../abbildungen/ablauf.png)

*Abbildung: Der Weg eines Flugblatts durch die Arbeitsschritte, am Beispiel von Flugblatt 850 („Zur Fachschaftssatzung“, Band 006, S. 394). Trennen und Mehrfachexemplare sind Vorschläge, die von Hand geprüft werden; Herausgeber zuordnen und Metadaten korrigieren geschehen von Hand, die übrigen Schritte laufen automatisch.*

## 1.2 Ziele

Wir wollten aus den Scans der Bände 1 bis 14 ein Korpus machen, das sich durchsuchen und auswerten lässt und das das Archiv selbst fortführen kann. Daraus ergeben sich vier Ziele, an denen Kap. 11 das Ergebnis misst:

| Ziel | Erreicht, wenn |
|---|---|
| Erschließen | jede Seite hat Volltext mit gemessener Fehlerrate, jedes Flugblatt hat Grenzen und Metadaten |
| Nachprüfbar machen | jede automatische Angabe hat einen Beleg im Scan und lässt sich korrigieren, ohne dass Korrekturen bei einer Neuberechnung verloren gehen |
| Recherche ohne Technikwissen | Suche, Filter, Leseansicht, Trends und Themen stehen in einer Weboberfläche |
| Fortführen | ein neuer Band lässt sich ohne Projektmitglied einlesen, die Kosten sind vorher bekannt |

Der Schwerpunkt lag damit auf der Erschließung. Eigene Auswertungen zur politischen Kommunikation, die die Themenstellung ebenfalls nennt, haben wir dafür zurückgestellt. Sie werden umso aussagekräftiger, je mehr Jahrgänge das Archiv scannt und mit der Anwendung erschließt; die Werkzeuge dafür liegen bereit (Kap. 9.7).

## 1.3 Projekt und Aufbau des Berichts

Das Projekt entstand im Praxisseminar des Masterstudiengangs Medieninformatik an der Universität Regensburg im Sommersemester 2026, in Zusammenarbeit mit dem Universitätsarchiv (Dr. Andreas Becker). Die Themenstellung lautete „Politik und Kommunikation – die Flugblattsammlung der Universität Regensburg“ und umfasste Digitalisierung und Erschließung, den Aufbau einer Oberfläche und die Analyse mit KI-Werkzeugen.

Der Bericht folgt einem Band durch die Verarbeitung. Kap. 2 beschreibt den Bestand, Kap. 3 bis 7 die Schritte Texterkennung, Trennen, Metadaten, Mehrfachexemplare und Themen. Kap. 8 fasst das Korpus in Zahlen, Kap. 9 beschreibt die Anwendung, Kap. 10 Grenzen und Ausblick, Kap. 11 fasst zusammen. Team, Organisation, Verlauf und Entscheidungen stehen in Kap. 12.
