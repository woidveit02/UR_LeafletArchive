
# Neuen Band einlesen

<!-- Anleitung für Personen ohne technische Vorkenntnisse. Je Schritt: was man sieht, was man tut,
     worauf man achtet, was es kostet. Screenshots nach abbildungen/. Quelle: arbeitsdokumente/import-plan.md. -->

## Voraussetzungen

<!-- Anwendung läuft, API-Schlüssel eingetragen (siehe betrieb.md), Scans liegen als PDF oder TIFF vor. -->

## 1. Band anlegen

<!-- Nummer, Jahr, Titel, Signatur, Portal-Link. -->

## 2. Scans hochladen

<!-- PDF oder TIFF-Ordner; TIFFs werden zu einem PDF zusammengefügt. -->

## 3. Text erkennen (OCR)

<!-- Kostenanzeige vor dem Start, Fortschritt, Fortsetzen nach Abbruch. -->

## 4. Flugblätter trennen

<!-- Vorschlag ansehen, Schnitte prüfen und korrigieren. Regeln für mehrseitige Hefte und Rückseiten: Bericht 4.2. -->

## 5. Metadaten erzeugen

<!-- Titel, Datum, Herausgeber, Reihe; Abgleich mit der Normdatei; Prüfliste. -->

## 6. Prüfen & freigeben

<!-- Bis zur Freigabe ist der Band ein Entwurf und in Liste, Suche und Trends unsichtbar. -->

## 7. Themen zuordnen

Optional, auch nach der Freigabe. „Themen zuordnen“ gibt jedem Flugblatt das Thema, das unter seinen fünf ähnlichsten Flugblättern überwiegt, und einen Punkt auf der Themenkarte. Braucht den OpenRouter-Key; kostet weniger als einen Cent je Band. Beim ersten Mal holt die App auch die Embeddings aller freigegebenen Flugblätter (etwa 2 Cent, einige Minuten).

Danach zeigt der Schritt eine Tabelle der Themen mit der Zahl der Flugblätter und der unsicheren, darunter die unsicher zugeordneten Flugblätter mit Link. Neue Themen entstehen hier nicht. Unter Verwaltung › Themen ist vermerkt, dass der Band nachträglich zugeordnet wurde; nach mehreren neuen Bänden lohnt es sich, die Themen neu zu berechnen (Handbuch Betrieb).

## Ohne Weboberfläche

Jeder Schritt lässt sich auch in der Kommandozeile ausführen, im laufenden Container:

```bash
docker compose exec backend python -m app.cli --help
docker compose exec backend python -m app.cli trennen --help   # Optionen eines Schritts
```

Ein ganzer Band, hier Nr. 16. Die Dateien müssen im Container liegen, etwa im Scan-Ordner `/data/pdfs`:

```bash
docker compose exec backend python -m app.cli band 16
docker compose exec backend python -m app.cli scans 16 /data/pdfs/neu/0118_0016.pdf
docker compose exec backend python -m app.cli ocr 16                       # --stufe balanced, --zip ERGEBNIS.zip
docker compose exec backend python -m app.cli trennen 16 --vorschlag       # oder --liste /data/pdfs/neu/liste.txt
docker compose exec backend python -m app.cli trennen 16                   # gespeicherte Trennungen bestätigen
docker compose exec backend python -m app.cli angaben 16                   # --modell anthropic/claude-sonnet-4.5
docker compose exec backend python -m app.cli anlegen 16
docker compose exec backend python -m app.cli freigeben 16
docker compose exec backend python -m app.cli themen 16
docker compose exec backend python -m app.cli status
```

Die Befehle prüfen dasselbe wie die App und nennen vor kostenpflichtigen Schritten den geschätzten Preis. Laufende Schritte zeigen ihren Fortschritt; Strg+C hält Texterkennung und Metadaten nach dem laufenden Teil an, fertige Teile bleiben erhalten. `themen-neu`, `themen-uebernehmen` und `themen-verwerfen` entsprechen „Themen neu berechnen“ unter Verwaltung › Themen; übernommen werden dabei die Titel des Sprachmodells, umbenennen lassen sie sich danach in der App.

Ohne Weboberfläche bleiben die Durchsicht der Trennungen am Bild, die Prüfhinweise und neue Herausgeber in Schritt 6. Die App weiß nichts von einem Lauf in der Kommandozeile: Denselben Band nicht gleichzeitig in beiden bearbeiten. Zeigt die App danach einen alten Stand, hilft `docker compose restart backend`.

## Wenn etwas schiefgeht

<!-- Unterbrochene Schritte fortsetzen, fehlende Schlüssel, Kosten. -->
