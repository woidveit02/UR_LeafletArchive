"""Scan figures for the report: OCR blocks and metadata evidence drawn onto pages of the running app.

    python scripts/scan_figures.py [flugblatt-id] [seite]   (app on http://localhost:8000)

Writes ocr_bloecke.png, metadaten_belege.png and ocr_schwierigkeiten.png to docs/abbildungen/.
"""
import html
import io
import json
import sqlite3
import re
import sys
import textwrap
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'src/backend/leaflet_database.db'
OUT = ROOT / 'docs/abbildungen'
APP = 'http://localhost:8000'
# colors from src/frontend/static/styles.css
BLUE, GREEN, ORANGE, RED, GREY, INK = '#1e5aa8', '#237a50', '#c2410c', '#a83535', '#68707c', '#20242b'
TYPES = {'PageHeader': ('Kopf- oder Fußzeile', ORANGE), 'PageFooter': ('Kopf- oder Fußzeile', ORANGE),
         'SectionHeader': ('Überschrift', BLUE), 'Text': ('Text', GREY), 'ListGroup': ('Liste', GREEN),
         'Table': ('Tabelle', GREEN), 'Picture': ('Abbildung', RED), 'Figure': ('Abbildung', RED)}
FONT = ImageFont.truetype('segoeui.ttf', 26)
BOLD = ImageFont.truetype('segoeuib.ttf', 26)


def page_image(leaflet, page):
    with urllib.request.urlopen(f'{APP}/leaflets/{leaflet}/pages/{page}.png?dpi=150') as r:
        return Image.open(io.BytesIO(r.read())).convert('RGB')


def rgba(color, alpha):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) + (alpha,)


def rect(img, box, pad=0):
    x, y, w, h = box
    return [x * img.width / 100 - pad, y * img.height / 100 - pad,
            (x + w) * img.width / 100 + pad, (y + h) * img.height / 100 + pad]


def highlight(img, boxes):
    """boxes: [(rect, color)] as translucent marker with a thin outline."""
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for r, color in boxes:
        draw.rounded_rectangle(r, radius=6, fill=rgba(color, 45), outline=rgba(color, 230), width=3)
    return Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')


def framed(img, legend_rows):
    """Page with the legend below it."""
    row = 44
    out = Image.new('RGB', (img.width, img.height + 30 + row * len(legend_rows)), 'white')
    out.paste(img)
    return out, img.height + 22, row


def mark(draw, x, y, n, color):
    draw.ellipse([x - 17, y - 17, x + 17, y + 17], fill=color)
    draw.text((x, y), str(n), fill='white', font=BOLD, anchor='mm')


def ocr_blocks(img, blocks):
    img = highlight(img, [(rect(img, b['box'], 4), TYPES.get(b['type'], ('', INK))[1]) for b in blocks])
    kinds = list(dict.fromkeys(TYPES.get(b['type'], (b['type'], INK)) for b in blocks))
    out, y, row = framed(img, [kinds])
    draw, x = ImageDraw.Draw(out), 24
    for name, color in kinds:
        draw.rounded_rectangle([x, y + 4, x + 30, y + 30], radius=4, fill=rgba(color, 255)[:3])
        draw.text((x + 40, y), name, fill=INK, font=FONT)
        x = draw.textbbox((x + 40, y), name, font=FONT)[2] + 40
    return out


def evidence(img, blocks, fields, page):
    """fields: [(name, value, color, block ids)]."""
    shown = [(name, value, color, [blocks[int(b.split('-')[1]) - 1] for b in ids if int(b.split('-')[0]) == page])
             for name, value, color, ids in fields]
    shown = [f for f in shown if f[3]]
    img = highlight(img, [(rect(img, b['box'], 6), color) for _, _, color, bs in shown for b in bs])
    out, y, row = framed(img, shown)
    draw = ImageDraw.Draw(out)
    for n, (name, value, color, bs) in enumerate(shown, 1):
        top = rect(img, bs[0]['box'])
        mark(draw, top[0] - 30, (top[1] + top[3]) / 2, n, color)
        mark(draw, 44, y + row * (n - 1) + 17, n, color)
        draw.text((74, y + row * (n - 1)), f'{name}:', fill=INK, font=BOLD)
        draw.text((74 + draw.textlength(f'{name}: ', font=BOLD), y + row * (n - 1)), value, fill=INK, font=FONT)
    return out


# (heading, band, page, crop in % of the page: x, y, w, h, OCR text to show around this word)
DIFFICULTIES = [('Handschrift', 3, 164, (0, 12, 100, 14), 'HEUTE'),
                ('Gesperrte Schrift', 3, 51, (14, 38.6, 76, 3), 'T E N D'),
                ('Verblichener Text', 4, 292, (14, 20, 60, 12), None),
                ('Stempel und Ablagenummer', 4, 292, (66, 3, 26, 11), None)]


def difficulties(con):
    """Grid of scan details, each with the text the OCR read there."""
    tiles = []
    for heading, vz, page, (x, y, w, h), focus in DIFFICULTIES:
        leaflet, raw = con.execute('SELECT p.leaflet_id, p.blocks FROM pages p JOIN volumes v ON v.id = p.volume_id '
                                   'WHERE v.vz = ? AND p.page_no = ?', (vz, page)).fetchone()
        img = page_image(leaflet, page)
        crop = img.crop(rect(img, (x, y, w, h)))
        inside = [b for b in json.loads(raw) if b['box'][1] < y + h and b['box'][1] + b['box'][3] > y
                  and b['box'][0] < x + w and b['box'][0] + b['box'][2] > x]
        text = ' '.join(re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', b['html']))).strip() for b in inside)
        if focus and focus in text:
            at = text.index(focus)
            text = ('… ' if at > 40 else '') + text[max(0, at - 40):at + 80] + ' …'
        tiles.append((heading, f'Band {vz:03d}, S. {page}', crop, text))
    width = 1400
    rows = []
    for heading, source, crop, text in tiles:
        scale = min((width - 40) / crop.width, 1.3)  # small crops are not blown up
        crop = crop.resize((round(crop.width * scale), round(crop.height * scale)))
        lines = textwrap.wrap(f'OCR: {text}', 95)[:4]
        tile = Image.new('RGB', (width, crop.height + 70 + 36 * len(lines)), 'white')
        draw = ImageDraw.Draw(tile)
        draw.text((20, 10), heading, fill=INK, font=BOLD)
        draw.text((30 + draw.textlength(heading, font=BOLD), 10), f'({source})', fill=GREY, font=FONT)
        tile.paste(crop, (20, 52))
        draw.rectangle([20, 52, 20 + crop.width, 52 + crop.height], outline='#c9c4ba', width=2)
        for n, line in enumerate(lines):
            draw.text((20, crop.height + 60 + 36 * n), line, fill=GREY, font=FONT)
        rows.append(tile)
    out = Image.new('RGB', (width, sum(r.height + 20 for r in rows)), 'white')
    top = 0
    for r in rows:
        out.paste(r, (0, top))
        top += r.height + 20
    return out


if __name__ == '__main__':
    leaflet = int(sys.argv[1]) if len(sys.argv) > 1 else 850
    con = sqlite3.connect(f'file:{DB.as_posix()}?mode=ro', uri=True)
    l = con.execute('SELECT start_page, title, title_blocks, date_text, date_iso, date_blocks, received_date, '
                    'received_blocks, doc_type FROM leaflets WHERE id = ?', (leaflet,)).fetchone()
    page = int(sys.argv[2]) if len(sys.argv) > 2 else l[0]
    blocks = json.loads(con.execute('SELECT p.blocks FROM pages p JOIN leaflets l ON l.volume_id = p.volume_id '
                                    'WHERE l.id = ? AND p.page_no = ?', (leaflet, page)).fetchone()[0])
    ids = lambda raw: json.loads(raw or '[]')
    fields = [('Titel', l[1], BLUE, ids(l[2])),
              ('Datum', f'„{l[3]}“ → {l[4]}', GREEN, ids(l[5])),
              ('Eingangsstempel', l[6] or '', ORANGE, ids(l[7]))]
    for role, surface, function, raw in con.execute('SELECT role, surface, function, blocks FROM leaflet_issuers '
                                                    'WHERE leaflet_id = ? ORDER BY id', (leaflet,)):
        fields.append(('Herausgeber' if role == 'issuer' else 'Unterzeichnend',
                       surface + (f' ({function})' if function else ''), RED if role == 'issuer' else GREY, ids(raw)))
    ocr_blocks(page_image(leaflet, page), blocks).save(OUT / 'ocr_bloecke.png', optimize=True)
    evidence(page_image(leaflet, page), blocks, fields, page).save(OUT / 'metadaten_belege.png', optimize=True)
    difficulties(con).save(OUT / 'ocr_schwierigkeiten.png', optimize=True)
    print(f'Flugblatt {leaflet}, Seite {page}: {len(blocks)} Blöcke -> {OUT}')
