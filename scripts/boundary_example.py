"""Figure for chapter 4: two real page transitions with the reasons and weights the app shows for them.

    python scripts/boundary_example.py [--ordner SCANS]

Measures the pages with the app's looks.py, reads the recognized text from the database and writes
docs/abbildungen/trennbeispiel.png: two close calls in Band 006, S. 441 → 442 (a new leaflet on the same paper) and
S. 454 → 455 (a back page after an imprint).
"""
import argparse
import html
import importlib.util
import json
import re
import sqlite3
import sys
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from boundary_figure import de, spelled
from scan_folder import ROOT, scan_dir

APP = ROOT / 'src/backend/app'
sys.path.insert(0, str(APP.parent))  # looks.py is imported as app.looks
DB = ROOT / 'src/backend/leaflet_database.db'
OUT = ROOT / 'docs/abbildungen/trennbeispiel.png'
# colors and fonts as in scan_figures.py
# green for a new leaflet, red against it, as the reasons in the splitter
PRO, CON, INK, LINE, MUTED = '#237a50', '#a83535', '#20242b', '#c9c4ba', '#68707c'
FONT = ImageFont.truetype('segoeui.ttf', 26)
SMALL = ImageFont.truetype('segoeui.ttf', 22)
BOLD = ImageFont.truetype('segoeuib.ttf', 26)
VZ, EXAMPLES = 6, [(441, 'Neues Flugblatt'), (454, 'Rückseite')]
PAGE_H, GAP = 620, 18


def module(name):
    spec = importlib.util.spec_from_file_location(f'app.{name}', APP / f'{name}.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


boundaries, looks = module('boundaries'), module('looks')


def blocks_of(con, page):
    """[(type, text, box in %)] as boundaries.page_blocks reads them, with the box from the database."""
    raw = con.execute('SELECT p.blocks FROM pages p JOIN volumes v ON v.id = p.volume_id WHERE v.vz = ? AND p.page_no = ?',
                      (VZ, page)).fetchone()[0]
    out = []
    for b in json.loads(raw):
        text = html.unescape(re.sub(r'<[^>]+>', '\n', b.get('html', '')))
        out.append((b['type'], '\n'.join(l.strip() for l in text.splitlines() if l.strip()), b['box']))
    return out


def where(label, before, after, look):
    """(0 for the page before or 1, box as fractions) of a reason, or None if it concerns the whole page."""
    def block(blocks, test):
        hit = next((box for t, x, box in blocks if test(t, x)), None)
        return [v / 100 for v in hit] if hit else None
    word = re.match(r'„(.+)“ am (Seitenanfang|Ende der Seite davor)', label)
    if word:
        side = 1 if word[2] == 'Seitenanfang' else 0
        found = block(after if side else before, lambda t, x: word[1] in x.lower())
        return (side, found) if found else None
    if label == 'Impressum auf der Seite davor':
        found = [box for t, x, box in before if boundaries.IMPRINT.search(x) or boundaries.RESPONSIBLE_LINE.search(x)]
        return (0, [v / 100 for v in found[-1]]) if found else None
    if label == 'Eingangsstempel':
        return 1, block(after, boundaries.is_stamp_block)
    if label == 'Überschrift am Anfang':
        return 1, block(after, lambda t, x: t == 'SectionHeader')
    if label == 'Löcher rechts: Rückseite':
        x, y, w, h = look['spots']['holes'][0]
        x2, y2, w2, h2 = look['spots']['holes'][-1]
        return 1, [x, y, max(w, w2), y2 + h2 - y]
    return None


def page_image(doc, page):
    pix = doc[page - 1].get_pixmap(dpi=100)
    img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    return img.resize((round(img.width * PAGE_H / img.height), PAGE_H))


def dot(img, cx, cy, r, color):
    """A filled circle with smooth edges: drawn four times larger, then scaled down."""
    big = Image.new('L', (8 * r, 8 * r), 0)
    ImageDraw.Draw(big).ellipse([0, 0, 8 * r - 1, 8 * r - 1], fill=255)
    mask = big.resize((2 * r, 2 * r), Image.LANCZOS)
    img.paste(Image.new('RGB', mask.size, color), (round(cx - r), round(cy - r)), mask)


def marker(img, draw, box, n, color, left_limit, placed):
    """A rounded frame around box with its number in a circle beside it, left unless there is no room."""
    draw.rounded_rectangle(box, radius=5, outline=color, width=3)
    cy = (box[1] + box[3]) / 2
    cx = box[0] - 22
    if cx < left_limit + 16 or any(abs(cx - x) < 36 and abs(cy - y) < 36 for x, y in placed):
        cx = box[2] + 22
    placed.append((cx, cy))
    dot(img, cx, cy, 16, color)
    draw.text((cx, cy), str(n), fill='white', font=SMALL, anchor='mm')


def panel(doc, con, first, title):
    before, after = blocks_of(con, first), blocks_of(con, first + 1)
    seen = [looks.measure(doc[p - 1]) for p in (first, first + 1)]
    strip = lambda bl: [(t, x) for t, x, _ in bl]
    _, reasons = boundaries.explain(strip(after), strip(before), seen[1], seen[0])
    reasons = [(label, round(w, 1)) for label, w in reasons]
    total = round(boundaries.PRIOR, 1) + sum(w for _, w in reasons)

    pages = [page_image(doc, p) for p in (first, first + 1)]
    pw = pages[0].width
    rows = len(reasons) + 3
    width = 2 * pw + GAP + 60 + 900
    out = Image.new('RGB', (width, max(PAGE_H + 120, 46 * rows + 120)), 'white')
    draw = ImageDraw.Draw(out)
    draw.text((0, 0), title, fill=INK, font=BOLD)
    draw.text((draw.textlength(title, font=BOLD) + 14, 0), f'Band {VZ:03d}, S. {first} → {first + 1}', fill=MUTED, font=FONT)
    top = 56
    for i, img in enumerate(pages):
        x = i * (pw + GAP)
        out.paste(img, (x, top))
        draw.rectangle([x, top, x + pw - 1, top + PAGE_H - 1], outline=LINE, width=2)
        draw.text((x + pw / 2, top + PAGE_H + 8), f'S. {first + i}', fill=MUTED, font=SMALL, anchor='ma')
    cut = total > 0
    mid = pw + GAP / 2
    if cut:  # dashed like a suggested cut in the app
        for y in range(top, top + PAGE_H, 22):
            draw.line([mid, y, mid, y + 12], fill=PRO, width=4)

    tx, ty = 2 * pw + GAP + 60, top
    placed = []
    for n, (label, w) in enumerate(reasons, 1):
        color = PRO if w > 0 else CON
        place = where(label, before, after, seen[1])
        if place and place[1]:
            side, (bx, by, bw, bh) = place
            x0, y0 = side * (pw + GAP) + bx * pw, top + by * PAGE_H
            marker(out, draw, [x0 - 4, y0 - 4, x0 + bw * pw + 4, y0 + bh * PAGE_H + 4], n, color, side * (pw + GAP), placed)
        dot(out, tx + 15, ty + 21, 15, color)
        draw.text((tx + 15, ty + 21), str(n), fill='white', font=SMALL, anchor='mm')
        draw.text((tx + 44, ty + 2), spelled(label), fill=INK, font=FONT)
        draw.text((width - 10, ty + 2), de(w), fill=color, font=BOLD, anchor='ra')
        ty += 46
    draw.text((tx + 44, ty + 2), 'Grundwert', fill=MUTED, font=FONT)
    draw.text((width - 10, ty + 2), de(boundaries.PRIOR), fill=MUTED, font=FONT, anchor='ra')
    ty += 50
    draw.line([tx, ty, width - 10, ty], fill=LINE, width=2)
    verdict = 'Trennung vorgeschlagen' if cut else 'keine Trennung vorgeschlagen'
    draw.text((tx + 44, ty + 10), f'Summe: {verdict}', fill=INK, font=BOLD)
    draw.text((width - 10, ty + 10), de(total), fill=PRO if cut else CON, font=BOLD, anchor='ra')
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ordner', help='Scan-Ordner, sonst LEAFLET_PDF_HOST_DIR aus .env')
    args = parser.parse_args()
    volume = next(v for v in json.loads((ROOT / 'data/volumes.json').read_text(encoding='utf-8')) if v['vz'] == VZ)
    con = sqlite3.connect(f'file:{DB.as_posix()}?mode=ro', uri=True)
    with pymupdf.open(scan_dir(args.ordner) / volume['label'] / f"{volume['stem']}.pdf") as doc:
        panels = [panel(doc, con, *example) for example in EXAMPLES]
    width = max(p.width for p in panels)
    out = Image.new('RGB', (width + 60, sum(p.height for p in panels) + 60 * len(panels) + 20), 'white')
    y = 30
    for p in panels:
        out.paste(p, (30, y))
        y += p.height + 60
    out.save(OUT, optimize=True)
    print(OUT)
