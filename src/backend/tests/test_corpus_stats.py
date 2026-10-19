import importlib.util
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.app.app as leaflet_app
from backend.app.database.base import Base
from backend.app.database.models import Leaflet, Page, Volume

# CORPUS_STATS_SCRIPT: for a run where the tests are not below the repository (the container)
SCRIPT = Path(os.environ.get("CORPUS_STATS_SCRIPT") or Path(__file__).resolve().parents[3] / "scripts" / "corpus_stats.py")
spec = importlib.util.spec_from_file_location("corpus_stats", SCRIPT)
corpus_stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus_stats)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(leaflet_app, "session", session)
    monkeypatch.setattr(leaflet_app, "database_stamp", lambda: (0, 0))
    yield session
    session.close()
    engine.dispose()


def seed(session):
    one = Volume(vz=1, stem="a", label="Band 1", year=1968)
    two = Volume(vz=2, stem="b", label="Band 2", year=1969)
    session.add_all([one, two])
    session.flush()
    rows = [(one, 1, "1968-05-02", None), (one, 2, "", None), (two, 1, "1970-01-01", 1), (two, 2, "", 1), (two, 3, "", None)]
    for volume, page, date, group in rows:
        leaflet = Leaflet(volume_id=volume.id, start_page=page, end_page=page, title=f"T{volume.vz}{page}", date_iso=date,
                          doc_type="flugblatt", copy_group=group)
        session.add(leaflet)
        session.flush()
        session.add(Page(volume_id=volume.id, page_no=page, text="x", leaflet_id=leaflet.id))
    session.add(Page(volume_id=one.id, page_no=9, text="", leaflet_id=None))  # a separator page
    session.flush()
    group = session.query(Leaflet).filter_by(copy_group=1).order_by(Leaflet.id).all()
    for leaflet in group:
        leaflet.canonical_leaflet_id = group[0].id
    session.commit()


def test_sums_and_order(db):
    seed(db)
    data = corpus_stats.compute()
    assert data["segments"] == 5 and data["documents"] == 4 and data["pages"] == 6
    for counts in (data["band_year"], data["date_year"]):
        for kind, total in (("segments", data["segments"]), ("documents", data["documents"])):
            assert sum(n for (k, _), n in counts.items() if k == kind) == total
    assert sum(v["pages"] for v in data["volumes"]) == data["pages"]
    assert data["date_year"]["documents", corpus_stats.UNDATED] == 2
    assert data["documents"] <= data["segments"]  # documents <= copies == segments


def test_generated_block_is_replaced_and_the_rest_stays(db):
    seed(db)
    block = corpus_stats.render(corpus_stats.compute())
    head, tail = "# Kennzahlen\n\n", "\n## OCR-Qualität\n\nCER 0,60 %\n"
    first = corpus_stats.replace_block(f"{head}{corpus_stats.FIRST_HEADING}\n\nvon Hand\n\n{tail}", block)
    assert "alte Tabelle" not in first and first.startswith(head) and first.endswith(tail)
    again = corpus_stats.replace_block(first, block.replace("1 547", "x"))
    assert again.startswith(head) and again.endswith(tail) and again.count(corpus_stats.BEGIN) == 1
    assert corpus_stats.replace_block(again, block) == first
