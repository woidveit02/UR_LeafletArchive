"""Overview for chapter 1.5: one leaflet (850) through all steps, as a strip of real details.

    python scripts/workflow_figure.py   (after app_screenshots.py and import_screenshots.py)

Writes docs/abbildungen/ablauf.png.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

FIGS = Path(__file__).resolve().parents[1] / 'docs/abbildungen'
INK, MUTED, LINE = '#20242b', '#68707c', '#c9c4ba'
FONT = ImageFont.truetype('segoeui.ttf', 28)
SMALL = ImageFont.truetype('segoeui.ttf', 23)
PANEL, PAD = (560, 360), 30


def fig(name, box=None):
    img = Image.open(FIGS / name).convert('RGB')
    return img.crop(box) if box else img


# (step, chapter, how, image); how: 'auto', 'check' (proposal, checked by hand) or 'hand'
STEPS = [('Text erkennen', 'Kap. 2 und 3', 'auto', lambda: fig('ocr_bloecke.png')),
         ('Flugblätter trennen', 'Kap. 4', 'check', lambda: fig('import_trennen.png')),
         ('Metadaten erzeugen', 'Kap. 5', 'auto', lambda: fig('metadaten_belege.png')),
         ('Mehrfachexemplare zusammenführen', 'Kap. 6', 'check', lambda: fig('nutzen_exemplare.png', (0, 100, 2100, 885))),
         ('Herausgeber zuordnen', 'Kap. 5 und 9', 'hand', lambda: fig('import_herausgeber.png')),
         ('Themen zuordnen', 'Kap. 7', 'auto', lambda: fig('app_themen.png', (30, 315, 2065, 1260))),
         ('Metadaten korrigieren', 'Kap. 9', 'hand', lambda: fig('nutzen_korrigieren.png')),
         ('Recherchieren', 'Kap. 9', 'auto', lambda: fig('nutzen_suche.png'))]
NOTE = {'auto': 'automatisch', 'check': 'Vorschlag, von Hand geprüft', 'hand': 'von Hand'}

cols, rows = 4, 2
cell_w, cell_h = PANEL[0] + PAD, PANEL[1] + 110
out = Image.new('RGB', (cols * cell_w + PAD, rows * cell_h + PAD), 'white')
draw = ImageDraw.Draw(out)
for n, (step, chapter, how, image) in enumerate(STEPS):
    x, y = PAD + (n % cols) * cell_w, PAD + (n // cols) * cell_h
    out.paste((ImageOps.fit(image(), PANEL, centering=(0.5, 0)) if n in (0, 2) else ImageOps.pad(image(), PANEL, color='white', centering=(0.5, 0))), (x, y))
    draw.rectangle([x, y, x + PANEL[0] - 1, y + PANEL[1] - 1], outline=LINE, width=2)
    draw.text((x, y + PANEL[1] + 12), f'{n + 1}  {step}', fill=INK, font=FONT)
    note = NOTE[how]
    draw.text((x, y + PANEL[1] + 52), f'{chapter} · {note}', fill=MUTED, font=SMALL)
out.save(FIGS / 'ablauf.png', optimize=True)
print(FIGS / 'ablauf.png')
