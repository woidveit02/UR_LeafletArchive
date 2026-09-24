import json
import os
from pathlib import Path

from .session import session
from .models import Volume, Page, Leaflet, Organization, LeafletIssuer

# Data dir: LEAFLET_DATA_DIR in Docker (mounted), else repo-root data/.
if os.environ.get("LEAFLET_DATA_DIR"):
    DATA_DIR = Path(os.environ["LEAFLET_DATA_DIR"])
else:
    DATA_DIR = Path(__file__).resolve().parents[4] / "data"


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


def fill_leaflets(orgs_by_variant):
    meta = load_json("nr002_metadata.json")
    records = meta["segments"]
    n_pages = max(r["end_page"] for r in records)

    volume = Volume(
        stem=meta["source_pdf"].removesuffix(".pdf"),
        label="Nr. 002 (1968)",
        year=1968,
        n_pages=n_pages,
    )
    session.add(volume)
    session.commit()

    leaflet_by_page = {}
    for r in records:
        if r.get("no_content"):
            continue
        leaflet = Leaflet(
            id=r["id"],
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
        session.add(Page(
            volume_id=volume.id,
            page_no=page_no,
            leaflet_id=leaflet_by_page.get(page_no),
        ))
    session.commit()


def fill_database():
    if session.query(Leaflet).count() > 0:
        return
    orgs_by_variant = fill_organizations()
    fill_leaflets(orgs_by_variant)
