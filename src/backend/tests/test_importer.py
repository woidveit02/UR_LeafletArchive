import base64
import io
import json
import time
import zipfile

import pymupdf
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import importer, ocr
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
    job = importer.JOBS[(volume.vz, "scans")]
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


# Tests if a new upload removes the cached page images of the old scan, and the scan has a new stamp for the addresses.
def test_new_scan_drops_the_old_thumbnails(folders, monkeypatch):
    import os
    from backend.app import pdf_service
    tmp_path, db = folders
    monkeypatch.setattr(pdf_service, "THUMB_DIR", tmp_path / "thumbs")
    volume = db.query(Volume).one()
    importer.save_scans(volume, [("a.tif", io.BytesIO(image()))])
    old = tmp_path / "thumbs" / "0118_0015-1" / "1-300.jpg"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"old page")
    unrelated = tmp_path / "thumbs" / "0118_0016-1"
    unrelated.mkdir()
    before = importer.scan_stamp(volume)
    os.utime(importer.scan_path(volume), (1, 1))  # as if the first scan had been made long ago
    importer.save_scans(volume, [("b.tif", io.BytesIO(image(80, 60)))])
    assert not old.parent.exists() and unrelated.exists()
    assert importer.scan_stamp(volume) >= before > 1


# ---------- text recognition ----------

IMAGE = "a" * 32 + "_img.jpg"


@pytest.fixture
def scan(folders, monkeypatch):
    """A volume with a scan of 120 pages (batches of 50, 50, 20) and a Datalab that is replaced by a fake."""
    tmp_path, db = folders
    volume = db.query(Volume).one()
    importer.claim(volume)
    path = importer.scan_path(volume)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    for _ in range(120):
        doc.new_page()
    doc.save(path)
    monkeypatch.setenv("DATALAB_API_KEY", "test-key-1234")
    monkeypatch.setattr(ocr, "make_client", lambda key: None)
    monkeypatch.setattr(ocr, "find_or_create_pipeline", lambda client, mode, captions: "pl_1")
    return volume


def fake_datalab(monkeypatch, calls, fail_pages=None):
    """Answers every batch like Datalab does: pages restart at 1 and the picture has the same name in every batch."""
    def convert(key, pipeline_id, pdf, phase=None):
        with pymupdf.open(pdf) as batch:
            n = batch.page_count
        calls.append(n)
        if n == fail_pages:
            raise ValueError("Datalab konnte nicht")
        children = [{"bbox": [0, 0, 100, 100], "children": [{"block_type": "Text", "html": "<p>Seite</p>", "bbox": [0, 0, 10, 10]}]}
                    for _ in range(n)]
        children[0]["children"].append({"block_type": "Picture", "html": f'<img src="{IMAGE}" alt="x">', "bbox": [0, 0, 5, 5]})
        return {"json": {"children": children}, "images": {IMAGE: base64.b64encode(b"jpg").decode()},
                "page_count": n, "_cost_cents": n}
    monkeypatch.setattr(ocr, "convert_batch", convert)


def wait_for(volume):
    job = importer.JOBS[(volume.vz, ocr.JOB)]
    for _ in range(200):
        if job["state"] != "running":
            break
        time.sleep(0.05)
    return job


# Tests if the batches are merged to the file the app reads, pictures of different batches keep different names,
# and the cost is the sum of the batches.
def test_text_recognition_merges_the_batches(scan, monkeypatch):
    calls = []
    fake_datalab(monkeypatch, calls)
    assert ocr.status(scan)["state"] == "none"
    ocr.start(scan)
    job = wait_for(scan)
    assert (job["state"], job["done"], sorted(calls)) == ("done", 120, [20, 50, 50])
    assert [p["state"] for p in job["parts"]] == ["fertig"] * 3 and ocr.status(scan)["seconds"] is not None
    out = importer.ocr_dir(scan)
    document = json.loads((out / "0118_0015.json").read_text(encoding="utf-8"))
    assert len(document["children"]) == 120
    names = {p.name for p in out.glob("*_img.jpg")}
    assert len(names) == 3 and IMAGE not in names  # one picture per batch, none of them overwritten
    assert not (out / ".batches").exists()
    info = ocr.status(scan)
    assert (info["state"], info["cost"]) == ("done", "1,07 €")
    first = ocr.page_blocks(scan, 1)
    assert [b["type"] for b in first] == ["Text", "Picture"] and first[0]["box"] == [0, 0, 10, 10]
    assert ocr.page_blocks(scan, 121) is None
    with pytest.raises(ValueError, match="schon erkannt"):
        ocr.start(scan)


# Tests if a run that fails halfway keeps the finished batches, and the next run only asks for the missing one.
def test_interrupted_run_is_continued(scan, monkeypatch):
    calls = []
    fake_datalab(monkeypatch, calls, fail_pages=20)
    ocr.start(scan)
    job = wait_for(scan)
    assert job["state"] == "error" and "Datalab konnte nicht" in job["error"]
    info = ocr.status(scan)
    assert (info["state"], info["kept"], info["batches"]) == ("partial", 2, 3)
    calls.clear()
    fake_datalab(monkeypatch, calls)
    ocr.start(scan)
    job = wait_for(scan)
    assert job["state"] == "done" and calls == [20] and job["done"] == 120  # the kept batches are not counted twice
    assert [p["kept"] for p in job["parts"]] == [True, True, False]


# Tests if a cancel stops the batches that are not sent yet, keeps the finished one, and a new run only does the rest.
def test_cancel_keeps_what_is_finished(scan, monkeypatch):
    monkeypatch.setattr(ocr, "CONCURRENCY", 1)
    calls, inner = [], []
    fake_datalab(monkeypatch, calls)
    inner.append(ocr.convert_batch)

    def first_then_cancel(key, pipeline_id, pdf, phase=None):
        result = inner[0](key, pipeline_id, pdf, phase)
        ocr.cancel(scan)  # as the button does, while the first batch is on its way
        return result
    monkeypatch.setattr(ocr, "convert_batch", first_then_cancel)
    ocr.start(scan)
    job = wait_for(scan)
    assert (job["state"], calls, ocr.status(scan)["kept"]) == ("cancelled", [50], 1)
    with pytest.raises(ValueError, match="keine Texterkennung"):
        ocr.cancel(scan)
    monkeypatch.setattr(ocr, "convert_batch", inner[0])
    ocr.start(scan)
    assert wait_for(scan)["state"] == "done" and calls == [50, 50, 20]


# Tests if the batch size sets the number of batches and is kept with an interrupted run like the quality level.
def test_batch_size(scan, monkeypatch):
    fake_datalab(monkeypatch, [], fail_pages=20)
    ocr.start(scan, size=100)  # 120 pages: a batch of 100 and one of 20, which fails
    job = wait_for(scan)
    info = ocr.status(scan)
    assert (job["state"], len(job["parts"]), info["state"], info["size"], info["kept"], info["batches"]) == ("error", 2, "partial", 100, 1, 2)
    with pytest.raises(ValueError, match="je 100 Seiten"):
        ocr.start(scan)  # the default size does not fit the kept batch
    for wrong in (1, 1000):
        with pytest.raises(ValueError, match="zwischen 5 und 250"):
            ocr.start(scan, size=wrong)
    fake_datalab(monkeypatch, [])
    ocr.start(scan, size=100)
    assert wait_for(scan)["state"] == "done" and ocr.status(scan)["size"] == 100


# Tests if a wrong key or an empty account is explained, and a new scan or discarding removes the text.
def test_no_credit_and_new_scan(scan, monkeypatch):
    class NoCredit(Exception):
        status_code = 402
    def refuse(key, pipeline_id, pdf, phase=None):
        raise NoCredit("payment required")
    monkeypatch.setattr(ocr, "convert_batch", refuse)
    ocr.start(scan)
    assert "Guthaben" in wait_for(scan)["error"]
    fake_datalab(monkeypatch, [])
    ocr.start(scan)
    wait_for(scan)
    assert ocr.status(scan)["state"] == "done"
    importer.save_scans(scan, [("a.tif", io.BytesIO(image()))])
    assert not importer.ocr_dir(scan).exists()  # the text belonged to the old scan


# Tests if the key from the page is saved outside the repository, shown only by its last characters, loses to
# the .env, and is refused when it cannot be one.
def test_key_handling(folders, monkeypatch):
    monkeypatch.delenv("DATALAB_API_KEY", raising=False)
    assert ocr.api_key() is None and ocr.key_info() is None
    for bad in ("", "short", "has a space in it"):
        with pytest.raises(ValueError, match="API-Key"):
            ocr.save_key(bad)
    ocr.save_key(" abcdefgh-1234 ")
    assert ocr.api_key() == "abcdefgh-1234" and ocr.key_info() == {"hint": "1234", "from_env": False}
    assert ocr.key_file().parent == fillDatabase.PDF_DIR
    monkeypatch.setenv("DATALAB_API_KEY", "from-env-9999")
    assert (ocr.api_key(), ocr.key_info()["from_env"]) == ("from-env-9999", True)
    monkeypatch.delenv("DATALAB_API_KEY")
    ocr.forget_key()
    assert ocr.api_key() is None
    with pytest.raises(ValueError, match="API-Key"):
        ocr.start(folders[1].query(Volume).one())


# Tests if the result can be downloaded and read in again, and a result of another scan is refused.
def test_result_zip_round_trip(scan, monkeypatch):
    fake_datalab(monkeypatch, [])
    ocr.start(scan)
    wait_for(scan)
    data = ocr.zip_result(scan)
    ocr.clear(scan)
    assert ocr.status(scan)["state"] == "none"
    ocr.import_zip(scan, io.BytesIO(data))
    info = ocr.status(scan)
    assert (info["state"], info["source"]) == ("done", "hochgeladen")
    assert info["mode_label"] == "Genau" and info["at"] is not None  # what the download carried
    assert len(list(importer.ocr_dir(scan).glob("*_img.jpg"))) == 3
    plain = io.BytesIO()  # a result from the pipeline: the JSON alone
    with zipfile.ZipFile(plain, "w") as z:
        z.writestr("x/0118_0015.json", json.dumps({"children": [{}] * 120}))
    ocr.import_zip(scan, plain)
    info = ocr.status(scan)
    assert (info["mode_label"], info["at"]) == ("Genau", None)  # taken as accurate, and no date made up
    with pytest.raises(ValueError, match="keine ZIP"):
        ocr.import_zip(scan, io.BytesIO(b"no zip"))
    short = io.BytesIO()
    with zipfile.ZipFile(short, "w") as z:
        z.writestr("x/x.json", json.dumps({"children": [{}] * 7}))
    with pytest.raises(ValueError, match="7 Seiten, der Scan 120"):
        ocr.import_zip(scan, short)


# Tests if the page of the step shows what the state calls for (estimate, button, progress, result, download) and
# never the key itself.
def test_text_step_page(scan, monkeypatch):
    from pathlib import Path
    from fastapi.templating import Jinja2Templates
    from starlette.requests import Request
    import backend.app.app as leaflet_app
    monkeypatch.setattr(leaflet_app, "session", fillDatabase.session)
    frontend = Path(__file__).resolve().parents[2] / "frontend" / "templates"
    if frontend.is_dir():
        monkeypatch.setattr(leaflet_app, "templates", Jinja2Templates(directory=frontend))

    def page(step="ocr"):
        request = Request({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
                           "scheme": "http", "path": "/import/15", "raw_path": b"/import/15", "query_string": b"",
                           "headers": [], "server": ("test", 80), "client": ("test", 1), "root_path": "",
                           "app": leaflet_app.app, "router": leaflet_app.app.router})
        return leaflet_app.import_page(request, scan.vz, step).body.decode()

    html = page()
    assert "1,07 €" in html and "Texterkennung starten" in html and "API-Key …1234)" in html
    assert "test-key-1234" not in html
    monkeypatch.delenv("DATALAB_API_KEY")
    ocr.save_key("saved-key-5678")  # a key saved from the page can be replaced or removed there
    assert 'name="forget" value="true"' in page() and "API-Key …5678)" in page()
    ocr.forget_key()
    assert "API-Key" in page() and "Speichere zuerst deinen API-Key" in page()
    monkeypatch.setenv("DATALAB_API_KEY", "test-key-1234")
    fake_datalab(monkeypatch, [])
    ocr.start(scan)
    wait_for(scan)
    html = page()
    assert 'name="captions" value="yes" checked' in html and "brauchten zuletzt" not in html
    assert "✓ Text für 120 Seiten erkannt" in html and "/import/15/ocr.zip" in html and "Erneut erkennen" in html
    assert 'class="done"' in page("trennen")  # the step bar marks the text as done
    ocr.import_zip(scan, io.BytesIO(ocr.zip_result(scan)))  # loaded from a ZIP, the page says imported, not recognized
    assert "Texterkennung für 120 Seiten importiert" in page() and "Datalab, Qualitätsstufe" not in page()
    scans_page = page("scans")
    assert "Aktuell gespeichert: <b>120 Seiten</b>" in scans_page and "Scans ersetzen" in scans_page
    assert '<details class="advanced"><summary class="button-outline">Scans ersetzen</summary>' in scans_page  # the drop zone is folded away
    assert "Upload abgeschlossen" not in scans_page and page("trennen")
    assert 'step-button disabled' in page("trennen") and 'step-button disabled' not in scans_page  # needs the saved cuts; scans are there


# Tests if the leaflet page names what is known about the text recognition and leaves out the rest.
def test_describe_text_recognition():
    assert ocr.describe("accurate", "2026-10-08") == "Datalab Convert, Qualitätsstufe Genau, 08.10.2026"
    assert ocr.describe("balanced+nocaptions", None) == "Datalab Convert, Qualitätsstufe Günstig, ohne Bildbeschreibungen"
    assert ocr.describe(None, None) == "Datalab Convert"


# Tests if the quality level sets the price and the pipeline, is kept with the batches of an interrupted run, and a
# run cannot be continued at another level.
def test_quality_level(scan, monkeypatch):
    seen = []
    monkeypatch.setattr(ocr, "find_or_create_pipeline", lambda client, mode, captions: seen.append((mode, captions)) or "pl_1")
    assert (ocr.price(120), ocr.price(120, "balanced")) == ("1,07 €", "0,43 €")
    fake_datalab(monkeypatch, [], fail_pages=20)
    ocr.start(scan, "balanced", captions=False)
    wait_for(scan)
    info = ocr.status(scan)
    assert (info["state"], info["mode"], info["mode_label"], seen) == ("partial", "balanced+nocaptions", "Günstig, ohne Bildbeschreibungen", [("balanced", False)])
    with pytest.raises(ValueError, match="Günstig"):
        ocr.start(scan, "accurate")
    with pytest.raises(ValueError, match="ohne Bildbeschreibungen"):
        ocr.start(scan, "balanced")  # the pictures were not described in the kept batches
    with pytest.raises(ValueError, match="gibt es nicht"):
        ocr.start(scan, "best")
    fake_datalab(monkeypatch, [])
    ocr.start(scan, "accurate", again=True)  # from the beginning at the other level
    wait_for(scan)
    info = ocr.status(scan)
    assert (info["state"], info["mode_label"]) == ("done", "Genau")


# Tests if opening a draft goes on with the first step that is not done yet.
def test_draft_opens_at_the_step_it_has_reached(scan, monkeypatch):
    import backend.app.app as leaflet_app
    assert leaflet_app.resume_step(scan) == "ocr"
    fake_datalab(monkeypatch, [])
    ocr.start(scan)
    wait_for(scan)
    assert leaflet_app.resume_step(scan) == "trennen"
    from backend.app import segments
    segments.save(scan, [60], 120)
    assert leaflet_app.resume_step(scan) == "angaben"
    importer.scan_path(scan).unlink()
    assert leaflet_app.resume_step(scan) == "scans"
