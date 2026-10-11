import re
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
    assert 'href="/leaflets?q=versammlung" title="Entfernen">1968' in html and 'Jahr: ' in html and 'value="versammlung"' in html
    assert f'href="/leaflets/{leaflets["ocr"].id}?q=versammlung&amp;jahr=1968&amp;ergebnisse=1#treffer-1"' in html


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
    assert '"/leaflets?typ=flugblatt\\u0026q=Blockade\\u0026text=1\\u0026jahr=1968"' in html
    assert 'value="Blockade, xy"' in html
    # the tab of a term shorter than 3 characters says that it is not searched
    assert "unter 3 Zeichen" in leaflet_app.trends(request("/trends", b"typ=flugblatt&tab=1"), begriffe="Blockade, xy, ").body.decode()
    # only the 1969 copy matches, yet the group counts with its 1968 copy, like in the totals
    assert '"counts": [1, 0]' in leaflet_app.trends(request("/trends", b""), begriffe="Polizei").body.decode()
    assert '"SS 68"' in html  # the semesters of the dated leaflets

    html = leaflet_app.trends(request("/trends", b""), begriffe="Blockade, Mensa").body.decode()
    assert 'Blockade + Mensa</a> <span class="meta">1</span>' in html and 'href="/leaflets?nur=' in html  # the leaflets both counted


# Every leaflet that the search finds has a form of the term, also if only another copy of it contains the word.
def test_every_hit_has_a_form(db):
    leaflets = seed(db)
    copy = add_leaflet(db, db.get(Volume, leaflets["ocr"].volume_id), 5, "Aufruf",
                       "Stre1kaufruf zur Blockade der Mensa. Polizei", date_iso="1969-02-01")
    leaflets["ocr"].copy_group = copy.copy_group = 7
    leaflets["ocr"].canonical_leaflet_id = copy.canonical_leaflet_id = leaflets["ocr"].id
    db.commit()
    search.rebuild_search_index(db.get_bind())
    for term, expected in (("Blockade", {"blockade"}), ("Polizei", {"polizei"}), ("Streikauf", {"streikaufruf"})):
        chosen = {leaflet_app.copy_key(i): i for i in leaflet_app.unique(leaflet_app.searched_items([]))}
        items = [chosen[leaflet_app.copy_key(i)] for i in leaflet_app.searched_items([("q", term), ("duplikate", "1")])]
        forms = leaflet_app.leaflet_forms(term, items)
        assert items and all(forms[i["leaflet"].id] for i in items), term
        assert set().union(*forms.values()) >= expected, term


# A form that is left out takes the leaflets with only that form out of all counts of the term.
def test_trends_leave_out_a_form(db, monkeypatch):
    monkeypatch.setattr(leaflet_app, "MIN_YEAR_SIZE", 1)
    seed(db)
    html = leaflet_app.trends(request("/trends", b""), begriffe="Streikauf").body.decode()
    assert "streikaufruf" in html and 'aria-checked="true"' in html and '<li class="off"' not in html
    html = leaflet_app.trends(request("/trends", b"ohne=Streikauf%3Astreikaufruf"), begriffe="Streikauf").body.decode()
    assert '<li class="off"' in html and '"counts": [0' in html


def test_year_buckets_merge_small_years():
    buckets = leaflet_app.year_buckets({"1967": 7, "1968": 52, "1969": 185, "1973": 3})
    assert buckets == {"1967": "1967/68", "1968": "1967/68", "1969": "1969", "1973": "1973"}


# `feld` limits the search to one field; an index without the signatories is rebuilt.
def test_field_search_and_old_index(db):
    leaflets = seed(db)
    db.add_all([LeafletIssuer(leaflet_id=leaflets["ocr"].id, role="signatory", surface="Hans Müller"),
                LeafletIssuer(leaflet_id=leaflets["unrelated"].id, role="issuer", surface="Müller GmbH")])
    db.commit()

    def found(*pairs):
        return set(ids(leaflet_app.filtered_items(list(pairs))))

    def check():
        assert found(("q", "müller"), ("feld", "unterzeichner")) == {leaflets["ocr"].id}
        assert found(("q", "müller"), ("feld", "herausgeber")) == {leaflets["unrelated"].id}
        assert found(("q", "müller")) == {leaflets["ocr"].id, leaflets["unrelated"].id}
        assert found(("q", "streikaufruf"), ("feld", "titel")) == {leaflets["other_year"].id}
        assert found(("q", "mensapreise"), ("feld", "text")) == set()

    search.rebuild_search_index(db.get_bind())
    check()
    assert leaflet_app.list_params(request("/leaflets", b"q=x&feld=foo")) == [("q", "x")]

    html = leaflet_app.leaflet_list(request("/leaflets", b"q=streikaufruf&feld=titel&jahr=1969"), ansicht="liste").body.decode()
    assert '<option value="titel" selected>' in html and 'value="streikaufruf"' in html

    with db.get_bind().begin() as conn:
        conn.exec_driver_sql("DROP TABLE leaflets_fts")
        conn.exec_driver_sql("CREATE VIRTUAL TABLE leaflets_fts USING fts5(leaflet_id UNINDEXED, title, series, publisher, "
                             "ocr_text, tokenize='trigram remove_diacritics 1')")
    search.ensure_search_index(db.get_bind())
    check()


# Further rows combine searches with UND, ODER and NICHT, from top to bottom.
def test_boolean_rows(db):
    leaflets = seed(db)

    def found(*pairs):
        return set(ids(leaflet_app.filtered_items(list(pairs))))

    streik = {leaflets["other_year"].id, leaflets["invitation"].id}
    assert found(("q", "streikaufruf")) == streik
    assert found(("q", "streikaufruf"), ("s", "und|titel|studenten")) == {leaflets["other_year"].id}
    assert found(("q", "streikaufruf"), ("s", "nicht|titel|studenten")) == {leaflets["invitation"].id}
    assert found(("q", "mensapreise"), ("s", "oder|text|feier")) == {leaflets["unrelated"].id, leaflets["invitation"].id}
    # a row without a word of three characters is left out
    assert found(("q", "streikaufruf"), ("s", "und||ab")) == streik

    bad = b"q=x&s=xor|titel|y&s=und|foo|y&s=und|titel|&s=kein"
    assert leaflet_app.list_params(request("/leaflets", bad)) == [("q", "x")]

    html = leaflet_app.leaflet_list(request("/leaflets", b"q=streikaufruf&s=nicht|titel|studenten&s=oder|text|feier"),
                                    ansicht="liste").body.decode()
    assert 'value="studenten"' in html and '<option value="nicht" selected>' in html
    assert "Gelesen als: ((streikaufruf NICHT studenten) ODER feier)" in html
    assert "active-filter" not in html  # the search stands in the rows, not in chips


# A search looks in all copies of a group and lists the main copy; with the switch each copy stands alone.
def test_list_finds_a_group_through_any_copy(db):
    leaflets = seed(db)
    copy = add_leaflet(db, db.get(Volume, leaflets["ocr"].volume_id), 5, "Aufruf",
                       "Stre1kaufruf zur Blockade der Mensa. Polizei", date_iso="1969-02-01")
    leaflets["ocr"].copy_group = copy.copy_group = 7
    leaflets["ocr"].canonical_leaflet_id = copy.canonical_leaflet_id = leaflets["ocr"].id
    db.commit()
    search.rebuild_search_index(db.get_bind())

    items = leaflet_app.filtered_items([("q", "polizei")])
    assert ids(items) == [leaflets["ocr"].id] and items[0]["text_id"] == copy.id
    leaflet_app.attach_passages(items, "polizei")
    assert "<mark>Polizei</mark>" in str(items[0]["snippets"][0])
    assert ids(leaflet_app.filtered_items([("q", "polizei"), ("duplikate", "1")])) == [copy.id]
    both = leaflet_app.filtered_items([("q", "blockade")])  # both copies match: the main copy's own text counts
    assert ids(both) == [leaflets["ocr"].id] and "text_id" not in both[0]


# Several values of one facet are alternatives, different facets must all match.
def test_facets_take_several_values(db):
    leaflets = seed(db)

    def found(*pairs):
        return set(ids(leaflet_app.filtered_items(list(pairs))))

    assert found(("jahr", "1968")) == {leaflets["ocr"].id, leaflets["invitation"].id, leaflets["unrelated"].id}
    assert found(("jahr", "1968"), ("jahr", "1969")) == {leaflets[k].id for k in ("ocr", "invitation", "unrelated", "other_year")}
    assert found(("jahr", "1968"), ("jahr", "1969"), ("typ", "einladung")) == {leaflets["invitation"].id}
    assert found(("q", "streikaufruf"), ("reihe", "AStA-Info"), ("reihe", "Rote Zelle")) == {leaflets["other_year"].id, leaflets["invitation"].id}

    html = leaflet_app.leaflet_list(request("/leaflets", b"jahr=1968&jahr=1969&typ=flugblatt&typ=einladung"),
                                    ansicht="liste").body.decode()
    assert html.count('class="topic-year active"') == 2 and "1968 <span" in html and " oder <a" in html
    assert html.count('role="checkbox" aria-checked="true"') == 2
    # a value is removed from the choice by the same link that added it
    links = re.findall(r'href="([^"]*)" title="[^"]*" role="checkbox" aria-checked="true"', html)
    assert sorted(links) == ["/leaflets?jahr=1968&amp;jahr=1969&amp;typ=einladung", "/leaflets?jahr=1968&amp;jahr=1969&amp;typ=flugblatt"]


# Without a search the list runs by date; the band and page show only when it is sorted by them.
def test_default_sort_is_date_and_band_shows_with_band_sort(db):
    leaflets = seed(db)
    order = lambda *pairs: ids(leaflet_app.filtered_items(list(pairs)))
    assert order() == [leaflets[k].id for k in ("unrelated", "ocr", "invitation", "other_year")]
    assert order(("sortierung", "band")) == [leaflets[k].id for k in ("ocr", "other_year", "invitation", "unrelated")]
    assert order(("q", "streikaufruf"))[0] == leaflets["other_year"].id  # a search stays by relevance

    db.query(Page).filter_by(leaflet_id=leaflets["ocr"].id).one().blocks = [
        {"type": "Text", "html": "<p>Kommt alle zur Versammlung in der Mensa und bringt Freunde mit</p>"}]
    db.commit()
    default = leaflet_app.leaflet_list(request("/leaflets", b""), ansicht="liste").body.decode()
    by_band = leaflet_app.leaflet_list(request("/leaflets", b"sortierung=band"), ansicht="liste").body.decode()
    assert 'class="locator"' not in default and 'class="locator"' in by_band
    assert '<option value="" selected>Datum aufsteigend</option>' in default
    searched = leaflet_app.leaflet_list(request("/leaflets", b"q=streikaufruf"), ansicht="liste").body.decode()
    assert 'class="preview"' in default and 'class="preview"' not in searched  # the text start only without a search


# The preview is the first running text block: not a header, a banner of repeated words or the title again.
def test_preview_takes_the_first_text_block(db):
    volume = Volume(vz=1, stem="sample", label="Band 1", year=1968)
    db.add(volume)
    db.flush()
    title = "Heute ist die letzte Gelegenheit zur Wahl der Mitte"
    leaflet = add_leaflet(db, volume, 1, title, title + " Kommt alle zur Versammlung in der Mensa")
    page = db.query(Page).filter_by(leaflet_id=leaflet.id).one()
    page.blocks = [{"type": "PageHeader", "html": "<p>- 1 -</p>"},
                   {"type": "Text", "html": "<p>+ AStA-Info + AStA-Info + AStA-Info + AStA-Info + AStA-Info +</p>"},
                   {"type": "Text", "html": "<p>STREIK ?? STREIK !! STREIK ?? STREIK !! STREIK ?? STREIK !!</p>"},
                   {"type": "Text", "html": "<p>a k t i o n s g e m e i n s c h a f t l i b e r a l e r s t u d e n t e n</p>"},
                   {"type": "Text", "html": "<p>aaaaa 1 sssss aktionsgemeinschaft a a 1 sssss liberaler aaaaaaa 1111 sssss studenten</p>"},
                   {"type": "SectionHeader", "html": f"<h2>{title}</h2>"},
                   {"type": "Text", "html": f"<p>{title.upper()}!</p>"},
                   {"type": "Text", "html": "<p>Kommt</p>"},
                   {"type": "Text", "html": "<p>Kommt alle zur Versammlung in der Mensa, die Hoch- schule braucht uns &amp; euch.</p>"}]
    db.commit()
    assert leaflet_app.text_previews([leaflet.id]) == {leaflet.id: "Kommt alle zur Versammlung in der Mensa, die Hochschule braucht uns & euch."}
    page.blocks = []
    db.commit()
    assert leaflet_app.text_previews([leaflet.id]) == {}  # no running text block: no preview


# From the result list the detail page pages through the results (also without filters) and leads back to their page.
def test_detail_pages_through_the_results_and_leads_back(db):
    leaflets = seed(db)
    order = [leaflets[k].id for k in ("unrelated", "ocr", "invitation", "other_year")]  # the default order: by date
    one = order[2]
    html = leaflet_app.leaflet_detail(request(f"/leaflets/{one}", b"ergebnisse=1&pro_seite=25"), one).body.decode()
    assert f'href="/leaflets/{order[1]}?pro_seite=25&amp;ergebnisse=1"' in html
    assert f'href="/leaflets/{order[3]}?pro_seite=25&amp;ergebnisse=1"' in html and "3 von 4" in html
    assert f'href="/leaflets?pro_seite=25#l{one}">← Zurück zu den Ergebnissen' in html
    assert "Flugblätter</a> /" not in html  # the breadcrumb of the volume is not needed then

    elsewhere = leaflet_app.leaflet_detail(request(f"/leaflets/{one}", b""), one).body.decode()
    assert "Zurück zu den Ergebnissen" not in elsewhere and "Flugblätter</a> /" in elsewhere

    filtered = leaflet_app.leaflet_detail(request(f"/leaflets/{leaflets['ocr'].id}", b"q=kaufruf&ergebnisse=1"), leaflets["ocr"].id).body.decode()
    assert '← Zurück zu den Ergebnissen' in filtered and 'href="/leaflets?q=kaufruf#l' in filtered


# The preview is tidied (not the stored text): spaced-out words joined, marks without a gap, cut at a word boundary.
def test_preview_is_tidied_and_cut_at_a_word():
    tidy = leaflet_app.tidy_preview
    assert tidy("Dr.med.Walter R o s s hielt, W e s t p h a l kam .") == "Dr.med.Walter Ross hielt, Westphal kam."
    assert tidy("AStA ( Termine von Veranstaltungen ) und Germanisten , die") == "AStA (Termine von Veranstaltungen) und Germanisten, die"
    assert tidy("Art. 2 a b gilt und z. B. das") == "Art. 2 a b gilt und z. B. das"  # two letters and a number are no lettering
    cut = leaflet_app.shorten_preview("Unter dieser Überschrift (Beschlusprotokoll, anstehende Probleme) " * 5, 80)
    assert cut.endswith(" …") and not cut[:-2].endswith((",", "(")) and len(cut) <= 82
    assert leaflet_app.shorten_preview("kurz") == "kurz"
    assert leaflet_app.shorten_preview("mit der offiziellen Begründung:") == "mit der offiziellen Begründung: …"
