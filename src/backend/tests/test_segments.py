import json
from types import SimpleNamespace

import pytest

from backend.app import segments
from backend.app.database import fillDatabase


# Tests if cuts become contiguous segments, a cut after the last page or outside the volume is ignored.
def test_cuts_make_contiguous_segments():
    result = segments.segments_from_cuts([3, 3, 7, 10, 0, 99], 10)
    assert [(s["start_page"], s["end_page"]) for s in result] == [(1, 3), (4, 7), (8, 10)]
    assert segments.cuts_from_segments(result) == [3, 7]
    assert [(s["start_page"], s["end_page"]) for s in segments.segments_from_cuts([], 4)] == [(1, 4)]


# Tests if saving keeps the notes of a segment whose pages did not change, and tells a suggestion from a confirmed file.
def test_save_keeps_notes_and_status(tmp_path, monkeypatch):
    monkeypatch.setattr(fillDatabase, "PDF_DIR", tmp_path)
    volume = SimpleNamespace(label="Nr. 016 (1974)", stem="0118_0016", vz=16)
    (tmp_path / volume.label).mkdir()
    assert segments.status(volume) == {"cuts": [], "suggested": [], "excluded": [], "reviewed": [], "hints": [], "saved": False, "confirmed": False}

    segments.save(volume, [2], 6, confirmed=False)
    assert segments.status(volume) == {"cuts": [2], "suggested": [2], "excluded": [], "reviewed": [], "hints": [], "saved": True, "confirmed": False}

    doc = segments.load(volume)
    doc["segments"][0]["note"] = "Seite fehlt"
    segments.path(volume).write_text(json.dumps(doc), encoding="utf-8")
    segments.save(volume, [2, 4], 6)  # (1, 2) stays, (3, 6) is split
    result = segments.load(volume)["segments"]
    assert [(s["start_page"], s["end_page"]) for s in result] == [(1, 2), (3, 4), (5, 6)]
    assert result[0]["note"] == "Seite fehlt" and "note" not in result[1]
    assert segments.status(volume)["confirmed"]


# Tests if saving half way keeps open suggestions open and the volume unfinished until it is finished.
def test_review_state(tmp_path, monkeypatch):
    monkeypatch.setattr(fillDatabase, "PDF_DIR", tmp_path)
    volume = SimpleNamespace(label="Nr. 016 (1974)", stem="0118_0016", vz=16)
    (tmp_path / volume.label).mkdir()
    segments.save(volume, [2, 4], 6, suggested=[4], reviewed=[1], finished=False)
    status = segments.status(volume)
    assert (status["cuts"], status["suggested"], status["reviewed"], status["confirmed"]) == ([2, 4], [4], [1], False)
    segments.save(volume, [2], 6, hints=[4], finished=False)  # a hint is no cut
    status = segments.status(volume)
    assert (status["cuts"], status["hints"]) == ([2], [4])
    segments.save(volume, [2, 4], 6, reviewed=[1, 3, 5])  # all decided and finished
    status = segments.status(volume)
    assert (status["suggested"], status["reviewed"], status["confirmed"]) == ([], [1, 3, 5], True)


# Tests if a list kept while scanning gives the cuts, whatever the separators, headers, notes and order.
def test_cuts_from_list():
    text = "# Nr. 016\nvon;bis\n1-2\n3\n4 – 6; Seite 5 doppelt\n\n7 bis 10\n"
    assert segments.parse_list(text, 10) == ([2, 3, 6], [])
    assert segments.parse_list("7-10\n1-6\n", 10) == ([6], [])  # the order of the lines does not matter
    assert segments.parse_list("1-4", 4) == ([], [])


# Tests if a list that does not cover every page exactly once is refused with the pages that do not fit.
def test_list_must_cover_every_page_once():
    import pytest
    with pytest.raises(ValueError) as gap:
        segments.parse_list("1-2\n5-6", 6)
    assert "Seite 3–4 steht in keinem Flugblatt" in str(gap.value)
    with pytest.raises(ValueError, match="Seite 2 steht in mehreren"):
        segments.parse_list("1-2\n2-3", 3)
    with pytest.raises(ValueError, match="Seite 5–6 fehlt am Ende"):
        segments.parse_list("1-4", 6)
    with pytest.raises(ValueError, match="nur 4 Seiten"):
        segments.parse_list("1-6", 4)
    with pytest.raises(ValueError, match="rückwärts"):
        segments.parse_list("5-3", 6)
    with pytest.raises(ValueError, match="keine Seitenangaben"):
        segments.parse_list("# nur ein Kommentar", 6)


# Tests if the example file offered for download is a valid list: 9 pages in 3 leaflets.
def test_example_list_is_valid():
    from pathlib import Path
    example = Path(__file__).resolve().parents[2] / "frontend" / "static" / "beispiel-flugblaetter.txt"
    if not example.is_file():
        pytest.skip("the frontend folder is not next to the tests (container)")
    assert segments.parse_list(example.read_text(encoding="utf-8"), 9) == ([2, 3], [])


# Tests if left-out pages (blank sheets, separators) become segments of their own, marked no_content, and come back
# as left-out pages without the cuts they forced; a list marks them with "x".
def test_excluded_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(fillDatabase, "PDF_DIR", tmp_path)
    volume = SimpleNamespace(label="Nr. 016 (1974)", stem="0118_0016", vz=16)
    (tmp_path / volume.label).mkdir()
    doc = segments.save(volume, [3], 8, excluded=[2, 3, 7])
    assert [(s["start_page"], s["end_page"], s.get("no_content", False)) for s in doc["segments"]] == [
        (1, 1, False), (2, 3, True), (4, 6, False), (7, 7, True), (8, 8, False)]
    assert segments.status(volume) == {"cuts": [], "suggested": [], "excluded": [2, 3, 7], "reviewed": list(range(1, 8)), "hints": [], "saved": True, "confirmed": True}
    segments.save(volume, [], 8)  # nothing left out any more: the flags are gone, too
    assert not any(s.get("no_content") for s in segments.load(volume)["segments"])
    text = "1\nx 2-3\n4-6\nx 7\nKein Inhalt 8\n"
    assert segments.parse_list(text, 8) == ([], [2, 3, 7, 8])
