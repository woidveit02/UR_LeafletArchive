import os
import threading
from pathlib import Path

import pymupdf

PDF_DIR = Path(os.environ.get("LEAFLET_PDF_DIR", "/data/pdfs"))
# next to the scans, so it survives rebuilding the container
THUMB_DIR = PDF_DIR / ".thumbs"

_doc_cache = {}
# PyMuPDF is not thread-safe; every call into it goes through this lock
_lock = threading.Lock()


def get_document(pdf_path):
    key = str(pdf_path)
    if key not in _doc_cache:
        _doc_cache[key] = pymupdf.open(pdf_path)
    return _doc_cache[key]


def page_size(pdf_path, page_no):
    with _lock:
        rect = get_document(pdf_path)[page_no - 1].rect
    return round(rect.width), round(rect.height)


def render_page(pdf_path, page_no, dpi=110):
    with _lock:
        page = get_document(pdf_path)[page_no - 1]
        return page.get_pixmap(dpi=dpi).tobytes("png")


def thumb_path(pdf_path, page_no, height):
    # the scan's modification time in the name: a replaced scan gets new thumbnails
    stamp = int(Path(pdf_path).stat().st_mtime)
    return THUMB_DIR / f"{Path(pdf_path).stem}-{stamp}" / f"{page_no}-{height}.jpg"


def render_thumb(pdf_path, page_no, height=300):
    """JPEG of the page, `height` pixels high, cached on disk because decoding
    the full-resolution scan takes about half a second."""
    cached = thumb_path(pdf_path, page_no, height)
    if cached.is_file():
        return cached.read_bytes()
    with _lock:
        page = get_document(pdf_path)[page_no - 1]
        dpi = round(height * 72 / page.rect.height)
        jpg = page.get_pixmap(dpi=dpi).tobytes("jpeg", jpg_quality=75)
    cached.parent.mkdir(parents=True, exist_ok=True)
    # write under a temporary name, so a half-written file is never served
    tmp = cached.with_name(f"{cached.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_bytes(jpg)
    os.replace(tmp, cached)
    return jpg


def render_clip(pdf_path, page_no, box, dpi=200):
    """box: [left, top, width, height] in percent of the page."""
    with _lock:
        page = get_document(pdf_path)[page_no - 1]
        w, h = page.rect.width, page.rect.height
        left, top, width, height = box
        clip = pymupdf.Rect(left / 100 * w, top / 100 * h,
                            (left + width) / 100 * w, (top + height) / 100 * h)
        return page.get_pixmap(dpi=dpi, clip=clip & page.rect).tobytes("png")
