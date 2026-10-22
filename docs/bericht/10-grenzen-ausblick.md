# 10 Grenzen und Ausblick

Im Verlauf der bisherigen Ausführungen wurde bereits mehrmals auf mögliche Grenzen, Probleme oder Fehler eingegangen. Im Folgenden soll erneut eine Übersicht über solche Problemstellungen gegeben werden. 

## 10.1 Bekannte Fehlerquellen

- Text: Die ermittelte Fehlerrate repräsentiert aufgrund der Evaluationstechnik eher eine Untergrenze, zudem wird Handschrift noch oft falsch erfasst. Das OCr-System tendiert ausserdem selten zum Halluzinieren. Zudem ist die falsche Erkennung von Sperrtext ein potentielles Hindernis für die Volltextsuche. 
- Trennung und Mehrfachexemplare: Die Automatische Trennung der PDFs in einzelne Flugblätter erfolgt aktuell noch unzureichend, sodass manuelles Überprüfen und Trennen unumgänglich ist, da die Ergebnisse sonst praktisch nicht nutzbar sind und in den folgenden Datenverarbeitungsprozessen zu teils größeren Fehlern führen können.
- Metadaten: Die Genauigkeit der automatischen Metadaten-Generierung wurde nicht evaluiert. Es gibt einige potentielle Problemquellen wo Daten misinterpretiert werden können, wie beispielsweise die Erkennung des Eingangsstempels als Erscheinungsdatum. Zudem konnten bei vielen Flugblättern manche Metadaten gar nicht ermittelt werden. 
- Themen: Momentan wird jedem Flugblatt nur ein Thema zugeordnet, manche Flugblätter besitzen aber mehrere Themen. Zudem ist die aktuelle Festlegung auf 40 Themen nur eine persönliche Schätzung.
- Betrieb: Das System ist aktuell abhängig von externen Diensten (Datalab, OpenRouter) und dessen Läufe sind nicht exakt wiederholbar. Die Anwendung hat keine Anmeldung und ist deshalb standardmäßig nur auf dem eigenen Rechner erreichbar (Freigabe im Netz: `handbuch/betrieb.md`).
- Tests: Insgesamt wurden viele Aspekte des Systems nicht systematisch getestet sondern basieren auf Einschätzung, Erfahrung oder inkrementeller Verbesserung. Beispielsweise wurde das User Interface auch keinem Nutzertest unterzogen, wodurch Usability-Probleme nicht ausgeshclossen werden können.

Neben technischen Fehlerquellen ergeben sich aus dem Korpus beziehungsweise dem Quellmaterial zudem noch thematische und Korpus-bezogene Fehlerquellen:

- Bestand/Korpus: Im Korpus fehlen noch mehrere Bände des Jahres 1973, wodurch noch keine repräsentativen Aussagen über dieses Jahr getroffen werden kann. Zudem sind die Jahre 1967 und 1968 aufgrund einer sehr geringen Zahl an Flugblätter nur dünn belegt. Generell ist der Korpus noch nicht 100% finalisiert, und sollte daher vor potentieller Nutzung für Forschungszwecke erst gründlich überprüft und valididert werden.
- Quelle: Die Flugblätter zeigen die Selbstdarstellung der Gruppen zu der Zeit, und sind kein sicherer Beleg für reale historische Ereignisse (Kap. 8.4). Jegliche Aussagen, die aus den Flugblätter entnommen werden, sollten entsprechend historisch eingeordnet und kontextualisiert werden, um Missverständnisse und Falschaussagen zu vermeiden.

## 10.2 Wo Unsicherheit markiert ist

Wie sich im vorhergehenden Kapitel zeigt, ist das System keineswegs perfekt und erzeugen im Verlauf kleine Unsicherheiten. Zudem ist das Quellmaterial ebenso schwierig, da manche Informationen nur in einem Kontext verständlich sind, der heute nicht mehr nachvollziehbar und ermittelbar ist. Das einfachste Beispiel sind Tagesangaben wie "nächsten Donnerstag", was bei einem Flugblatt ohne jegliches Datum unmöglich in eine konkrete Datumsangabe umgewandelt werden kann. Da es an manchen Stellen des Verarbeitungsprozesses unumgänglich ist, dass Unsicherheiten entstehen, wurden diese Unsicherheiten stellenweise einfach deutlich markiert.

Manche Flugblätter, denen initial kein automatisch generiertes Thema zugewiesen werden konnte, erhielten nachträglich das statistisch passendste Thema. Diese Unsicheren Themen wurden somit entsprechend markiert, sodass diese Information nicht als sicher gewertet wird. Zudem sind die Metadaten auch potentiell fehlerbehaftet, was minimiert wurde, indem die Belege für diese Metadaten leicht aufrufbar sind, so lässt sich die Korrektheit der Angaben leicht prüfen. Zudem lassen sich manche Felder per Hand korrigieren.

## 10.3 Datenschutz und Urheberrecht

Da in den Flugblättern oft Namen von Personen fallen, wurde das Thema Datenschutz auch berücksichtigt. Jedoch zeigte sich in der Besprechung mit Herrn Becker, dass Datenschutz bei Flugblättern sehr simpel geregelt ist. Da die Flugblätter für die Öffentlichkeit bestimmt waren, ergeben sich im Umgang mit diesen potentiell persönlichen Daten der (möglicherweise noch lebenden) Personen keine datenschutzrechtlichen Hindernisse. Der Inhalt dieser Flugblätter darf frei veröffentlicht werden.

## 10.4 Ausblick

Es gibt viele potentielle Veränderungen, Verbesserungen oder Tests, die im Projekt verwirklicht werden könnten und obige Problemfelder (zumindest teilweise oder ganz) lösen können. Da die Grundstruktur der Anwendung solide steht, sollte in Zukunft der Fokus auf einer Verbesserung der automatisierten Datenverarbeitung liegen. 

Eine einfache und notwendige Verbesserung ist natürlich das kontinuierliche Hinzufügen neuer Flugblätter, vor allem der verbleibenden Bände des Jahres 1973.

Ein Aspekt, der definitiv in Zukunft im Fokus liegen sollte ist das OCR-System. Wie bereits im Kapitel zur Texterkennung beschrieben verschiebt sich aktuell der State-Of-The-Art fast Monatlich, konstant gibt es neue Veröffentlichungen, und daher kann es gut sein, dass ein Wechsel des OCR-System demnächst möglich oder nötig ist.

Zudem könnte die Erkennung von Maschinenschrift und Handschrift getrennt werden, da es für die Erkennung handgeschriebener Texte separate und spezialisiertere OCr-Modelle gibt.

Ein System zur Fuzzy-Suche könnte zudem die Auswirkungen fehlerhaften OCRs vermindern.

Ein weiteres Datenverarbeitungssystem, das als neues Feature hinzugefügt werden kann, ist Named entity Recognition, das erwähnte Personen und Orte als eigene Felder erkennt, vor allekm mit Belegstellen, mit OCR-Fehlern und Schreibvarianten (Obermair, Obermaier). Der Aufwand liegt weniger in der Erkennung als im Zusammenführen der Varianten und in der Messung an einer Stichprobe.

Zudem sollte und könnte das System vor einer langfristigen Nutzung ausgbieig getestet werden. Wie bereits erwähnt sind viele Variablen, Einstellungen oder Designentscheidungen nur das Produkt gradueller iterativer Verbesserung, meist basierend auf subjektiver Einschätzung durch die Entwickler. So wäre es sinnvoll, zu ermitteln, wie das System denn objektiv peformt. Beispielsweise die Korrektheit der extrahierten Metadaten könnte ermittelt werden, oder die reale Character Error Rate des OCR.

Seitens des Universitätsarchivs wurde großes Interesse an der Anwendung bekundet und der Wunsch geäußert, diese auch über das Projektende hinaus nutzen zu können. Eine mögliche Umsetzung wäre die Bereitstellung auf einem Universitätsserver, sodass die Anwendung dem Archiv dauerhaft zur Verfügung steht. Damit wäre jedoch auch ein fortlaufender Betreuungsaufwand verbunden. Dazu zählen insbesondere die Behebung auftretender Fehler, die Anpassung an technische Änderungen sowie gegebenenfalls eine Hilfestellung beim Import weiterer Bände. Um diese Herausforderungen in Zukunft einzugrenzen, wurde während der Entwicklung darauf geachtet, die Anwendung so robust, wartbar und nutzerfreundlich wie möglich zu gestalten. Eine ausführliche Dokumentation soll zudem sicherstellen, dass Einarbeitungszeit in die Anwendung auch für externe Nutzer so gering wie möglich ausfällt.

Aufgrund des positiven Interesses seitens des Universitätsarchivs haben wir uns dazu entschieden, das Gespräch mit den Verantwortlichen zu suchen und gemeinsam eine Lösung für die zukünftige Bereitstellung und Betreuung der Anwendung zu erarbeiten. Dabei sollen insbesondere die technischen und organisatorischen Voraussetzungen für einen dauerhaften Betrieb sowie die Zuständigkeiten für Wartung, Fehlerbehebung und den Import weiterer Bände geklärt werden.
