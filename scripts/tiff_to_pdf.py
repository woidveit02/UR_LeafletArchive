"""Fügt einen Ordner mit TIFF-Scans zu einem PDF zusammen, mit denselben Einstellungen wie Schritt 2 des Imports.

    python scripts/tiff_to_pdf.py ORDNER [-o ausgabe.pdf]

Eine Seite je Bild in der Reihenfolge der Dateinamen, als JPEG (Qualität 75) bei 400 dpi.
Ohne -o entsteht ORDNER.pdf neben dem Ordner. Braucht PyMuPDF (pip install pymupdf).
"""
import argparse
import sys
from pathlib import Path

import pymupdf

JPEG_QUALITY, DPI = 75, 400  # as importer.tiffs_to_pdf of the app
TIFF_SUFFIXES = {".tif", ".tiff"}


def tiffs_to_pdf(paths, out):
    doc = pymupdf.open()
    for n, path in enumerate(paths, 1):
        pix = pymupdf.Pixmap(str(path))
        if pix.colorspace.n != 3 or pix.alpha:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        if pix.alpha:
            pix = pymupdf.Pixmap(pix, 0)
        page = doc.new_page(width=pix.width * 72 / DPI, height=pix.height * 72 / DPI)
        page.insert_image(page.rect, stream=pix.tobytes("jpg", jpg_quality=JPEG_QUALITY))
        if n % 50 == 0 or n == len(paths):
            print(f"{n}/{len(paths)} Seiten", flush=True)
    doc.save(out, garbage=3, deflate=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ordner", type=Path, help="Ordner mit den .tif- oder .tiff-Dateien")
    ap.add_argument("-o", "--ausgabe", type=Path, help="Name des PDFs (Standard: ORDNER.pdf neben dem Ordner)")
    args = ap.parse_args(argv)
    tiffs = sorted(p for p in args.ordner.iterdir() if p.suffix.lower() in TIFF_SUFFIXES) if args.ordner.is_dir() else []
    if not tiffs:
        sys.exit(f"In {args.ordner} liegen keine TIFF-Dateien.")
    out = args.ausgabe or args.ordner.parent / f"{args.ordner.name}.pdf"
    if out.exists():
        sys.exit(f"{out} gibt es schon. Bitte löschen oder mit -o einen anderen Namen angeben.")
    tiffs_to_pdf(tiffs, out)
    print(f"Fertig: {out}")


if __name__ == "__main__":
    main()
