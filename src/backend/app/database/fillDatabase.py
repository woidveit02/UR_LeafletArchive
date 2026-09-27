import html
import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path

from .session import session
from .models import Volume, Page, Leaflet, Organization, LeafletIssuer

if os.environ.get("LEAFLET_DATA_DIR"):
    DATA_DIR = Path(os.environ["LEAFLET_DATA_DIR"])
else:
    DATA_DIR = Path(__file__).resolve().parents[4] / "data"

PDF_DIR = Path(os.environ.get("LEAFLET_PDF_DIR", "/data/pdfs"))


def load_json(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def fill_organizations():
    orgs_by_variant = {}
    for org in load_json("organizations.json"):
        session.add(Organization(
            id=org["org_id"],
            name=org["name"],
            full_name=org.get("full_name", ""),
            type=org.get("type", ""),
            variants=org.get("variants", []),
            jahre=org.get("jahre", []),
            vz=org.get("vz", []),
            gnd_id=org.get("gnd_id", ""),
            notes=org.get("notes", ""),
        ))
        for variant in org.get("variants", []):
            orgs_by_variant[variant.strip().lower()] = org["org_id"]
    session.commit()
    return orgs_by_variant


VOLUMES = [
    {"metadata_file": "nr002_metadata.json",
     "label": "Nr. 002 (1968)", "year": 1968},
]


ALLOWED_TAGS = {"p", "br", "u", "b", "i", "strong", "em",
                "ul", "ol", "li", "h1", "h2", "h3", "h4",
                "table", "thead", "tbody", "tr", "th", "td"}


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag in ("ul", "ol"):
            self.out.append(f'<{tag} class="ocr-list">')
        elif tag in ALLOWED_TAGS:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in ALLOWED_TAGS and tag != "br":
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        self.out.append(html.escape(data))


def sanitize(raw):
    parser = _Sanitizer()
    parser.feed(raw)
    parser.close()
    return "".join(parser.out)


def load_pages(volume_label, stem):
    json_path = PDF_DIR / volume_label / stem / f"{stem}.json"
    if not json_path.is_file():
        return {}
    doc = json.loads(json_path.read_text(encoding="utf-8"))
    pages = {}
    for page_no, page in enumerate(doc.get("children", []), start=1):
        px0, py0, px1, py1 = page.get("bbox", [0, 0, 1, 1])
        pw, ph = (px1 - px0) or 1, (py1 - py0) or 1
        blocks, parts = [], []
        for b in page.get("children", []):
            block_type = b.get("block_type", "Text")
            x0, y0, x1, y1 = b.get("bbox", [0, 0, 0, 0])
            box = [round((x0 - px0) / pw * 100, 2),
                   round((y0 - py0) / ph * 100, 2),
                   round((x1 - x0) / pw * 100, 2),
                   round((y1 - y0) / ph * 100, 2)]
            if block_type == "Picture":
                blocks.append({"type": block_type, "html": "", "box": box})
                continue
            clean = sanitize(b.get("html", ""))
            blocks.append({"type": block_type, "html": clean, "box": box})
            parts.append(html.unescape(re.sub(r"<[^>]+>", " ", clean)))
        text = re.sub(r"\s+", " ", " ".join(parts)).strip()
        pages[page_no] = {"text": text, "blocks": blocks}
    return pages


def fill_volume(cfg, orgs_by_variant):
    meta = load_json(cfg["metadata_file"])
    records = meta["segments"]
    n_pages = max(r["end_page"] for r in records)
    stem = meta["source_pdf"].removesuffix(".pdf")
    ocr_pages = load_pages(cfg["label"], stem)
    if not ocr_pages:
        print(f"Warnung: Keine OCR-Daten unter {PDF_DIR / cfg['label']}, "
              "Transkriptionen bleiben leer.")

    volume = Volume(
        stem=stem,
        label=cfg["label"],
        year=cfg["year"],
        n_pages=n_pages,
    )
    session.add(volume)
    session.commit()

    leaflet_by_page = {}
    for r in records:
        if r.get("no_content"):
            continue
        leaflet = Leaflet(
            volume_id=volume.id,
            start_page=r["start_page"],
            end_page=r["end_page"],
            title=r.get("title", ""),
            title_type=r.get("title_type", ""),
            date_text=r.get("date_text", ""),
            date_iso=r.get("date_iso", ""),
            date_type=r.get("date_type", ""),
            doc_type=r.get("doc_type", ""),
            confidence=r.get("confidence", 0),
        )
        session.add(leaflet)
        session.flush()
        for issuer in r.get("issuers", []):
            session.add(LeafletIssuer(
                leaflet_id=leaflet.id,
                surface=issuer["surface"],
                role=issuer["role"],
                org_id=orgs_by_variant.get(issuer["surface"].strip().lower()),
            ))
        for page_no in range(r["start_page"], r["end_page"] + 1):
            leaflet_by_page[page_no] = leaflet.id
    session.commit()

    for page_no in range(1, n_pages + 1):
        ocr = ocr_pages.get(page_no, {})
        session.add(Page(
            volume_id=volume.id,
            page_no=page_no,
            text=ocr.get("text", ""),
            blocks=ocr.get("blocks", []),
            leaflet_id=leaflet_by_page.get(page_no),
        ))
    session.commit()


def fill_database():
    if session.query(Leaflet).count() > 0:
        return
    orgs_by_variant = fill_organizations()
    for cfg in VOLUMES:
        fill_volume(cfg, orgs_by_variant)
