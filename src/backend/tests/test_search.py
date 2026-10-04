from pathlib import Path

import pytest
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

import backend.app.app as leaflet_app
from backend.app.database import search
from backend.app.database.base import Base
from backend.app.database.models import Leaflet, Page, Volume


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    search.ensure_search_index(engine)
    test_session = sessionmaker(bind=engine)()
    monkeypatch.setattr(leaflet_app, "session", test_session)
    frontend_templates = Path(__file__).resolve().parents[2] / "frontend" / "templates"
    if frontend_templates.is_dir():
        monkeypatch.setattr(leaflet_app, "templates", Jinja2Templates(directory=frontend_templates))
    yield test_session
    test_session.close()
    engine.dispose()


def add_leaflet(session, volume, page_no, title, ocr, **fields):
    leaflet = Leaflet(volume_id=volume.id, start_page=page_no, end_page=page_no,
                      title=title, **{"date_iso": "", **fields})
    session.add(leaflet)
    session.flush()
    session.add(Page(volume_id=volume.id, page_no=page_no, text=ocr, leaflet_id=leaflet.id))
    return leaflet


def seed(session):
    volume = Volume(vz=1, stem="sample", label="Band 1", year=1968)
    session.add(volume)
    session.flush()
    leaflets = {
        # OCR errors: "1" for "l" and a broken umlaut
        "ocr": add_leaflet(session, volume, 1, "Aufruf",
                           "Die Vo11versammlung ruft zum Stre1kaufruf und zur Blockade der Mensa auf.",
                           doc_type="flugblatt", series="AStA-Info", date_iso="1968-05-02"),
        "other_year": add_leaflet(session, volume, 2, "Streikaufruf der Studenten",
                                  "Kommt alle zur Vollversammlung.", doc_type="flugblatt",
                                  series="Rote Zelle", date_iso="1969-01-10"),
        "invitation": add_leaflet(session, volume, 3, "Einladung zum Fest",
                                  "Streikaufruf-Feier im Foyer <script>alert(1)</script>.",
                                  doc_type="einladung", series="AStA-Info",
                                  date_iso="1968-07-01"),
        "unrelated": add_leaflet(session, volume, 4, "Mensapreise", "Preise steigen.",
                                 doc_type="flugblatt"),
    }
    session.commit()
    return leaflets


def ids(items):
    return [item["leaflet"].id for item in items]


# Substrings from the core of a word find leaflets even where the OCR garbled other parts.
def test_trigram_matches_word_cores_despite_ocr_errors(db):
    leaflets = seed(db)

    hits = leaflet_app.filtered_items([("q", "kaufru")])
    assert set(ids(hits)) == {leaflets["ocr"].id, leaflets["other_year"].id,
                              leaflets["invitation"].id}

    # "Vo11versammlung" is not a word of its own, but its tail "versammlung" matches
    hits = leaflet_app.filtered_items([("q", "versammlung")])
    assert set(ids(hits)) == {leaflets["ocr"].id, leaflets["other_year"].id}

    hit = next(i for i in leaflet_app.filtered_items([("q", "blockade")])
               if i["leaflet"].id == leaflets["ocr"].id)
    assert "<mark>Blockade</mark>" in hit["snippet"]


# Title-only hits show the start of the OCR text; OCR text is HTML-escaped in snippets.
def test_snippet_fallback_and_escaping(db):
    leaflets = seed(db)

    title_hit = leaflet_app.filtered_items([("q", "Einladung")])[0]
    assert title_hit["leaflet"].id == leaflets["invitation"].id
    assert "&lt;script&gt;" in title_hit["snippet"] and "<script>" not in title_hit["snippet"]

    hit = leaflet_app.filtered_items([("q", "Foyer")])[0]
    assert "<mark>Foyer</mark>" in hit["snippet"]
    assert "<script>" not in hit["snippet"]


# Title and series weigh more than OCR text: the title hit ranks before the text-only hit.
def test_relevance_prefers_title_over_ocr_text(db):
    leaflets = seed(db)
    assert ids(leaflet_app.filtered_items([("q", "kaufruf")]))[0] == \
        leaflets["other_year"].id
    # an explicit sort order beats relevance
    by_date = leaflet_app.filtered_items([("q", "kaufruf"), ("sortierung", "datum_auf")])
    assert [i["leaflet"].date_iso for i in by_date] == ["1968-05-02", "1968-07-01", "1969-01-10"]


# q is combined by AND with the metadata filters.
def test_query_combines_with_filters(db):
    leaflets = seed(db)
    everything = {leaflets["ocr"].id, leaflets["other_year"].id, leaflets["invitation"].id}
    assert set(ids(leaflet_app.filtered_items([("q", "kaufruf")]))) == everything

    cases = [
        ([("typ", "einladung")], {leaflets["invitation"].id}),
        ([("reihe", "AStA-Info")], {leaflets["ocr"].id, leaflets["invitation"].id}),
        ([("jahr", "1969")], {leaflets["other_year"].id}),
        ([("jahr", "1968"), ("typ", "flugblatt")], {leaflets["ocr"].id}),
        ([("jahr", "1969"), ("typ", "einladung")], set()),
    ]
    for filters, expected in cases:
        hits = leaflet_app.filtered_items([("q", "kaufruf")] + filters)
        assert set(ids(hits)) == expected, filters
    # the unrelated leaflet never appears, filter-only requests still work without q
    assert leaflets["unrelated"].id in ids(leaflet_app.filtered_items([("typ", "flugblatt")]))


# Unfinished input and FTS5 syntax must not raise; short queries fall back to title/series.
def test_query_sanitizing_and_short_queries(db):
    leaflets = seed(db)
    for evil in ['streik"', '"', "*", "(Streik", "Streik OR", "NOT", "a:b", "streik -", "NEAR(", "^"]:
        leaflet_app.filtered_items([("q", evil)])

    assert search.match_expression('Streik" OR (x) NOT *kauf') == '"Streik" "kauf"'
    assert search.match_expression("ab") is None
    # two characters: substring search in title and series only
    assert ids(leaflet_app.filtered_items([("q", "Ro")])) == [leaflets["other_year"].id]
    assert leaflet_app.filtered_items([("q", "%")]) == []


# The triggers keep the index in step with inserts, updates and deletes.
def test_index_follows_changes(db):
    leaflets = seed(db)

    leaflets["unrelated"].title = "Wohnungsnot"
    db.commit()
    assert ids(leaflet_app.filtered_items([("q", "wohnungsnot")])) == [leaflets["unrelated"].id]
    assert leaflet_app.filtered_items([("q", "mensapreise")]) == []

    db.query(Page).filter_by(leaflet_id=leaflets["unrelated"].id).update({"text": "Mietstreik jetzt"})
    db.commit()
    assert ids(leaflet_app.filtered_items([("q", "mietstreik")])) == [leaflets["unrelated"].id]

    db.delete(leaflets["unrelated"])
    db.commit()
    assert leaflet_app.filtered_items([("q", "wohnungsnot")]) == []

    db.execute(text("DELETE FROM leaflets_fts"))
    db.commit()
    assert search.index_is_stale(db.get_bind())
    assert search.rebuild_search_index(db.get_bind()) == 3
    assert leaflet_app.filtered_items([("q", "mietstreik")]) == []
    assert len(leaflet_app.filtered_items([("q", "kaufruf")])) == 3


def request(path, query_string):
    return Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
        "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": query_string, "headers": [], "server": ("test", 80),
        "client": ("test", 1), "root_path": "", "app": leaflet_app.app,
        "router": leaflet_app.app.router,
    })


# The hit count is shown, snippets render <mark> safely, and q survives paging on the detail page.
def test_list_and_detail_keep_query(db):
    leaflets = seed(db)
    query = b"q=kaufruf&typ=flugblatt"

    html = leaflet_app.leaflet_list(request("/leaflets", query), ansicht="liste").body.decode()
    assert "2 Treffer für „kaufruf“" in html
    assert "<mark>" in html and "<script>alert" not in html

    first = ids(leaflet_app.filtered_items(leaflet_app.list_params(request("/leaflets", query))))
    detail = leaflet_app.leaflet_detail(request(f"/leaflets/{first[0]}", query), first[0])
    body = detail.body.decode()
    assert f'href="/leaflets/{first[1]}?q=kaufruf&amp;typ=flugblatt"' in body
