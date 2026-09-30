import os
from pathlib import Path

import pymupdf

PDF_DIR = Path(os.environ.get("LEAFLET_PDF_DIR", "/data/pdfs"))

_doc_cache = {}


def get_document(pdf_path):
    key = str(pdf_path)
    if key not in _doc_cache:
        _doc_cache[key] = pymupdf.open(pdf_path)
    return _doc_cache[key]


def page_size(pdf_path, page_no):
    rect = get_document(pdf_path)[page_no - 1].rect
    return round(rect.width), round(rect.height)


def render_page(pdf_path, page_no, dpi=110):
    doc = get_document(pdf_path)
    page = doc[page_no - 1]
    return page.get_pixmap(dpi=dpi).tobytes("png")


def render_clip(pdf_path, page_no, box, dpi=200):
    """box: [left, top, width, height] in percent of the page."""
    page = get_document(pdf_path)[page_no - 1]
    w, h = page.rect.width, page.rect.height
    left, top, width, height = box
    clip = pymupdf.Rect(left / 100 * w, top / 100 * h,
                        (left + width) / 100 * w, (top + height) / 100 * h)
    return page.get_pixmap(dpi=dpi, clip=clip & page.rect).tobytes("png")
