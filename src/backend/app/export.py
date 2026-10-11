"""The released volumes as open files (JSONL, CSV, TXT) that can be read without the app.

    python -m app.export <ordner>      (in src/backend)
"""
import csv
import datetime
import io
import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from .database.models import RELEASED, Leaflet, LeafletIssuer, Organization, Page, Topic, Volume
from .database.session import session

LEAFLET_FIELDS = ['id', 'band', 'signatur', 'seiten', 'titel', 'titelart', 'datum', 'datum_wortlaut', 'datumsart',
                  'eingangsstempel', 'eingang_unsicher', 'reihe', 'nummer', 'dokumenttyp', 'herausgeber',
                  'unterzeichnende', 'thema', 'thema_unsicher', 'hauptexemplar', 'korrigiert']


def leaflet_key(volume, leaflet):
    """Stays the same when the database is rebuilt, unlike the number in the app's address."""
    pages = leaflet.start_page if leaflet.start_page == leaflet.end_page else f"{leaflet.start_page}-{leaflet.end_page}"
    return f"{volume.stem}_S{pages}"


def table(rows, fields):
    """CSV with BOM so that Excel reads the umlauts; lists become "a; b"."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows({k: '; '.join(v) if isinstance(v, list) else v for k, v in row.items()} for row in rows)
    return '﻿' + out.getvalue()


def jsonl(rows):
    return ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows)


def files(bands=None, main_only=False, persons=True, pages=True, only=None, link=''):
    """{file name: content} of the export: the released volumes (or those of `bands` among them), only the main copies,
    without the signatories (all of them persons), without seiten.jsonl. `only`: these leaflet ids in this order (a list
    of the app); `link`: the app's address, for a column with the link to each leaflet."""
    query = session.query(Volume).filter_by(status=RELEASED).order_by(Volume.vz)
    volumes = {v.id: v for v in (query.filter(Volume.vz.in_(bands)) if bands else query)}
    every = {l.id: l for l in session.query(Leaflet)}
    leaflets = sorted((l for l in every.values() if l.volume_id in volumes
                       and not (main_only and l.canonical_leaflet_id not in (None, l.id))),
                      key=lambda l: (volumes[l.volume_id].vz, l.start_page))
    if only is not None:
        position = {leaflet_id: n for n, leaflet_id in enumerate(only)}
        leaflets = sorted((l for l in leaflets if l.id in position), key=lambda l: position[l.id])
    keys = {l.id: leaflet_key(volumes[l.volume_id], l) for l in leaflets}
    orgs = {o.id: o for o in session.query(Organization)}
    topics = {t.id: t for t in session.query(Topic)}
    texts = defaultdict(list)
    for leaflet_id, text in (session.query(Page.leaflet_id, Page.text).filter(Page.leaflet_id.in_(keys))
                             .order_by(Page.volume_id, Page.page_no)):
        if text:
            texts[leaflet_id].append(text)
    issuers = defaultdict(list)
    for i in session.query(LeafletIssuer).filter(LeafletIssuer.leaflet_id.in_(keys)).order_by(LeafletIssuer.id):
        if persons or i.role != 'signatory':
            issuers[i.leaflet_id].append(i)

    def name(i):
        return (orgs[i.org_id].full_name or orgs[i.org_id].name) if i.org_id in orgs else i.surface

    records = []
    for l in leaflets:
        v, main = volumes[l.volume_id], every.get(l.canonical_leaflet_id)
        records.append({
            'id': keys[l.id], 'band': v.vz, 'signatur': v.signature,
            'seiten': f"{l.start_page}-{l.end_page}", 'titel': l.display_title, 'titelart': l.title_type,
            'datum': l.date_iso, 'datum_wortlaut': l.date_text, 'datumsart': l.date_type,
            'eingangsstempel': l.received_date, 'eingang_unsicher': bool(l.received_uncertain),
            'reihe': l.series, 'nummer': l.issue, 'dokumenttyp': l.doc_type,
            'herausgeber': list(dict.fromkeys(name(i) for i in issuers[l.id] if i.role == 'issuer')),
            'unterzeichnende': list(dict.fromkeys(name(i) for i in issuers[l.id] if i.role == 'signatory')),
            'thema': topics[l.topic_id].title if l.topic_id in topics else '', 'thema_unsicher': bool(l.topic_uncertain),
            # copies of one leaflet point to the same main copy; a copy in an unreleased volume keeps its key
            'hauptexemplar': leaflet_key(session.get(Volume, main.volume_id), main) if main else '',
            'korrigiert': l.corrected or [],
            'text': '\n\n'.join(texts[l.id]),
            **({'link': f"{link}/leaflets/{l.id}"} if link else {}),
        })

    released = {v.vz for v in volumes.values()}
    count = Counter(l.volume_id for l in leaflets)
    out = {
        'flugblaetter.jsonl': jsonl(records),
        'flugblaetter.csv': table(records, LEAFLET_FIELDS + (['link'] if link else [])),
        'flugblatt_herausgeber.csv': table(
            [{'flugblatt': keys[l], 'rolle': 'herausgeber' if i.role == 'issuer' else 'unterzeichnend',
              'herausgeber_id': i.org_id or '', 'name': name(i), 'wortlaut': i.surface, 'funktion': i.function,
              'beleg': i.quote} for l in keys for i in issuers[l]],
            ['flugblatt', 'rolle', 'herausgeber_id', 'name', 'wortlaut', 'funktion', 'beleg']),
        'herausgeber.csv': table(
            [{'id': o.id, 'name': o.name, 'voller_name': o.full_name, 'typ': o.type,
              'varianten': o.variants or [], 'jahre': [str(j) for j in o.jahre or []],
              'baende': [str(n) for n in o.vz or [] if n in released], 'notiz': o.notes} for o in orgs.values()],
            ['id', 'name', 'voller_name', 'typ', 'varianten', 'jahre', 'baende', 'notiz']),
        'baende.csv': table(
            [{'band': v.vz, 'signatur': v.signature, 'titel': v.title, 'jahr': v.year, 'gruppe': v.group,
              'archivportal': v.portal_url, 'datei': v.stem, 'seiten': v.n_pages, 'flugblaetter': count[v.id],
              'ocr_modus': v.ocr_mode, 'ocr_datum': v.ocr_created, 'metadaten_modell': v.meta_model,
              'metadaten_datum': v.meta_created} for v in volumes.values()],
            ['band', 'signatur', 'titel', 'jahr', 'gruppe', 'archivportal', 'datei', 'seiten', 'flugblaetter',
             'ocr_modus', 'ocr_datum', 'metadaten_modell', 'metadaten_datum']),
        'themen.csv': table([{'id': t.id, 'titel': t.title, 'quelle': t.source, 'woerter': t.words}
                             for t in topics.values()], ['id', 'titel', 'quelle', 'woerter']),
        'README.md': readme(len(volumes), len(records), main_only, persons, pages),
    }
    if pages:
        all_pages = session.query(Page).filter(Page.volume_id.in_(volumes)).order_by(Page.volume_id, Page.page_no)
        out['seiten.jsonl'] = jsonl({'band': volumes[p.volume_id].vz, 'seite': p.page_no, 'flugblatt': keys.get(p.leaflet_id),
                                     'text': p.text, 'bloecke': p.blocks} for p in all_pages)
    out.update({f"texte/{r['id']}.txt": r['text'] for r in records})
    return out


def readme(n_volumes, n_leaflets, main_only, persons, pages):
    left_out = [part for part, out in (('Weitere Exemplare (nur Hauptexemplare)', main_only),
                                       ('Namen der Unterzeichnenden (im Volltext stehen sie weiter)', not persons),
                                       ('`seiten.jsonl`', not pages)) if out]
    return f"""# Flugblätter der Universität Regensburg (Rep. 118)

Export vom {datetime.date.today():%d.%m.%Y}: {n_volumes} freigegebene Bände, {n_leaflets} Flugblätter.
{'Weggelassen: ' + ', '.join(left_out) + '.' if left_out else ''}

## Dateien

- `flugblaetter.jsonl`: eine Zeile (JSON) pro Flugblatt, alle Angaben und der Volltext (`text`).
- `flugblaetter.csv`: dieselben Angaben ohne Volltext, mehrere Werte durch `; ` getrennt.
- `texte/<id>.txt`: der Volltext jedes Flugblatts als einzelne Datei.
- `flugblatt_herausgeber.csv`: Herausgeber und Unterzeichnende je Flugblatt, mit Wortlaut und Beleg aus dem Text.
- `herausgeber.csv`: das Register der Herausgeber (`id` wie in `herausgeber_id`, GND-Nummer, Namensvarianten).
- `baende.csv`: die Archivbände mit Signatur, Link ins Archivportal-D und den Läufen von Texterkennung und Metadaten.
- `themen.csv`: die Themen aus dem Topic Modelling mit ihren Schlagwörtern.
- `seiten.jsonl`: jede Seite mit Text und Textblöcken (`box`: x, y, Breite, Höhe in Prozent der Seite; `html`).
  Seiten ohne `flugblatt` sind Trenn- oder Leerseiten.

## Felder in `flugblaetter`

- `id`: Datei des Bandes und Seiten (`0118_0003_S127-128`); bleibt bei späteren Exporten gleich, solange die Seitengrenzen bleiben.
- `datum`: ISO-Datum, so genau wie bekannt (`1968`, `1968-05`, `1968-05-14`); `datum_wortlaut` wie im Text.
- `hauptexemplar`: bei weiteren Exemplaren die `id` des Hauptexemplars, sonst leer.
- `korrigiert`: die von Hand geprüften Felder. Alle anderen Angaben hat ein Sprachmodell aus dem OCR-Text erzeugt.

## Grenzen

- Der Text stammt aus automatischer Texterkennung (Datalab) und enthält Lesefehler, besonders bei Handschrift und schlechten Kopien.
- Titel, Datum, Herausgeber und Thema sind größtenteils automatisch erzeugt und nicht einzeln geprüft (siehe `korrigiert`).
- Die Grenzen zwischen Flugblättern wurden automatisch gezogen und stichprobenartig geprüft.

## Einlesen

```python
import pandas as pd
df = pd.read_json("flugblaetter.jsonl", lines=True)
```
"""


def zip_bytes(**options):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, content in files(**options).items():
            z.writestr(f"flugblaetter-export/{name}", content)
    return buffer.getvalue()


if __name__ == '__main__':
    target = Path(sys.argv[1] if len(sys.argv) > 1 else 'flugblaetter-export')
    for name, content in files().items():
        (target / name).parent.mkdir(parents=True, exist_ok=True)
        (target / name).write_text(content, encoding='utf-8')
    print(f"{target}: {len(list(target.rglob('*')))} Dateien")
