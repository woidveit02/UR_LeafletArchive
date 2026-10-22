import csv
import html
import json
import os
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

from . import copy_decisions, corrections, search
from .session import session
from .models import DRAFT, RELEASED, Volume, Page, Leaflet, Organization, LeafletIssuer, Topic

if os.environ.get("LEAFLET_DATA_DIR"):
    DATA_DIR = Path(os.environ["LEAFLET_DATA_DIR"])
else:
    DATA_DIR = Path(__file__).resolve().parents[4] / "data"

PDF_DIR = Path(os.environ.get("LEAFLET_PDF_DIR", "/data/pdfs"))
CORRECTIONS = Path(os.environ.get("LEAFLET_CORRECTIONS") or DATA_DIR / "corrections.jsonl")
COPY_DECISIONS = Path(os.environ.get("LEAFLET_COPY_DECISIONS") or DATA_DIR / "copy_decisions.jsonl")
CHECKED = Path(os.environ.get("LEAFLET_CHECKED") or DATA_DIR / "checked.jsonl")  # "Passt so" for the remarks of the checks


def load_json(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def save_json(name, data):
    # same layout as the files in the repo (two spaces, CRLF, no final newline), so only changes show up in git
    text = json.dumps(data, ensure_ascii=False, indent=2).replace("\n", "\r\n")
    with open(DATA_DIR / name, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def copy_groups(stems, name="copies.tsv"):
    """(volume stem, start page, end page) -> (group id, proposed main copy), from copies.tsv
    of find_copies.py. stems: volume label -> stem."""
    path = DATA_DIR / name
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f, delimiter="\t") if r["band"] in stems]
    first_last = [(r, r["seiten"].partition("-")) for r in rows]
    return {(stems[r["band"]], int(first), int(last or first)): (int(r["gruppe"]), r["kanonisch"] == "ja")
            for r, (first, _, last) in first_last}


def copy_review():
    """(groups, unresolved reviews, leaflet by anchor): the automatic groups of copies.tsv
    with the reviews of copy_decisions.jsonl applied, for the imported leaflets."""
    leaflets = {(stem, lf.start_page, lf.end_page): lf
                for lf, stem in session.query(Leaflet, Volume.stem).join(Volume)}
    stems = dict(session.query(Volume.label, Volume.stem))
    groups, unresolved = copy_decisions.resolve(
        copy_groups(stems), copy_decisions.follow(corrections.load(COPY_DECISIONS), set(leaflets)), set(leaflets))
    return groups, unresolved, leaflets


def fill_copies():
    """Writes the groups into the leaflets; also used after a review, so it starts from scratch."""
    session.query(Leaflet).update({Leaflet.copy_group: None, Leaflet.canonical_leaflet_id: None,
                                   Leaflet.copies_checked: False, Leaflet.copy_candidate_of: None})
    groups, _, leaflets = copy_review()
    drafts = {v.id for v in session.query(Volume).filter_by(status=DRAFT)}
    for number, group in enumerate(groups, 1):
        main = leaflets[group["canonical"]].id
        released = [leaflets[a] for a in group["members"] if leaflets[a].volume_id not in drafts]
        if leaflets[group["canonical"]].volume_id in drafts and released:  # a draft must not hide a released leaflet
            main = max(released, key=lambda lf: sum(len(p.text or "") for p in
                                                   session.query(Page).filter_by(leaflet_id=lf.id))).id
        for a in group["members"]:
            leaflet = leaflets[a]
            leaflet.copy_group, leaflet.canonical_leaflet_id = number, main
            leaflet.copies_checked = group["checked"]
        for a in group["candidates"]:
            leaflets[a].copy_candidate_of = number
    session.commit()


def issuer_org_ids(issuer, orgs_by_variant, known_ids):
    if issuer.get("role") == "signatory":
        return [None]
    # newer metadata carries org_ids, older only the surface form
    if "org_ids" in issuer:  # a spelling decided in the app since is in the variants
        return [i for i in issuer["org_ids"] if i in known_ids] or [orgs_by_variant.get(issuer["surface"].strip().lower())]
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


def variant_index():
    """Lower-cased spelling -> org id, from organizations.json."""
    return {variant.strip().lower(): org["org_id"]
            for org in load_json("organizations.json")
            for variant in org.get("variants", [])}


def fill_organizations():
    for org in load_json("organizations.json"):
        session.add(Organization(
            id=org["org_id"],
            name=org["name"],
            full_name=org.get("full_name", ""),
            type=org.get("type", ""),
            variants=org.get("variants", []),
            jahre=org.get("jahre", []),
            vz=org.get("vz", []),
            notes=org.get("notes", ""),
        ))
    session.commit()
    return variant_index()


def volume_from_entry(v):
    return Volume(vz=v["vz"], stem=v["stem"], label=v["label"],
                  year=v["year"], title=v["title"], group=v["group"],
                  signature=v["signature"],
                  digitized=v["digitized"],
                  portal_url=v.get("portal_url"))


def fill_volumes():
    volumes = {}
    for v in load_json("volumes.json"):
        volume = volume_from_entry(v)
        session.add(volume)
        volumes[v["label"]] = volume
    session.commit()
    return volumes


def fill_topics():
    """Import topic labels and apply page-range assignments by volume stem."""
    if not (DATA_DIR / "topics.json").is_file():
        return

    data = load_json("topics.json")
    session.query(Leaflet).update({Leaflet.topic_id: None})
    session.query(Topic).filter(Topic.id.notin_([t["id"] for t in data["topics"]])).delete()  # after a new run with fewer topics
    for topic in data["topics"]:
        session.merge(Topic(
            id=topic["id"],
            title=topic["title"],
            source=topic["title_source"],
            words=topic["words"],
        ))

    assignments = {
        (item["volume"], item["start_page"], item["end_page"]): item
        for item in data["leaflets"]
    }
    leaflets = session.query(Leaflet, Volume.stem).join(Volume)
    for leaflet, volume_stem in leaflets:
        assignment = assignments.get(
            (volume_stem, leaflet.start_page, leaflet.end_page))
        topic_id = assignment.get("topic") if assignment else None
        leaflet.topic_id = topic_id
        leaflet.topic_uncertain = bool(
            assignment and topic_id is not None and assignment["uncertain"])
    session.commit()


def fill_topic_map():
    """Import the fixed 2D layout (topic_map.py) by volume stem and page range."""
    if not (DATA_DIR / "topic_map.json").is_file():
        return

    points = {(item["stem"], item["start_page"], item["end_page"]): item
             for item in load_json("topic_map.json")}
    leaflets = session.query(Leaflet, Volume.stem).join(Volume)
    for leaflet, volume_stem in leaflets:
        point = points.get((volume_stem, leaflet.start_page, leaflet.end_page))
        leaflet.x = point["x"] if point else None
        leaflet.y = point["y"] if point else None
    session.commit()


# every volume with a metadata file in data/ is imported
VOLUMES = [{"metadata_file": f"nr{v['vz']:03d}_metadata.json", "label": v["label"], "year": v["year"]}
           for v in load_json("volumes.json")
           if (DATA_DIR / f"nr{v['vz']:03d}_metadata.json").is_file()]


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


def automatic_values(r, series_by_key):
    return dict(
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
        series_blocks=[], series_quote="", corrected=[],
    )


def add_issuers(leaflet, r, orgs_by_variant, known_ids):
    for issuer in r.get("issuers", []):
        for org_id in issuer_org_ids(issuer, orgs_by_variant, known_ids):
            session.add(LeafletIssuer(
                leaflet_id=leaflet.id,
                surface=issuer["surface"],
                role=issuer["role"],
                org_id=org_id,
                blocks=own_blocks(issuer.get("blocks"), r, f"issuer {issuer['surface']!r}"),
                quote=issuer.get("evidence", ""),
                function=(issuer.get("function") or "").strip(),
                marker=(issuer.get("marker") or "").strip(),
                other_institution=(issuer.get("_other_institution") or [None])[0],
            ))


def automatic_record(leaflet):
    volume = session.get(Volume, leaflet.volume_id)  # by number: VOLUMES misses a volume created since the start
    return next(r for r in load_json(f"nr{volume.vz:03d}_metadata.json")["segments"]
                if (r["start_page"], r["end_page"]) == (leaflet.start_page, leaflet.end_page))


def reset_leaflet(leaflet):
    """Back to the values of the metadata file, as before any manual correction."""
    r = automatic_record(leaflet)
    for column, value in automatic_values(r, series_names(VOLUMES)).items():
        setattr(leaflet, column, value)
    session.query(LeafletIssuer).filter_by(leaflet_id=leaflet.id).delete()
    add_issuers(leaflet, r, variant_index(),
                {org_id for (org_id,) in session.query(Organization.id)})


def fill_volume(cfg, orgs_by_variant, volumes, series_by_key, fixes):
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
    try:  # written by the app's text recognition; volumes recognized earlier have none
        run = json.loads((PDF_DIR / cfg["label"] / stem / "ocr-lauf.json").read_text(encoding="utf-8"))
        volume.ocr_mode, volume.ocr_created = run.get("mode"), (run.get("at") or "")[:10]
    except (OSError, ValueError):
        pass
    session.commit()

    known_ids = {org_id for (org_id,) in session.query(Organization.id)}
    leaflet_by_page = {}
    corrected = []
    for r in records:
        if r.get("no_content"):
            continue
        leaflet = Leaflet(
            volume_id=volume.id,
            start_page=r["start_page"],
            end_page=r["end_page"],
            **automatic_values(r, series_by_key),
        )
        session.add(leaflet)
        session.flush()
        add_issuers(leaflet, r, orgs_by_variant, known_ids)
        corrected.append((leaflet, fixes.get((stem, r["start_page"], r["end_page"]), [])))
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

    # after the pages: manual evidence takes its wording from their OCR text
    for leaflet, entries in corrected:
        corrections.apply(leaflet, entries)
    session.commit()


def import_volume(vz):
    """Reads one volume into the existing database, as a draft until it is released.

    Needs its entry in volumes.json and nrXXX_metadata.json; nothing else in the
    database is touched. Raises ValueError if the volume already has leaflets.
    """
    entry = next((v for v in load_json("volumes.json") if v["vz"] == vz), None)
    if entry is None:
        raise ValueError(f"volumes.json has no volume {vz}")
    cfg = {"metadata_file": f"nr{vz:03d}_metadata.json", "label": entry["label"], "year": entry["year"]}
    volume = session.query(Volume).filter_by(vz=vz).first()
    if volume and session.query(Leaflet).filter_by(volume_id=volume.id).count():
        raise ValueError(f"volume {vz} is already imported")
    if volume is None:
        volume = volume_from_entry(entry)
        session.add(volume)
    volume.status = DRAFT
    session.commit()
    configs = [c for c in VOLUMES if c["label"] != cfg["label"]] + [cfg]
    fill_volume(cfg, variant_index(), {cfg["label"]: volume}, series_names(configs),
                corrections.by_segment(corrections.load(CORRECTIONS)))
    fill_copies()
    return volume


def release_volume(vz, status=RELEASED):
    """Makes a draft visible in the list, the search, the trends and the topics; status=DRAFT hides a volume again."""
    volume = session.query(Volume).filter_by(vz=vz).one()
    volume.status = status
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
    engine = session.get_bind()
    search.ensure_search_index(engine)
    if session.query(Leaflet).count() > 0:
        if data_ok and session.query(Page).filter(Page.text != "").first() is None:
            print("Note: the database was built without OCR text, but the "
                  "data folder is complete now. Delete the .db and restart.")
        return
    orgs_by_variant = fill_organizations()
    volumes = fill_volumes()
    series_by_key = series_names(VOLUMES)
    fixes = corrections.by_segment(corrections.load(CORRECTIONS))
    for cfg in VOLUMES:
        fill_volume(cfg, orgs_by_variant, volumes, series_by_key, fixes)
    fill_copies()
    fill_topics()
    fill_topic_map()
    search.rebuild_search_index(engine)
