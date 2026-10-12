from types import SimpleNamespace

from backend.app.database import corrections


# Tests if appended corrections are found again only under their exact page range.
def test_roundtrip_and_page_range(tmp_path):
    path = tmp_path / "corrections.jsonl"
    key = {"volume": "0118_0003", "start_page": 129, "end_page": 132}
    corrections.append(path, [{**key, "field": "title", "value": "Alt"}])
    corrections.append(path, [{**key, "field": "title", "value": "Neu"}])
    index = corrections.by_segment(corrections.load(path))
    assert [e["value"] for e in index[("0118_0003", 129, 132)]] == ["Alt", "Neu"]
    assert ("0118_0003", 129, 130) not in index  # boundary changed: not applied
    assert corrections.load(tmp_path / "missing.jsonl") == []


# Tests if corrected fields drop their evidence and the last value wins.
def test_apply():
    leaflet = SimpleNamespace(title="OCR", title_blocks=["1-1"], title_quote="OCR",
                              date_iso="", date_type="undated", date_blocks=[], date_quote="",
                              corrected=[])
    corrections.apply(leaflet, [
        {"field": "title", "value": "Erst"},
        {"field": "title", "value": "Richtig"},
        {"field": "date", "value": {"iso": "1969-12-17", "type": "issued"}},
    ])
    assert (leaflet.title, leaflet.title_blocks, leaflet.title_quote) == ("Richtig", [], "")
    assert (leaflet.date_iso, leaflet.date_type) == ("1969-12-17", "issued")
    assert leaflet.corrected == ["date", "title"]


# Tests if a revert line cancels the earlier corrections, but not later ones.
def test_revert():
    leaflet = SimpleNamespace(title="OCR", title_blocks=[], title_quote="", corrected=[])
    corrections.apply(leaflet, [{"field": "title", "value": "Falsch"},
                                {"field": "revert", "value": "all"}])
    assert (leaflet.title, leaflet.corrected) == ("OCR", [])
    corrections.apply(leaflet, [{"field": "revert", "value": "all"},
                                {"field": "title", "value": "Neu"}])
    assert (leaflet.title, leaflet.corrected) == ("Neu", ["title"])


# Tests if a field revert cancels only that field's earlier lines.
def test_field_revert():
    entries = [{"field": "title", "value": "A"}, {"field": "doc_type", "value": "Flugblatt"},
               {"field": "revert", "value": "title"}, {"field": "doc_type", "value": "Protokoll"}]
    assert [e["value"] for e in corrections.active(entries)] == ["Flugblatt", "Protokoll"]


# Tests if the page shows what the import applies: the last line per field that no revert cancelled.
def test_in_force():
    from backend.app.app import in_force
    line = lambda field, value: {"field": field, "value": value}
    entries = [line("title", "A"), line("issuers", []), line("revert", "issuers"), line("title", "B"),
               line("date", {"iso": "1969", "type": ""}), line("revert", "all"), line("title", "C")]
    assert in_force(entries) == [line("title", "C")]
    assert [e["value"] for e in in_force(entries[:4])] == ["B"]
