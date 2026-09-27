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
