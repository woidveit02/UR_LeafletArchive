# 7 Themen zuordnen

Ein Themenmodell gruppiert inhaltlich ähnliche Flugblätter zu 40 Themen und schafft so einen Zugang, den das Findmittel nicht bietet. Das Ergebnis ist eine Schätzung: 408 Flugblätter sind nur unsicher zugeordnet und als solche markiert.

## 7.1 Aufgabe

- Einen thematischen Zugang zum Bestand schaffen.

## 7.2 Herausforderungen

- Viele Flugblätter behandeln mehrere Themen, das Modell vergibt aber nur eines.
- Formelhafte Wörter, Gruppenkürzel und OCR-Reste überlagern den Inhalt.

## 7.3 Verfahren und Entscheidung

- Textvorverarbeitung: Blockfilter (Kopf- und Fußzeilen, Seitenzahlen, Bilder), Silbentrennung zusammenführen, Gruppenkürzel zusammenfassen [aus alter Fassung 5.3, Quelle handbuch/ngrams.md].
- bge-m3 bildet den ganzen Text jedes Flugblatts als Vektor ab (bis 8 192 Token).
- BERTopic gruppiert mit UMAP und HDBSCAN: 50 Themen, zusammengefasst auf 40; Stoppwörter und Organisationskürzel entfernt.
- Flugblätter ohne klares Thema werden dem ähnlichsten zugeordnet und als unsicher markiert.
- Titel: Ein Sprachmodell schlägt sie aus Schlagwörtern und Textauszügen vor; danach wurden alle 40 von Hand nach Leitlinien geprüft, 15 am 13./14.10. geändert (`docs/analyse/themen-titel-vorschlaege.md` im Arbeits-Repository).
- Aktueller Lauf vom 03.10.2026, Startwert 42.

## 7.4 Wie gut

- Keine Messung.
- 1 078 Flugblätter sicher zugeordnet, 408 unsicher, 61 ohne Thema.
- Größte Themen: Streiks und Vollversammlungen gegen das Hochschulgesetz (136), Debatte um Hochschulgesetz und Hochschulreform (71), Hochschulwahlen (47).
- Beispiel für eine Fehlzuordnung: Das Flugblatt zum Streik gegen die Notstandsgesetze vom 29.05.1968 liegt im Thema zum Hochschulgesetz, weil beide um Streiks gehen.

## 7.5 Was von Hand bleibt

- Titel prüfen und umbenennen (über `data/topics.json`).

## 7.6 Kosten

- Wenige Cent je Lauf über den ganzen Bestand.

## 7.7 Für die Weiterarbeit

- Ein neuer Lauf vergibt neue Themennummern; die von Hand geprüften Titel gehen dann verloren.
- Jedes Flugblatt hat genau ein Thema.
- Das Modell rechnet über alle Exemplare statt nur über die Hauptexemplare.
- Themen neu berechnen über das eigene Docker-Profil, Ergebnis zuerst als Kandidat neben `topics.json` (Handbuch Betrieb).
- Abbildung: Themenliste der Anwendung.
