"""Screenshots of the import steps for docs/handbuch/neue-baende-importieren.md (needs playwright, see app_screenshots.py).

    python scripts/import_screenshots.py      (test instance on http://localhost:8002)

Run it against a copy of the data, never the real app: it opens the splitter, which marks visited transitions as
checked. The copy needs volume 15 as a draft at step 6 and volume 14 with assigned topics.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / 'docs/abbildungen'
APP = 'http://localhost:8002'


def open_details(n=0):
    return lambda page: page.locator('details.help > summary').nth(n).click()


def splitter(page):
    page.click('#split-open')
    page.wait_for_timeout(2000)
    page.click('figure.split-page[data-page="24"] img')
    page.wait_for_timeout(2500)
    page.click('#split-decide .split-q')


def issuer_choice(page):  # the first suggestion chosen, so its evidence shows
    page.set_viewport_size({'width': 1400, 'height': 1530})
    page.locator('.org-results input').first.check()


# (file, address, action before the shot, clip in CSS pixels or None: from below the menu to the end of the step)
SHOTS = [('import_verwaltung.png', '/verwaltung', None, (0, 90, 1400, 458)),
         ('import_band.png', '/import/neu', None, None),
         ('import_scans.png', '/import/15?schritt=scans', open_details(), None),
         ('import_ocr.png', '/import/15?schritt=ocr', open_details(), None),
         ('import_trennen.png', '/import/15?schritt=trennen', splitter, (0, 0, 1400, 900)),
         ('import_metadaten.png', '/import/15?schritt=angaben', open_details(), None),
         ('import_pruefen.png', '/import/15?schritt=pruefen', None, None),
         ('import_herausgeber.png', '/import/0/herausgeber?nr=2', issuer_choice, (0, 90, 1400, 1440)),
         ('import_themen.png', '/import/14?schritt=themen', None, (0, 90, 1400, 516))]

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1400, 'height': 900}, device_scale_factor=1.5)
    for name, address, act, clip in [s for s in SHOTS if not sys.argv[1:] or s[0] in sys.argv[1:]]:
        page.goto(APP + address, wait_until='load')
        page.wait_for_timeout(1500)
        if act:
            act(page)
            page.wait_for_timeout(2000)
        page.mouse.move(0, 0)
        if not clip:
            box = page.locator('.import-body').bounding_box()
            clip = (0, 90, 1400, box['y'] + box['height'] + 16 - 90)
        x, y, w, h = clip
        page.screenshot(path=OUT / name, clip={'x': x, 'y': y, 'width': w, 'height': h}, full_page=True)
        print(name)
    browser.close()
