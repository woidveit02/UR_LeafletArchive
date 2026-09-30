"""Renders the missing card thumbnails (first page of each leaflet) once
after the import. Runs as its own process next to the server, so visible
thumbnails the server renders on demand never wait behind this job.

    python -m app.warm_thumbs
"""
import logging

from . import pdf_service
from .app import THUMB_HEIGHT, volume_pdf
from .database.models import Leaflet, Volume
from .database.session import session

logger = logging.getLogger(__name__)


def main():
    pdfs = {v.id: volume_pdf(v) for v in session.query(Volume)}
    done = failed = 0
    for lf in session.query(Leaflet).order_by(Leaflet.volume_id, Leaflet.start_page):
        pdf = pdfs[lf.volume_id]
        if not pdf.is_file():
            continue
        try:
            pdf_service.render_thumb(pdf, lf.start_page, height=2 * THUMB_HEIGHT)
            done += 1
        except Exception:
            # one broken scan must not stop the rest
            logger.exception("Thumbnail failed: %s, page %s", pdf.name, lf.start_page)
            failed += 1
    logger.info("Thumbnails ready: %s, failed: %s", done, failed)


if __name__ == "__main__":
    main()
