# 10 Grenzen und Ausblick

Jedes der Kapitel 3 bis 7 nennt die Grenzen seines Schritts. Wer mit dem Korpus arbeitet, findet sie hier gesammelt, dazu, wie die Anwendung Unsicherheit kennzeichnet, was für Datenschutz und Urheberrecht gilt und wo sich die Arbeit fortsetzen lässt.

## 10.1 Bekannte Fehlerquellen

Die Fehlerquellen folgen den Arbeitsschritten. Beim Text ist die gemessene Fehlerrate wegen der Art der Messung eher eine Untergrenze (Kap. 3.10). Handschrift erkennt das System noch oft falsch, selten erfindet es Text, und gesperrt geschriebene Wörter können die Volltextsuche behindern.

Die Trennung in Flugblätter liefert nur Vorschläge, mit etwa 12 Fehlern je 100 Seitenwechsel (Kap. 4.5). Jeder Seitenwechsel muss deshalb von Hand bestätigt werden, weil sich Fehler sonst in alle folgenden Schritte fortsetzen. In den Bänden 1 bis 14 sind Stellen der Verdachtsliste unbearbeitet geblieben (Kap. 12.8), und fünf Seiten, die als leer gelten, enthalten möglicherweise Text (Kap. 4.7).

Die Genauigkeit der Metadaten haben wir nicht gemessen (Kap. 5.4). Fehldeutungen sind möglich, etwa wenn das Modell den Eingangsstempel für das Erscheinungsdatum hält, und bei vielen Flugblättern fehlen einzelne Felder ganz. Die Bände 001–004 und 005–014 beruhen auf verschiedenen Fassungen des Prompts (Kap. 5.3), und neuere Modelle wie Claude Sonnet 5 haben wir nicht getestet. Wie viele Mehrfachexemplare das Verfahren übersieht, ist nicht gemessen (Kap. 6.4).

Bei den Themen bekommt jedes Flugblatt nur eines, obwohl manche mehrere behandeln. Die Zahl von 40 Themen beruht zudem nur auf unserer Durchsicht.

Für den Betrieb hängt das System von externen Diensten ab (Datalab, OpenRouter), deren Läufe sich nicht exakt wiederholen lassen. Die Anwendung hat keine Anmeldung und ist deshalb standardmäßig nur auf dem eigenen Rechner erreichbar (Freigabe im Netz: [Installation und Betrieb](../handbuch/installieren-und-betreiben.md#auf-einem-server-des-archivs)).

Über alle Schritte hinweg gilt: Viele Einstellungen beruhen auf Einschätzung, Erfahrung und schrittweiser Verbesserung, nicht auf systematischen Tests. Auch die Oberfläche hat keinen Nutzertest durchlaufen, Probleme in der Bedienung sind also nicht ausgeschlossen.

Hinzu kommen Grenzen, die im Material selbst liegen. Im Korpus fehlt für 1973 noch mindestens Band 15 (Kap. 2.5), sodass sich über dieses Jahr noch keine repräsentativen Aussagen treffen lassen, und 1967 und 1968 sind nur dünn belegt. Zitate und Zahlen sollten vor einer Nutzung für die Forschung deshalb am Scan geprüft werden. Vor allem aber zeigen die Flugblätter die Selbstdarstellung der Gruppen und sind kein sicherer Beleg für die Ereignisse selbst (Kap. 8.3). Aussagen aus den Flugblättern sollten deshalb historisch eingeordnet werden, um Missverständnisse und Fehlschlüsse zu vermeiden.

## 10.2 Kennzeichnung von Unsicherheit

Weil sich diese Fehler nicht ganz vermeiden lassen, kennzeichnet die Anwendung unsichere Angaben. Manche Unsicherheit liegt schon im Material: Angaben wie „nächsten Donnerstag“ lassen sich bei einem Flugblatt ohne Datum nicht in ein konkretes Datum umrechnen, weil der Zusammenhang heute fehlt.

Flugblätter, denen der erste Lauf kein Thema zuweisen konnte, haben nachträglich das passendste Thema erhalten; die Anwendung markiert diese Zuordnungen als unsicher (Kap. 7.3). Bei den Metadaten führt ein Klick auf den Beleg zur Stelle im Scan, sodass sich jede Angabe prüfen lässt, und viele Felder lassen sich von Hand korrigieren (Kap. 9.3).

## 10.3 Datenschutz und Urheberrecht

Die Flugblätter nennen viele Personen mit Namen, vor allem als Unterzeichnende oder als presserechtlich Verantwortliche. Manche von ihnen leben vermutlich noch. Nach Einschätzung des Universitätsarchivs, die Andreas Becker in einer Besprechung erläutert hat, ergeben sich daraus keine datenschutzrechtlichen Hindernisse: Flugblätter waren dafür bestimmt, öffentlich verteilt zu werden, und die Namen stehen bewusst darauf. Dieser Einschätzung folgen wir.

Für die Arbeit im Archiv und für die Forschung sehen wir damit kein Hindernis. Nicht geprüft haben wir, ob die Scans für Texterkennung und Metadaten an externe Dienste (Datalab, OpenRouter) gehen dürfen; das sollte das Archiv vor weiteren Importen klären. Bei einer Veröffentlichung im Netz wären die Namen zusätzlich über Suche, Filter und Export für alle auffindbar und mit anderen Daten verknüpfbar. Ob und in welcher Form das geschehen soll, entscheidet das Archiv nach den Regeln für seine Bestände. Dasselbe gilt für das Urheberrecht, denn die Texte aus den Jahren 1967 bis 1973 können noch geschützt sein.

## 10.4 Ausblick

Die Grundstruktur der Anwendung steht. Weiterarbeit lohnt sich deshalb vor allem bei der automatischen Verarbeitung und beim Bestand.

Am einfachsten und am nötigsten ist es, neue Flugblätter hinzuzufügen, vor allem die übrigen Bände von 1973. Auch die Flugblattsammlung im Privatarchiv Wiesner (Rep. 113, 1970 bis 1987, Kap. 2.1) ließe sich nach dem Scannen mit den Werkzeugen erschließen und würde den Zeitraum bis in die 1980er Jahre erweitern. Mit jedem Jahrgang werden auch die Auswertungen aussagekräftiger, die wir zugunsten der Erschließung zurückgestellt haben (Kap. 1.2).

Bei der Texterkennung verschiebt sich der Stand der Technik fast monatlich (Kap. 3.2), sodass ein Wechsel des Systems bald möglich oder nötig sein kann. Maschinenschrift und Handschrift ließen sich getrennt erkennen, weil es für Handschrift eigene, spezialisierte Modelle gibt. Eine unscharfe Suche (Fuzzy-Suche) könnte die Folgen von Erkennungsfehlern mildern.

Als neue Funktion käme eine Erkennung von Personen und Orten (Named Entity Recognition) als eigene Felder in Frage, mit Belegstellen und über OCR-Fehler und Schreibvarianten hinweg (Obermair, Obermaier). Der Aufwand liegt weniger in der Erkennung als im Zusammenführen der Varianten und in der Messung an einer Stichprobe.

Vor einer langfristigen Nutzung sollte das System gründlicher getestet werden. Viele Einstellungen und Entwurfsentscheidungen sind das Ergebnis schrittweiser Verbesserung nach unserer eigenen Einschätzung. Messen ließe sich etwa die Richtigkeit der Metadaten oder die Fehlerrate der Texterkennung über den ganzen Bestand.

Das Archiv möchte die Anwendung über das Projektende hinaus nutzen. Das bringt laufenden Betreuungsaufwand mit sich: Fehler beheben, die Anwendung an technische Änderungen anpassen und gegebenenfalls beim Import weiterer Bände helfen. Um diesen Aufwand gering zu halten, lässt sich die Datenbank jederzeit aus den Dateien neu aufbauen (Kap. 9.5), automatische Tests prüfen unter anderem Mehrfachexemplare, Korrekturen und Datumsangaben, und die Dokumentation soll auch Außenstehenden die Einarbeitung erleichtern. Wie der Betrieb verabredet ist und was dafür noch zu klären ist, steht in Kap. 9.7.
