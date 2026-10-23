"""Issuers the metadata named but the register does not know: grouped by spelling, with the known organizations
of a similar name, and the decision on each (a new organization or a spelling of a known one) kept in the
register file. Also the leaflets with no issuer at all, until someone decided on each."""
import difflib
import re

from .database import corrections, fillDatabase
from .database.models import RELEASED, Leaflet, LeafletIssuer, Organization, Page, Volume

SIMILAR, SHOWN = 0.75, 3
NONE = {"personen": "Nur Personen", "unbekannt": "Nicht feststellbar"}  # decisions on a leaflet without issuer
IMPRINT = re.compile(r"verantwortlich|v\.\s?i\.\s?s\.\s?d\.\s?p|hrsg\.|herausgeber|herausgegeben|eigendruck|selbstverlag", re.I)


def key(surface):
    return " ".join(surface.split()).casefold()


def other_copy(leaflet):
    """A copy of a checked group but its main copy: its details are those of the main copy, decided there."""
    return leaflet.copies_checked and leaflet.canonical_leaflet_id not in (None, leaflet.id)


def unmatched(vz=0):
    """[{surface, issuers: [(leaflet, issuer row)], vz: {leaflet id: volume number}}] for the issuers of the volume
    (0: of all released volumes) without an organization, most frequent first. Not an other copy."""
    groups = {}
    for issuer, leaflet, number in fillDatabase.session.query(LeafletIssuer, Leaflet, Volume.vz).select_from(LeafletIssuer).join(Leaflet).join(Volume).filter(
            Volume.vz == vz if vz else Volume.status == RELEASED, LeafletIssuer.role == "issuer",
            LeafletIssuer.org_id.is_(None)).order_by(Volume.vz, Leaflet.start_page):
        if issuer.surface.strip() and not other_copy(leaflet):
            group = groups.setdefault(key(issuer.surface), {"surface": issuer.surface.strip(), "issuers": [], "vz": {}})
            if leaflet not in [lf for lf, _ in group["issuers"]]:
                group["issuers"].append((leaflet, issuer))
                group["vz"][leaflet.id] = number
    return sorted(groups.values(), key=lambda g: (-len(g["issuers"]), g["surface"].casefold()))


def decisions():
    """(volume stem, first page, last page) -> the last decision on a leaflet without issuer: {"value": a key of
    NONE, "at": its day}."""
    return {(e["volume"], e["start_page"], e["end_page"]): e
            for e in corrections.load(fillDatabase.CHECKED) if e["field"] == "issuers"}


def missing(vz=0):
    """Groups like unmatched, one per leaflet of the volume (0: of all released volumes) that names no issuer and
    nobody decided on yet; surface "". Not an other copy."""
    session, decided = fillDatabase.session, decisions()
    named = {i for (i,) in session.query(LeafletIssuer.leaflet_id).filter(LeafletIssuer.role == "issuer")}
    rows = session.query(Leaflet, Volume.vz, Volume.stem).join(Volume).filter(
        Volume.vz == vz if vz else Volume.status == RELEASED).order_by(Volume.vz, Leaflet.start_page)
    return [{"surface": "", "issuers": [(lf, None)], "vz": {lf.id: number}}
            for lf, number, stem in rows
            if lf.id not in named and (stem, lf.start_page, lf.end_page) not in decided
            and not other_copy(lf)]


def decide_none(volume, leaflet, value):
    """Keeps that a leaflet has no issuer ("personen", "unbekannt"); like "Passt so" by its pages, so it outlasts
    rebuilding the database."""
    corrections.append(fillDatabase.CHECKED, [{"volume": volume.stem, "start_page": leaflet.start_page,
                                               "end_page": leaflet.end_page, "field": "issuers", "value": value}])


def imprint_blocks(leaflet):
    """Block ids such as "3-2" of the leaflet whose text sounds like an imprint ("Verantwortlich", "Eigendruck" …)."""
    return [f"{p.page_no}-{n}" for p in fillDatabase.session.query(Page).filter_by(leaflet_id=leaflet.id).order_by(Page.page_no)
            for n, b in enumerate(p.blocks or [], 1) if IMPRINT.search(b.get("html", ""))]


def candidates(surface):
    """[(organization, its most similar form)] of a similar spelling, or whose short form is a word of the
    surface, best first; none rather than weak ones."""
    k, scored = key(surface), {}
    for org in fillDatabase.session.query(Organization):
        for form in {f for f in [org.name, org.full_name, *(org.variants or [])] if f}:
            score = difflib.SequenceMatcher(None, k, key(form)).ratio()  # ponytail: spelling only, no meaning
            if len(form) >= 3 and re.search(rf"(?<!\w){re.escape(key(form))}(?!\w)", k):
                score = max(score, SIMILAR)
            if score >= SIMILAR and score > scored.get(org.id, (0,))[0]:
                scored[org.id] = (score, org, form)
    return [(org, form) for _, org, form in sorted(scored.values(), key=lambda s: -s[0])[:SHOWN]]


def create(orgs, name, full_name, variants):
    """Adds an organization to orgs (the entries of the register file) and to the database; returns its id."""
    base = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_") or "org"
    taken = {o["org_id"] for o in orgs}
    org_id = next(i for i in [base] + [f"{base}_{n}" for n in range(2, 99)] if i not in taken)
    entry = {"org_id": org_id, "name": name, "full_name": full_name, "type": "", "variants": variants,
             "jahre": [], "vz": [], "notes": "in der App angelegt"}
    orgs.append(entry)
    fillDatabase.session.add(Organization(id=org_id, name=name, full_name=full_name, type="", variants=variants,
                                          jahre=[], vz=[], notes=entry["notes"]))
    return org_id


def new(name, full_name=""):
    """A new organization that is only one of several named in a spelling ("AStA und Fachschaft Chemie"), so the
    spelling does not become its variant; returns its id."""
    orgs = fillDatabase.load_json("organizations.json")
    name, full_name = name.strip(), full_name.strip()
    org_id = create(orgs, name, full_name if full_name != name else "", [v for v in dict.fromkeys((name, full_name)) if v])
    fillDatabase.save_json("organizations.json", orgs)
    fillDatabase.session.commit()
    return org_id


def decide(surface, choice, full_name="", short=""):
    """choice: "neu" (a new organization named so, or by its short name if given) or the id of a known organization
    the spelling belongs to. Returns the organization's id."""
    session, k, surface, short = fillDatabase.session, key(surface), surface.strip(), short.strip()
    orgs = fillDatabase.load_json("organizations.json")
    if choice == "neu":
        full_name = full_name.strip() or (surface if short and short != surface else "")
        org_id = create(orgs, short or surface, full_name, [surface] + [short] * bool(short and short != surface))
    else:
        org_id = choice
        entry = next(o for o in orgs if o["org_id"] == org_id)
        entry["variants"] = entry.get("variants", []) + [surface] * (surface not in entry.get("variants", []))
        session.get(Organization, org_id).variants = list(entry["variants"])
    fillDatabase.save_json("organizations.json", orgs)
    for issuer in session.query(LeafletIssuer).filter(LeafletIssuer.role == "issuer", LeafletIssuer.org_id.is_(None)):
        if key(issuer.surface) == k:
            issuer.org_id = org_id
    session.commit()
    return org_id
