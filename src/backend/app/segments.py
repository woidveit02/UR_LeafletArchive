"""Step 4 of an import: where one leaflet ends and the next begins in the scan.

The result is <stem>.segments.json next to the scan PDF, the file format of flugblatt_splitter and the
pipeline. A cut after page n means that page n + 1 starts a new leaflet.
"""
import json
import re
from datetime import datetime, timezone

from . import boundaries, importer, ocr


def path(volume):
    return importer.scan_path(volume).with_name(f"{volume.stem}.segments.json")


def load(volume):
    """The saved document, or None."""
    return json.loads(path(volume).read_text(encoding="utf-8")) if path(volume).is_file() else None


def segments_from_cuts(cuts, page_count, confirmed=True):
    """Contiguous segments for the cut points (after which page); cuts outside the volume are ignored."""
    starts = [1] + [c + 1 for c in sorted(set(cuts)) if 1 <= c < page_count]
    ends = [s - 1 for s in starts[1:]] + [page_count]
    return [{"id": i, "title": "", "date": "", "start_page": s, "end_page": e, "confirmed": confirmed}
            for i, (s, e) in enumerate(zip(starts, ends), 1)]


def cuts_from_segments(segments):
    return [s["end_page"] for s in sorted(segments, key=lambda s: s["start_page"])[:-1]]


def excluded_pages(segments):
    """The pages left out of every leaflet: the segments marked "no_content" (blank pages, separators)."""
    return {p for s in segments if s.get("no_content") for p in range(s["start_page"], s["end_page"] + 1)}


def forced_cuts(excluded, page_count):
    """A left-out page is cut off from the leaflets next to it."""
    return {p for p in range(1, page_count) if (p in excluded) != (p + 1 in excluded)}


def save(volume, cuts, page_count, confirmed=True, excluded=(), suggested=(), reviewed=None, finished=True, hints=()):
    """Writes the segments for the cuts; the pages in `excluded` become segments of their own, marked no_content.
    A segment with the same pages as before keeps its other fields (title, date, note).
    `suggested` are cuts nobody has decided yet, `reviewed` the transitions (after page n) somebody found to belong
    together; `hints` the transitions where a cut is possible but not set (an overlooked one); `finished` says the
    whole volume was looked through."""
    excluded = set(excluded)
    before = {(s["start_page"], s["end_page"]): s for s in (load(volume) or {}).get("segments", [])}
    segments = []
    for s in segments_from_cuts(set(cuts) | forced_cuts(excluded, page_count), page_count, confirmed):
        s["confirmed"] = s["confirmed"] and s["start_page"] - 1 not in suggested
        merged = {**before.get((s["start_page"], s["end_page"]), {}), **s}
        if excluded.issuperset(range(s["start_page"], s["end_page"] + 1)):
            merged["no_content"] = True
        else:
            merged.pop("no_content", None)
        segments.append(merged)
    doc = {"source_pdf": f"{volume.stem}.pdf", "created": datetime.now(timezone.utc).isoformat(),
           "finished": finished, "segments": segments}
    if reviewed is not None:
        doc["reviewed"] = sorted(reviewed)
    if hints:
        doc["hints"] = sorted(hints)
    part = path(volume).with_name(path(volume).name + ".part")  # a broken write must not leave half a file
    part.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    part.replace(path(volume))
    return doc


LIST_LINE = re.compile(r"^\s*(?P<out>x|(?:ohne|kein)(?:\s+inhalt)?)?\.?\s*(?P<a>\d+)(?:\s*(?:[-–—:;,\t]|bis)?\s*(?P<b>\d+))?",
                       re.IGNORECASE)


def pages_text(first, last):
    return f"{first}" if first == last else f"{first}–{last}"


def parse_list(text, page_count):
    """(cuts, excluded pages) of a list kept while scanning: one leaflet per line, its pages as "5-7" or "9",
    pages to leave out as "x 17" or "x 17-18".

    Lines starting with # and lines without a number (headers, blank lines) are skipped, anything after the
    range on a line (a note, further CSV columns) is ignored. The lines must cover every page of the volume
    exactly once; otherwise a ValueError names the pages that do not fit.
    """
    ranges, excluded = [], set()
    for number, line in enumerate(text.splitlines(), 1):
        match = None if line.lstrip().startswith("#") else LIST_LINE.match(line)
        if match:
            first, last = int(match["a"]), int(match["b"] or match["a"])
            if last < first:
                raise ValueError(f"Zeile {number} („{line.strip()}“) geht rückwärts.")
            ranges.append((first, last))
            if match["out"]:
                excluded.update(range(first, last + 1))
    if not ranges:
        raise ValueError("In der Datei stehen keine Seitenangaben.")
    problems, expected = [], 1
    for first, last in sorted(ranges):
        if first > expected:
            problems.append(f"Seite {pages_text(expected, first - 1)} steht in keinem Flugblatt")
        elif first < expected:
            problems.append(f"Seite {pages_text(first, min(last, expected - 1))} steht in mehreren Flugblättern")
        expected = max(expected, last + 1)
    if expected - 1 < page_count:
        problems.append(f"Seite {pages_text(expected, page_count)} fehlt am Ende")
    elif expected - 1 > page_count:
        problems.append(f"die Liste geht bis Seite {expected - 1}, der Band hat nur {page_count} Seiten")
    if problems:
        raise ValueError("Die Liste passt nicht zum Band: " + "; ".join(problems) + ".")
    ends = sorted(last for _, last in ranges)[:-1]
    # a cut next to a left-out page follows from it; between two left-out pages it means nothing
    return [c for c in ends if c not in excluded and c + 1 not in excluded], sorted(excluded)


def status(volume):
    """What the page shows: the cuts and the left-out pages, and whether somebody has finished looking through them (a
    suggestion is not decided: its segment says "confirmed": false in the file; "suggested" are the cuts before such a
    segment; "reviewed" the transitions found to belong together). The cuts next to a left-out page follow from it
    and are not listed. Files from before the review (no "finished") count as finished when all is confirmed."""
    doc = load(volume)
    if doc is None:
        return {"cuts": [], "suggested": [], "excluded": [], "reviewed": [], "hints": [], "saved": False, "confirmed": False}
    segments = sorted(doc["segments"], key=lambda s: s["start_page"])
    excluded = excluded_pages(segments)
    pages = max(s["end_page"] for s in segments)
    forced = forced_cuts(excluded, pages)
    confirmed = all(s.get("confirmed") for s in segments) and doc.get("finished", True)
    return {"cuts": [c for c in cuts_from_segments(segments) if c not in forced], "excluded": sorted(excluded),
            "suggested": [a["end_page"] for a, b in zip(segments, segments[1:]) if not b.get("confirmed")],
            "reviewed": doc.get("reviewed", list(range(1, pages)) if confirmed else []), "hints": doc.get("hints", []),
            "saved": True, "confirmed": confirmed}


def missed_cuts(volume, cuts, excluded, page_count):
    """Where a list has no cut but the recognized text makes a start likely: possibly overlooked, to be decided (nothing
    is cut). None if there is no text that fits the scans."""
    result = ocr.result_path(volume)
    if not result.is_file():
        return None
    found, pages = boundaries.suggest(result, boundaries.HINT_PROBABILITY)
    if pages != page_count:
        return None
    skip = set(cuts) | forced_cuts(excluded, page_count)
    return sorted(c for c in found if c not in skip and not (c in excluded and c + 1 in excluded))


def suggest_from_text(volume):
    """Saves the cuts that the recognized text makes very probable (boundaries.py), unconfirmed; returns their number."""
    result = ocr.result_path(volume)
    if not result.is_file():
        raise ValueError("Der Text der Scans ist noch nicht erkannt.")
    cuts, page_count = boundaries.suggest(result)
    if page_count != importer.page_count(volume):
        raise ValueError("Der erkannte Text passt nicht zu den Scans (andere Seitenzahl). Bitte die Texterkennung wiederholen.")
    save(volume, cuts, page_count, confirmed=False, reviewed=[], hints=[])
    return len(cuts)
