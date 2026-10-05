import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import fillDatabase
from backend.app.database.base import Base
from backend.app.database.models import Leaflet, Volume
from backend.app.database.session import session


# Tests if copy groups are keyed by volume stem and page range, with the proposed main copy.
def test_copy_groups(tmp_path, monkeypatch):
    (tmp_path / "copies.tsv").write_text(
        "gruppe\tkanonisch\tband\tseiten\n"
        "7\tja\tNr. 003 (1969)\t12-13\n"
        "7\tnein\tNr. 004 (1970)\t5\n"
        "8\tja\tNr. 099 (1999)\t1\n", encoding="utf-8")  # volume that is not imported
    monkeypatch.setattr(fillDatabase, "DATA_DIR", tmp_path)
    stems = {"Nr. 003 (1969)": "0118_0003", "Nr. 004 (1970)": "0118_0004"}
    assert fillDatabase.copy_groups(stems) == {("0118_0003", 12, 13): (7, True), ("0118_0004", 5, 5): (7, False)}
    assert fillDatabase.copy_groups(stems, "missing.tsv") == {}


# Tests if the import applies a review: members, main copy, rejected leaflet and a new automatic hit.
def test_fill_copies_applies_reviews(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    volume = Volume(vz=2, stem="0118_0002", label="Nr. 002 (1968)", year=1968)
    db.add(volume)
    db.flush()
    a, b, c, d = (Leaflet(volume_id=volume.id, start_page=p, end_page=p) for p in (2, 5, 8, 11))
    db.add_all([a, b, c, d])
    db.commit()
    (tmp_path / "copies.tsv").write_text(
        "gruppe\tkanonisch\tband\tseiten\n" + "".join(
            f"1\t{'ja' if p == 2 else ''}\tNr. 002 (1968)\t{p}\n" for p in (2, 5, 8, 11)), encoding="utf-8")
    ref = lambda p: {"volume": "0118_0002", "start_page": p, "end_page": p}
    (tmp_path / "copy_decisions.jsonl").write_text(json.dumps(
        {"members": [ref(2), ref(5)], "rejected": [ref(8)], "canonical": ref(5), "at": "2026-10-05T10:00:00"}) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(fillDatabase, "session", db)
    monkeypatch.setattr(fillDatabase, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fillDatabase, "COPY_DECISIONS", tmp_path / "copy_decisions.jsonl")

    fillDatabase.fill_copies()
    assert a.copy_group == b.copy_group is not None
    assert a.canonical_leaflet_id == b.canonical_leaflet_id == b.id and a.copies_checked
    # the rejected leaflet and the new hit stay a proposal of their own, and the new hit is offered to the group
    assert c.copy_group == d.copy_group != a.copy_group and not c.copies_checked
    assert d.copy_candidate_of == a.copy_group and c.copy_candidate_of is None


# Tests if, after the real import, every group has exactly one main copy that belongs to it.
def test_every_group_has_one_main_copy():
    groups = {}
    for leaflet in session.query(Leaflet).filter(Leaflet.copy_group.isnot(None)):
        groups.setdefault(leaflet.copy_group, []).append(leaflet)
    assert groups
    for members in groups.values():
        assert len(members) > 1
        mains = {m.canonical_leaflet_id for m in members}
        assert len(mains) == 1 and mains <= {m.id for m in members}
