# 3 Text erkennen

Nachdem der Bestand der Allgemeinen Flugblattsammlung übermittelt und gesichtet worden war, musste die Information aus den Bildern der PDFs extrahiert werden. Für die Texterkennung haben wir acht Systeme verglichen und die Datalab API gewählt, weil sie Text und Layout am genauesten wiedergibt. Gemessen an einem von Hand korrigierten Goldstandard sind etwa 6 von 1000 Zeichen falsch. Die Erkennung kostet rund 10 $ je 1000 Seiten und läuft ohne Handarbeit. 

Die Texterkennung liefert die Grundlage für alle weiteren Schritte: Segmentierung, Metadatenextraktion, Suche und Analyse arbeiten mit ihrem Ergebnis, und Fehler an dieser Stelle wirken sich auf jeden späteren Schritt aus.

## 3.1 Anforderungen

Das Material stellt die Texterkennung vor mehrere Schwierigkeiten. Die meisten Blätter sind beispielsweise mit Schreibmaschine geschrieben und von den Gruppen selbst vervielfältigt. Rund 230 Blätter tragen den Vermerk „Eigendruck im Selbstverlag“. Das Layout ist oft kompliziert: Neben einspaltigem Fließtext gibt es mehrspaltige Seiten, teils auch im Querformat, Tabellen, Abbildungen und Stempel. Handschrift steht im Text und am Rand, etwa als Ablagenummer, Unterstreichung oder Korrektur, und manche Stellen sind durchgestrichen. Typisch für die Zeit sind außerdem Sperrschrift zur Hervorhebung, Silbentrennung am Zeilenende, mit der Schreibmaschine überschriebene Stellen und verblichene Abzüge. Zudem fiel ins Gewicht, wie gut ein System mit den Scans selbst umgeht. Die Vorlagen sind Aufnahmen gealterter Blätter und keine digital erzeugten Dateien: Das Papier ist teils verfärbt, die Schrift ausgeblichen, und die Rückseite scheint mitunter durch. Alle Digitalisate wurden mittels eines einfachen Kamera-Setups erstellt, daher spielt die Qualität der Bilder selbst noch eine Rolle. Außerdem spielt die Sprache noch eine Rolle, die Texte sind größtenteils deutsch, mit Umlauten und ß, alten Formulierungen und Wörtern ("dass"/"daß") oder alte Umgangs- und Jugendsprache, die heute nicht mehr genutzt wird ("Teach-In").

![Ausschnitte aus vier Seiten mit dem, was die OCR dort gelesen hat](../abbildungen/ocr_schwierigkeiten.png)

*Abbildung: Typische Schwierigkeiten und was die Datalab API daraus macht. Die gemalte Überschrift wird zu „VRABSTIMMUNG“ statt „Urabstimmung“; gesperrte Wörter erscheinen Buchstabe für Buchstabe; der stark verblichene Text wird hier richtig gelesen; die Paraphe im Stempel beschreibt die API auf Englisch, die handschriftliche Ablagenummer liest sie richtig.*

Für die weitere Verarbeitung reicht reiner Text nicht aus. Die Segmentierung nutzt Kopfzeilen als Hinweis auf den Beginn eines neuen Blatts (Kapitel 4), die Textvorverarbeitung filtert Kopf- und Fußzeilen, Seitenzahlen und Bilder heraus (Kapitel 7). Das System sollte deshalb den Text in Blöcke gliedern, diesen Blöcken einen Typ zuweisen und ihre Lage auf der Seite angeben (Bounding Boxes).

![Seite 394 aus Band 006 mit den Blöcken, in die die Datalab API sie gliedert](../abbildungen/ocr_bloecke.png)

*Abbildung: So gliedert die Datalab API eine Seite (Flugblatt 850, Band 006, S. 394). Jeder Rahmen ist ein Block mit Typ und Lage; Kopfzeile, Überschriften und Fließtext sind getrennt.*

## 3.2 Kandidatensuche

Wie oben gezeigt erfordert dieses Projekt ein wesentlich besseres Texterkennungssystem als für konventionelles Scannen einer Seite Drucktext. Aber durch aktuelle Entwicklungen im Bereich KI (TODO: Quelle) ergeben sich im Bereich Texterkennung beziehungsweise OCR (Optical Character Recognition) zurzeit monatlich neue Fortschritte. 

So haben wir uns über drei Wege einen Überblick über die vorhandenen Produkte erstellt: Über die Technical Reports der Entwickler, über die Ranglisten der Benchmarks olmOCR-Bench [@olmocrbench] und OmniDocBench [@omnidocbench] und über Blog- und Forenbeiträge, vor allem auf Reddit und Hacker News. Vor allem über die Ranglisten der Benchmarks, die bereits eine qualifizierte Evaluation der OCR-Systeme zum Vergleich anbieten, lässt sich bereits vorher die Qualität vergleichen.

Ausgewählt wurden Systeme aus drei Gruppen. Die erste bilden große Vision-Sprachmodelle für allgemeine Zwecke, die Seiten als Bild entgegennehmen und Text ausgeben (Claude Sonnet 5, Gemini 3.5 Flash und Qwen3-VL). Die zweite sind kommerzielle Dienste, die auf Dokumente spezialisiert sind (Datalab API und Mistral OCR 4). Die dritte sind spezialisierte Modelle mit offenen Gewichten, die in den Quellen häufig für den Betrieb auf eigener Hardware beschrieben werden (GLM-OCR, PaddleOCR und MinerU).

## 3.3 Testkorpus

Um die Qualität beziehungsweise Performance der OCR-Systeme zu evaluieren wurde erst ein Test-Korpus von 100 Seiten erzeugt. Je 20 Seiten aus den Jahrgängen 1969, 1970, 1971, 1972 und 1973. Innerhalb eines Jahrgangs wurden die Seiten zufällig und gleichverteilt aus allen Seiten seiner Bände gezogen (Skript `test_set_generator.py`, 30.06.2026), ohne Schichtung nach Layout, Textsorte oder Scanqualität. Die Jahrgänge 1967 (13 Seiten) und 1968 (85 Seiten) wurden wegen ihres geringen Umfangs nicht aufgenommen.

Gleich viele Seiten je Jahrgang bedeuten eine unterschiedliche Abdeckung. Aus 1969 stammen 20 von 317 Seiten (6,3 %), aus 1973 20 von 1 518 (1,3 %), die frühen und kleineren Jahrgänge sind also gegenüber ihrem Anteil am Bestand übergewichtet. Für den Vergleich der Systeme ist das unproblematisch, weil jeder Jahrgang mit genug Seiten vertreten ist. Eine Fehlerrate für den Gesamtbestand müsste dagegen nach Seitenzahl je Jahrgang gewichtet werden.

Die Ziehung verwendete keinen festen Zufallswert und protokollierte die gezogenen Seiten nicht. Wir haben die Herkunft jeder Testseite deshalb nachträglich rekonstruiert, indem wir ihren OCR-Text mit allen Bandseiten verglichen haben (Übereinstimmung der Wort-Trigramme, `pipelines/03_eval/testkorpus-seiten.csv` im Arbeits-Repository, Kap. 12.6). 94 Seiten ließen sich so eindeutig zuordnen. Vier weitere haben wir über einen Bildvergleich bestimmt: zwei Seiten mit wenig Text (ein Formular und eine handgezeichnete Karte) und zwei Blätter, von denen ein weiteres Exemplar in einem Band eines anderen Jahrgangs liegt, das der Textvergleich zuerst gefunden hatte. Zwei Seiten sind leer, eine davon eine Rückseite; ihre Herkunft lässt sich nicht bestimmen.

## 3.4 Kandidaten und Merkmale

(TODO: Betrieb von PaddleOCR und MinerU ergänzen, je Merkmal mit Quelle, Version und Abrufdatum.
     Modellkennungen laut Ausgabedateien: anthropic/claude-sonnet-5, qwen/qwen3-vl-235b-a22b-instruct
     (beide über OpenRouter), gemini-3.5-flash; Läufe am 09.07.2026.
     GLM-OCR: Der Test lief am 08.07.2026 mit GLM-OCR/ocr_test.py, das nur Text je Seite liefert. Das spätere
     glm_convert.py (Ausgabe jsonGLM vom 17.08.2026) erzeugt über PP-DocLayout-V3 Blöcke mit Lage; falls das
     erwähnt werden soll, als Nachtrag kennzeichnen.)

Acht Systeme wurden am 8. und 9. Juli 2026 auf das Testkorpus angewendet. Die Skripte dafür liegen im Arbeits-Repository (Kap. 12.6).

| System | Art | Betrieb im Test | Blöcke mit Lage | Anmerkung |
|---|---|---|---|---|
| GLM-OCR | spezialisiertes OCR-Modell, offene Gewichte | selbst gehostet, Modell direkt angesprochen | nein, nur Text | läuft über Ollama auch ohne GPU |
| PaddleOCR (klassische PP-OCR-Pipeline) | OCR-Pipeline aus Erkennung und Lesung von Zeilen, offene Gewichte | lokal ausgeführt | Zeilen mit Lage, keine Blocktypen | Layout im Test oft falsch erkannt |
| MinerU 3.4.2 (Backend `pipeline`) | Dokument-Pipeline aus Layout- und OCR-Modellen, offene Gewichte | lokal ausgeführt | ja | geringere Textgenauigkeit |
| Qwen3-VL (235B-A22B Instruct) | allgemeines Vision-Sprachmodell | API über OpenRouter | nein, nur Text | gute Textgenauigkeit |
| Claude Sonnet 5 | allgemeines Vision-Sprachmodell | API über OpenRouter, Seiten als Bilder gesendet | nein, nur Text | |
| Gemini 3.5 Flash | allgemeines Vision-Sprachmodell | Gemini-API | nein, nur Text | |
| Datalab API (verbesserte Fassung von Chandra OCR 2) | OCR-Dienst | API | ja, mit Blocktypen | Wort-Boxen optional |
| Mistral OCR 4 | OCR-Dienst | API | ja | Confidence-Wert je Wort |

Die Entwickler veröffentlichen eigene Benchmark-Ergebnisse, aber nicht für alle Kandidaten und nicht immer für die getesteten Fassungen [@glmocr; @paddleocrvl15; @mineru25pro; @qwen3vl; @claudesonnet5; @chandra2; @mistralocr4]. Eine Übersicht mit Größe, Lizenz, Benchmark-Werten und allen Quellen liegt im Arbeits-Repository unter `pipelines/03_eval/ocr-modelle-uebersicht.md` (Stand 17.08.2026). Diese Zahlen sind nur eingeschränkt vergleichbar. Die Versionen 1.0, 1.5 und 1.6 von OmniDocBench [@omnidocbench] verwenden unterschiedliche Bewertungsverfahren, ihre Werte lassen sich nicht nebeneinanderstellen. olmOCR-Bench [@olmocrbench] hat eine Unsicherheit von etwa einem Punkt. Abstände unter rund zwei Punkten sagen daher wenig. An der Methodik von olmOCR-Bench gibt es außerdem Kritik [@llamaindexolmocr]: Die Testfälle wurden aus Seiten erzeugt, die Claude Sonnet 4.0 geschrieben hat, und die Kategorie für Kopf- und Fußzeilen belohnt das Weglassen sichtbarer Inhalte. Bei Datalab sind die gehostete API und die offenen Gewichte von Chandra OCR 2 verschiedene Systeme mit verschiedenen Ergebnissen. Wir haben die API genutzt.

## 3.5 Vorauswahl

Nach einer ersten Durchsicht der Ausgaben auf dem Testkorpus schieden sechs Systeme aus. GLM-OCR, Claude Sonnet 5 und Gemini 3.5 Flash lieferten nur Text, ohne Bounding Boxes und ohne Blocktypen. Ihnen fehlt damit eine Layouterkennung, die Tabellen, Listen und mehrspaltige Seiten als solche wiedergibt. Qwen3-VL erkannte den Text gut, gliederte die Seite aber ebenfalls nicht. PaddleOCR erkannte das Layout häufig falsch. MinerU erkannte das Layout, lieferte aber eine geringere Textgenauigkeit. Die besten Ergebnisse erzielten die Datalab API, die eine verbesserte Fassung von Chandra OCR 2 einsetzt, und Mistral OCR 4, die damit in die engere Wahl kamen.

Beide Systeme hatten beim Test mit dem Testkorpus vieles gemeinsam. Sie erkennen auch komplexe Layouts, gliedern die Seite in Blöcke mit Lage und Typ und kommen mit Handschrift gut zurecht. Beide erzeugen Beschreibungen für Abbildungen, Mistral OCR 4 kostet über die API 4$ je 1000 Seiten, die Datalab API im Modus `accurate` 10$ (Preise Stand August 2026, siehe 3.9). Beide Anbieter veröffentlichen eigene Benchmark-Ergebnisse für Deutsch (Datalab) bzw. für die westeuropäische Sprachgruppe (Mistral). Im olmOCR-Bench geben die Anbieter 86,7 ± 0,8 Punkte für die Datalab API [@chandra2] und 85,20 Punkte für Mistral OCR 4 an [@mistralocr4]. Das sind Herstellerangaben, die wir nicht selbst nachgemessen haben, und der Abstand liegt innerhalb der Unsicherheit des Benchmarks. Mistral OCR 4 liefert zusätzlich für jedes Wort einen Confidence-Wert und war in unserem Test schneller: Die 100 Testseiten waren in 14 bis 22 Sekunden verarbeitet.

## 3.6 Qualitativer Vergleich

Die beiden Kandidaten der engeren Wahl haben wir Seite für Seite verglichen. Jede der drei Personen im Team übernahm ein Drittel des Testkorpus (Seiten 1 bis 33, 34 bis 66 und 67 bis 100) und notierte Unterschiede und wiederkehrende Muster zwischen den beiden Ausgaben. Grundlage waren die Ausgaben der Datalab API und von Mistral OCR 4.

Bei der Wortgenauigkeit lag Datalab meist vorn, besonders bei verblichenem Text, wo ein Wortvergleich deutlich weniger Fehler zeigte (Seiten 5 und 24). Mistral ersetzte mehrfach seltene Wörter durch geläufige, etwa „Aluminium“ statt „Alumneum“ und „ständigen“ statt „stämmigen“, verlas getippte Zahlen und schrieb einen Professorennamen falsch, den Datalab richtig erkannte. Seite 49 hat Mistral nicht verarbeitet, Seite 50 vollständig halluziniert. Erfundene Wörter kamen aber bei beiden Systemen vor: Aus „Gesicht und Nacken“ wurde bei Datalab „Gesicht und Rücken“, bei Mistral „Gesicht und Backen“. Datalab schrieb „AStA“ auf einer Seite als „ASTA“, auf einer anderen richtig; Mistral las das große S in „AStA“ einmal als „ß“. Ein Verdacht, Datalab habe auf Seite 86 Text in einer Schleife wiederholt, bestätigte sich in der gespeicherten Ausgabe nicht.

Das Layout gab Datalab näher am Original wieder. Mistral fasste mehrfach Blöcke zusammen, die getrennt stehen (auf Seite 3 etwa 17 statt 19 Blöcke), und verschmolz einmal zwei Listenpunkte. Tabellen erkannte Datalab als Tabellen, Mistral nur als einzelne Zeilen (Seiten 9 und 16). Datalab unterscheidet Kopf- und Fußzeilen, Mistral fasst beide in einer Kategorie zusammen und hielt auf Seite 5 drei Elemente fälschlich für Kopfzeilen. Auf Seite 31 erkannte dagegen nur Mistral die Fußzeile richtig.

Datalab übernahm mehr von der Formatierung: Unterstreichungen, Nummern in Aufzählungen, Zeilenumbrüche in Impressumsangaben, doppelte Anführungszeichen und handschriftliche Hervorhebungen als Fettdruck. Mistral wandelte doppelte in einfache Anführungszeichen um, erkannte dafür Hochstellungen und behielt das „ß“, das Datalab teils durch „ss“ ersetzte. Wo mit der Schreibmaschine nachträglich korrigiert wurde, gab Datalab eher den ursprünglichen Text wieder, Mistral eher die Korrektur.

Bei Handschrift scheiterten beide an denselben Stellen: „Urabstimmung“ wurde zu „Vrabstimmung“, handschriftliche Ablagenummern und verschnörkelte Schrift las keines der Systeme richtig. Nachträgliche Korrekturen von Hand verarbeiteten beide gut. Gesperrte Wörter („T E N D E N Z E N“) gaben beide meist Buchstabe für Buchstabe wieder. Die Beobachtungen im Team dazu sind nicht einheitlich, auf einer Seite fügte Mistral die Buchstaben zu Wörtern zusammen, was für die Suche brauchbarer ist. Bei der Silbentrennung am Zeilenende waren die Ergebnisse wechselhaft: Mal setzte Mistral die Wortteile richtig zusammen (Seite 15), mal Datalab (Seite 30). Datalab neigte allgemein dazu, Wörter zusammenzuziehen, Mistral dazu, sie unnötig zu trennen.

Zu Abbildungen erzeugte Datalab zutreffende Beschreibungen in englischer Sprache, Mistral auf denselben Seiten nicht. Datalab schnitt Bilder großzügiger aus. Einmal verwies es auf die falsche Bilddatei, beschrieb aber das richtige Bild. Buchstaben, die zu einem Bild angeordnet sind, erkannte keines der Systeme.

Infolge dieser ganzen Faktoren fiel die vorläufige Entscheidung in Abstimmung im Team auf Datalab. 

## 3.7 Goldstandard

Um die Genauigkeit von Datalab zu beziffern, haben wir einen Goldstandard erstellt. Dazu wurde die Datalab-Ausgabe des Testkorpus im Korrekturmodus des OCR-Viewers, eines eigenen Werkzeugs für den Vergleich der Systeme, Block für Block gegen den Scan geprüft und berichtigt. Eine Seite galt als fertig, wenn jeder Block als geprüft oder unleserlich markiert und Layout und Lesereihenfolge bewertet waren. Die Fehlerraten wurden mit dinglehopper berechnet. Die Seiten 1 bis 5 bearbeiteten alle drei Personen, um die Übereinstimmung zwischen ihnen zu prüfen. Insgesamt entstanden bis zum 03.08.2026 113 Seitenannotationen, davon 105 vollständige, die in die Auswertung eingingen. Die Kürzel in den Tabellen stehen für Felix Lindner (fl), Sebastian Simbeck (ss) und Veit Korpies (vk).

| Person | Seiten | CER (Mittel je Seite) | WER (Mittel je Seite) | CER (längengewichtet) | WER (längengewichtet) |
|---|---|---|---|---|---|
| fl | 33 | 0,85 % | 5,32 % | 0,56 % | 3,39 % |
| ss | 37 | 0,99 % | 3,51 % | 0,62 % | 3,03 % |
| vk | 35 | 0,83 % | 1,54 % | 0,60 % | 1,33 % |
| gesamt | 105 | 0,89 % | 3,42 % | 0,60 % | 2,53 % |

Über alle 105 bewerteten Seiten liegt die Zeichenfehlerrate bei 0,60 %, die Wortfehlerrate bei 2,53 % (jeweils längengewichtet). Man beachte, dass die Werte voneinander abweichen müssen, da es sich um verschiedene Flugblätter handelt. Auf den fünf Kalibrierungsseiten, die alle drei bearbeitet haben, lag die Zeichenfehlerrate bei allen unter 1 % und je Seite höchstens 0,3 Prozentpunkte auseinander.

Fehler im Layout wiesen 18 der 105 Seiten auf (17 %), Fehler in der Lesereihenfolge 8 (8 %). Typisch waren Blöcke in falscher Reihenfolge, Blöcke, die zusammengehören, aber getrennt erkannt wurden, ein spiegelverkehrt gescanntes Blatt, ein als Bild erkannter Stempel und gesperrt geschriebene Buchstaben, die die Erkennung stören. Als unleserlich markiert wurden insgesamt 20 Blöcke. Die übrigen Markierungen für fehlende, überzählige, zusammengefasste oder geteilte Blöcke wurden nicht vergeben.

## 3.8 Entscheidung

Der oben beschrieben Test zeigte, dass die Datalab API eine valide Wahl als OCR-Syystem in diesem Kontext ist. Ausschlaggebend waren die höhere Textgenauigkeit im Vergleich, vor allem bei verblichenen Seiten und Eigennamen, und die genauere Wiedergabe des Layouts. Für die weitere Verarbeitung zählt außerdem, dass Datalab Kopf- und Fußzeilen getrennt ausweist und Tabellen als solche erkennt. Die Vorteile von Mistral OCR 4, die Confidence-Werte je Wort und die höhere Geschwindigkeit, wogen das nicht auf.

## 3.9 Produktionslauf

Den Gesamtbestand von 14 Bänden mit 4464 Seiten haben wir zwischen dem 17. und 19.08.2026 verarbeitet. Das Skript `flugblatt_convert.py` nutzt das offizielle Python-SDK von Datalab mit folgenden Einstellungen: Modus `accurate`, Seitenumbrüche markiert (`paginate`), seitenübergreifende Inhalte zusammengeführt (`merge_cross_page`), Kopf- und Fußzeilen in der Ausgabe behalten, zusätzliche Blocktypen (`new_block_types`) und Bildextraktion aktiv. Wort-Boxen (`word_bboxes`) waren nicht aktiviert.

Datalab nimmt Dateien bis 200 MB an. Das Skript teilt jeden Band deshalb in Abschnitte von höchstens 50 Seiten (beobachtet 115 bis 135 MB), schickt bis zu 15 davon gleichzeitig ab, speichert jeden fertigen Abschnitt zwischen und fügt am Ende alles zu einer JSON-Datei je Band zusammen. Bricht ein Lauf ab, setzt ein erneuter Aufruf bei den fehlenden Abschnitten fort, ohne bereits bezahlte erneut zu verarbeiten. Ist das Guthaben eines Kontos aufgebraucht, wechselt das Skript zum nächsten hinterlegten Schlüssel. Der kostenlose Tarif erlaubt 25 gleichzeitige Ausführungen und 25 Anfragen pro Minute.

Ein Beispiel ist Band 003 (1969): 317 Seiten in 7 Abschnitten, nach 3 Minuten und 10 Sekunden fertig. Die Rechenzeit auf dem Server betrug 2,2 Sekunden je Seite, im Mittel fielen 906 Token je Seite an. Über den Gesamtbestand wurden 1 162 Bilder extrahiert, etwa eines auf 3,8 Seiten.

Datalab berechnet im Modus `accurate` 10 $ je 1000 Seiten, bei Datenhaltung in der EU das 1,25-Fache. Für die 4464 Seiten ergeben sich damit rund 45 $. In der Besprechung vom 19.08.2026 haben wir die Kosten auf etwa 40 € beziffert. Der kostenlose Tarif enthält ein monatliches Guthaben von 10 $, bei Anmeldung mit einer Universitätsadresse 20 $. Zunächst wurde dieses Guthaben aufgebraucht, danach wurden am 18.08.2026 20,11 $ (18,04 €) abgebucht.

Für neue Bände zeigt die Anwendung vor dem OCR-Lauf eine Kostenschätzung an (Kapitel 9). Sie rechnet mit dem Listenpreis von 10 $ je 1000 Seiten und stimmt gut mit den abgerechneten Beträgen überein.

## 3.10 Grenzen der Evaluation

Das Testkorpus ist mit 100 Seiten klein, und seine Zusammensetzung übergewichtet die frühen Jahrgänge (3.3). Seiten aus 1967 und 1968 fehlen ganz.

Der Goldstandard entstand durch Nachkorrektur der Datalab-Ausgabe. Wer eine vorhandene Ausgabe korrigiert, übersieht leichter Fehler als jemand, der unabhängig abschreibt. Die gemessene Fehlerrate von Datalab ist daher eher eine Untergrenze. Mistral OCR 4 wurde nicht an diesem Goldstandard gemessen; der Vergleich der beiden Systeme in 3.6 ist qualitativ.

Zudem gab es im qualitativen Vergleich kein gemeinsames Bewertungsschema, was bei der Auswerkung bemerkbar wurde. Die Beobachtungen lassen sich daher nicht auszählen und widersprechen sich in Einzelfällen, etwa bei der Sperrschrift. Die Benchmark-Werte in 3.4 sind Angaben der Anbieter und wurden nicht überprüft.

Die Läufe lassen sich nur eingeschränkt wiederholen, weil sich die Modelle hinter den Diensten ändern. Gemini 3.5 Flash ist inzwischen abgekündigt. Anfragen unter dieser Modellkennung werden auf Gemini 3.6 Flash umgeleitet und liefern heute also ein anderes Modell. Die gespeicherten Ausgaben im Arbeits-Repository (Kap. 12.6) sind deshalb der eigentliche Beleg für den Test.
