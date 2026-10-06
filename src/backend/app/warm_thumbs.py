"""Renders the missing thumbnails (every page of every scanned volume: the
cards and the band view) once after the import. Runs as its own process
next to the server, so visible thumbnails the server renders on demand never wait behind this job.

    python -m app.warm_thumbs
"""
import logging

from . import pdf_service
from .app import THUMB_HEIGHT, volume_pdf
from .database.models import Volume
from .database.session import session

logger = logging.getLogger(__name__)


def main():
    done = failed = 0
    for volume in session.query(Volume).order_by(Volume.id):
        pdf = volume_pdf(volume)
        if not pdf.is_file():
            continue
        for page_no in range(1, (volume.n_pages or 0) + 1):
            try:
                pdf_service.render_thumb(pdf, page_no, height=2 * THUMB_HEIGHT)
                done += 1
            except Exception:
                # one broken page must not stop the rest
                logger.exception("Thumbnail failed: %s, page %s", pdf.name, page_no)
                failed += 1
    logger.info("Thumbnails ready: %s, failed: %s", done, failed)


if __name__ == "__main__":
    main()
