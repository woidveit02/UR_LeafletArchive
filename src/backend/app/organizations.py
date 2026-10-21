"""Issuers the metadata named but the register does not know: grouped by spelling, with the known organizations
of a similar name, and the decision on each (a new organization or a spelling of a known one) kept in the
register file."""
import difflib
import re

from .database import fillDatabase
from .database.models import Leaflet, LeafletIssuer, Organization, Volume

SIMILAR, SHOWN = 0.75, 3


def key(surface):
    return " ".join(surface.split()).casefold()


def unmatched(vz):
    """[{surface, issuers: [(leaflet, issuer row)]}] for the issuers of the volume without an organization,
    most frequent first."""
    groups = {}
    for issuer, leaflet in fillDatabase.session.query(LeafletIssuer, Leaflet).join(Leaflet).join(Volume).filter(
            Volume.vz == vz, LeafletIssuer.role == "issuer", LeafletIssuer.org_id.is_(None)).order_by(Leaflet.start_page):
        if issuer.surface.strip():
            group = groups.setdefault(key(issuer.surface), {"surface": issuer.surface.strip(), "issuers": []})
            if leaflet not in [lf for lf, _ in group["issuers"]]:
                group["issuers"].append((leaflet, issuer))
    return sorted(groups.values(), key=lambda g: (-len(g["issuers"]), g["surface"].casefold()))


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


def decide(surface, choice, full_name="", short=""):
    """choice: "neu" (a new organization named so, or by its short name if given) or the id of a known organization
    the spelling belongs to. Returns the organization's id."""
    session, k, surface, short = fillDatabase.session, key(surface), surface.strip(), short.strip()
    orgs = fillDatabase.load_json("organizations.json")
    if choice == "neu":
        name = short or surface
        full_name = full_name.strip() or (surface if short and short != surface else "")
        variants = [surface] + [short] * bool(short and short != surface)
        base = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_") or "org"
        taken = {o["org_id"] for o in orgs}
        org_id = next(i for i in [base] + [f"{base}_{n}" for n in range(2, 99)] if i not in taken)
        entry = {"org_id": org_id, "name": name, "full_name": full_name, "type": "", "variants": variants,
                 "jahre": [], "vz": [], "notes": "in der App angelegt"}
        orgs.append(entry)
        session.add(Organization(id=org_id, name=name, full_name=full_name, type="", variants=variants,
                                 jahre=[], vz=[], notes=entry["notes"]))
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
