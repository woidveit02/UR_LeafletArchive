import csv
import io
import json

import pytest

from backend.app import export
from backend.app.database.models import RELEASED, Leaflet, Volume
from backend.app.database.session import session


@pytest.mark.built_db
def test_export_reads_back():
    """Only reads the database: every released leaflet once, with its text, in each file."""
    released = session.query(Leaflet).join(Volume, Leaflet.volume_id == Volume.id).filter(Volume.status == RELEASED).count()
    if not released:
        pytest.skip("no released volume in the database")
    files = export.files(pages=True)
    records = [json.loads(line) for line in files['flugblaetter.jsonl'].splitlines()]
    rows = list(csv.DictReader(io.StringIO(files['flugblaetter.csv'].lstrip('﻿'))))
    assert len(records) == len(rows) == released
    assert len({r['id'] for r in records}) == released
    assert [r['id'] for r in records] == [r['id'] for r in rows]
    assert all(f"texte/{r['id']}.txt" in files for r in records)
    ids = {r['id'] for r in records}
    assert {r['flugblatt'] for r in csv.DictReader(io.StringIO(files['flugblatt_herausgeber.csv'].lstrip('﻿')))} <= ids
    assert 'seiten.jsonl' in files

    band = records[0]['band']
    small = export.files(bands=[band], main_only=True, persons=False, pages=False)
    rows = [json.loads(line) for line in small['flugblaetter.jsonl'].splitlines()]
    assert rows and {r['band'] for r in rows} == {band}
    assert all(not r['unterzeichnende'] for r in rows)
    assert all(r['hauptexemplar'] in ('', r['id']) for r in rows)
    assert 'seiten.jsonl' not in small and 'Weggelassen' in small['README.md']
