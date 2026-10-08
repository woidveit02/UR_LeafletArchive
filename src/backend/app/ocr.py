"""Text recognition of a volume's scan with Datalab, with the batches and settings of pipelines/02_ocr/flugblatt_convert.py.
Finished batches are kept; the merged result is <stem>/<stem>.json plus pictures, which fillDatabase.load_pages reads.
A result can also be downloaded and loaded again as ZIP."""
import base64
import binascii
import hashlib
import io
import json
import logging
import os
import re
import shutil
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pymupdf

from . import importer
from .database import fillDatabase

logger = logging.getLogger(__name__)
JOB = "ocr"
BATCH_PAGES = 50  # pages per batch unless chosen otherwise, within these limits (Datalab takes 200 MB per file)
BATCH_MIN, BATCH_MAX = 5, 250
CONCURRENCY = 4  # batches in flight at once, each with its own client (the SDK's is not thread safe)
POLL_SECONDS, MAX_POLLS = 10, 180  # 30 minutes per batch
# quality levels with the price per page in $ (datalab.to/pricing: $10 accurate, $4 balanced and fast), for the estimate only
MODES = {"accurate": ("Genau", 0.01, "Voreinstellung, wie bei den Bänden 1 bis 14"),
         "balanced": ("Günstig", 0.004, "Geringere Kosten, möglicherweise mehr Erkennungsfehler")}
USD_PER_EUR, RATES_FROM = 1.1177, "7.10.2026"  # ECB rate of that day; the prices are estimates, so change both together
DEFAULT_MODE = "accurate"  # as the volumes 1 to 14
NO_CREDIT = (401, 402, 403)  # wrong key or empty account
PIPELINE_NAME = "Flugblatt_Pipeline"  # accurate; the other level gets "_balanced"
PIPELINE_SETTINGS = {  # as in the pipeline script
    "output_mode": "accurate", "paginate": True, "merge_cross_page": True, "disable_image_captions": False,
    "keep_pageheader_in_output": True, "keep_pagefooter_in_output": True, "word_bboxes": False,
    "add_block_ids": False, "disable_image_extraction": False, "extras": ["new_block_types"]}
FINISHED = ("completed", "completed_with_errors", "failed")
IMAGE_NAME = re.compile(r"^[0-9a-f]{32}_img\.\w+$")
MAX_UNPACKED = 2_000_000_000  # of an uploaded ZIP


# ---------- the key ----------

def key_file():
    return fillDatabase.PDF_DIR / ".datalab-key"  # next to the scans, outside the repository


def api_key():
    """DATALAB_API_KEY from the .env wins over the key saved from the page."""
    key = os.getenv("DATALAB_API_KEY", "").strip()
    if key:
        return key
    try:
        return key_file().read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def key_info():
    """What the page may show of the key: its source and last four characters."""
    key = api_key()
    if not key:
        return None
    return {"hint": key[-4:], "from_env": bool(os.getenv("DATALAB_API_KEY", "").strip())}


def save_key(key):
    key = key.strip()
    if len(key) < 10 or re.search(r"\s", key):
        raise ValueError("Das sieht nicht nach einem API-Key aus. Er steht auf datalab.to unter „API Keys“.")
    path = key_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # only the app's user may read it
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(key)
    except OSError as error:
        raise ValueError(importer.storage_problem(error, path)) from error


def forget_key():
    key_file().unlink(missing_ok=True)


# ---------- state ----------

def batches(n_pages, size=BATCH_PAGES):
    """The batches as (first page, last page), 1-based."""
    return [(a, min(a + size - 1, n_pages)) for a in range(1, n_pages + 1, size)]


def result_path(volume):
    return importer.ocr_dir(volume) / f"{volume.stem}.json"


def batch_path(volume, first, last):
    return importer.ocr_dir(volume) / ".batches" / f"{first:05d}-{last:05d}.json"


def euro(dollars):
    return f"{dollars / USD_PER_EUR:.2f}".replace(".", ",") + " €"


def price(pages, mode=DEFAULT_MODE):
    return euro(pages * MODES[mode][1])


def variant(mode, captions=True):
    """The level of a run, plus "+nocaptions" if pictures were not described. Written next to the batches."""
    return mode + ("" if captions else "+nocaptions")


def variant_label(value):
    mode, _, extra = (value or "").partition("+")
    return MODES.get(mode, ("unbekannt",))[0] + (", ohne Bildbeschreibungen" if extra else "")


def describe(mode, created):
    """Line for the leaflet page, e.g. "Datalab Convert, Qualitätsstufe Genau, 08.10.2026". Volumes recognized before
    the app may lack level or date."""
    bits = ["Datalab Convert"]
    if mode:
        bits.append(f"Qualitätsstufe {variant_label(mode)}")
    if created:
        bits.append(".".join(reversed(created.split("-"))))
    return ", ".join(bits)


def kept_mode(volume):
    """Variant of the batches kept from an interrupted run, if any."""
    folder = importer.ocr_dir(volume) / ".batches"
    try:
        return (folder / "modus.txt").read_text(encoding="utf-8") if any(folder.glob("0*.json")) else None
    except OSError:
        return None


def kept_size(volume):
    """Pages per batch of the kept batches (a run of another size cannot reuse them)."""
    try:
        return int((importer.ocr_dir(volume) / ".batches" / "groesse.txt").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return BATCH_PAGES


def status(volume):
    """State for the page: "none", "partial" (batches kept from an interrupted run) or "done"."""
    pages = importer.page_count(volume) if volume.stem else None
    if not pages:
        return {"state": "none", "pages": None}
    size = kept_size(volume)
    kept = sum(batch_path(volume, *b).is_file() for b in batches(pages, size))
    state = "done" if result_path(volume).is_file() else "partial" if kept else "none"
    info = {"state": state, "pages": pages, "kept": kept, "batches": len(batches(pages, size)), "rates_from": RATES_FROM,
            "size": size, "size_min": BATCH_MIN, "size_max": BATCH_MAX,
            "modes": [{"key": k, "label": label, "price": price(pages, k), "hint": hint}
                      for k, (label, _, hint) in MODES.items()]}
    try:
        info.update(json.loads((importer.ocr_dir(volume) / "ocr-lauf.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    if state != "partial":
        info["size"] = info.get("size") or BATCH_PAGES
    if state == "partial":
        info["mode"] = kept_mode(volume)
    mode, _, extra = (info.get("mode") or "").partition("+")
    info.update(mode_key=mode or DEFAULT_MODE, no_captions=bool(extra), mode_label=variant_label(info.get("mode")))
    if info.get("cost_cents"):
        info["cost"] = euro(info["cost_cents"] / 100)
    return info


def page_blocks(volume, number):
    """Recognized blocks of one page (type, html, box in percent, pictures with image and description), or None."""
    page = fillDatabase.load_pages(volume.label, volume.stem).get(number)
    return None if page is None else page["blocks"]


# ---------- Datalab ----------

def make_client(key):
    try:
        from datalab_sdk import DatalabClient  # only the text recognition needs it
    except ImportError as error:
        raise ValueError("Der App fehlt noch die Datalab-Bibliothek. Bitte das Image neu bauen: docker compose up --build.") from error
    return DatalabClient(api_key=key)


def find_or_create_pipeline(client, mode=DEFAULT_MODE, captions=True):
    from datalab_sdk import PipelineProcessor
    name = PIPELINE_NAME + ("" if mode == DEFAULT_MODE else f"_{mode}") + ("" if captions else "_nocaptions")
    for p in client.list_pipelines(saved_only=True, include_archived=False).get("pipelines", []):
        if p.name == name:
            return p.pipeline_id
    settings = {**PIPELINE_SETTINGS, "output_mode": mode, "disable_image_captions": not captions}
    draft = client.create_pipeline(steps=[PipelineProcessor(type="convert", settings=settings)])
    return client.save_pipeline(draft.pipeline_id, name=name).pipeline_id


def convert_batch(key, pipeline_id, pdf, phase=None):
    """One batch through the pipeline, with its cost in cents. phase("datalab") is called once the upload is done."""
    client = make_client(key)
    execution = client.run_pipeline(pipeline_id, file_path=str(pdf), output_format="json", max_polls=1)
    if phase:
        phase("datalab")
    if execution.status not in FINISHED:
        execution = client.get_pipeline_execution(execution.execution_id, max_polls=MAX_POLLS, poll_interval=POLL_SECONDS)
    step = execution.steps[-1]
    if execution.status not in ("completed", "completed_with_errors") or step.status == "failed":
        reason = step.error_message or ("keine Antwort nach 30 Minuten" if execution.status != "failed" else "unbekannt")
        raise ValueError(f"Datalab konnte einen Teil des Bandes nicht erkennen: {reason}")
    result = client.get_step_result(execution.execution_id, step.step_index)
    if not result.get("success", True):
        raise ValueError(f"Datalab konnte einen Teil des Bandes nicht erkennen: {result.get('error')}")
    rate = (execution.rate_breakdown or {}).get("total_rate_per_1000_cents")
    result["_cost_cents"] = None if rate is None else rate * (result.get("page_count") or 0) / 1000
    return result


def keep_batch(volume, first, last, key, pipeline_id, scan, part=None):
    """Recognizes the batch unless an earlier run kept it, and writes the result at once. part is the dict the page
    shows for it: its state ("upload", "datalab", "fertig") and since when."""
    path = batch_path(volume, first, last)
    if path.is_file():
        return

    def phase(state):
        if part is not None:
            part.update(state=state, since=time.time())
    phase("upload")
    path.parent.mkdir(parents=True, exist_ok=True)
    piece = pymupdf.open()
    with pymupdf.open(scan) as doc:
        piece.insert_pdf(doc, from_page=first - 1, to_page=last - 1)
    pdf = path.with_suffix(".pdf")
    piece.save(pdf)
    try:
        result = convert_batch(key, pipeline_id, pdf, phase)
    finally:
        pdf.unlink(missing_ok=True)
    path.with_suffix(".part").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    path.with_suffix(".part").replace(path)
    phase("fertig")


def unique_images(result, number):
    """Batches reuse page ids, so picture names repeat across them (see fix_image_collisions.unique_batch_images)."""
    images = result.get("images") or {}
    names = {n: hashlib.md5(f"batch{number}/{n}".encode()).hexdigest() + n[n.find("_"):] for n in images}
    content = json.dumps(result["json"])
    for old, new in names.items():
        content = content.replace(old, new)
    return json.loads(content), {names[n]: b for n, b in images.items()}


def merge(volume, pages, mode, seconds=None, size=BATCH_PAGES):
    """Merges the kept batches into the result and removes them. Pictures go first, so an existing result is complete."""
    out = importer.ocr_dir(volume)
    merged, images, cost = None, {}, 0.0
    for number, (first, last) in enumerate(batches(pages, size)):
        result = json.loads(batch_path(volume, first, last).read_text(encoding="utf-8"))
        document, pictures = unique_images(result, number)
        merged = merged or dict(document)
        if number:
            merged["children"] = merged["children"] + document["children"]
        images.update(pictures)
        cost += result.get("_cost_cents") or 0
    write_result(volume, merged, images, {"cost_cents": cost or None, "source": "Datalab", "mode": mode, "seconds": seconds, "size": size})
    shutil.rmtree(out / ".batches", ignore_errors=True)


def write_result(volume, document, images, run):
    out = importer.ocr_dir(volume)
    out.mkdir(parents=True, exist_ok=True)
    for name, data in images.items():
        if IMAGE_NAME.match(name):
            try:
                (out / name).write_bytes(base64.b64decode(data) if isinstance(data, str) else data)
            except (binascii.Error, ValueError):
                continue
    part = out / f"{volume.stem}.json.part"
    part.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    run = {"at": datetime.now().isoformat(timespec="minutes"), **run}  # a date given by the caller wins, even None
    (out / "ocr-lauf.json").write_text(json.dumps(run), encoding="utf-8")
    part.replace(result_path(volume))


def clear(volume):
    shutil.rmtree(importer.ocr_dir(volume), ignore_errors=True)


def start(volume, mode=DEFAULT_MODE, again=False, captions=True, size=BATCH_PAGES):
    """Recognizes the text in the background (poll importer.JOBS[(vz, "ocr")]). Batches kept from an interrupted run
    are not paid twice, so a continued run needs the same level and size; again=True drops them and any finished result."""
    if mode not in MODES:
        raise ValueError("Diese Qualitätsstufe gibt es nicht.")
    if not BATCH_MIN <= size <= BATCH_MAX:
        raise ValueError(f"Die Teilgröße muss zwischen {BATCH_MIN} und {BATCH_MAX} Seiten liegen.")
    key = api_key()
    if not key:
        raise ValueError("Für die Texterkennung fehlt der Zugang zu Datalab. Bitte unten den API-Key eintragen.")
    scan = importer.scan_path(volume)
    if not scan.is_file():
        raise ValueError("Es sind noch keine Scans hochgeladen.")
    if importer.running(volume, JOB) or importer.running(volume):
        raise ValueError("Für diesen Band läuft schon ein Upload oder die Texterkennung. Bitte warten.")
    if again:
        clear(volume)
    elif kept_mode(volume) not in (None, variant(mode, captions)) or (kept_mode(volume) and kept_size(volume) != size):
        raise ValueError(f"Die schon erkannten Teile haben die Qualität „{variant_label(kept_mode(volume))}“ und je "
                         f"{kept_size(volume)} Seiten. Entweder damit fortsetzen oder von vorn beginnen.")
    pages = importer.page_count(volume)
    if result_path(volume).is_file():
        raise ValueError("Der Text ist schon erkannt.")
    started = time.time()
    job = importer.JOBS[(volume.vz, JOB)] = {"state": "running", "done": 0, "total": pages, "error": "",
                                             "started": started, "parts": []}
    (importer.ocr_dir(volume) / ".batches").mkdir(parents=True, exist_ok=True)
    (importer.ocr_dir(volume) / ".batches" / "modus.txt").write_text(variant(mode, captions), encoding="utf-8")
    (importer.ocr_dir(volume) / ".batches" / "groesse.txt").write_text(str(size), encoding="utf-8")

    def run():
        try:
            client = make_client(key)
            pipeline_id = find_or_create_pipeline(client, mode, captions)
            parts = [{"first": first, "last": last, "kept": batch_path(volume, first, last).is_file(), "since": started}
                     for first, last in batches(pages, size)]
            for part in parts:
                part["state"] = "fertig" if part["kept"] else "wartet"
            job["done"] = sum(p["last"] - p["first"] + 1 for p in parts if p["kept"])
            job["parts"] = parts

            def one(part):
                if part["kept"] or job.get("cancel"):
                    return
                try:
                    keep_batch(volume, part["first"], part["last"], key, pipeline_id, scan, part)
                except Exception:
                    part["state"] = "fehler"
                    raise
                job["done"] += part["last"] - part["first"] + 1

            with ThreadPoolExecutor(CONCURRENCY) as pool:
                list(pool.map(one, parts))  # the first failure ends the run; running batches finish and are kept
            if all(p["state"] == "fertig" for p in parts):
                merge(volume, pages, variant(mode, captions), round(time.time() - started), size)
                job["state"] = "done"
            else:
                job["state"] = "cancelled"  # unsent batches were skipped, finished ones are kept
        except Exception as error:  # report from the thread
            job.update(state="error", error=explain(error))

    threading.Thread(target=run, daemon=True).start()


def cancel(volume):
    """Stops sending batches. Batches Datalab already has finish and are paid for (ponytail: no way to recall one)."""
    job = importer.JOBS.get((volume.vz, JOB))
    if not job or job["state"] != "running":
        raise ValueError("Es läuft gerade keine Texterkennung.")
    job["cancel"] = True


def explain(error):
    if getattr(error, "status_code", None) in NO_CREDIT:
        return ("Datalab hat den API-Key abgelehnt oder das Guthaben ist aufgebraucht. Bereits erkannte Teile bleiben "
                "erhalten: unten einen anderen API-Key eintragen und die Texterkennung fortsetzen.")
    if isinstance(error, ValueError):
        return str(error)
    logger.exception("text recognition failed")
    return f"Die Texterkennung wurde unterbrochen ({error}). Bereits erkannte Teile bleiben erhalten, sie lässt sich fortsetzen."


# ---------- download and upload ----------

def zip_result(volume):
    """The result as ZIP: the JSON and its pictures, in a folder named like the scan."""
    out, stem = importer.ocr_dir(volume), volume.stem
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(out.iterdir()):
            if path.is_file() and (path.name in (f"{stem}.json", "ocr-lauf.json") or IMAGE_NAME.match(path.name)):
                z.write(path, f"{stem}/{path.name}")
    return buffer.getvalue()


def import_zip(volume, source):
    """Takes a result made elsewhere (a ZIP of the pipeline's folder, or of the download) if it fits the scan."""
    pages = importer.page_count(volume) if volume.stem else None
    if not pages:
        raise ValueError("Es sind noch keine Scans hochgeladen.")
    if importer.running(volume, JOB) or importer.running(volume):
        raise ValueError("Für diesen Band läuft schon ein Upload oder die Texterkennung. Bitte warten.")
    try:
        with zipfile.ZipFile(source) as z:
            members = {Path(i.filename).name: i for i in z.infolist() if not i.is_dir()}
            if sum(i.file_size for i in members.values()) > MAX_UNPACKED:
                raise ValueError("Die ZIP-Datei ist zu groß.")
            documents = []
            for name, info in members.items():
                if name.lower().endswith(".json") and not name.startswith("."):
                    try:
                        document = json.loads(z.read(info).decode("utf-8-sig"))
                    except ValueError:
                        continue
                    if isinstance(document, dict) and isinstance(document.get("children"), list):
                        documents.append(document)
            if len(documents) != 1:
                raise ValueError("In der ZIP-Datei muss genau eine JSON-Datei von Datalab liegen.")
            document = documents[0]
            if len(document["children"]) != pages:
                raise ValueError(f"Das Ergebnis hat {len(document['children'])} Seiten, der Scan {pages}. "
                                 "Es gehört vermutlich zu einem anderen Scan.")
            images = {n: z.read(i) for n, i in members.items() if IMAGE_NAME.match(n)}
            try:  # this app's download carries the run's data
                made = json.loads(z.read(members["ocr-lauf.json"]).decode("utf-8-sig")) if "ocr-lauf.json" in members else {}
            except ValueError:
                made = {}
    except zipfile.BadZipFile as error:
        raise ValueError("Das ist keine ZIP-Datei.") from error
    clear(volume)
    # ponytail: without that file a result counts as accurate, like all made by the pipeline so far
    write_result(volume, document, images, {"cost_cents": made.get("cost_cents"), "source": "hochgeladen",
                                            "mode": made.get("mode") or DEFAULT_MODE, "at": made.get("at"),
                                            "size": made.get("size")})
