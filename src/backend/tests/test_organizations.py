import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import organizations
from backend.app.database import fillDatabase
from backend.app.database.base import Base
from backend.app.database.models import Leaflet, LeafletIssuer, Organization, Volume


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
