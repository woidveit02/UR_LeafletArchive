import io
import json

import pymupdf
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import importer
from backend.app.database import fillDatabase
from backend.app.database.base import Base
from backend.app.database.models import DRAFT, Volume


def image(width=40, height=60):
    return pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height), False).tobytes("png")


@pytest.fixture
def folders(tmp_path, monkeypatch):
    entry = {"vz": 15, "label": "Nr. 015 (1973)", "stem": None, "year": 1973, "title": "T", "signature": "S",
             "digitized": False, "portal_url": None, "group": "1973"}
    (tmp_path / "volumes.json").write_text(json.dumps([entry]), encoding="utf-8")
    units = [("vz", "jahr", "einheit", "bestellsignatur", "portal_url"),
             ("15", "1973", "Flugblätter 1973", "Rep. 118, 15", ""),
             ("16", "1974", "Flugblätter 1974", "Rep. 118, 16", "https://portal.example/16"),
             ("17", "1975", "Flugblätter 1975", "Rep. 118, 17", "")]
    (tmp_path / "findmittel.tsv").write_text("\n".join("\t".join(row) for row in units), encoding="utf-8")
    monkeypatch.setattr(fillDatabase, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fillDatabase, "PDF_DIR", tmp_path / "pdfs")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(fillDatabase.volume_from_entry(entry))
    db.commit()
    monkeypatch.setattr(fillDatabase, "session", db)
    return tmp_path, db


# Tests if a unit of the findmittel becomes a draft volume with its data, and an unknown or taken number is refused.
def test_new_volume_is_a_draft_from_the_findmittel(folders):
    tmp_path, db = folders
    assert [u["vz"] for u in importer.free_units()] == [16, 17]
    volume = importer.new_volume(16, portal_url=" ")
    assert volume.portal_url == "https://portal.example/16"  # the link of the findmittel unless one is typed in
    assert (volume.vz, volume.label, volume.stem, volume.status) == (16, "Nr. 016 (1974)", "0118_0016", DRAFT)
    assert (volume.title, volume.signature) == ("Flugblätter 1974", "Rep. 118, 16")
    assert [u["vz"] for u in importer.free_units()] == [17]
    for taken in (16, 15, 99):
        with pytest.raises(ValueError, match="im Findmittel nicht"):
            importer.new_volume(taken)
    assert [e["vz"] for e in json.loads((tmp_path / "volumes.json").read_text(encoding="utf-8"))] == [15, 16]
    assert importer.pending_volumes() == db.query(Volume).order_by(Volume.vz).all()


# Tests if the portal link can be changed or removed, in volumes.json and in the database.
def test_portal_link_can_be_changed(folders):
    tmp_path, db = folders
    volume = db.query(Volume).one()
    importer.set_portal_url(volume, " https://portal.example/15 ")
    assert volume.portal_url == "https://portal.example/15"
    assert json.loads((tmp_path / "volumes.json").read_text(encoding="utf-8"))[0]["portal_url"] == "https://portal.example/15"
    importer.set_portal_url(volume, "")
    assert volume.portal_url is None


# Tests if TIFFs are merged in file name order into one PDF and a volume nobody digitized yet becomes a draft.
def test_tiffs_become_one_pdf_and_claim_the_volume(folders):
    tmp_path, db = folders
    volume = db.query(Volume).one()
    files = [("0002.tif", io.BytesIO(image())), ("0001.tif", io.BytesIO(image(80, 60)))]
    assert importer.save_scans(volume, files) == 2
    assert (volume.stem, volume.digitized, volume.status) == ("0118_0015", True, DRAFT)
    with pymupdf.open(importer.scan_path(volume)) as doc:
        assert [round(p.rect.width * 400 / 72) for p in doc] == [80, 40]  # 0001 first
    entry = json.loads((tmp_path / "volumes.json").read_text(encoding="utf-8"))[0]
    assert entry["stem"] == "0118_0015" and entry["digitized"]


# Tests if a chosen folder works with other files in it, and files without a scan are refused with a message
# and leave nothing behind.
def test_folder_with_other_files_and_wrong_files(folders):
    _, db = folders
    volume = db.query(Volume).one()
    with pytest.raises(ValueError, match="TIFF-Dateien"):
        importer.save_scans(volume, [("Thumbs.db", io.BytesIO(b"")), ("notes.txt", io.BytesIO(b""))])
    assert importer.save_scans(volume, [("scan/0001.tif", io.BytesIO(image())), ("scan/Thumbs.db", io.BytesIO(b""))]) == 1
    importer.scan_path(volume).unlink()
    with pytest.raises(ValueError, match="nicht als Scan lesen"):
        importer.save_scans(volume, [("a.tif", io.BytesIO(b"no image"))])
    assert importer.page_count(volume) is None


# Tests if the scan PDF is built in the background and the job reports the pages done, then "done".
def test_background_job_reports_progress(folders):
    import time
    _, db = folders
    volume = db.query(Volume).one()
    importer.start_scans(volume, [(f"{n}.tif", io.BytesIO(image())) for n in "abc"])
    job = importer.JOBS[volume.vz]
    assert job["total"] == 3
    with pytest.raises(ValueError, match="läuft schon"):
        if job["state"] != "running":
            pytest.skip("finished before the second upload")
        importer.start_scans(volume, [("d.tif", io.BytesIO(image()))])
    for _ in range(100):
        if job["state"] != "running":
            break
        time.sleep(0.05)
    assert (job["state"], job["done"]) == ("done", 3) and importer.page_count(volume) == 3


# Tests if discarding removes the scan and gives the unit back: an added volume disappears, an archive unit
# of volumes.json only goes back to "not digitized".
def test_discard_volume(folders, monkeypatch):
    from backend.app import pdf_service
    monkeypatch.setattr(pdf_service, "THUMB_DIR", folders[0] / "thumbs")
    tmp_path, db = folders
    archive_unit = db.query(Volume).one()
    importer.save_scans(archive_unit, [("a.tif", io.BytesIO(image()))])
    scan = importer.scan_path(archive_unit)
    assert scan.is_file()
    importer.discard(archive_unit)
    entry = json.loads((tmp_path / "volumes.json").read_text(encoding="utf-8"))[0]
    assert not scan.exists() and (entry["stem"], entry["digitized"]) == (None, False)
    assert (archive_unit.stem, archive_unit.digitized, archive_unit.status) == (None, False, "freigegeben")

    added = importer.new_volume(16)
    importer.discard(added)
    assert db.query(Volume).filter_by(vz=16).count() == 0
    assert [u["vz"] for u in importer.free_units()] == [16, 17]  # number free again
