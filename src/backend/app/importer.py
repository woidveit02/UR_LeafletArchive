"""Import of a new volume, step by step: the entry in volumes.json, the volume in the database
as a draft, the scans as one PDF in the scan folder."""
import csv
import json
import logging
import shutil
import threading
from pathlib import Path

import pymupdf

from . import pdf_service
from .database import fillDatabase
from .database.models import DRAFT, RELEASED, Leaflet, Volume

logger = logging.getLogger(__name__)
TIFF_SUFFIXES = {".tif", ".tiff"}
JPEG_QUALITY, DPI = 75, 400  # as pipelines/01_pdf/tiff_to_pdf.py
STEPS = {"band": "Band wählen", "scans": "Scans hochladen", "ocr": "Text erkennen", "trennen": "Flugblätter trennen",
         "angaben": "Metadaten", "pruefen": "Prüfen & freigeben", "themen": "Themen zuordnen"}
# what a step is for, said to somebody who does not know the system: under the step bar and as its tooltips
STEP_HELP = {"band": "Wähle den Band, dessen Scans du hinzufügen möchtest.",
             "scans": "Die gescannten Seiten des Bandes hochladen.",
             "ocr": "Der Text der Scans wird automatisch erkannt, damit er sich lesen und durchsuchen lässt.",
             "trennen": "Festlegen, wo ein Flugblatt endet und das nächste beginnt.",
             "angaben": "Titel, Datum, Herausgeber und weitere Angaben werden automatisch aus dem Text ermittelt.",
             "pruefen": "Die Ergebnisse durchsehen und den Band für alle sichtbar machen.",
             "themen": "Die Flugblätter werden Themen zugeordnet."}


def load_entries():
    return fillDatabase.load_json("volumes.json")


def save_entries(entries):
    # same layout as the file in the repo (two spaces, CRLF, no final newline), so only changes show up in git
    text = json.dumps(entries, ensure_ascii=False, indent=2).replace("\n", "\r\n")
    with open(fillDatabase.DATA_DIR / "volumes.json", "w", encoding="utf-8", newline="") as f:
        f.write(text)


def running(volume, kind="scans"):
    return JOBS.get((volume.vz, kind), {}).get("state") == "running"


def update_entry(vz, **changes):
    """Changes the fields of one volume in volumes.json."""
    save_entries([{**e, **changes} if e["vz"] == vz else e for e in load_entries()])


def n_leaflets(volume):
    return fillDatabase.session.query(Leaflet).filter_by(volume_id=volume.id).count()


def scan_path(volume):
    return fillDatabase.PDF_DIR / volume.label / f"{volume.stem}.pdf"


def ocr_dir(volume):
    """Where the text recognition of the scan lives: <stem>.json, its pictures and the unfinished batches."""
    return scan_path(volume).parent / volume.stem


def pending_volumes():
    """Volumes without leaflets yet: not digitized, or a draft in progress."""
    session = fillDatabase.session
    return [v for v in session.query(Volume).order_by(Volume.vz) if not n_leaflets(v)]


def free_units():
    """The archive's units (findmittel.tsv, all 85 of 1967-2024) that have no entry in volumes.json yet."""
    known = {e["vz"] for e in load_entries()}
    with open(fillDatabase.DATA_DIR / "findmittel.tsv", encoding="utf-8", newline="") as f:
        units = [{"vz": int(r["vz"]), "year": int(r["jahr"]), "title": r["einheit"], "signature": r["bestellsignatur"],
                  "portal_url": r.get("portal_url") or None}
                 for r in csv.DictReader(f, delimiter="	")]
    return [u for u in units if u["vz"] not in known]


def new_volume(vz, portal_url=""):
    """Adds a unit of the archive as volume: entry in volumes.json and draft in the database."""
    unit = next((u for u in free_units() if u["vz"] == vz), None)
    if unit is None:
        raise ValueError(f"Nr. {vz} gibt es im Findmittel nicht oder sie ist schon angelegt.")
    year = unit["year"]
    entry = {"vz": vz, "label": f"Nr. {vz:03d} ({year})", "stem": f"0118_{vz:04d}", "year": year,
             "title": unit["title"], "signature": unit["signature"],
             "added": True, "digitized": True, "portal_url": portal_url.strip() or unit["portal_url"], "group": str(year)}
    entries = load_entries()
    save_entries(entries + [entry])
    session = fillDatabase.session
    volume = fillDatabase.volume_from_entry(entry)
    volume.status = DRAFT
    session.add(volume)
    session.commit()
    return volume


def set_portal_url(volume, portal_url):
    """Changes the archive portal link of a volume, in volumes.json and in the database."""
    volume.portal_url = portal_url.strip() or None
    update_entry(volume.vz, portal_url=volume.portal_url)
    fillDatabase.session.commit()


def drop_thumbs(stem):
    """The cached page images of a scan; they are made again from the next scan."""
    for thumbs in pdf_service.THUMB_DIR.glob(f"{stem}-*"):
        shutil.rmtree(thumbs, ignore_errors=True)


def scan_stamp(volume):
    """Changes whenever the scan is replaced; in the image addresses, so the browser does not show the old pages."""
    path = scan_path(volume)
    return int(path.stat().st_mtime) if path.is_file() else 0


def discard(volume):
    """Removes a volume that is still being imported: its scan and temporary files, and the volume itself.

    A unit the archive listed in volumes.json from the start only goes back to "not digitized";
    one added by new_volume disappears, so its number is free again.
    """
    if n_leaflets(volume):
        raise ValueError("Dieser Band ist schon eingelesen und lässt sich hier nicht löschen.")
    if any(running(volume, kind) for kind in ("scans", "segment", "ocr")):
        raise ValueError("Für diesen Band läuft gerade ein Upload oder eine Berechnung. Bitte warten, bis sie fertig ist.")
    for kind in ("scans", "segment", "ocr"):
        JOBS.pop((volume.vz, kind), None)
    if volume.stem:
        target = scan_path(volume)
        pdf_service._doc_cache.pop(str(target), None)
        target.unlink(missing_ok=True)
        target.with_name(f"{volume.stem}.segments.json").unlink(missing_ok=True)
        shutil.rmtree(target.parent / f".upload-{volume.vz}", ignore_errors=True)
        shutil.rmtree(ocr_dir(volume), ignore_errors=True)
        drop_thumbs(volume.stem)
        try:
            target.parent.rmdir()  # only if nothing else is in it
        except OSError:
            pass
    entries = load_entries()
    added = next(e for e in entries if e["vz"] == volume.vz).get("added")
    if added:
        save_entries([e for e in entries if e["vz"] != volume.vz])
    else:
        update_entry(volume.vz, stem=None, digitized=False)
    session = fillDatabase.session
    if added:
        session.delete(volume)
    else:
        volume.stem, volume.digitized, volume.status, volume.n_pages = None, False, RELEASED, None
    session.commit()


def tiffs_to_pdf(paths, out, progress=None):
    """One page per image, in the order given, recompressed as JPEG like the pipeline does.
    progress(n) is called after n pages."""
    doc = pymupdf.open()
    for n, path in enumerate(paths, 1):
        pix = pymupdf.Pixmap(str(path))
        if pix.colorspace.n != 3 or pix.alpha:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        if pix.alpha:
            pix = pymupdf.Pixmap(pix, 0)
        page = doc.new_page(width=pix.width * 72 / DPI, height=pix.height * 72 / DPI)
        page.insert_image(page.rect, stream=pix.tobytes("jpg", jpg_quality=JPEG_QUALITY))
        if progress:
            progress(n)
    doc.save(out, garbage=3, deflate=True)


def claim(volume):
    """A volume the findmittel lists but nobody digitized yet becomes a draft with a stem of its own."""
    if volume.stem and volume.digitized and volume.status == DRAFT:
        return
    volume.stem = volume.stem or f"0118_{volume.vz:04d}"
    volume.digitized, volume.status = True, DRAFT
    update_entry(volume.vz, stem=volume.stem, digitized=True)
    fillDatabase.session.commit()


def stage(volume, files):
    """Checks the uploaded files (name, file object) and copies them next to the scan; returns
    (kind, paths, target). One PDF is taken as it is, TIFFs are merged in file name order; other
    files, such as Thumbs.db from a chosen folder, are left out. Raises ValueError with a message
    for the user if the files do not fit or the folder cannot be written."""
    if n_leaflets(volume):
        raise ValueError("Dieser Band ist schon eingelesen, seine Scans lassen sich nicht ersetzen.")
    if running(volume) or running(volume, "ocr"):
        raise ValueError("Für diesen Band läuft schon ein Upload oder die Texterkennung. Bitte warten, bis sie fertig ist.")
    if len(files) == 1 and Path(files[0][0]).suffix.lower() == ".pdf":
        kind = "pdf"
    else:
        files = [f for f in files if Path(f[0]).suffix.lower() in TIFF_SUFFIXES]
        kind = "tiff"
    if not files:
        raise ValueError("Bitte ein PDF oder TIFF-Dateien (.tif, .tiff) auswählen, einzeln oder als Ordner.")

    claim(volume)
    target = scan_path(volume)
    staging = target.parent / f".upload-{volume.vz}"
    try:
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        paths = []
        for name, source in sorted(files, key=lambda f: f[0].lower()):
            paths.append(staging / Path(name).name)
            with open(paths[-1], "wb") as out:
                shutil.copyfileobj(source, out)
    except OSError as error:
        raise ValueError(storage_problem(error, target)) from error
    return kind, paths, target


def storage_problem(error, target):
    if isinstance(error, PermissionError):
        return (f"Der Scan-Ordner {target.parent} ist nicht beschreibbar. Ist LEAFLET_PDF_HOST_DIR "
                "in der .env gesetzt und der Ordner für Docker schreibbar freigegeben?")
    return f"Die Scans konnten nicht gespeichert werden: {error}"


def build(kind, paths, target, progress=None):
    """Makes the scan PDF from the staged files and removes them. Raises ValueError like stage."""
    staging = paths[0].parent
    result = target.parent / f"{target.name}.part"
    try:
        if kind == "pdf":
            pymupdf.open(paths[0]).close()  # raises if it is no PDF
            paths[0].replace(result)
        else:
            tiffs_to_pdf(paths, result, progress)
        with pdf_service._lock:
            pdf_service._doc_cache.pop(str(target), None)  # a replaced scan must not stay cached
            drop_thumbs(target.stem)
            shutil.rmtree(target.parent / target.stem, ignore_errors=True)  # the text belongs to the old scan
            result.replace(target)
    except OSError as error:
        raise ValueError(storage_problem(error, target)) from error
    except (pymupdf.FileDataError, pymupdf.mupdf.FzErrorBase) as error:
        raise ValueError("Eine der Dateien lässt sich nicht als Scan lesen. Sind es wirklich PDF- "
                         "oder TIFF-Dateien?") from error
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        result.unlink(missing_ok=True)


def save_scans(volume, files):
    """Stores the files as the volume's scan PDF and returns its page count."""
    kind, paths, target = stage(volume, files)
    build(kind, paths, target)
    return page_count(volume)


# per (volume number, "scans" | "segment" | "ocr"): {"state": "running" | "done" | "error", "error": text, ...}
JOBS = {}  # ponytail: in memory, gone after a restart; a jobs table when OCR needs one


def start_scans(volume, files):
    """Like save_scans, but the PDF is built in the background; poll JOBS[volume.vz]."""
    kind, paths, target = stage(volume, files)
    job = JOBS[(volume.vz, "scans")] = {"state": "running", "done": 0, "total": len(paths) if kind == "tiff" else 1, "error": ""}

    def run():
        try:
            build(kind, paths, target, lambda n: job.update(done=n))
            job.update(state="done", done=job["total"])
        except ValueError as error:
            job.update(state="error", error=str(error))
        except Exception as error:  # a thread must report, not die silently
            logger.exception("building the scan failed")
            job.update(state="error", error=f"Unerwarteter Fehler: {error}")

    threading.Thread(target=run, daemon=True).start()


def page_count(volume):
    """Pages of the volume's scan PDF, or None if there is none yet."""
    path = scan_path(volume)
    if not path.is_file():
        return None
    with pymupdf.open(path) as doc:
        return doc.page_count
