import asyncio
import json
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

import backend.app.app as leaflet_app
from backend.app.database import corrections, fillDatabase
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


def page(path, query=b""):
    return Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
        "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": query, "headers": [],
        "server": ("test", 80), "client": ("test", 1), "root_path": "", "app": leaflet_app.app,
        "router": leaflet_app.app.router})


def post(path, body):
    async def receive():
        return {"type": "http.request", "body": body.encode(), "more_body": False}
    return Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
        "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"", "headers": [],
        "server": ("test", 80), "client": ("test", 1), "root_path": "", "app": leaflet_app.app,
        "router": leaflet_app.app.router}, receive)


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
    assert left["blocks"][1]["html"].endswith('<mark class="gap" data-diff="2" title="Im anderen Duplikat nicht erkannt">∅</mark></p>')
    assert right["differs"] == 3 and right["words"] == 8 and left["diffs"] == right["diffs"] == 2
    assert [b["marked"] for b in right["blocks"]] == [True, True] and left["blocks"][1]["marked"] is True
    assert [b["id"] for b in left["blocks"]] == ["1-1", "1-2"]  # page and block number, as in the evidence image
    assert [b["partners"] for b in left["blocks"]] == [{1: "1-1"}, {1: "1-2"}]  # the block of the other copy with the same words
    assert [b["partners"] for b in right["blocks"]] == [{0: "1-1"}, {0: "1-2"}]


# Tests if with three copies the odd one out is marked, not the others, and the partner blocks lead to the reference.
def test_ocr_group_marks_the_odd_one_out():
    blocks = lambda html: [(1, 1, {"type": "Text", "html": html})]
    typo, right1, right2 = ocr = [blocks("<p>Die Fachschaftvertretungen tagen</p>"), blocks("<p>Die Fachschaftsvertretungen tagen</p>"),
                                  blocks("<p>Die Fachschaftsvertretungen tagen heute</p>")]
    a, b, c = leaflet_app.ocr_group(ocr)
    assert '<mark data-diff="1">Fachschaftvertretungen</mark>' in a["blocks"][0]["html"]  # only the typo is marked
    assert "<mark" not in b["blocks"][0]["html"].replace('class="gap"', "") or b["differs"] == 0
    assert c["blocks"][0]["html"].count("<mark") == 1 and "heute</mark>" in c["blocks"][0]["html"]  # an extra word is its own
    assert a["differs"] == 1 and b["differs"] == 0 and a["blocks"][0]["partners"] == {1: "1-1", 2: "1-1"}


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
    # the first three side by side, in letter order: all three numbers differ, so each is marked; the fourth is not shown
    assert all(f'>{n}</mark></p>' in show(a) for n in (2, 5, 8)) and '>11</mark>' not in show(a)
    assert show(a).count('name="show"') == 4  # all four can be shown
    fragment = leaflet_app.copy_pair_page(page("/"), a.id, f"{a.id},{d.id}").body.decode()
    assert ">11</mark>" in fragment and ">8</mark>" not in fragment  # any leaflets can be compared
    assert ">2</mark>" in fragment  # with two, both sides are marked
    assert f'data-leaflet="{d.id}"' in fragment and 'data-block="11-1" data-partners="0:2-1"' in fragment  # a click opens the scans
    with pytest.raises(HTTPException):  # one leaflet is not a comparison
        leaflet_app.copy_pair_page(page("/"), a.id, f"{a.id},{a.id}")
    with pytest.raises(HTTPException):
        leaflet_app.copy_page(page("/"), a.id + 100)

    leaflet_app.save_copy_review(a, {"main": [str(b.id)], "out": [str(c.id), str(d.id)]})
    assert a.copy_group == b.copy_group and a.canonical_leaflet_id == b.id and a.copies_checked
    # a pair is judged with one button per card, not with choices
    assert show(a).count('name="verdict" value="main:') == 1 and 'value="next:' not in show(a)  # only the other one can become main
    assert 'name="main"' not in show(a) and "Prüfung zurücknehmen" in show(a)

    leaflet_app.save_copy_review(a, {"revert": ["1"]})
    assert not a.copies_checked and len({x.copy_group for x in (a, b, c, d)}) == 1
    with pytest.raises(HTTPException):  # the main copy was excluded
        leaflet_app.save_copy_review(a, {"main": [str(b.id)], "out": [str(b.id)]})


# Tests if a pair is judged with one button, the review goes on with the next group that is not checked,
# and the queue says where a group stands.
def test_pair_verdict_and_queue(tmp_path, monkeypatch):
    a, b, c, d = copy_db(tmp_path, monkeypatch)
    leaflet_app.save_copy_review(a, {"main": [str(a.id)], "out": [str(c.id), str(d.id)]})  # a and b: checked; c and d: not
    assert leaflet_app.review_queue(a) == {"previous": None, "next": c.id, "position": None, "total": 1}
    assert leaflet_app.review_queue(c) == {"previous": None, "next": None, "position": 1, "total": 1}
    assert "1 von 1 ungeprüft" in leaflet_app.copy_page(page("/"), c.id).body.decode()

    def judge(leaflet, verdict):
        return asyncio.run(leaflet_app.copy_save(post(f"/leaflets/{leaflet.id}/exemplare", urlencode({"verdict": verdict})), leaflet.id))
    # a verdict stays on the page; the next group to check is offered there
    assert c.copy_candidate_of is None and d.copy_candidate_of is None  # a re-review does not bring back what was rejected
    assert judge(b, f"main:{b.id}").headers["location"] == f"/leaflets/{b.id}/exemplare?meldung=gespeichert"
    assert b.canonical_leaflet_id == b.id
    assert f'class="button-small review-next" href="/leaflets/{c.id}/exemplare"' in leaflet_app.copy_page(page("/"), b.id).body.decode()
    # the pair is judged with the other card as main copy
    assert judge(c, f"main:{d.id}").headers["location"] == f"/leaflets/{c.id}/exemplare?meldung=gespeichert"
    assert c.canonical_leaflet_id == d.id and c.copies_checked
    # two different leaflets: the pair is dissolved, the page stays and offers to take it back or go on
    a, b, c, d = copy_db(tmp_path, monkeypatch)
    leaflet_app.save_copy_review(a, {"main": [str(a.id)], "out": [str(c.id), str(d.id)]})
    assert judge(a, "different").headers["location"] == f"/leaflets/{a.id}/exemplare?meldung=getrennt" and a.copy_group is None
    split = leaflet_app.copy_page(page("/"), a.id, "getrennt").body.decode()  # b stays proposed with c and d
    assert "Als verschiedene Flugblätter gespeichert." in split and f'href="/leaflets/{b.id}"' in split and "review-next" in split
    undo = asyncio.run(leaflet_app.copy_save(post(f"/leaflets/{a.id}/exemplare", "revert=1"), a.id))
    assert undo.headers["location"] == f"/leaflets/{a.id}/exemplare?meldung=zurueckgenommen" and a.copy_group == b.copy_group
    # choose the main copy and go on to the next group to check
    a, b, c, d = copy_db(tmp_path, monkeypatch)
    leaflet_app.save_copy_review(a, {"main": [str(a.id)], "out": [str(c.id), str(d.id)]})
    assert judge(a, f"next:{b.id}").headers["location"] == f"/leaflets/{c.id}/exemplare" and b.canonical_leaflet_id == b.id


# Tests if the start page counts a leaflet with duplicates once.
def test_start_page_counts_duplicates_once(tmp_path, monkeypatch):
    copy_db(tmp_path, monkeypatch)  # four leaflets in one group
    body = leaflet_app.index(page("/")).body.decode()
    assert "1 Flugblätter" in body and "4 Flugblätter" not in body


# Tests if a leaflet of four sheets gets the page strip, with an outline from its headings; a short one does not.
def test_long_leaflet_has_page_strip_and_outline(tmp_path, monkeypatch):
    a, b, c, d = copy_db(tmp_path, monkeypatch)
    for n in (3, 4, 5):
        leaflet_app.session.add(Page(volume_id=a.volume_id, page_no=n, leaflet_id=a.id,
                                     blocks=[{"type": "SectionHeader", "html": f"<h2>Abschnitt {n}</h2>", "box": [0, 0, 1, 1]}]))
    leaflet_app.session.commit()
    detail = lambda leaflet: leaflet_app.leaflet_detail(page(f"/leaflets/{leaflet.id}"), leaflet.id).body.decode()
    assert 'class="page-nav"' in detail(a) and 'href="#b-3-1"' in detail(a) and "Abschnitt 4" in detail(a)
    assert 'class="page-nav"' not in detail(b)


# Tests if the overview counts groups by review state and filters by it.
def test_copy_overview(tmp_path, monkeypatch):
    a, b, c, d = copy_db(tmp_path, monkeypatch)
    show = lambda status="": leaflet_app.copy_list(page("/exemplare"), status).body.decode()
    assert "Nicht geprüft (1)" in show() and "Geprüft (0)" in show()
    leaflet_app.save_copy_review(a, {"main": [str(b.id)], "out": [str(c.id), str(d.id)]})
    # checked: the group of a and b, and c and d, which were split off (and are still proposed as a group of their own)
    assert "Nicht geprüft (1)" in show() and "Geprüft (3)" in show() and "Alle (4)" in show()
    assert f'/leaflets/{b.id}/exemplare' in show("geprueft") and show("geprueft").count("<li>") == 3
    assert show("unsinn").count("<li>") == 4  # an unknown filter shows everything
    # four copies in one volume are one group of that volume
    assert [r["volumes"] for r in leaflet_app.copy_rows()] == [{2}, {2}]
    assert "Alle (4)" in leaflet_app.copy_list(page("/exemplare"), band=2).body.decode()
    assert "Alle (0)" in leaflet_app.copy_list(page("/exemplare"), band=3).body.decode()


# Tests if the leaflets a review split off are listed as checked, sortable by review date; a reverted review is not.
def test_separated_list(tmp_path, monkeypatch):
    ref = lambda p: {"volume": "0118_0002", "start_page": p, "end_page": p}
    review = lambda at, kept, out: {"members": [ref(kept)], "rejected": [ref(out)], "canonical": ref(kept), "at": at}
    a, b, c, d = copy_db(tmp_path, monkeypatch, [
        review("2026-10-05T10:00:00", 2, 5), review("2026-10-06T09:30:00", 8, 11),
        review("2026-10-06T12:00:00", 11, 2), {"revert": "2026-10-06T12:00:00", "at": "2026-10-06T12:01:00"}])
    rows = lambda sort="": [(r["id"], [f["id"] for f in r["from"]]) for r in leaflet_app.copy_list(
        page("/exemplare"), "geprueft", sort).context["rows"] if r["state"] == "getrennt"]
    assert rows("neu") == [(d.id, [c.id]), (b.id, [a.id])] and rows("alt") == [(b.id, [a.id]), (d.id, [c.id])]
    html = leaflet_app.copy_list(page("/exemplare"), "geprueft").body.decode()
    assert "06.10.2026, 11:30</span><br>Getrennt" in html  # stored in UTC, shown in German summer time
    assert leaflet_app.review_date("2026-12-01T09:30:00+00:00") == "01.12.2026, 10:30"


# Tests if the detail page and the list say which copy is the main one and whether the group is checked.
def test_review_shows_on_detail_and_list(tmp_path, monkeypatch):
    ref = lambda p: {"volume": "0118_0002", "start_page": p, "end_page": p}
    a, b, c, d = copy_db(tmp_path, monkeypatch)
    detail = lambda leaflet: leaflet_app.leaflet_detail(page(f"/leaflets/{leaflet.id}"), leaflet.id).body.decode()
    listing = lambda: leaflet_app.leaflet_list(page("/leaflets"), ansicht="liste").body.decode()
    assert 'class="dup-inline"' in detail(a) and "</span><strong>" in detail(a)  # this leaflet is set in bold
    assert "Hauptexemplar" not in detail(a) + detail(b) and "Duplikat<" not in detail(b)  # the proposal is not shown as a choice
    assert "Noch nicht geprüft" in detail(a) and "3 mögliche Duplikate" in listing()
    assert f'href="/leaflets/{a.id}' in listing() and f'href="/leaflets/{b.id}' not in listing()  # a group is listed once
    everything = leaflet_app.leaflet_list(page("/leaflets", b"duplikate=1"), ansicht="liste").body.decode()
    assert f'href="/leaflets/{b.id}' in everything and "checked" in everything  # the switch brings the other copies back
    assert f'href="/leaflets/{a.id}/exemplare">3 mögliche Duplikate</a>' in listing()  # an unchecked group links to its review

    leaflet_app.save_copy_review(a, {"main": [str(b.id)], "out": [str(c.id), str(d.id)]})
    assert ">Geprüft</a>" in detail(a) and 'class="alt-note"' in detail(a) and 'class="alt-note"' not in detail(b) and 'role main">Hauptexemplar' in detail(b)
    assert "1 Duplikat" in listing() and "1 mögliches Duplikat" in listing()  # a and b checked, c and d not

    # a new automatic hit for a checked group is offered, not added (a fresh import with a review on file)
    reviewed = copy_db(tmp_path, monkeypatch, [{"members": [ref(2), ref(5)], "rejected": [ref(8)],
                                                  "canonical": ref(2), "at": "2026-10-05T10:00:00"}])
    assert "Neu gefunden" in detail(reviewed[3]) and "Neu gefunden" in detail(reviewed[0])  # listed in the group of both
    assert "Neu gefunden" not in detail(reviewed[2])  # the leaflet that was rejected is not part of the group


# Tests if the details of a group are corrected on the comparison page: one form, at the main copy, which keeps its evidence;
# a form without changes writes nothing, a changed title is a correction of the main copy only, a wrong date is shown again,
# an alternative has no form of its own and points at the main copy.
def test_copy_details(tmp_path, monkeypatch):
    a, b, c, d = copy_db(tmp_path, monkeypatch)
    leaflet_app.save_copy_review(a, {"main": [str(a.id)]})  # the details are those of the chosen main copy
    corrections_file = tmp_path / "corrections.jsonl"
    monkeypatch.setattr(leaflet_app, "CORRECTIONS", corrections_file)
    monkeypatch.setattr(corrections, "session", leaflet_app.session)
    monkeypatch.setattr(leaflet_app, "automatic_text", lambda leaflet: {})  # these values come from the metadata files
    a.title, a.title_blocks = "Alter Titel", ["2-1"]
    html = leaflet_app.copy_page(page(f"/leaflets/{a.id}/exemplare"), a.id).body.decode()
    assert f'id="title-{a.id}"' in html and f'id="title-{b.id}"' not in html
    assert 'name="title_blocks" value="2-1"' in html and 'class="pick-evidence"' in html  # evidence is kept and can be picked
    assert html.count(" data-main") == 1 and 'class="ocr-box"' in html  # only the main copy's column and scan offer blocks
    edit_page = leaflet_app.leaflet_detail(page(f"/leaflets/{a.id}"), a.id, bearbeiten="").body.decode()
    assert f'id="title-{a.id}"' in edit_page and "Beleg: 1 Textstelle" in edit_page  # the detail page picks evidence

    def posted(leaflet, **changes):  # the body of its form as the browser sends it
        v = leaflet_app.current_values(leaflet)
        fields = {"title": v["title"], "title_blocks": " ".join(v["title_blocks"]), "date": leaflet_app.german_date(v["date_iso"]),
                  "date_type": v["date_type"], "series": v["series"], "issue": v["issue"], "doc_type": v["doc_type"]}
        return {k: [x] for k, x in {**fields, **changes}.items()}

    form, error = leaflet_app.read_metadata_form(a, posted(a))
    leaflet_app.save_metadata(a, form)
    assert not error and not corrections_file.exists()  # nothing changed, nothing written

    form, error = leaflet_app.read_metadata_form(a, posted(a, title="Neuer Titel", date="12.03.1969", date_type="issued"))
    leaflet_app.save_metadata(a, form)
    assert not error and (a.title, a.date_iso, a.corrected) == ("Neuer Titel", "1969-03-12", ["date", "title"])
    assert a.title_blocks == ["2-1"] and b.title is None and not b.corrected  # the other copies stay as they are
    assert len(corrections.load(corrections_file)) == 2

    form, error = leaflet_app.read_metadata_form(a, posted(a, received="07.04.1969", received_blocks="2-1"))
    leaflet_app.save_metadata(a, form)  # the stamp can be corrected, with evidence; the form without the field left it alone
    assert not error and (a.received_date, a.received_uncertain, a.received_blocks) == ("1969-04-07", False, ["2-1"]) and "received" in a.corrected
    assert "TT.MM.JJJJ" in leaflet_app.read_metadata_form(a, posted(a, received="31.02.1969"))[1]
    assert len(corrections.load(corrections_file)) == 3

    form, error = leaflet_app.read_metadata_form(a, posted(a, date="31.02.1969"))
    assert "TT.MM.JJJJ" in error
    shown = leaflet_app.copy_view(page(f"/leaflets/{a.id}/exemplare"), a, "", True, form, error)
    assert shown.status_code == 400 and 'class="form-error"' in shown.body.decode()
    assert "31.02.1969" in shown.body.decode() and len(corrections.load(corrections_file)) == 3

    body = urlencode({k: v[0] for k, v in posted(a, title="Gruppentitel").items()})
    with pytest.raises(HTTPException):  # saved at the main copy only
        asyncio.run(leaflet_app.copy_details_save(post(f"/leaflets/{b.id}/exemplare/angaben", body), b.id))
    done = asyncio.run(leaflet_app.copy_details_save(post(f"/leaflets/{a.id}/exemplare/angaben", body), a.id))
    assert done.status_code == 303 and a.title == "Gruppentitel" and b.title is None
    b.title = "Anderer Titel"  # what a duplicate says differently is offered for taking over
    offered = leaflet_app.copy_page(page(f"/leaflets/{a.id}/exemplare"), a.id).body.decode()
    assert f'value="title:{b.id}"' in offered and 'value="date:' not in offered
    body = urlencode({"take": f"title:{b.id}"})
    asyncio.run(leaflet_app.copy_details_take(post(f"/leaflets/{a.id}/exemplare/uebernehmen", body), a.id))
    assert a.title == "Anderer Titel" and a.title_blocks == []  # the evidence of the other leaflet is not taken
    with pytest.raises(HTTPException):
        asyncio.run(leaflet_app.copy_details_take(post(f"/leaflets/{a.id}/exemplare/uebernehmen", "take=title%3A99999"), a.id))
    alternative = leaflet_app.leaflet_detail(page(f"/leaflets/{b.id}"), b.id).body.decode()
    assert 'class="alt-note"' in alternative and f'href="/leaflets/{a.id}"' in alternative


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
