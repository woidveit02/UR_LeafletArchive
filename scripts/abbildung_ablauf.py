"""Overview for chapter 1.5: one leaflet (850) through all steps, as a strip of real details.

    python scripts/abbildung_ablauf.py   (after abbildungen_scans.py and abbildungen_app.py; app on localhost:8000)

Writes docs/abbildungen/ablauf.png.
"""
import io
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

FIGS = Path(__file__).resolve().parents[1] / 'docs/abbildungen'
INK, MUTED, LINE = '#20242b', '#68707c', '#c9c4ba'
FONT = ImageFont.truetype('segoeui.ttf', 26)
SMALL = ImageFont.truetype('segoeui.ttf', 22)
PANEL, PAD = (520, 340), 30


def scan():
    with urllib.request.urlopen('http://localhost:8000/leaflets/850/pages/394.png?dpi=100') as r:
        return Image.open(io.BytesIO(r.read())).convert('RGB')


def fig(name, box=None):
    img = Image.open(FIGS / name).convert('RGB')
    return img.crop(box) if box else img


# (step, chapter, checked by hand, image)
STEPS = [('Scan', 'Kap. 2', False, lambda: scan()),
         ('Text erkennen', 'Kap. 3', False, lambda: fig('ocr_bloecke.png')),
         ('Flugblätter trennen', 'Kap. 4', True, lambda: fig('app_band.png', (215, 0, 815, 487))),
         ('Metadaten erzeugen', 'Kap. 5', False, lambda: fig('metadaten_belege.png')),
         ('Mehrfachexemplare', 'Kap. 6', True, lambda: fig('app_band.png', (825, 170, 1223, 470))),
         ('Themen', 'Kap. 7', False, lambda: fig('app_themen.png', (40, 380, 1300, 1260))),
         ('Anwendung', 'Kap. 9', False, lambda: fig('app_leseansicht.png', (0, 0, 1500, 980)))]

cols, rows = 4, 2
cell_w, cell_h = PANEL[0] + PAD, PANEL[1] + 110
out = Image.new('RGB', (cols * cell_w + PAD, rows * cell_h + PAD), 'white')
draw = ImageDraw.Draw(out)
for n, (step, chapter, checked, image) in enumerate(STEPS):
    x, y = PAD + (n % cols) * cell_w, PAD + (n // cols) * cell_h
    out.paste(ImageOps.fit(image(), PANEL, centering=(0.5, 0)), (x, y))
    draw.rectangle([x, y, x + PANEL[0] - 1, y + PANEL[1] - 1], outline=LINE, width=2)
    draw.text((x, y + PANEL[1] + 12), f'{n + 1}  {step}', fill=INK, font=FONT)
    note = 'Vorschlag, von Hand geprüft' if checked else 'automatisch'
    draw.text((x, y + PANEL[1] + 50), f'{chapter} · {note}', fill=MUTED, font=SMALL)
out.save(FIGS / 'ablauf.png', optimize=True)
print(FIGS / 'ablauf.png')
