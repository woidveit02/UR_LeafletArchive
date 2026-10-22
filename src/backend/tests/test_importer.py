import base64
import io
import json
import math
import time
import zipfile

import pymupdf
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import importer, keys, ocr
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
    tmp_path, _ = folders
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


# Tests if the scan PDF is built in the background and the job says what it is doing, then "done".
def test_background_job_reports_progress(folders, monkeypatch):
    import time
    _, db = folders
    volume = db.query(Volume).one()
    phases = []
    copy = importer.copy_with_progress
    monkeypatch.setattr(importer, "copy_with_progress", lambda *a: phases.append(job["phase"]) or copy(*a))
    importer.start_scans(volume, [(f"{n}.tif", io.BytesIO(image())) for n in "abc"])
    job = importer.JOBS[(volume.vz, "scans")]
    with pytest.raises(ValueError, match="läuft schon"):
        if job["state"] != "running":
            pytest.skip("finished before the second upload")
        importer.start_scans(volume, [("d.tif", io.BytesIO(image()))])
    for _ in range(100):
        if job["state"] != "running":
            break
        time.sleep(0.05)
    assert job["state"] == "done" and importer.page_count(volume) == 3
    assert phases == ["PDF wird erstellt"] and job["phase"].startswith("Alte Vorschaubilder")


# Tests if a volume scanned in several folders (15.1, 15.2, ..., 15.10) with a PDF each becomes one PDF in the order
# of the folders.
def test_pdfs_in_several_folders_are_joined_in_order(folders):
    _, db = folders
    volume = db.query(Volume).one()

    def pdf(width):
        doc = pymupdf.open()
        doc.new_page(width=width, height=100)
        return io.BytesIO(doc.tobytes())
    files = [("15.10/scan.pdf", pdf(30)), ("15.2/scan.pdf", pdf(20)), ("15.1/scan.pdf", pdf(10))]
    assert importer.save_scans(volume, files) == 3
    with pymupdf.open(importer.scan_path(volume)) as doc:
        assert [p.rect.width for p in doc] == [10, 20, 30]
    with pytest.raises(ValueError, match="nicht beides"):
        importer.save_scans(volume, [("a.pdf", pdf(10)), ("b.tif", io.BytesIO(image()))])


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
    job = importer.JOBS[(16, "bild")] = {"state": "running"}  # a running job does not stop it, it is told to end
    importer.discard(added)
    assert job["cancel"] and (16, "bild") not in importer.JOBS
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
    assert (info["state"], info["cost"]) == ("done", "1,20 $")
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
    assert keys.get("datalab") is None and keys.info("datalab") is None
    for bad in ("", "short", "has a space in it"):
        with pytest.raises(ValueError, match="API-Key"):
            keys.save("datalab", bad)
    keys.save("datalab", " abcdefgh-1234 ")
    assert keys.get("datalab") == "abcdefgh-1234" and keys.info("datalab") == {"hint": "1234", "from_env": False}
    assert keys.path("datalab").parent == fillDatabase.PDF_DIR
    monkeypatch.setenv("DATALAB_API_KEY", "from-env-9999")
    assert (keys.get("datalab"), keys.info("datalab")["from_env"]) == ("from-env-9999", True)
    monkeypatch.delenv("DATALAB_API_KEY")
    keys.forget("datalab")
    assert keys.get("datalab") is None
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
    assert "1,20 $" in html and "Texterkennung starten" in html and "API-Key …1234)" in html
    assert "test-key-1234" not in html
    monkeypatch.delenv("DATALAB_API_KEY")
    keys.save("datalab", "saved-key-5678")  # a key saved from the page can be replaced or removed there
    assert 'name="forget" value="true"' in page() and "API-Key …5678)" in page()
    keys.forget("datalab")
    assert "API-Key" in page() and "Speichere zuerst deinen API-Key" in page()
    monkeypatch.setenv("DATALAB_API_KEY", "test-key-1234")
    fake_datalab(monkeypatch, [])
    ocr.start(scan)
    wait_for(scan)
    html = page()
    assert 'name="captions" value="yes" checked' in html and "brauchten zuletzt" not in html
    assert "120 Seiten · Text erkannt" in html and "/import/15/ocr.zip" in html and "Neu erkennen" in html
    assert 'class="done"' in page("trennen")  # the step bar marks the text as done
    ocr.import_zip(scan, io.BytesIO(ocr.zip_result(scan)))  # loaded from a ZIP, the page says imported, not recognized
    assert "120 Seiten · Text aus ZIP geladen" in page() and "Datalab, Qualitätsstufe" not in page()
    scans_page = page("scans")
    assert "Aktuell gespeichert: 120 Seiten" in scans_page and "Scans ersetzen" in scans_page
    assert '<summary>Andere Scans hochladen</summary>' in scans_page  # the drop zone is folded away
    assert "Upload abgeschlossen" not in scans_page and page("trennen")
    assert 'step-button disabled' in page("trennen") and 'step-button disabled' not in scans_page  # needs the saved cuts; scans are there
    from backend.app import metadata, segments
    monkeypatch.setattr(metadata, "models", lambda: [("a/b", "Modell B", 1e-6, 2e-6)])  # the default is gone
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert "Flugblätter getrennt sein" in page("angaben")
    segments.save(scan, [60], 120)
    html = page("angaben")
    assert "Metadaten erzeugen" in html and 'value="a/b" selected' in html and "gibt es bei OpenRouter nicht mehr" in html
    assert "Speichere zuerst deinen API-Key" in html
    with pytest.raises(ValueError, match="OpenRouter"):
        metadata.start(scan, "a/b", [])


# Tests if "Neu erzeugen" after a finished run asks the model again instead of taking the kept answers, and if the
# price says so; after a new split the leaflets with the same pages are still taken over.
def test_metadata_again_asks_again(scan, monkeypatch):
    from backend.app import metadata, segments
    fake_datalab(monkeypatch, [])
    ocr.start(scan)
    wait_for(scan)
    segments.save(scan, [60], 120)
    asked = []
    monkeypatch.setattr(metadata, "extract", lambda key, model, prompt, state, cost: asked.append(model) or {})
    monkeypatch.setattr(metadata, "models", lambda: [("a/b", "Modell B", 1e-6, 2e-6)])
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-9999")
    totals, recheck = [], metadata.recheck  # the job's total before the next phase: the leaflets asked for
    monkeypatch.setattr(metadata, "recheck", lambda *a: totals.append(importer.JOBS[(scan.vz, metadata.JOB)]["total"]) or recheck(*a))

    def run():
        asked.clear()
        metadata.start(scan, "a/b", [])
        job = importer.JOBS[(scan.vz, metadata.JOB)]
        for _ in range(200):
            if job["state"] != "running":
                break
            time.sleep(0.05)
        assert job["state"] == "done", job
        return totals[-1]
    assert run() == 2 and asked and metadata.status(scan)["state"] == "done"
    assert metadata.prices(scan)["a/b"] == "etwa 0,00 $" and metadata.prices(scan, fresh=True)["a/b"] != "etwa 0,00 $"
    assert run() == 2  # asked again, not taken from the kept answers
    segments.save(scan, [30, 60], 120)  # 1-30 and 31-60 are new, 61-120 stays
    assert run() == 2

# Tests if "Probleme beheben" throws away just what it says: the text takes the metadata with it, the cuts stay.
def test_resets_without_access_to_the_files(scan, monkeypatch):
    import backend.app.app as leaflet_app
    from backend.app import metadata, pdf_service, segments
    from backend.app.database import fillDatabase
    monkeypatch.setattr(leaflet_app, "session", fillDatabase.session)
    fake_datalab(monkeypatch, [])
    ocr.start(scan)
    wait_for(scan)
    segments.save(scan, [60], 120)
    metadata.result_path(scan).write_text("{}", encoding="utf-8")
    (importer.ocr_dir(scan) / "metadata-1234abcd.jsonl").write_text("", encoding="utf-8")
    pdf_service.render_thumb(importer.scan_path(scan), 1, height=100)
    assert list(pdf_service.THUMB_DIR.glob(f"{scan.stem}-*"))

    leaflet_app.import_reset(None, scan.vz, "vorschau")
    assert not list(pdf_service.THUMB_DIR.glob(f"{scan.stem}-*"))
    leaflet_app.import_reset(None, scan.vz, "metadaten")
    assert not metadata.result_path(scan).exists() and not list(importer.ocr_dir(scan).glob("metadata-*"))
    assert ocr.status(scan)["state"] == "done"
    leaflet_app.import_reset(None, scan.vz, "text")
    assert ocr.status(scan)["state"] == "none" and segments.status(scan)["cuts"] == [60] and importer.page_count(scan) == 120

# Tests if the leaflet page names what is known about the text recognition and leaves out the rest.
def test_describe_text_recognition():
    assert ocr.describe("accurate", "2026-10-08") == "Datalab Convert, accurate, 08.10.2026"
    assert ocr.describe("balanced+nocaptions", None) == "Datalab Convert, balanced, ohne Bildbeschreibungen"
    assert ocr.describe(None, None) == "Datalab Convert"


# Tests if the quality level sets the price and the pipeline, is kept with the batches of an interrupted run, and a
# run cannot be continued at another level.
def test_quality_level(scan, monkeypatch):
    seen = []
    monkeypatch.setattr(ocr, "find_or_create_pipeline", lambda client, mode, captions: seen.append((mode, captions)) or "pl_1")
    assert (ocr.price(120), ocr.price(120, "balanced")) == ("1,20 $", "0,48 $")
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


# Tests if cuts are suggested where the text speaks for a new leaflet, not where it speaks against one or says
# nothing, and are saved as unconfirmed.
def test_cuts_from_the_text(scan):
    from backend.app import boundaries, segments
    with pytest.raises(ValueError, match="noch nicht erkannt"):
        segments.suggest(scan)
    assert segments.missed_cuts(scan, [9], [], 120) is None  # no text, no hints
    # no hint, no cut: a page without any feature stays below the threshold (check again after learning new weights)
    assert boundaries.probability(set()) < boundaries.MIN_PROBABILITY

    def page(*blocks):
        return {"children": [{"block_type": t, "html": f"<p>{x}</p>"} for t, x in blocks]}
    call = "Wir fordern alle Studenten auf, zur Vollversammlung zu kommen."
    other = "Alle Hochschulgruppen protestieren gegen Kürzungen beim Studentenwerk heute"  # a few words in common
    pages = [page(("Text", call))] * 120
    pages[9] = page(("PageHeader", "LSD - LSD - LSD"), ("Text", other + "."))  # masthead: a start
    pages[29] = page(("Text", "UB Regensburg eingelaufen am: 1. FEB. 1973"), ("Text", other + "."))  # stamp: a start
    pages[39] = page(("Text", "- 2 -"), ("Text", call))  # a page number: a continuation
    pages[48] = page(("Text", call.rstrip(".")))
    pages[49] = page(("Text", other))  # nothing for or against a start
    ocr.result_path(scan).parent.mkdir(parents=True, exist_ok=True)
    ocr.result_path(scan).write_text(json.dumps({"children": pages}), encoding="utf-8")
    blocks = boundaries.page_blocks(ocr.result_path(scan))
    assert boundaries.features(blocks[49], blocks[48]) == set()
    assert segments.suggest(scan) == 2
    status = segments.status(scan)
    assert (status["cuts"], status["suggested"], status["confirmed"]) == ([9, 29], [9, 29], False)
    why = segments.reasons(scan)  # for every transition, from the text alone while the scan is not measured
    assert not why["images"] and len(why["transitions"]) == 119 and why["transitions"][8][0] >= 0.5
    # looks of another scan do not count
    from backend.app import looks
    other = {"version": looks.VERSION, "scan": importer.scan_stamp(scan) - 1, "pages": []}
    segments.write(segments.looks_path(scan), other)
    assert segments.load_looks(scan) is None
    # with the looks of this scan its blank pages are left out
    look = {"size": [595, 842], "paper": [230, 228, 220], "ink": 0.05, "margins": [0.1] * 4, "blank": False,
            "sign": False, "stamp": False, "holes": "none", "spots": {"holes": [], "blue": []}}
    pages = [look] * 49 + [look | {"blank": True, "ink": 0.0}] + [look] * 70
    other["scan"], other["pages"] = importer.scan_stamp(scan), pages
    segments.write(segments.looks_path(scan), other)
    segments.suggest(scan)
    assert segments.status(scan)["excluded"] == [50] and segments.reasons(scan)["images"]
    segments.save(scan, [9, 29, 60], 120)  # saved by somebody: nothing is a suggestion any more
    assert (segments.status(scan)["suggested"], segments.status(scan)["confirmed"]) == ([], True)
    # a list without the cut after 30 gets it as a hint; its own cuts and the ones a left-out page forces are no hints
    assert segments.missed_cuts(scan, [9, 60], [], 120) == [29]
    assert segments.missed_cuts(scan, [9], [30], 120) == []


# Tests if the reasons of a suggestion add up to its probability, strongest for first, with only the strongest word
# for a cut counted, and if the scan adds to the text: holes on the right make a page the back of the sheet before.
def test_reasons_of_a_suggestion():
    from backend.app import boundaries
    previous = [("Text", "Wir fordern alle auf.\nVerantwortlich: A. Muster, Eigendruck")]
    page = [("Text", "UB Regensburg eingelaufen am: 1. FEB. 1973"), ("Text", "Alle Gruppen protestieren heute")]
    p, reasons = boundaries.explain(page, previous)
    assert p == pytest.approx(1 / (1 + math.exp(-(boundaries.PRIOR + sum(w for _, w in reasons)))))
    assert [w for _, w in reasons] == sorted((w for _, w in reasons), reverse=True)
    labels = [label for label, _ in reasons]
    assert "Eingangsstempel" in labels and "Impressum auf der Seite davor" in labels
    # only the strongest word for a cut counts: "eingelaufen" is stronger than "eigendruck"
    assert [label for label in labels if "„" in label] == ["„eingelaufen“ am Seitenanfang"]

    look = {"size": [595, 842], "paper": [230, 228, 220], "ink": 0.05, "margins": [0.1, 0.1, 0.1, 0.1],
            "blank": False, "sign": False, "stamp": False, "holes": "none"}
    plain = [("Text", "und deshalb fordern wir die Abschaffung")]
    alone = boundaries.explain(plain, previous)[0]
    assert boundaries.explain(plain, previous, None, look)[0] == alone  # without the looks of both pages: text only
    back, reasons = boundaries.explain(plain, previous, look | {"holes": "right"}, look)
    assert back < alone and ("Löcher rechts: Rückseite", boundaries.IMAGE_WEIGHTS["back"]) in reasons
    assert ("gleiche Papierfarbe", boundaries.IMAGE_WEIGHTS["paper_same"]) in reasons
