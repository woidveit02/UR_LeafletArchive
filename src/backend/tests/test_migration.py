import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import backend.app.app as leaflet_app
from backend.app.database import fillDatabase
from backend.app.database.base import Base
from backend.app.database.createDatabase import add_missing_columns
from backend.app.database.models import DRAFT, RELEASED, Leaflet, Volume


# Tests if a column the models have and an old database lacks is added with its default, keeping the rows.
def test_add_missing_columns_keeps_rows():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE volumes (id INTEGER PRIMARY KEY, vz INTEGER)"))
        connection.execute(text("INSERT INTO volumes VALUES (1, 7)"))
    add_missing_columns(engine)
    add_missing_columns(engine)  # nothing left to add the second time
    with engine.connect() as connection:
        assert connection.execute(text("SELECT vz, status FROM volumes")).all() == [(7, RELEASED)]


# Tests if an imported volume stays hidden as a draft until it is released.
def test_draft_volume_is_hidden_until_released(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([Volume(vz=1, label="Nr. 001", year=1967), Volume(vz=2, label="Nr. 002", year=1968, status=DRAFT)])
    db.flush()
    for volume in db.query(Volume):
        db.add(Leaflet(volume_id=volume.id, start_page=1, end_page=1))
    db.commit()
    monkeypatch.setattr(leaflet_app, "session", db)
    assert [lf.volume_id for lf in leaflet_app.released_leaflets()] == [1]
    db.query(Volume).filter_by(vz=2).one().status = RELEASED
    assert db.query(Leaflet).count() == leaflet_app.released_leaflets().count() == 2


# Tests if import_volume reads one volume as a draft, refuses a second import and release_volume publishes it.
def test_import_volume_as_draft_then_release(tmp_path, monkeypatch):
    entry = {"vz": 9, "label": "Nr. 009", "stem": "0118_0009", "year": 1972, "title": "T", "signature": "S",
             "digitized": True, "group": "g"}
    (tmp_path / "volumes.json").write_text(json.dumps([entry]), encoding="utf-8")
    (tmp_path / "organizations.json").write_text("[]", encoding="utf-8")
    (tmp_path / "nr009_metadata.json").write_text(json.dumps({
        "source_pdf": "0118_0009.pdf", "model": "m", "created": "2026-10-08T10:00",
        "segments": [{"start_page": 1, "end_page": 2, "title": "Aufruf", "issuers": []}]}), encoding="utf-8")
    monkeypatch.setattr(fillDatabase, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fillDatabase, "VOLUMES", [])  # the real volumes are not in tmp_path
    monkeypatch.setattr(fillDatabase, "PDF_DIR", tmp_path / "pdfs")
    monkeypatch.setattr(fillDatabase, "CORRECTIONS", tmp_path / "none.jsonl")
    monkeypatch.setattr(fillDatabase, "COPY_DECISIONS", tmp_path / "none2.jsonl")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setattr(fillDatabase, "session", db)

    volume = fillDatabase.import_volume(9)
    assert volume.status == DRAFT and db.query(Leaflet).count() == 1
    with pytest.raises(ValueError):
        fillDatabase.import_volume(9)  # a second import would double the leaflets
    fillDatabase.release_volume(9)
    assert db.query(Volume).one().status == RELEASED
    assert "status" not in fillDatabase.load_json("volumes.json")[0]
    fillDatabase.release_volume(9, DRAFT)
    assert db.query(Volume).one().status == DRAFT
    # volumes.json keeps it, so a rebuilt database does not release the draft
    assert fillDatabase.volume_from_entry(fillDatabase.load_json("volumes.json")[0]).status == DRAFT
