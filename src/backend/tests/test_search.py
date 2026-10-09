from pathlib import Path

import pytest
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

import backend.app.app as leaflet_app
from backend.app.database import search
from backend.app.database.base import Base
from backend.app.database.models import Leaflet, LeafletIssuer, Organization, Page, Volume


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
    search.rebuild_search_index(session.get_bind())
    return leaflets


def ids(items):
    return [item["leaflet"].id for item in items]


def with_passages(q):
    items = leaflet_app.filtered_items([("q", q)])
    leaflet_app.attach_passages(items, q)
    return items


# Substrings from the core of a word find leaflets even where the OCR garbled other parts.
def test_trigram_matches_word_cores_despite_ocr_errors(db):
    leaflets = seed(db)

    hits = leaflet_app.filtered_items([("q", "kaufru")])
    assert set(ids(hits)) == {leaflets["ocr"].id, leaflets["other_year"].id,
                              leaflets["invitation"].id}

    # "Vo11versammlung" is not a word of its own, but its tail "versammlung" matches
    hits = leaflet_app.filtered_items([("q", "versammlung")])
    assert set(ids(hits)) == {leaflets["ocr"].id, leaflets["other_year"].id}

    hit = next(i for i in with_passages("blockade") if i["leaflet"].id == leaflets["ocr"].id)
    assert "<mark>Blockade</mark>" in hit["snippets"][0]


# Title-only hits show the start of the OCR text; OCR text is HTML-escaped in snippets.
def test_snippet_fallback_and_escaping(db):
    leaflets = seed(db)

    title_hit = with_passages("Einladung")[0]
    assert title_hit["leaflet"].id == leaflets["invitation"].id
    assert "&lt;script&gt;" in title_hit["snippets"][0] and "<script>" not in title_hit["snippets"][0]

    hit = with_passages("Foyer")[0]
    assert "<mark>Foyer</mark>" in hit["snippets"][0]
    assert "<script>" not in hit["snippets"][0] and hit["hits"] == 1


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

    assert search.match_expression('Streik" OR (x) NOT *kauf') == '("streik") AND ("kauf")'
    assert search.match_expression("ab") is None
    # two characters: substring search in title and series only
    assert ids(leaflet_app.filtered_items([("q", "Ro")])) == [leaflets["other_year"].id]
    assert leaflet_app.filtered_items([("q", "%")]) == []


# Quotes search a phrase, ß and ss find each other, line-end hyphenation is joined.
def test_phrases_spelling_and_hyphenation(db):
    leaflets = seed(db)
    assert ids(leaflet_app.filtered_items([("q", "Mensa Blockade")])) == [leaflets["ocr"].id]
    assert ids(leaflet_app.filtered_items([("q", '"Mensa Blockade"')])) == []
    assert ids(leaflet_app.filtered_items([("q", '"Blockade der Mensa"')])) == [leaflets["ocr"].id]

    volume = db.query(Volume).first()
    hyphen = add_leaflet(db, volume, 5, "Satzung", "Das neue Hochschul- gesetz, daß es gilt.")
    db.commit()
    search.rebuild_search_index(db.get_bind())
    assert ids(leaflet_app.filtered_items([("q", "Hochschulgesetz")])) == [hyphen.id]
    assert ids(leaflet_app.filtered_items([("q", "dass")])) == [hyphen.id]
    assert search.match_expression('daß "Rote Zelle"') == '("rote zelle") AND ("daß" OR "dass")'


# Each facet counts over the other filters, so a chosen year still shows the other years.
def test_facet_counts_follow_the_selection(db):
    seed(db)
    items, counts = leaflet_app.faceted_items([("q", "kaufruf"), ("jahr", "1968")])
    assert len(items) == 2
    assert counts["jahr"] == {"1968": 2, "1969": 1}
    assert counts["typ"] == {"flugblatt": 1, "einladung": 1}
    assert counts["reihe"]["AStA-Info"] == 2
    # leaflets without issuer or topic are a facet value of their own
    assert counts["org"]["keiner"] == 2 and counts["thema"]["keins"] == 2
    assert "nicht_im_register" not in counts["org"]


# Passages: every occurrence with its context, in the spellings the search uses.
def test_kwic():
    text = "Wir fordern, daß die Mensa bleibt. Dass die Hochschul- gesetze fallen, ist klar."
    assert [hit for _, hit, _ in search.kwic(text, "dass")] == ["daß", "Dass"]
    assert search.kwic(text, '"Hochschulgesetze fallen"', width=8) ==         [("die ", "Hochschulgesetze fallen", ", ist")]
    assert search.kwic(text, "ab") == []
    # repeated header words are shortened
    assert search.kwic("LSD LSD LSD LSD fordert die Mensa", "Mensa")[0][0] == "LSD … fordert die "


# The triggers keep the index in step with inserts, updates and deletes.
def test_index_follows_changes(db):
    leaflets = seed(db)

    leaflets["unrelated"].title = "Wohnungsnot"
    db.commit()
    assert ids(leaflet_app.filtered_items([("q", "wohnungsnot")])) == [leaflets["unrelated"].id]
    assert leaflet_app.filtered_items([("q", "mensapreise")]) == []

    db.delete(leaflets["unrelated"])
    db.commit()
    assert leaflet_app.filtered_items([("q", "wohnungsnot")]) == []

    db.execute(text("DELETE FROM leaflets_fts"))
    db.commit()
    assert search.rebuild_search_index(db.get_bind()) == 3
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


# Issuers split into "not in the register" and "none found"; each chip and the clear link
# remove only their own parameter; passages in the list link to their hit.
def test_issuer_facets_chips_and_passage_links(db):
    leaflets = seed(db)
    db.add(Organization(id="asta", name="AStA", full_name="Allgemeiner Studentenausschuss"))
    db.add_all([LeafletIssuer(leaflet_id=leaflets["ocr"].id, role="issuer", surface="AStA", org_id="asta"),
                LeafletIssuer(leaflet_id=leaflets["other_year"].id, role="issuer", surface="Rote Zelle")])
    db.commit()
    _, counts = leaflet_app.faceted_items([("q", "kaufruf")])
    assert counts["org"] == {"asta": 1, "nicht_im_register": 1, "keiner": 1}

    html = leaflet_app.leaflet_list(request("/leaflets", b"q=versammlung&jahr=1968"),
                                    ansicht="liste").body.decode()
    assert 'href="/leaflets?jahr=1968" title="Entfernen">„versammlung“' in html
    assert 'class="search-clear" href="/leaflets?jahr=1968"' in html
    assert f'href="/leaflets/{leaflets["ocr"].id}?q=versammlung&amp;jahr=1968#treffer-1"' in html


def test_trends_count_copies_once(db, monkeypatch):
    monkeypatch.setattr(leaflet_app, "MIN_YEAR_SIZE", 1)
    leaflets = seed(db)
    # a copy of the 1968 call, filed in 1969: counts once, in 1968
    copy = add_leaflet(db, db.get(Volume, leaflets["ocr"].volume_id), 5, "Aufruf",
                       "Stre1kaufruf zur Blockade der Mensa. Polizei", date_iso="1969-02-01")
    leaflets["ocr"].copy_group = copy.copy_group = 7
    leaflets["ocr"].canonical_leaflet_id = copy.canonical_leaflet_id = leaflets["ocr"].id
    db.commit()
    search.rebuild_search_index(db.get_bind())

    items = leaflet_app.unique(leaflet_app.searched_items([("q", "blockade")]))
    assert [i["leaflet"].id for i in items] == [leaflets["ocr"].id]

    html = leaflet_app.trends(request("/trends", b"typ=flugblatt"), begriffe="Blockade, xy, ").body.decode()
    assert '"shares": [50.0, 0.0]' in html  # 1968: 1 of 2 leaflets of type "flugblatt", copy once
    assert '"/leaflets?typ=flugblatt\\u0026q=Blockade\\u0026jahr=1968"' in html
    assert "unter 3 Zeichen" in html and 'value="Blockade, xy"' in html
    # only the 1969 copy matches, yet the group counts with its 1968 copy, like in the totals
    assert '"counts": [1, 0]' in leaflet_app.trends(request("/trends", b""), begriffe="Polizei").body.decode()
    assert '"labels": ["1968-05"]' in html  # months with a hit

    html = leaflet_app.trends(request("/trends", b""), begriffe="Blockade, Mensa").body.decode()
    assert 'href="/leaflets?q=Blockade+Mensa">Blockade + Mensa</a> <span class="meta">1</span>' in html


def test_year_buckets_merge_small_years():
    buckets = leaflet_app.year_buckets({"1967": 7, "1968": 52, "1969": 185, "1973": 3})
    assert buckets == {"1967": "1967/68", "1968": "1967/68", "1969": "1969", "1973": "1973"}
