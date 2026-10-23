# 7 Themen zuordnen

Suche, Bände und Herausgeber erschließen das Korpus über Wörter und Herkunft. Themen fügen einen Zugang über den Inhalt hinzu, den auch das Findmittel nicht bietet. Am Ende hat der größte Teil der Flugblätter ein Thema, ein Teil davon nur unsicher. Entstanden ist das Verfahren in mehreren Anläufen (Kap. 12.6, Kap. 12.8); heute ist es Teil der Anwendung.

## 7.1 Aufgabe

Ein Topic Model fasst Flugblätter mit ähnlichem Inhalt automatisch zu Themen zusammen.

## 7.2 Herausforderungen

Zwei Eigenschaften der Flugblätter erschweren das. Viele behandeln mehrere Themen; das berücksichtigt das Verfahren bisher nicht, jedes Flugblatt bekommt nur eines. Außerdem überlagern formelhafte Wörter, Gruppenkürzel und Reste der Texterkennung den eigentlichen Inhalt. Gegen diese zweite Schwierigkeit richtet sich die Bereinigung in 7.3.

## 7.3 Verfahren

Vor der Berechnung bereinigen wir den Text. Aus der Texterkennung bleiben nur die Textblöcke; Bilder, Kopf- und Fußzeilen fallen weg. Vermerke des Archivs wie „Ablage“ mit Eingangsstempel, „z. K.“ oder „Erbitte Rückgabe“ entfernen wir. Sehr kurze Flugblätter gehen nicht ein, sehr lange werden gekürzt. Die Anwendung bereitet den Text beim Zuordnen neuer Bände und bei der Neuberechnung genauso auf.

Das Modell bge-m3 bildet dann den ganzen Text jedes Flugblatts als Vektor ab. BERTopic gruppiert diese Vektoren mit UMAP und HDBSCAN zu 50 Themen, die anschließend auf 40 zusammengefasst werden. Für die Schlagwörter eines Themas zählen nur Substantive in ihrer Grundform, ohne Stoppwörter und Kürzel von Organisationen.

Flugblätter, die im ersten Lauf als Ausreißer kein Thema erhalten hatten, bekommen nachträglich das Thema zugeordnet, dem sie am ähnlichsten sind. Diese Zuordnung ist nicht getestet und dient nur der Vollständigkeit; die Anwendung markiert sie entsprechend.

## 7.4 Qualität

Gemessen haben wir die Qualität der Zuordnung nicht. 1078 Flugblätter sind sicher zugeordnet, 408 unsicher [offen: sind das die nachträglich zugeordneten Ausreißer aus 7.3?] und 61 haben kein Thema. Die größten Themen sind „Streiks und Vollversammlungen gegen das Hochschulgesetz“ (136 Flugblätter), „Debatte um Hochschulgesetz und Hochschulreform“ (71) und „Hochschulwahlen: Kandidaten, Listen und Ergebnisse“ (47).

Fehlzuordnungen kommen vor. Das Flugblatt zum Streik gegen die Notstandsgesetze vom 29.05.1968 etwa liegt im Thema zum Hochschulgesetz, weil es in beiden um Streiks geht.

![Themenkarte und Themenliste der Anwendung](../abbildungen/app_themen.png)

*Abbildung: Themenkarte der Anwendung. Jeder Punkt ist ein Flugblatt, nahe Punkte haben ähnliche Texte. Flugblatt 850 gehört zum Thema „Fachschaftssatzungen und Urabstimmungen“ (25 Flugblätter).*

## 7.5 Manuelle Prüfung

Von Hand prüfen wir nur die Titel der Themen und benennen sie bei Bedarf um, in der Anwendung unter Verwaltung › Themen.

## 7.6 Kosten

Ein Lauf über den ganzen Bestand kostet wenige Cent.

Hinweise für die Weiterentwicklung stehen im Handbuch [Weiterentwicklung](../handbuch/weiterentwickeln.md#themen).
