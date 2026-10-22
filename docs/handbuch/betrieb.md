
# Betrieb

## Installation

<!-- Docker, Docker Compose, erster Start. -->

## Konfiguration

<!-- .env: Pfade zu PDFs und OCR-Daten, DATALAB_API_KEY, OPENROUTER_API_KEY.
     Was passiert, wenn ein Schlüssel fehlt. -->

Die API-Keys für Datalab (Texterkennung) und OpenRouter (Metadaten, Themen) lassen sich unter Verwaltung › API-Keys eintragen, ändern und entfernen. Ein Schlüssel in `.env` hat Vorrang vor einem dort gespeicherten.

## Zugriff und Betrieb auf einem Server

Die Anwendung hat keine eigene Anmeldung. Wer sie im Browser erreicht, kann Angaben ändern, Bände löschen, kostenpflichtige OCR- und Metadatenläufe starten und den vollständigen Export mit Personennamen laden. Deshalb ist sie standardmäßig nur auf dem Rechner selbst erreichbar (`docker-compose.yml` bindet den Port an `127.0.0.1`).

### Auf einem Server des Archivs

Voraussetzungen, von der IT zu klären: ein Server mit Docker, ein Rechnername im Uni-Netz (im Beispiel `flugblaetter.example.uni-regensburg.de`) und ein Zertifikat dafür. Wer die Anwendung nutzen darf, legt das Archiv fest. [offen: Regeln des Archivs für Zugriff und Personennamen]

1. Starten Sie die Anwendung wie im [README](../../README.md) unter „Schnellstart“ beschrieben. Ändern Sie die Portbindung nicht: Die Anwendung bleibt nur für den Server selbst erreichbar.
2. Installieren Sie auf dem Server den Webserver [Caddy](https://caddyserver.com/docs/install). Er nimmt die Anfragen von außen an, verlangt ein Passwort und reicht sie an die Anwendung weiter.
3. Erzeugen Sie den Hash für das Passwort: `caddy hash-password`.
4. Legen Sie die Datei `/etc/caddy/Caddyfile` an:

   ```
   flugblaetter.example.uni-regensburg.de {
       tls /etc/caddy/zertifikat.pem /etc/caddy/schluessel.pem
       basic_auth {
           archiv <Hash aus Schritt 3>
       }
       reverse_proxy 127.0.0.1:8000
   }
   ```

   Ist der Server aus dem Internet erreichbar, kann die Zeile `tls …` entfallen. Caddy holt das Zertifikat dann selbst.
5. Starten Sie Caddy neu: `systemctl reload caddy`.

Die Anwendung startet nach einem Neustart des Servers von selbst (`restart: unless-stopped`), sobald Docker läuft. Wer sie mit `docker compose stop` anhält, muss sie auch wieder selbst starten.

Ergebnis: `https://flugblaetter.example.uni-regensburg.de` fragt nach Benutzername und Passwort. Von einem anderen Rechner aus antwortet `http://<Server>:8000` nicht.

Das Passwort schützt die ganze Anwendung, auch das Lesen. Getrennte Rechte für Lesen und Bearbeiten gibt es noch nicht. Setzen Sie zusätzlich bei Datalab und OpenRouter ein Ausgabenlimit für die hinterlegten Schlüssel.

### Kurz im lokalen Netz zeigen

Für eine Vorführung im eigenen Netz tragen Sie in `.env` die Zeile `LEAFLET_BIND=0.0.0.0` ein und starten mit `docker compose up -d`. Danach ist die Anwendung für alle im Netz ohne Passwort erreichbar. Löschen Sie die Zeile nach der Vorführung und starten Sie erneut mit `docker compose up -d`.

## Datenbank

<!-- Migration beim Start, keine Neuerstellung; Sicherung. -->

## Tests

<!-- Tests laufen nur gegen die Testdatenbank (Umgebungsvariable), nie gegen die echte. -->

## Themen neu berechnen

Unter Verwaltung › Themen › „Themen neu berechnen“. Braucht den OpenRouter-Key; die Berechnung läuft einige Minuten im Hintergrund. Auf der Seite Verwaltung › Themen lassen sich außerdem die Titel der jetzigen Themen ändern („Bearbeiten“).

1. Höchstzahl der Themen und Sprachmodell für die Titel wählen, „Themen neu berechnen“. Voreingestellt sind die Zahl der jetzigen Themen und das Modell der bisherigen Titel. Die geschätzten Kosten stehen beim Modell. Die Ähnlichkeit berechnet immer bge-m3.
2. Das Ergebnis liegt als `data/topics.kandidat.json` und `data/topic_map.kandidat.json` neben den bisherigen Dateien und ist noch nicht in Gebrauch.
3. Auf der Prüfseite die Titel durchgehen. In den Feldern stehen die Vorschläge des Sprachmodells. Je Thema steht darunter, aus welchem bisherigen Thema die meisten Flugblätter stammen; „… Flugblätter“ öffnet sie in der Flugblattliste.
4. „Neue Einteilung übernehmen“ ersetzt `topics.json` und `topic_map.json`; die alten Dateien bleiben als `topics.bis-<Zeit>.json` und `topic_map.bis-<Zeit>.json`. „Neuberechnung verwerfen“ löscht nur den Kandidaten.
5. Entwürfe danach in Schritt 7 neu zuordnen.

Fehlt das bisherige Titelmodell bei OpenRouter, ist das stärkste Modell vorausgewählt, das für den Lauf höchstens etwa 0,10 $ kostet. Scheitern zu viele Titelanfragen, bricht der Lauf ab, statt Schlüsselwörter als Titel zu liefern.

Die Embeddings speichert die Anwendung in `data/embeddings.bge-m3.npz`; ein zweiter Lauf fragt nur neue Texte an. Das Image enthält dafür BERTopic, UMAP, HDBSCAN und das spaCy-Modell `de_core_news_lg` und ist dadurch etwa 1,5 GB groß.

## Kosten

<!-- OCR und LLM je Band; Verweis auf kennzahlen.md. -->
