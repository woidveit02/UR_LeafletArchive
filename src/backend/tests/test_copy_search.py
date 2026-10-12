from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import copy_search
from backend.app.database import fillDatabase
from backend.app.database.base import Base
from backend.app.database.models import Leaflet, Page, Volume

TEXT = "Kommilitonen! Die Vollversammlung am Mittwoch beschließt den Streik gegen das Hochschulgesetz. " * 3
OTHER = "Einladung zum Sommerfest der Fachschaft mit Musik, Getränken und einem Vortrag über die Mensa. " * 3


# Tests if a new volume's copies join the group of their partner, a lone partner gets a group, and taking the
# volume back leaves copies.tsv as before.
def test_add_and_remove(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setattr(fillDatabase, "session", db)
    monkeypatch.setattr(fillDatabase, "DATA_DIR", tmp_path)
    old = Volume(vz=2, stem="0118_0002", label="Nr. 002 (1968)", year=1968)
    new = Volume(vz=15, stem="0118_0015", label="Nr. 015 (1973)", year=1973)
    db.add_all([old, new])
    db.flush()
    for volume, texts in [(old, [TEXT, TEXT, OTHER]), (new, [TEXT + " Nachtrag", OTHER, "zu kurz"])]:
        for p, text in enumerate(texts, 1):
            db.add(Leaflet(volume_id=volume.id, start_page=p, end_page=p))
            db.add(Page(volume_id=volume.id, page_no=p, text=f"Kopfzeile {text}", blocks=[
                {"type": "PageHeader", "html": "Kopfzeile"}, {"type": "Text", "html": f"<p>{text}</p>"}]))
    db.commit()
    before = "gruppe\tkanonisch\tband\tseiten\tsegment_id\tzeichen\tanfang\r\n" \
             "1\tja\tNr. 002 (1968)\t1\t1\t300\tKommilitonen\r\n1\t\tNr. 002 (1968)\t2\t2\t300\tKommilitonen\r\n"
    (tmp_path / "copies.tsv").write_text(before, encoding="utf-8", newline="")

    assert copy_search.add(new) == 2
    rows = {(r["band"], r["seiten"]): (r["gruppe"], r["kanonisch"], r["segment_id"]) for r in copy_search.read()[1]}
    assert rows[("Nr. 015 (1973)", "1")] == ("1", "", "")  # joins the group of its partner
    assert rows[("Nr. 015 (1973)", "2")][0] == rows[("Nr. 002 (1968)", "3")][0] == "2"  # a new group with the lone partner
    assert rows[("Nr. 002 (1968)", "3")][2] == "+0118_0015" and ("Nr. 015 (1973)", "3") not in rows
    assert db.query(Leaflet).filter_by(volume_id=new.id, start_page=1).one().copy_group is not None

    copy_search.remove(new)
    assert (tmp_path / "copies.tsv").read_text(encoding="utf-8") == before.replace("\r\n", "\n")
