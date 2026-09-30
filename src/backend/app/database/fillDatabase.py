import html
import json
import os
import re
from collections import Counter
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


def issuer_org_ids(issuer, orgs_by_variant, known_ids):
    # newer metadata carries org_ids, older only the surface form
    if "org_ids" in issuer:
        return [i for i in issuer["org_ids"] if i in known_ids] or [None]
    return [orgs_by_variant.get(issuer["surface"].strip().lower())]


def series_key(name):
    return re.sub(r"[^a-z0-9äöüß]", "", (name or "").lower())


def series_names(configs):
    """Most frequent spelling per series across all volumes."""
    counts = {}
    for cfg in configs:
        for r in load_json(cfg["metadata_file"])["segments"]:
            name = (r.get("series") or "").strip()
            if name:
                counts.setdefault(series_key(name), Counter())[name] += 1
    return {key: c.most_common(1)[0][0] for key, c in counts.items()}


def own_blocks(block_ids, record, label=None):
    """Block ids on the leaflet's pages; none if the pipeline's grounding check
    found the quote missing from them (label as in check_block_ids)."""
    if label and any(p.startswith(f"{label}:") and ("nicht in den genannten" in p or "unbekannt" in p)
                     for p in record.get("_grounding") or []):
        return []
    pages = range(record["start_page"], record["end_page"] + 1)
    return [b for b in block_ids or [] if b.split("-")[0].isdigit() and int(b.split("-")[0]) in pages]


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


def fill_volumes():
    volumes = {}
    for v in load_json("volumes.json"):
        volume = Volume(vz=v["vz"], stem=v["stem"], label=v["label"],
                        year=v["year"], title=v["title"], group=v["group"],
                        signature=v["signature"], collection=v["collection"],
                        digitized=v["digitized"],
                        portal_url=v.get("portal_url"))
        session.add(volume)
        volumes[v["label"]] = volume
    session.commit()
    return volumes


VOLUMES = [
    {"metadata_file": "nr001_metadata.json",
     "label": "Nr. 001 (1967)", "year": 1967},
    {"metadata_file": "nr002_metadata.json",
     "label": "Nr. 002 (1968)", "year": 1968},
    {"metadata_file": "nr004_metadata.json",
     "label": "Nr. 004 (1970)", "year": 1970},
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
                src = re.search(r'src="([^"]+)"', b.get("html", ""))
                alt = re.search(r'alt="([^"]*)"', b.get("html", ""))  # Datalab image caption
                blocks.append({"type": block_type, "html": "", "box": box,
                               "image": src.group(1) if src else None,
                               "description": html.unescape(alt.group(1)) if alt else ""})
                continue
            clean = sanitize(b.get("html", ""))
            blocks.append({"type": block_type, "html": clean, "box": box})
            parts.append(html.unescape(re.sub(r"<[^>]+>", " ", clean)))
        text = re.sub(r"\s+", " ", " ".join(parts)).strip()
        pages[page_no] = {"text": text, "blocks": blocks}
    return pages


def fill_volume(cfg, orgs_by_variant, volumes, series_by_key=None):
    meta = load_json(cfg["metadata_file"])
    records = meta["segments"]
    n_pages = max(r["end_page"] for r in records)
    stem = meta["source_pdf"].removesuffix(".pdf")
    ocr_pages = load_pages(cfg["label"], stem)

    volume = volumes.get(cfg["label"])
    if volume is None:
        volume = Volume(label=cfg["label"], year=cfg["year"])
        session.add(volume)
    volume.stem = stem
    volume.n_pages = n_pages
    volume.meta_model = meta.get("model")
    volume.meta_created = meta.get("created", "")[:10]
    session.commit()

    known_ids = {org_id for (org_id,) in session.query(Organization.id)}
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
            series=(series_by_key or {}).get(series_key(r.get("series")),
                                             (r.get("series") or "").strip()),
            issue=(r.get("issue") or "").strip(),
            received_date=r.get("received_date", ""),
            received_uncertain=bool(r.get("received_year_uncertain")),
            doc_type=r.get("doc_type", ""),
            confidence=r.get("confidence", 0),
            title_blocks=own_blocks(r.get("title_blocks"), r, "title"),
            date_blocks=own_blocks(r.get("date_blocks"), r, "date"),
            received_blocks=own_blocks(r.get("received_blocks"), r),
            title_quote=r.get("title_evidence", ""),
            date_quote=r.get("date_evidence", ""),
            received_quote=r.get("received_evidence", ""),
        )
        session.add(leaflet)
        session.flush()
        for issuer in r.get("issuers", []):
            for org_id in issuer_org_ids(issuer, orgs_by_variant, known_ids):
                session.add(LeafletIssuer(
                    leaflet_id=leaflet.id,
                    surface=issuer["surface"],
                    role=issuer["role"],
                    org_id=org_id,
                    blocks=own_blocks(issuer.get("blocks"), r, f"issuer {issuer['surface']!r}"),
                    quote=issuer.get("evidence", ""),
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


def check_data_dir(pdf_dir=PDF_DIR):
    """Returns readable hints if PDFs or OCR files are missing in the
    mounted data folder; empty list if everything is in place."""
    if not pdf_dir.is_dir() or not any(pdf_dir.iterdir()):
        return [f"{pdf_dir} is empty or missing. Is the path in "
                "LEAFLET_PDF_HOST_DIR (.env) correct? For a wrong path, "
                "Docker silently creates an empty folder."]
    problems = []
    for cfg in VOLUMES:
        label = cfg["label"]
        stem = load_json(cfg["metadata_file"])["source_pdf"].removesuffix(".pdf")
        vol_dir = pdf_dir / label
        if not vol_dir.is_dir():
            if (pdf_dir / f"{stem}.pdf").is_file():
                hint = "The path points one level too deep, at the volume folder itself."
            elif any(p.is_dir() for p in pdf_dir.glob(f"*/{label}")):
                hint = "The path points one level too high."
            elif (pdf_dir / "organizations.json").is_file():
                hint = "The default folder ./data is mounted. Is the .env missing?"
            else:
                found = ", ".join(sorted(p.name for p in pdf_dir.iterdir())[:5])
                hint = f"Found instead: {found}"
            problems.append(f"Folder '{label}' is missing. {hint}")
            continue
        if not (vol_dir / f"{stem}.pdf").is_file():
            problems.append(f"{label}: {stem}.pdf is missing, no scans will be shown.")
        if not (vol_dir / stem / f"{stem}.json").is_file():
            problems.append(f"{label}: {stem}/{stem}.json is missing, "
                            "transcriptions will be empty.")
    return problems


def report_data_dir():
    problems = check_data_dir()
    host_dir = os.environ.get("LEAFLET_PDF_HOST_DIR") or "(not set)"
    if not problems:
        print(f"Data folder ok: {host_dir}")
        return True
    print(f"WARNING data folder {host_dir}:")
    for problem in problems:
        print(f"  - {problem}")
    print("  The site still runs, but without scans or OCR text. "
          "After fixing it, delete the .db and restart.")
    return False


def fill_database():
    data_ok = report_data_dir()
    if session.query(Leaflet).count() > 0:
        if data_ok and session.query(Page).filter(Page.text != "").first() is None:
            print("Note: the database was built without OCR text, but the "
                  "data folder is complete now. Delete the .db and restart.")
        return
    orgs_by_variant = fill_organizations()
    volumes = fill_volumes()
    series_by_key = series_names(VOLUMES)
    for cfg in VOLUMES:
        fill_volume(cfg, orgs_by_variant, volumes, series_by_key)
