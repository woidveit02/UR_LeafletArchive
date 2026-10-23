# Installation und Betrieb

## Installation

Die Anwendung läuft in Docker. Sie brauchen Docker mit Docker Compose (unter Windows und macOS Docker Desktop, unter Linux Docker Engine mit dem Compose-Plugin) und den Ordner `UR_LeafletArchive_data` mit Scans und Texterkennung. Die Schritte für Windows, macOS und Linux stehen in der README im Hauptverzeichnis des Repositorys unter „Schnellstart“. Kurz:

```
Flugblattsammlung/
├── UR_LeafletArchive/         der Code
└── UR_LeafletArchive_data/    Scans und Texterkennung
```

```bash
cd UR_LeafletArchive
docker compose up --build -d
```

Liegt der Datenordner wie oben neben dem Repository, ist keine `.env` nötig. Der erste Start baut das Image (etwa 1,5 GB, 10 bis 20 Minuten), legt die Datenbank an und rendert im Hintergrund die Vorschaubilder. Danach ist die Anwendung unter http://localhost:8000/ erreichbar. In der Ausgabe von `docker compose logs backend` muss „Data folder ok“ stehen; sonst nennt die Meldung, was am Pfad nicht stimmt.

Das Image wird für Intel- und AMD-Prozessoren gebaut (`platform: linux/amd64` in `docker-compose.yml`), weil das Paket `hdbscan` für ARM nicht fertig gebaut vorliegt. Auf einem Mac mit Apple-Chip emuliert Docker Desktop es; das funktioniert, ist aber langsamer.

Nach einem Update des Repositorys: Haben sich `Dockerfile`, `requirements.txt` oder die Dokumentation in `docs/` geändert, mit `docker compose up --build -d` neu bauen. Die Dokumentation wird dabei ins Image gebaut und ist in der Anwendung unter http://localhost:8000/doku/ erreichbar. Zum Löschen der Datenbank siehe [Datensicherung](#datensicherung).

## Konfiguration

Alle Einstellungen stehen in `.env`. Für den Normalfall braucht es die Datei nicht; die Vorlage `.env.example` erklärt jede Zeile.

| Eintrag | Pflicht | Wofür |
|---|---|---|
| `LEAFLET_PDF_HOST_DIR` | nein | Pfad zum Datenordner, darin je Band ein Ordner wie „Nr. 002 (1968)“. Ohne Eintrag gilt `UR_LeafletArchive_data` neben dem Repository. Unter Windows mit Schrägstrichen: `C:/Users/Name/UR_LeafletArchive_data`. Stimmt der Pfad nicht, startet die Anwendung ohne Scans und Text und zeigt oben auf jeder Seite einen Hinweis. |
| `DATALAB_API_KEY` | nur für den Import | Texterkennung (Schritt 3) |
| `OPENROUTER_API_KEY` | nur für den Import | Metadaten (Schritt 5), Themen |
| `LEAFLET_BIND` | nein | `0.0.0.0` macht die Anwendung im ganzen Netz erreichbar, siehe [Im lokalen Netz](#im-lokalen-netz) |

Die API-Keys lassen sich auch unter Verwaltung › API-Keys eintragen, ändern und entfernen. Ein API-Key in `.env` hat Vorrang vor einem dort gespeicherten. Fehlt ein API-Key, läuft alles außer dem jeweiligen Importschritt; dessen Startknopf bleibt grau.

## Betrieb auf einem Server

Die Anwendung hat keine eigene Anmeldung. Wer sie im Browser erreicht, kann Metadaten ändern, Bände löschen, kostenpflichtige OCR- und Metadatenläufe starten und den vollständigen Export mit Personennamen laden. Deshalb ist sie standardmäßig nur auf dem Rechner selbst erreichbar (`docker-compose.yml` bindet den Port an `127.0.0.1`).

### Auf einem Server des Archivs

Diese Anleitung haben wir nicht auf einem Server des Archivs erprobt. Sie beschreibt das übliche Vorgehen mit dem Webserver Caddy. Welche Lösung das Rechenzentrum einsetzt, klärt das Archiv mit ihm (Kap. 9.7 des Berichts).

Voraussetzungen, die das Archiv mit dem Rechenzentrum klärt: ein Server mit Docker, ein Rechnername im Uni-Netz und ein Zertifikat dafür. Im Beispiel heißt der Rechner `flugblaetter.example.uni-regensburg.de`; setzen Sie den tatsächlichen Namen ein. Wer die Anwendung nutzen darf, legt das Archiv fest. Nach Auskunft des Universitätsarchivs (Dr. Andreas Becker, Oktober 2026) dürfen Korpus und Metadaten öffentlich zugänglich sein, auch mit den Namen von Personen. Das Passwort schützt deshalb vor allem die Pflege: Wer die Anwendung erreicht, kann auch ändern.

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

Prüfen Sie danach zweierlei: `https://<Rechnername>` muss nach Benutzername und Passwort fragen, und von einem anderen Rechner aus darf `http://<Server>:8000` nicht antworten. Antwortet die Anwendung dort, ist die Portbindung geändert worden (Schritt 1).

Die Anwendung startet nach einem Neustart des Servers von selbst (`restart: unless-stopped`), sobald Docker läuft. Wer sie mit `docker compose stop` anhält, muss sie auch wieder selbst starten.

Das Passwort schützt die ganze Anwendung, auch das Lesen. Getrennte Rechte für Lesen und Bearbeiten gibt es noch nicht. Setzen Sie zusätzlich bei Datalab und OpenRouter ein Ausgabenlimit für die hinterlegten API-Keys.

### Im lokalen Netz

Für eine Vorführung im eigenen Netz tragen Sie in `.env` die Zeile `LEAFLET_BIND=0.0.0.0` ein und starten mit `docker compose up -d`. Danach ist die Anwendung für alle im Netz ohne Passwort erreichbar. Löschen Sie die Zeile nach der Vorführung und starten Sie erneut mit `docker compose up -d`.

## Datensicherung

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
