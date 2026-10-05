import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

import backend.app.app as leaflet_app
from backend.app.database import fillDatabase
from backend.app.database.base import Base
from backend.app.database.models import Leaflet, Page, Volume
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


def copy_db(tmp_path, monkeypatch, decisions=()):
    """In-memory database with four leaflets of one automatic group, imported with the decisions."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    volume = Volume(vz=2, stem="0118_0002", label="Nr. 002 (1968)", year=1968)
    db.add(volume)
    db.flush()
    leaflets = [Leaflet(volume_id=volume.id, start_page=p, end_page=p) for p in (2, 5, 8, 11)]
    db.add_all(leaflets)
    db.flush()
    for leaflet in leaflets:  # the pages belong to their leaflet, as in the import
        p = leaflet.start_page
        db.add(Page(volume_id=volume.id, page_no=p, leaflet_id=leaflet.id, text=f"Text von Seite {p}",
                    blocks=[{"type": "Text", "html": f"<p>Text von Seite {p}</p>", "box": [0, 0, 1, 1]}]))
    db.commit()
    (tmp_path / "copies.tsv").write_text(
        "gruppe\tkanonisch\tband\tseiten\n" + "".join(
            f"1\t{'ja' if p == 2 else ''}\tNr. 002 (1968)\t{p}\n" for p in (2, 5, 8, 11)), encoding="utf-8")
    decisions_file = tmp_path / "copy_decisions.jsonl"
    decisions_file.write_text("".join(json.dumps(d) + "\n" for d in decisions), encoding="utf-8")
    for module in (fillDatabase, leaflet_app):
        monkeypatch.setattr(module, "session", db)
        monkeypatch.setattr(module, "COPY_DECISIONS", decisions_file)
    monkeypatch.setattr(fillDatabase, "DATA_DIR", tmp_path)
    fillDatabase.fill_copies()
    return leaflets


# Tests if the import applies a review: members, main copy, rejected leaflet and a new automatic hit.
def test_fill_copies_applies_reviews(tmp_path, monkeypatch):
    ref = lambda p: {"volume": "0118_0002", "start_page": p, "end_page": p}
    a, b, c, d = copy_db(tmp_path, monkeypatch, [
        {"members": [ref(2), ref(5)], "rejected": [ref(8)], "canonical": ref(5), "at": "2026-10-05T10:00:00"}])
    assert a.copy_group == b.copy_group is not None
    assert a.canonical_leaflet_id == b.canonical_leaflet_id == b.id and a.copies_checked
    # the rejected leaflet and the new hit stay a proposal of their own, and the new hit is offered to the group
    assert c.copy_group == d.copy_group != a.copy_group and not c.copies_checked
    assert d.copy_candidate_of == a.copy_group and c.copy_candidate_of is None


def page(path):
    return Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
        "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"", "headers": [],
        "server": ("test", 80), "client": ("test", 1), "root_path": "", "app": leaflet_app.app,
        "router": leaflet_app.app.router})


# Tests if the OCR blocks stay structured and only words without a counterpart in the reference are marked.
def test_ocr_marks_differences():
    blocks = lambda *htmls: [(1, i, {"type": "Text", "html": h}) for i, h in enumerate(htmls, 1)]
    left, right = leaflet_app.ocr_pair(
        blocks("<p>Der <b>Weg</b> zum Erfolg!</p>", "<p>Zweiter Absatz</p>"),
        blocks("<p>der Weg zum Erfolge</p>", "<p>Zweiter Absatz &amp; mehr</p>"))
    # both sides are marked; case and punctuation do not count, extra words do
    assert left["blocks"][0]["html"] == '<p>Der <b>Weg</b> zum <mark data-diff="1">Erfolg!</mark></p>' and left["differs"] == 1
    assert right["blocks"][0]["html"] == '<p>der Weg zum <mark data-diff="1">Erfolge</mark></p>'
    # the second deviation: the words exist only on the right, so the left text gets a gap marker at its end
    assert right["blocks"][1]["html"] == '<p>Zweiter Absatz <mark data-diff="2">&amp;</mark> <mark data-diff="2">mehr</mark></p>'
    assert left["blocks"][1]["html"].endswith('<mark class="gap" data-diff="2" title="Im anderen Exemplar nicht erkannt">∅</mark></p>')
    assert right["differs"] == 3 and right["words"] == 8 and left["diffs"] == right["diffs"] == 2
    assert [b["marked"] for b in right["blocks"]] == [True, True] and left["blocks"][1]["marked"] is True
    assert [b["id"] for b in left["blocks"]] == ["1-1", "1-2"]  # page and block number, as in the evidence image
    assert [b["partner"] for b in left["blocks"]] == ["1-1", "1-2"]  # the block of the other copy with the same words
    assert [b["partner"] for b in right["blocks"]] == ["1-1", "1-2"]


# Tests if a word hyphenated at the line end is the same as the whole word, however it is split.
def test_ocr_ignores_hyphenation():
    blocks = lambda *htmls: [(1, i, {"type": "Text", "html": h}) for i, h in enumerate(htmls, 1)]
    left, right = leaflet_app.ocr_pair(
        blocks("<p>Die Literaturwissen- schaften und Studenten- Dachverbände</p>"),
        blocks("<p>Die Literatur- wissenschaften und Studenten-Dachverbände</p>"))
    assert left["diffs"] == 0 and left["differs"] == right["differs"] == 0 and "<mark" not in left["blocks"][0]["html"]
    other = leaflet_app.ocr_pair(blocks("<p>Die Literaturwissen- schaften</p>"), blocks("<p>Die Literaturwissen</p>"))
    assert other[0]["diffs"] == 1 and other[0]["differs"] == 2  # both halves belong to the deviation


# Tests if only the copies that deviate from the most common value count as different.
def test_deviating_copies():
    cards = lambda *values: [{"id": i, "x": x} for i, x in enumerate(values)]
    assert leaflet_app.deviating(cards("a", "a", "b"), "x") == {2}
    assert leaflet_app.deviating(cards("a", "a"), "x") == set()
    assert leaflet_app.deviating(cards("a", "b"), "x") == {0, 1}  # nothing to call the usual one
    assert leaflet_app.deviating(cards("a", "a", "b", "b"), "x") == {0, 1, 2, 3}
    assert leaflet_app.deviating(cards("a", "", "a"), "x") == set()  # a missing value is no contradiction
    assert leaflet_app.deviating(cards("a", "a", "b", ""), "x") == {2}


# Tests if the comparison page shows the group, a confirmed review is applied at once, can be reverted,
# and a main copy outside the group is refused.
def test_comparison_page_confirm_and_revert(tmp_path, monkeypatch):
    a, b, c, d = copy_db(tmp_path, monkeypatch)
    show = lambda leaflet: leaflet_app.copy_page(page(f"/leaflets/{leaflet.id}/exemplare"), leaflet.id).body.decode()
    assert show(a).count('name="main"') == 4 and "Prüfung zurücknehmen" not in show(a)
    # the main copy (page 2) is on the left, the first other copy (page 5) on the right; the numbers differ
    assert '<p>Text von Seite <mark data-diff="1">2</mark></p>' in show(a) and '>5</mark></p>' in show(a)
    fragment = leaflet_app.copy_pair_page(page("/"), a.id, a.id, d.id).body.decode()
    assert ">11</mark>" in fragment and ">8</mark>" not in fragment  # any copy can take the right side
    assert f'data-leaflet="{d.id}"' in fragment and 'data-block="11-1" data-partner="2-1"' in fragment  # a click opens both scans
    with pytest.raises(HTTPException):  # the left copy cannot be compared with itself
        leaflet_app.copy_pair_page(page("/"), a.id, a.id, a.id)
    with pytest.raises(HTTPException):
        leaflet_app.copy_page(page("/"), a.id + 100)

    leaflet_app.save_copy_review(a, {"main": [str(b.id)], "out": [str(c.id), str(d.id)]})
    assert a.copy_group == b.copy_group and a.canonical_leaflet_id == b.id and a.copies_checked
    assert show(a).count('name="main"') == 2 and "Prüfung zurücknehmen" in show(a)

    leaflet_app.save_copy_review(a, {"revert": ["1"]})
    assert not a.copies_checked and len({x.copy_group for x in (a, b, c, d)}) == 1
    with pytest.raises(HTTPException):  # the main copy was excluded
        leaflet_app.save_copy_review(a, {"main": [str(b.id)], "out": [str(b.id)]})


# Tests if the overview counts groups by review state and filters by it.
def test_copy_overview(tmp_path, monkeypatch):
    a, b, c, d = copy_db(tmp_path, monkeypatch)
    show = lambda status="": leaflet_app.copy_list(page("/exemplare"), status).body.decode()
    assert "Nicht geprüft (1)" in show() and "Geprüft (0)" in show()
    leaflet_app.save_copy_review(a, {"main": [str(b.id)], "out": [str(c.id), str(d.id)]})
    assert "Nicht geprüft (1)" in show() and "Geprüft (1)" in show() and "Alle (2)" in show()
    assert f'/leaflets/{b.id}/exemplare' in show("geprueft") and f'/leaflets/{c.id}/exemplare' not in show("geprueft")
    assert show("unsinn").count("<li>") == 2  # an unknown filter shows everything


# Tests if the detail page and the list say which copy is the main one and whether the group is checked.
def test_review_shows_on_detail_and_list(tmp_path, monkeypatch):
    ref = lambda p: {"volume": "0118_0002", "start_page": p, "end_page": p}
    a, b, c, d = copy_db(tmp_path, monkeypatch)
    detail = lambda leaflet: leaflet_app.leaflet_detail(page(f"/leaflets/{leaflet.id}"), leaflet.id).body.decode()
    listing = lambda: leaflet_app.leaflet_list(page("/leaflets"), ansicht="liste").body.decode()
    assert "dieses Blatt ist das Hauptexemplar" in detail(a) and "(Hauptexemplar)" in detail(b)
    assert "nicht geprüft" in detail(a) and "3 mögliche weitere Exemplare" in listing()

    leaflet_app.save_copy_review(a, {"main": [str(b.id)], "out": [str(c.id), str(d.id)]})
    assert "Gruppe geprüft" in detail(a) and "(Hauptexemplar)" in detail(a) and "dieses Blatt ist das Hauptexemplar" in detail(b)
    assert "1 weiteres Exemplar" in listing() and "1 mögliches weiteres Exemplar" in listing()  # a and b checked, c and d not

    # a new automatic hit for a checked group is offered, not added (a fresh import with a review on file)
    reviewed = copy_db(tmp_path, monkeypatch, [{"members": [ref(2), ref(5)], "rejected": [ref(8)],
                                                  "canonical": ref(2), "at": "2026-10-05T10:00:00"}])
    assert "neuer möglicher Treffer" in detail(reviewed[3]) and "neuer möglicher Treffer" not in detail(reviewed[0])


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
