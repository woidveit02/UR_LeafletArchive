"""Screenshots of the running app for the report (needs playwright: pip install playwright; playwright install chromium).

    python scripts/app_screenshots.py      (app on http://localhost:8000)

Only read-only pages of released volumes; never the import of drafts.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / 'docs/abbildungen'
APP = 'http://localhost:8000'
# (file, address, clip in CSS pixels: x, y, width, height)
SHOTS = [('app_leseansicht.png', '/leaflets/850', (0, 90, 1400, 810)),
         ('app_band.png', '/volumes/6#page-394', (155, 60, 815, 325)),
         ('app_themen.png', '/themen', (0, 60, 1400, 840))]

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1400, 'height': 900}, device_scale_factor=1.5)
    for name, address, (x, y, w, h) in SHOTS:
        page.goto(APP + address, wait_until='load')
        page.wait_for_timeout(2500)
        page.screenshot(path=OUT / name, clip={'x': x, 'y': y, 'width': w, 'height': h})
        print(name)
    browser.close()
