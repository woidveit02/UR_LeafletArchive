# Installieren und betreiben

## Installation

Die Anwendung läuft in Docker. Sie brauchen Docker mit Docker Compose (unter Windows und macOS Docker Desktop, unter Linux Docker Engine mit dem Compose-Plugin) und den Ordner `UR_LeafletArchive_data` mit Scans und Texterkennung. Die Schritte für Windows, macOS und Linux stehen in der README im Hauptverzeichnis des Repositorys unter „Schnellstart“. Kurz:

```
Flugblattsammlung/
├── UR_LeafletArchive/         der Code
└── UR_LeafletArchive_data/    Scans und Texterkennung
```

```bash
cd UR_LeafletArchive
docker compose up -d
```

Liegt der Datenordner wie oben neben dem Repository, ist keine `.env` nötig. Der erste Start baut das Image (etwa 1,5 GB, 10 bis 20 Minuten), legt die Datenbank an und rendert im Hintergrund die Vorschaubilder. Danach ist die Anwendung unter http://localhost:8000/ erreichbar. In der Ausgabe von `docker compose logs backend` muss „Data folder ok“ stehen; sonst nennt die Meldung, was am Pfad nicht stimmt.

Das Image wird für Intel- und AMD-Prozessoren gebaut (`platform: linux/amd64` in `docker-compose.yml`), weil das Paket `hdbscan` für ARM nicht fertig gebaut vorliegt. Auf einem Mac mit Apple-Chip emuliert Docker Desktop es; das funktioniert, ist aber langsamer.

Nach einem Update des Repositorys: Haben sich `Dockerfile`, `requirements.txt` oder die Dokumentation in `docs/` geändert, mit `docker compose up -d --build` neu bauen. Die Dokumentation wird dabei ins Image gebaut und ist in der Anwendung unter http://localhost:8000/doku/ erreichbar. Zum Löschen der Datenbank siehe [Sichern](#sichern).

## Konfiguration

Alle Einstellungen stehen in `.env`. Für den Normalfall braucht es die Datei nicht; die Vorlage `.env.example` erklärt jede Zeile.

| Eintrag | Pflicht | Wofür |
|---|---|---|
| `LEAFLET_PDF_HOST_DIR` | nein | Pfad zum Datenordner, darin je Band ein Ordner wie „Nr. 002 (1968)“. Ohne Eintrag gilt `UR_LeafletArchive_data` neben dem Repository. Unter Windows mit Schrägstrichen: `C:/Users/Name/UR_LeafletArchive_data`. Stimmt der Pfad nicht, startet die Anwendung ohne Scans und Text und zeigt oben auf jeder Seite einen Hinweis. |
| `DATALAB_API_KEY` | nur für den Import | Texterkennung (Schritt 3) |
| `OPENROUTER_API_KEY` | nur für den Import | Metadaten (Schritt 5), Themen |
| `LEAFLET_BIND` | nein | `0.0.0.0` macht die Anwendung im ganzen Netz erreichbar, siehe [Kurz im lokalen Netz zeigen](#kurz-im-lokalen-netz-zeigen) |

Die API-Keys lassen sich auch unter Verwaltung › API-Keys eintragen, ändern und entfernen. Ein API-Key in `.env` hat Vorrang vor einem dort gespeicherten. Fehlt ein API-Key, läuft alles außer dem jeweiligen Importschritt; dessen Startknopf bleibt grau.

## Zugriff und Betrieb auf einem Server

Die Anwendung hat keine eigene Anmeldung. Wer sie im Browser erreicht, kann Metadaten ändern, Bände löschen, kostenpflichtige OCR- und Metadatenläufe starten und den vollständigen Export mit Personennamen laden. Deshalb ist sie standardmäßig nur auf dem Rechner selbst erreichbar (`docker-compose.yml` bindet den Port an `127.0.0.1`).

### Auf einem Server des Archivs

Voraussetzungen, von der IT zu klären: ein Server mit Docker, ein Rechnername im Uni-Netz (im Beispiel `flugblaetter.example.uni-regensburg.de`) und ein Zertifikat dafür. Wer die Anwendung nutzen darf, legt das Archiv fest. [offen: Regeln des Archivs für Zugriff und Personennamen]

1. Starten Sie die Anwendung wie in der README im Hauptverzeichnis des Repositorys unter „Schnellstart“ beschrieben. Ändern Sie die Portbindung nicht: Die Anwendung bleibt nur für den Server selbst erreichbar.
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
5. Laden Sie die Konfiguration von Caddy neu: `systemctl reload caddy`.

Die Anwendung startet nach einem Neustart des Servers von selbst (`restart: unless-stopped`), sobald Docker läuft. Wer sie mit `docker compose stop` anhält, muss sie auch wieder selbst starten.

Ergebnis: `https://flugblaetter.example.uni-regensburg.de` fragt nach Benutzername und Passwort. Von einem anderen Rechner aus antwortet `http://<Server>:8000` nicht.

Das Passwort schützt die ganze Anwendung, auch das Lesen. Getrennte Rechte für Lesen und Bearbeiten gibt es noch nicht. Setzen Sie zusätzlich bei Datalab und OpenRouter ein Ausgabenlimit für die hinterlegten API-Keys.

### Kurz im lokalen Netz zeigen

Für eine Vorführung im eigenen Netz tragen Sie in `.env` die Zeile `LEAFLET_BIND=0.0.0.0` ein und starten mit `docker compose up -d`. Danach ist die Anwendung für alle im Netz ohne Passwort erreichbar. Löschen Sie die Zeile nach der Vorführung und starten Sie erneut mit `docker compose up -d`.

## Sichern

Was die Anwendung weiß, liegt in Dateien an zwei Orten. Sichern Sie beide regelmäßig, mindestens nach jedem Import und jeder größeren Runde von Korrekturen.

| Ort | Inhalt | Wenn er verloren geht |
|---|---|---|
| `data/` im Repository | Metadaten je Band (`nr001_metadata.json` …), Register der Herausgeber (`organizations.json`), Themen (`topics.json`, `topic_map.json`), Handkorrekturen (`corrections.jsonl`), geprüfte Exemplare (`copy_decisions.jsonl`), bestätigte Hinweise und Entscheidungen zu Herausgebern (`checked.jsonl`), ein geänderter Prompt (`metadata_prompt.txt`), Embeddings | Die `.jsonl`-Dateien und die Ergänzungen im Register sind Handarbeit und lassen sich nicht wiederherstellen. Metadaten und Embeddings kosten neu. |
| Datenordner (`UR_LeafletArchive_data`) | Scans, Texterkennung je Band, Trennung (`*.segments.json`), in der Verwaltung gespeicherte API-Keys (`.datalab-key`, `.openrouter-key`) | Die Texterkennung kostet neu, die Trennung ist Handarbeit. Die Ordner `.thumbs` und `.ngrams` müssen nicht gesichert werden, sie entstehen von selbst neu. |

Die Datenbank `src/backend/leaflet_database.db` ist ein Abbild von `data/`. Beim Start legt die Anwendung fehlende Tabellen und Spalten an. Fehlt die Datenbank, baut sie sie aus `data/` neu auf; eine vorhandene bleibt, wie sie ist. Nach Änderungen an `data/` von außen, etwa durch ein Update des Repositorys, löschen Sie sie deshalb und starten neu:

```bash
rm src/backend/leaflet_database.db      # Windows: del src\backend\leaflet_database.db
docker compose restart
```

Ob ein Band Entwurf oder freigegeben ist, steht auch in `data/volumes.json` (`"status": "entwurf"`). Ein Neuaufbau übernimmt es, ein Entwurf bleibt also Entwurf. Den Fortschritt eines laufenden Imports (Texterkennung, Trennung) hält der Datenordner fest. Starten Sie den Neuaufbau trotzdem nicht, während ein Importschritt läuft.

## Themen neu berechnen

Unter Verwaltung › Themen › „Themen neu berechnen“. Braucht den OpenRouter-Key; die Berechnung läuft einige Minuten im Hintergrund. Auf der Seite Verwaltung › Themen lassen sich außerdem die Titel der jetzigen Themen ändern („Bearbeiten“).

1. Höchstzahl der Themen und Sprachmodell für die Titel wählen, „Themen neu berechnen“. Voreingestellt sind die Zahl der jetzigen Themen und das Modell der bisherigen Titel. Die geschätzten Kosten stehen beim Modell. Die Ähnlichkeit berechnet immer bge-m3.
2. Das Ergebnis liegt als `data/topics.kandidat.json` und `data/topic_map.kandidat.json` neben den bisherigen Dateien und ist noch nicht in Gebrauch.
3. Auf der Prüfseite die Titel durchgehen. In den Feldern stehen die Vorschläge des Sprachmodells. Je Thema steht darunter, aus welchem bisherigen Thema die meisten Flugblätter stammen; „… Flugblätter“ öffnet sie in der Flugblattliste.
4. „Neue Einteilung übernehmen“ ersetzt `topics.json` und `topic_map.json`; die alten Dateien bleiben als `topics.bis-<Zeit>.json` und `topic_map.bis-<Zeit>.json`. „Neuberechnung verwerfen“ löscht nur den Kandidaten.
5. Entwürfe danach mit „Themen zuordnen“ neu zuordnen.

Fehlt das bisherige Titelmodell bei OpenRouter, ist das stärkste Modell vorausgewählt, das für den Lauf höchstens etwa 0,10 $ kostet. Scheitern zu viele Titelanfragen, bricht der Lauf ab, statt Schlüsselwörter als Titel zu liefern.

Die Embeddings speichert die Anwendung in `data/embeddings.bge-m3.npz`; ein zweiter Lauf fragt nur neue Texte an. Das Image enthält dafür BERTopic, UMAP, HDBSCAN und das spaCy-Modell `de_core_news_lg` und ist dadurch etwa 1,5 GB groß.

## Kosten

Kosten entstehen nur beim Import und beim Neuberechnen der Themen. Lesen, Suchen, Korrigieren und Exportieren kosten nichts. Beide Dienste rechnen in Dollar über das Konto ab, zu dem der API-Key gehört.

| Posten | Dienst | Kosten | Grundlage |
|---|---|---|---|
| Texterkennung, Stufe „Genau“ | Datalab | 1,00 $ je 100 Seiten | Preisliste vom 7.10.2026, am Testimport bestätigt (230 Seiten: 2,30 $) |
| Texterkennung, Stufe „Günstig“ | Datalab | 0,40 $ je 100 Seiten | Preisliste |
| Metadaten, Claude Sonnet 4.5 | OpenRouter | etwa 0,90 $ je 100 Seiten | Testimport (230 Seiten, 83 Flugblätter: 2,11 $) |
| Themen zuordnen | OpenRouter | unter 1 Cent je Band, beim ersten Mal etwa 2 Cent | |
| Themen neu berechnen | OpenRouter | höchstens etwa 0,10 $ für die Titel, dazu Embeddings neuer Texte | |

Ein Band mit 300 Seiten kostet damit etwa 6 $. Vor jedem kostenpflichtigen Schritt zeigt die Anwendung den geschätzten Preis. Was das Projekt für die Bände 1 bis 14 bezahlt hat, steht in den [Kennzahlen](../kennzahlen.md#kosten).
