# Recherchieren und pflegen

Diese Anleitung beschreibt, wie Sie in der Anwendung recherchieren und den Bestand pflegen. Wie ein neuer Band dazukommt, steht in [Neue Bände importieren](neue-baende-importieren.md).

Die Anwendung hat zwei Bereiche. Die Leiste oben führt zum **Recherchieren**: Flugblätter, Herausgeber, Bände, Themen, Trends und die Suche. **Verwaltung** rechts oben führt zum Pflegen: Mehrfachexemplare, Herausgeber zuordnen, Korrekturen, Themen, Export, API-Keys und Import. Metadaten korrigieren Sie direkt auf der Seite eines Flugblatts.

## Recherchieren

### Suchen und filtern

![Flugblattliste mit der Suche nach „berufsverbot“, links die Filter](../abbildungen/nutzen_suche.png)

Das Suchfeld oben auf jeder Seite durchsucht Titel, Reihe, Herausgeber, Unterzeichnende und den erkannten Text aller freigegebenen Flugblätter.

- Die Suche findet auch Wortteile: „versammlung“ trifft „Vollversammlung“ und, trotz Lesefehler, „Vo11versammlung“.
- Mehrere Wörter müssen alle vorkommen. Wörter in Anführungszeichen suchen eine feste Wortfolge.
- „daß“ und „dass“ finden sich gegenseitig.
- Begriffe unter drei Zeichen sucht die App nur in Titel und Reihe.
- Über „Alle Felder“ lässt sich die Suche auf ein Feld beschränken. „+ Suchbedingung hinzufügen“ verknüpft mehrere Bedingungen mit UND, ODER oder NICHT.

Links stehen die Filter: Jahr, Herausgeber, Thema, Datierung, Textsorte und Reihe. Die Zahl neben jedem Wert nennt die Treffer mit diesem Wert. Mehrere Filter grenzen gemeinsam ein. Als Jahr zählt das Datum auf dem Blatt, bei undatierten Blättern das Jahr des Bandes.

Über der Liste lassen sich die Sortierung und die Ansicht wählen: **Liste** mit Textausschnitten, **Kacheln** und, wenn ein Suchbegriff eingegeben ist, **Fundstellen**: alle Textstellen aller Treffer untereinander, nach Datum. „Trend über die Jahre“ öffnet die Suche in den Trends. Unter der Liste lädt ein Link alle Treffer als CSV-Tabelle (Titel, Datum, Herausgeber, Thema und Link, ohne Volltext).

Ein Flugblatt, das in mehreren Exemplaren im Bestand liegt, steht nur einmal in der Liste, mit dem Hinweis „1 weiteres Exemplar“. Unter „Mehrfach vorhandene Blätter“ › „Jedes Exemplar einzeln zeigen“ erscheinen alle.

### Flugblattansicht

![Leseansicht eines Flugblatts](../abbildungen/app_leseansicht.png)

Oben stehen die Metadaten. Ein Klick auf „Beleg“ zeigt die Textstelle im Scan, auf die sich eine Angabe stützt. Darunter steht für jede Seite der erkannte Text neben dem Scan. „Vergrößern“ öffnet den Scan in voller Auflösung.

| Taste oder Link | Wirkung |
|---|---|
| ← → | vorige / nächste Seite des Flugblatts |
| 1 bis 9 | zur Seite mit dieser Nummer |
| „‹ Voriges“, „Nächstes ›“ | voriges / nächstes Flugblatt der Liste, aus der Sie gekommen sind |

### Bände, Herausgeber, Themen

- **Bände** listet alle Bände des Bestands wie im Findmittel. Die Seite eines Bandes zeigt seine Scanseiten der Reihe nach, nach Flugblättern gruppiert, und den Link ins Archivportal-D.

  ![Ausschnitt aus der Seite von Band 006](../abbildungen/app_band.png)

- **Herausgeber** ist das Register der Organisationen. Die Seite einer Organisation zeigt ihre Flugblätter, den Verlauf über die Jahre, die häufigsten Themen und mit wem sie gemeinsam herausgegeben hat.
- **Themen** zeigt die Themen mit ihren Schlüsselwörtern, der Zahl der Flugblätter und der Verteilung über die Jahre, dazu die Themenkarte: Jeder Punkt ist ein Flugblatt, ähnliche Texte liegen nah beieinander. Wie die Themen entstanden sind, steht in [Kapitel 7](../bericht/07-themen.md).

  ![Themenseite mit Themenkarte](../abbildungen/app_themen.png)

### Trends

![Trends für Notstand, Berufsverbot und Numerus](../abbildungen/nutzen_trends.png)

Die Trends zeigen, welcher Anteil der Flugblätter eines Jahres einen Begriff enthält. Exemplare desselben Flugblatts zählen einmal.

1. Bis zu vier Begriffe durch Komma getrennt eingeben, „Vergleichen“. Auch hier zählen Wortteile, Wörter in Anführungszeichen suchen eine feste Wortfolge.
2. „Jahr“ oder „Semester“ wählen. Jahre mit weniger als 20 Flugblättern sind mit dem folgenden zusammengefasst (im Bild 1967/68). Unter jedem Jahr steht die Zahl der Flugblätter (n).
3. Darunter steht, wie oft die Begriffe gemeinsam in einem Flugblatt vorkommen, und je Begriff ein Reiter mit den getroffenen Wortformen und dem Link „Alle … Flugblätter anzeigen“.

Die Kurven zeigen, was im Bestand liegt, nicht, wie viel damals diskutiert wurde. „So liest du diese Seite“ erklärt das in der App.

## Pflegen

Was Sie in der Anwendung korrigieren oder entscheiden, speichert sie in eigenen Dateien in `data/`, getrennt von den automatisch erzeugten Metadaten. Es bleibt deshalb erhalten, wenn die Datenbank neu aufgebaut oder ein Band neu eingelesen wird ([Installieren und betreiben › Sichern](installieren-und-betreiben.md#sichern)).

### Metadaten korrigieren

![Formular „Metadaten korrigieren“](../abbildungen/nutzen_korrigieren.png)

1. Auf der Seite des Flugblatts „Metadaten korrigieren“.
2. Felder ändern. Herausgeber wählen Sie aus dem Register („Organisation suchen …“). Fehlt eine Organisation, legen Sie sie über [Herausgeber zuordnen](#herausgeber-zuordnen) an.
3. Zu einer geänderten Angabe „Beleg wählen“ und die Textblöcke im Scan oder im erkannten Text anklicken. Ein zweiter Klick entfernt einen Block.
4. „Speichern“.

Geänderte Felder tragen danach den Hinweis „von Hand korrigiert“. „Alle Handkorrekturen entfernen“ stellt die automatisch erkannten Metadaten wieder her. Eine Korrektur gilt für das Flugblatt mit genau diesen Seiten. Ändert sich später die Trennung, erscheint sie unter [Korrekturen](#korrekturen) zum Prüfen.

Beim Import zeigt die App Flugblätter mit Prüfhinweisen. Auf ihrer Seite bestätigt „Passt so“, dass ein Hinweis keine Korrektur braucht.

### Mehrfachexemplare prüfen

Viele Flugblätter liegen in mehreren Exemplaren im Bestand. Die App hat Exemplare mit fast gleichem Text zu Gruppen zusammengefasst. Ungeprüft zählen sie in Trends und Statistiken mehrfach.

Verwaltung › „Mehrfachexemplare“ listet alle Gruppen mit ihrem Stand. „Ungeprüfte durchgehen →“ führt durch die offenen.

![Drei Exemplare eines Flugblatts aus Band 006 nebeneinander](../abbildungen/nutzen_exemplare.png)

1. Die Exemplare stehen nebeneinander, Abweichungen in den Metadaten sind farbig markiert. Ganz unten stehen Text und Scan der Exemplare im Vergleich.
2. Wählen Sie bei dem Exemplar mit den richtigsten Metadaten, dem besten Scan und dem vollständigsten Text „Hauptexemplar“. Es vertritt alle Exemplare in Liste, Trends und Export.
3. Gehört ein Blatt nicht zur Gruppe, haken Sie „gehört nicht dazu“ an. Sind es lauter verschiedene Flugblätter, „Das sind verschiedene Flugblätter“.
4. Unter „Gemeinsame Metadaten“ korrigieren Sie die Metadaten für alle Exemplare. Sagt ein anderes Exemplar etwas anderes, steht sein Wert darunter. „übernehmen“ setzt ihn ein.
5. „Speichern & weiter“ springt zur nächsten ungeprüften Gruppe.

„Prüfung zurücknehmen“ macht eine Gruppe wieder ungeprüft.

### Herausgeber zuordnen

Verwaltung › „Herausgeber zuordnen“ listet über alle freigegebenen Bände die Flugblätter, deren Herausgeber das Register noch nicht kennt („Offen“), und die ohne erkannten Herausgeber („Ohne Herausgeber“). Die Zuordnung funktioniert wie in Schritt 6 des Imports, siehe [Herausgeber zuordnen](neue-baende-importieren.md#herausgeber-zuordnen).

### Korrekturen

![Korrekturen als Tabelle](../abbildungen/nutzen_korrekturen.png)

Verwaltung › „Korrekturen“ zeigt alle Handkorrekturen: je Flugblatt das Feld, den automatisch erkannten und den korrigierten Wert und das Datum. Die Knöpfe oben filtern nach Feld, „Band“ nach Band. Ein Klick auf den Titel öffnet das Flugblatt, „← Korrekturen“ führt zurück.

Passt eine Korrektur oder Exemplar-Prüfung nicht mehr zu den Seiten, weil sich die Trennung geändert hat, steht sie hier getrennt. Sie lässt sich verwerfen oder für die neuen Seiten neu prüfen.

### Themen umbenennen

Verwaltung › „Themen“ › „Bearbeiten“ ändert den Titel eines Themas. Neue Bände ordnen Sie über [Themen zuordnen](neue-baende-importieren.md#themen-zuordnen) zu. Die Themen ganz neu zu berechnen, beschreibt [Installieren und betreiben](installieren-und-betreiben.md#themen-neu-berechnen).

### Exportieren

![Export mit Dateiliste und Optionen](../abbildungen/nutzen_export.png)

Verwaltung › „Datensatz exportieren“ lädt die freigegebenen Bände als ZIP. Die Dateien lassen sich ohne die Anwendung öffnen, die CSV-Dateien etwa in Excel. Entwürfe und Scans sind nicht dabei.

1. Bände wählen.
2. **Exemplare:** „Alle“ oder „Nur Hauptexemplare“, etwa zum Zählen.
3. **Personen:** „Mit Namen“ oder „Ohne Namen“. Ohne Namen fehlen die Unterzeichnenden in den Metadaten, im Volltext stehen sie weiterhin. Was das Archiv mit Namen weitergeben darf, ist noch zu klären [offen: Regeln des Archivs für Personennamen].
4. Unter „Zusätzlich“ auf Wunsch die Textblöcke jeder Scanseite mit ihrer Lage (`seiten.jsonl`).
5. „ZIP erstellen“.

Das ZIP enthält eine `README.md`, die jedes Feld erklärt. Die Felder beschreibt auch [Kapitel 9](../bericht/09-anwendung.md).
