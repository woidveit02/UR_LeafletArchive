"""Manual corrections, one JSON line per field (format: pipeline repo,
docs/korpus/korpusstruktur.md, 7.3). A correction is applied only to the
segment with exactly the page range it was made for; after a boundary change
it stays in the file and is listed under /korrekturen for review."""
import html
import json
import re
import threading
from datetime import date

from .models import LeafletIssuer, Organization, Page
from .session import session

FIELDS = {"title": "Titel", "date": "Datum", "series": "Reihe",
          "doc_type": "Textsorte", "issuers": "Herausgeber",
          "signatories": "Unterzeichnende", "received": "Eingang im Archiv"}
_lock = threading.Lock()


def load(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def by_segment(entries):
    """(volume stem, start page, end page) -> entries, in file order."""
    index = {}
    for e in entries:
        index.setdefault((e["volume"], e["start_page"], e["end_page"]), []).append(e)
    return index


def append(path, entries):
    # append only: earlier lines stay, later lines win on import
    stamp = date.today().isoformat()
    with _lock, open(path, "a", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps({**e, "at": stamp}, ensure_ascii=False) + "\n")


def quote(leaflet, blocks):
    """OCR wording of evidence blocks such as ["2-3"]; needs the pages imported."""
    parts = []
    for block in blocks:
        page_no, index = map(int, block.split("-"))
        page = session.query(Page).filter_by(volume_id=leaflet.volume_id,
                                             page_no=page_no).first()
        if page and 0 < index <= len(page.blocks or []):
            parts.append(page.blocks[index - 1].get("html", ""))
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", " ".join(parts)))).strip()


def active(entries):
    """Lines still in force: a "revert" line cancels the earlier lines
    of the leaflet ("all") or of one field."""
    kept = []
    for e in entries:
        if e["field"] == "revert":
            kept = [k for k in kept if e["value"] not in ("all", k["field"])]
        else:
            kept.append(e)
    return kept


def apply(leaflet, entries):
    """Overwrite the leaflet's fields; manual evidence replaces the automatic one."""
    for e in active(entries):
        field, value, blocks = e["field"], e["value"], e.get("blocks", [])
        leaflet.corrected = sorted(set(leaflet.corrected or []) | {field})
        if field == "title":
            leaflet.title, leaflet.title_blocks = value, blocks
            leaflet.title_quote = quote(leaflet, blocks)
        elif field == "date":
            leaflet.date_iso, leaflet.date_type = value["iso"], value["type"]
            leaflet.date_blocks, leaflet.date_quote = blocks, quote(leaflet, blocks)
        elif field == "received":  # a stamp read by hand is certain
            leaflet.received_date, leaflet.received_uncertain = value, False
            leaflet.received_blocks, leaflet.received_quote = blocks, quote(leaflet, blocks)
        elif field == "series":
            leaflet.series, leaflet.issue = value["name"], value["issue"]
            leaflet.series_blocks = blocks
            leaflet.series_quote = quote(leaflet, blocks)
        elif field == "doc_type":
            leaflet.doc_type = value
        elif field == "issuers":
            session.query(LeafletIssuer).filter_by(
                leaflet_id=leaflet.id, role="issuer").delete()
            for item in value:
                org = session.get(Organization, item["org"])
                if org:
                    session.add(LeafletIssuer(
                        leaflet_id=leaflet.id, role="issuer", org_id=org.id, surface=org.name,
                        blocks=item["blocks"], quote=quote(leaflet, item["blocks"])))
        elif field == "signatories":
            session.query(LeafletIssuer).filter_by(
                leaflet_id=leaflet.id, role="signatory").delete()
            for item in value:
                session.add(LeafletIssuer(
                    leaflet_id=leaflet.id, role="signatory", surface=item["name"],
                    function=item["details"], marker="",
                    blocks=item["blocks"], quote=quote(leaflet, item["blocks"])))
