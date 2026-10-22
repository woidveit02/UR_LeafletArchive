"""Screenshots of the running app for the report and docs/handbuch/recherchieren-und-pflegen.md
(needs playwright: pip install playwright; playwright install chromium).

    python scripts/app_screenshots.py                     (app on http://localhost:8000)
    python scripts/app_screenshots.py nutzen_trends.png   (only these)

Only read-only pages of released volumes; never the import of drafts.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / 'docs/abbildungen'
APP = 'http://localhost:8000'
# (file, address, clip in CSS pixels: x, y, width, height)
SHOTS = [('app_leseansicht.png', '/leaflets/850', (0, 90, 1400, 810)),
         ('app_band.png', '/volumes/6#page-394', (155, 60, 815, 325)),
         ('app_themen.png', '/themen', (0, 60, 1400, 840)),
         ('nutzen_suche.png', '/leaflets?q=berufsverbot', (0, 60, 1400, 840)),
         ('nutzen_korrigieren.png', '/leaflets/850?bearbeiten', (0, 60, 1400, 790)),
         ('nutzen_trends.png', '/trends?begriffe=Notstand%2C%20Berufsverbot%2C%20Numerus', (0, 60, 1400, 640)),
         ('nutzen_exemplare.png', '/leaflets/851/exemplare', (0, 60, 1400, 590)),
         ('nutzen_korrekturen.png', '/korrekturen', (0, 60, 1400, 560)),
         ('nutzen_export.png', '/verwaltung/export', (0, 60, 1400, 736))]

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1400, 'height': 900}, device_scale_factor=1.5)
    for name, address, (x, y, w, h) in [s for s in SHOTS if not sys.argv[1:] or s[0] in sys.argv[1:]]:
        page.goto(APP + address, wait_until='domcontentloaded')  # 'load' waits for every scan of a long page
        page.wait_for_timeout(4000)
        page.screenshot(path=OUT / name, clip={'x': x, 'y': y, 'width': w, 'height': h})
        print(name)
    browser.close()
