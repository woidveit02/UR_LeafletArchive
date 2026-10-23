import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import organizations
from backend.app.database import fillDatabase
from backend.app.database.base import Base
from backend.app.database.models import Leaflet, LeafletIssuer, Organization, Page, Volume


# Tests if unknown issuers are grouped with similar organizations, and if each decision reaches the register file and the database.
def test_decide(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setattr(fillDatabase, "session", db)
    monkeypatch.setattr(fillDatabase, "DATA_DIR", tmp_path)
    fillDatabase.save_json("organizations.json", [{"org_id": "asta", "name": "AStA", "variants": ["AStA"]}])
    db.add(Organization(id="asta", name="AStA", full_name="", variants=["AStA"]))
    volume = Volume(vz=15, stem="0118_0015", label="Nr. 015 (1973)", year=1973)
    db.add(volume)
    db.flush()
    for p, surface in [(1, "Fachschaft Chemie"), (2, "fachschaft  chemie"), (3, "ASTA."), (4, "Hans Meier")]:
        leaflet = Leaflet(volume_id=volume.id, start_page=p, end_page=p)
        db.add(leaflet)
        db.flush()
        db.add(LeafletIssuer(leaflet_id=leaflet.id, role="issuer", surface=surface))
    db.commit()

    groups = organizations.unmatched(15)
    assert [(g["surface"], len(g["issuers"])) for g in groups] == [("Fachschaft Chemie", 2), ("ASTA.", 1), ("Hans Meier", 1)]
    assert [g["surface"] for g in organizations.unmatched()] == [g["surface"] for g in groups]  # all released volumes
    volume.status = "entwurf"
    assert organizations.unmatched() == [] and len(organizations.unmatched(15)) == 3  # a draft only on its own
    volume.status = "freigegeben"
    copy = db.query(Leaflet).filter_by(start_page=2).one()
    copy.copies_checked, copy.canonical_leaflet_id = True, db.query(Leaflet).filter_by(start_page=1).one().id
    assert len(organizations.unmatched(15)[0]["issuers"]) == 1  # another copy: decided on its main copy
    copy.copies_checked = False
    assert [(o.id, form) for o, form in organizations.candidates("ASTA.")] == [("asta", "AStA")]
    assert [o.id for o, _ in organizations.candidates("AStA der Uni Regensburg")] == ["asta"]
    assert organizations.candidates("Hans Meier") == []

    assert organizations.decide("Fachschaft Chemie", "neu") == "fachschaft_chemie"
    organizations.decide("ASTA.", "asta")
    assert [g["surface"] for g in organizations.unmatched(15)] == ["Hans Meier"]
    assert {i.surface: i.org_id for i in db.query(LeafletIssuer)} == {
        "Fachschaft Chemie": "fachschaft_chemie", "fachschaft  chemie": "fachschaft_chemie", "ASTA.": "asta", "Hans Meier": None}
    register = {o["org_id"]: o["variants"] for o in json.loads((tmp_path / "organizations.json").read_text(encoding="utf-8"))}
    assert register == {"asta": ["AStA", "ASTA."], "fachschaft_chemie": ["Fachschaft Chemie"]}
    assert fillDatabase.issuer_org_ids({"surface": "ASTA.", "org_ids": []}, fillDatabase.variant_index(), {"asta"}) == ["asta"]

    # a new organization with a short name: named by it, the spelling in the text becomes its long form
    assert organizations.decide("Liberaler Studentenbund Deutschlands", "neu", short="LSD") == "lsd"
    entry = json.loads((tmp_path / "organizations.json").read_text(encoding="utf-8"))[-1]
    assert (entry["name"], entry["full_name"], entry["variants"]) == ("LSD", "Liberaler Studentenbund Deutschlands",
                                                                      ["Liberaler Studentenbund Deutschlands", "LSD"])

    # one of several named together: the spelling of the text stays unknown, no issuer gets it
    assert organizations.new("FS Chemie", "Fachschaft Chemie") == "fs_chemie"
    entry = json.loads((tmp_path / "organizations.json").read_text(encoding="utf-8"))[-1]
    assert (entry["name"], entry["full_name"], entry["variants"]) == ("FS Chemie", "Fachschaft Chemie", ["FS Chemie", "Fachschaft Chemie"])
    assert db.get(Organization, "fs_chemie") and [g["surface"] for g in organizations.unmatched(15)] == ["Hans Meier"]

    # a leaflet naming no issuer stays open until decided, its imprint is found for the evidence
    monkeypatch.setattr(fillDatabase, "CHECKED", tmp_path / "checked.jsonl")
    bare = Leaflet(volume_id=volume.id, start_page=5, end_page=5)
    db.add(bare)
    db.flush()
    db.add(Page(volume_id=volume.id, page_no=5, leaflet_id=bare.id, text="",
                blocks=[{"html": "<p>Aufruf</p>"}, {"html": "<p>Verantwortlich: Hans Meier</p>"}]))
    db.commit()
    assert [g["issuers"][0][0].id for g in organizations.missing(15)] == [bare.id]
    assert organizations.imprint_blocks(bare) == ["5-2"]
    organizations.decide_none(volume, bare, "personen")
    assert organizations.missing(15) == [] and organizations.missing() == []
