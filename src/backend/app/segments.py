"""Step 3 of an import: where one leaflet ends and the next begins in the scan.

The result is <stem>.segments.json next to the scan PDF, the file format of flugblatt_splitter and the
pipeline. A cut after page n means that page n + 1 starts a new leaflet.
"""
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone

import pymupdf
import requests

from . import importer

logger = logging.getLogger(__name__)
API_URL = "https://www.datalab.to/api/v1/segment"
POLL_SECONDS, MAX_WAIT_SECONDS = 3, 30 * 60
SEGMENT_JOB = "segment"


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


def save(volume, cuts, page_count, confirmed=True, excluded=()):
    """Writes the segments for the cuts; the pages in `excluded` become segments of their own, marked no_content.
    A segment with the same pages as before keeps its other fields (title, date, note)."""
    excluded = set(excluded)
    before = {(s["start_page"], s["end_page"]): s for s in (load(volume) or {}).get("segments", [])}
    segments = []
    for s in segments_from_cuts(set(cuts) | forced_cuts(excluded, page_count), page_count, confirmed):
        merged = {**before.get((s["start_page"], s["end_page"]), {}), **s}
        if excluded.issuperset(range(s["start_page"], s["end_page"] + 1)):
            merged["no_content"] = True
        else:
            merged.pop("no_content", None)
        segments.append(merged)
    doc = {"source_pdf": f"{volume.stem}.pdf", "created": datetime.now(timezone.utc).isoformat(),
           "segments": segments}
    path(volume).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
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
    """What the page shows: the cuts and the left-out pages, and whether somebody has confirmed them
    (a suggestion is not). The cuts next to a left-out page follow from it and are not listed."""
    doc = load(volume)
    if doc is None:
        return {"cuts": [], "excluded": [], "saved": False, "confirmed": False}
    segments = doc["segments"]
    excluded = excluded_pages(segments)
    forced = forced_cuts(excluded, max(s["end_page"] for s in segments))
    return {"cuts": [c for c in cuts_from_segments(segments) if c not in forced], "excluded": sorted(excluded),
            "saved": True, "confirmed": all(s.get("confirmed") for s in segments)}


def cuts_from_datalab(datalab_segments):
    """Datalab gives 0-indexed page lists per segment; the cut is after the last page of each but the final one."""
    ends = sorted(max(s["pages"]) + 1 for s in datalab_segments)
    return ends[:-1]


def ask_datalab(pdf_path, api_key, job):
    headers = {"X-API-Key": api_key}
    with open(pdf_path, "rb") as f:
        response = requests.post(API_URL, headers=headers, files={"file": (pdf_path.name, f, "application/pdf")},
                                 data={"mode": "balanced", "segmentation_schema": json.dumps({"segments": []})},
                                 timeout=600)
    response.raise_for_status()
    check_url, started = response.json()["request_check_url"], time.monotonic()
    while time.monotonic() - started < MAX_WAIT_SECONDS:
        result = requests.get(check_url, headers=headers, timeout=60).json()
        job["seconds"] = round(time.monotonic() - started)
        if result.get("status") == "complete":
            if not result.get("success", True):
                raise ValueError(f"Datalab konnte den Band nicht trennen: {result.get('error')}")
            return result["segmentation_results"]["segments"]
        if result.get("status") == "failed":
            raise ValueError(f"Datalab konnte den Band nicht trennen: {result.get('error')}")
        time.sleep(POLL_SECONDS)
    raise ValueError("Datalab hat nach 30 Minuten noch keine Antwort geliefert.")


def start_suggestion(volume):
    """Has Datalab suggest the cuts, in the background; poll importer.JOBS[(vz, "segment")]."""
    api_key = os.getenv("DATALAB_API_KEY")
    if not api_key:
        raise ValueError("Für den Vorschlag fehlt der Zugang zu Datalab: DATALAB_API_KEY in der .env eintragen "
                         "und die App neu starten.")
    scan = importer.scan_path(volume)
    if not scan.is_file():
        raise ValueError("Es sind noch keine Scans hochgeladen.")
    if importer.running(volume, SEGMENT_JOB):
        raise ValueError("Der Vorschlag wird gerade berechnet.")
    with pymupdf.open(scan) as doc:
        page_count = doc.page_count
    job = importer.JOBS[(volume.vz, SEGMENT_JOB)] = {"state": "running", "seconds": 0, "error": ""}

    def run():
        try:
            save(volume, cuts_from_datalab(ask_datalab(scan, api_key, job)), page_count, confirmed=False)
            job["state"] = "done"
        except (ValueError, requests.RequestException) as error:
            job.update(state="error", error=str(error))
        except Exception as error:  # a thread must report, not die silently
            logger.exception("suggesting the cuts failed")
            job.update(state="error", error=f"Unerwarteter Fehler: {error}")

    threading.Thread(target=run, daemon=True).start()
