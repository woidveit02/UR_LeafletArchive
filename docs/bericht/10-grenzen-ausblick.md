# 10 Grenzen und Ausblick

Die Ergebnisse sind brauchbar, aber an mehreren Stellen unsicher. Wo die Unsicherheit liegt, ist in den Daten markiert. Dieses Kapitel sagt, wofür man den Daten trauen kann und wofür nicht.

## 10.1 Bekannte Fehlerquellen

- Bestand: Einheit 15 fehlt; viele Flugblätter aus 1972/73 zeigen, was überliefert ist, nicht zwingend mehr Publikationen; 1967 und 1968 sind dünn belegt.
- Text: Fehlerrate eher Untergrenze; Handschrift wird oft falsch gelesen; vereinzelt Halluzinationen; gesperrter Text wird Buchstabe für Buchstabe erkannt, was die Suche erschwert.
- Trennung und Mehrfachexemplare: Vorschläge, jede Entscheidung von Hand; die Referenz für die Messung ist nur teilweise geprüft.
- Metadaten: Genauigkeit nicht gemessen; bekannte Fehler wie Eingangsstempel als Erscheinungsdatum; bei 54 % stammt das Jahr nur aus dem Band.
- Themen: Schätzung, 408 unsicher, ein Thema je Flugblatt.
- Quelle: Flugblätter zeigen die Selbstdarstellung der Gruppen, nicht die Ereignisse (Kap. 8.4).
- Betrieb: abhängig von externen Diensten (Datalab, OpenRouter), Läufe nicht exakt wiederholbar; die Anwendung ist ohne Anmeldung auf allen Schnittstellen erreichbar; der Container startet nach einem Neustart nicht von selbst.
- Kein Usability-Test.

## 10.2 Wo Unsicherheit markiert ist

- Unsichere Themen, Belege je Feld, Prüfstatus der Exemplargruppen, von Hand korrigierte Felder.
- Auswertungen zusätzlich auf der geprüften Teilmenge rechnen [aus alter Fassung 9.3].

## 10.3 Datenschutz und Urheberrecht

- Die Flugblätter waren für die Öffentlichkeit bestimmt. Auf ihnen stehen aber Namen von Studierenden, die heute noch leben können.
- Welche Regeln für die Verarbeitung durch externe Dienste und für Auswertungen mit Namen gelten, mit dem Universitätsarchiv klären [offen].
- Zurückhaltung bei Auswertungen, die Personen namentlich zusammenstellen; besser nach Funktionen oder Gruppen.

## 10.4 Ausblick

- Einheit 15 digitalisieren und über den Import einspielen.
- Metadaten an einer Stichprobe messen.
- Fuzzy-Suche in der Oberfläche.
- Export als ALTO in METS (PAGE-XML als Arbeitsformat optional). ALTO ist das übliche Volltextformat in Kitodo, im DFG-Viewer und in der Deutschen Digitalen Bibliothek; die TU Berlin zeigt ihre Flugblätter in Kitodo. Mit dem Export ließe sich der Bestand in solche Portale übernehmen. Einschränkung: Datalab liefert nur Blöcke, keine Zeilen und Wörter, ein ALTO-Export wäre daher gröber als üblich (siehe Wort-Boxen). Welche Plattform das Universitätsarchiv nutzen könnte: [offen].
- Themenlauf mit den Leitlinien im Prompt und Erhalt der geprüften Titel.
- Wort-Boxen bei der Texterkennung.
- Named Entity Recognition: erwähnte Personen und Orte als eigene Felder, mit Belegstelle wie bei den Metadaten. Bisher findet man Namen nur über die Volltextsuche, mit OCR-Fehlern und Schreibvarianten (Obermair, Obermaier). Der Aufwand liegt weniger in der Erkennung als im Zusammenführen der Varianten und in der Messung an einer Stichprobe. Vorher mit dem Universitätsarchiv klären, ob ein Personenregister zulässig ist (10.3), etwa nur für Personen des öffentlichen Lebens. Ein günstiger erster Schritt ist ein Test mit spaCy über alle Flugblätter.
