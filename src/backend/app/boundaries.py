"""Cuts suggested from the recognized text, without Datalab's segmentation and without cost.

Features: an archive stamp, a date in the header, a masthead, an imprint on the page before or little in common
with it speak for a new leaflet; a running page number, "b.w.", a hyphen at the end of the page before or
"Fortsetzung" against it. The weights come from scripts/learn_boundary_weights.py. Measured volume by volume on Nr. 1 to 14, the
suggestion leaves about half of the corrections a volume needs without one (report, chapter 4.4).
"""
import html
import json
import math
import re

# weights (log likelihood ratios) and prior learned on Nr. 1 to 14 by scripts/learn_boundary_weights.py; ponytail: frozen,
# learn again there when the archive has grown considerably
WEIGHTS = {"stamp": 3.542, "headdate": 2.535, "masthead": 1.99, "prev_imprint": 1.865, "pagenum": -1.801,
           "prev_bw": -1.302, "prev_hyphen": -2.087, "cont_word": -1.394, "overlap_low": 0.966, "first_heading": 0.435,
           "prev_blank": 1.983, "overlap_high": -1.1, "blank": 0.229, "prev_end": -0.649}
PRIOR = -0.216
# above the prior's 0.45: a page without any feature is not cut
MIN_PROBABILITY = 0.5
HINT_PROBABILITY = 0.7  # stricter, for hints on a list that somebody wrote: fewer false alarms (precision 0.84, recall 0.58)

DATE_RE = re.compile(
    r"\b\d{1,2}\.\s*\d{1,2}\.\s*\d{2,4}\b"
    r"|\b\d{1,2}\.\s*(?:Jan|Feb|M[äa]r|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)[a-zäöü]*\.?\s*\d{2,4}\b",
    re.IGNORECASE)
STAMP_DATE = (r"\d{1,2}\s*\.?\s*(?:JAN|FEB|MRZ|MÄR|MÄRZ|APR|MAI|JUNI?|JULI?|AUG|"
              r"SEPT?|OKT|NOV|DEZ)\.?\s*19\d\d")
STAMP_INLINE = re.compile(
    rf"(?:eingeliefert|eingegangen|eingetroffen|eingelaufen)\s+am\s*:?\s*-?\s*{STAMP_DATE}"
    rf"|\bAblage\s*[\d\s()]{{2,8}}(?:{STAMP_DATE})?|\bz\.\s?K\.")
STAMP_ONLY = re.compile(rf"^\W*(?:am\s*:?\s*-?\s*)?{STAMP_DATE}\W*$")
STAMP_PICTURE = re.compile(r"stamp|stempel|eingeliefert|eingegangen|eingetroffen|eingelaufen", re.I)
RESPONSIBLE_LINE = re.compile(
    r"(?im)^\s*(?:verantwortlich(?:\s+für\s+den\s+inhalt)?|verantwortl\.|"
    r"v\.\s?i\.\s?s\.\s?d\.\s?p\.?|gez\.)\s*:?\s*([^\n]+)")
IMPRINT = re.compile(r"(?im)^\s*(herausgeber|hrsg\.|eigendruck|druck\s*:|selbstverlag)")
PAGENUM = re.compile(r"^[\s\-–—]*(?:seite|s\.)?[\s.]*?([2-9]|1\d)[.)]?[\s\-–—]*$", re.I)
CONT_WORD = re.compile(r"(?i)^\W*(fortsetzung|forts\.)")
BW = re.compile(r"(?i)\b(b\.\s?w\.|bitte\s+wenden|bitte\s+umblättern|siehe\s+rückseite)\W*$")
SKIP = {"PageHeader", "PageFooter", "Picture", "Figure"}
WORD = re.compile(r"[a-zäöüß]{4,}")
SENTENCE_END = re.compile(r"[.!?:)\"“”]\s*$")

LABEL = {"stamp": "Eingangsstempel", "headdate": "Datum in der Kopfzeile", "masthead": "Kopfleiste",
         "prev_imprint": "Impressum auf der Seite davor", "overlap_low": "kaum gemeinsame Wörter mit der Seite davor",
         "first_heading": "Überschrift am Anfang", "prev_blank": "Seite davor fast leer", "blank": "Seite fast leer"}


def is_masthead(text):
    """Three or more dash-separated parts that repeat with a short period, e.g. "LSD - LSD - LSD"."""
    parts = [p.strip().lower() for p in re.split(r"[-–—]", text) if p.strip()]
    if len(parts) < 3 or any(len(p) > 30 or len(p.split()) > 4 for p in parts):
        return False
    return any(all(parts[i] == parts[i % period] for i in range(len(parts)))
               for period in range(1, len(parts) // 2 + 1) if len(parts) >= period * 2)


def is_stamp_block(block_type, text):
    if block_type == "Picture":
        return bool(STAMP_PICTURE.search(text))
    return bool(STAMP_ONLY.match(" ".join(text.split())))


def page_blocks(ocr_json):
    """[[(block_type, text)] per page] of the Datalab result; text is the block's html without tags, one line per row."""
    pages = []
    for page in json.loads(ocr_json.read_text(encoding="utf-8")).get("children", []):
        blocks = []
        for b in page.get("children", []):
            text = html.unescape(re.sub(r"<[^>]+>", "\n", b.get("html", "")))
            blocks.append((b.get("block_type", "Text"), "\n".join(l.strip() for l in text.splitlines() if l.strip())))
        pages.append(blocks)
    return pages


def body_words(blocks):
    return set(WORD.findall(" ".join(x.lower() for t, x in blocks if x and t not in SKIP)))


def features(blocks, previous):
    """The features of a page that are present, with their weights as in WEIGHTS; previous = blocks of the page before."""
    texts = [(t, x) for t, x in blocks if x]
    found = set()
    if any(PAGENUM.match(x) for _, x in texts[:2] + texts[-2:]):
        found.add("pagenum")
    for t, x in texts[:3]:
        if is_masthead(" ".join(x.split())):
            found.add("masthead")
        if t == "PageHeader" and DATE_RE.search(x):
            found.add("headdate")
    if any(is_stamp_block(t, x) or (t != "Picture" and STAMP_INLINE.search(x)) for t, x in texts):
        found.add("stamp")
    body = [x for t, x in texts if t not in SKIP and not is_stamp_block(t, x)]
    if body and CONT_WORD.match(body[0]):
        found.add("cont_word")
    before = [x for t, x in previous or [] if x and t not in SKIP]
    if before:
        if any(BW.search(x.strip()) for x in before[-2:]):
            found.add("prev_bw")
        last = before[-1].strip()
        # "-Eigendruck im Selbstverlag-" is decoration, not a hyphenated word
        if re.search(r"[a-zäöüß]-$", last) and not last.startswith(("-", "–")):
            found.add("prev_hyphen")
        if any(RESPONSIBLE_LINE.search(x) or IMPRINT.search(x) for x in before[-4:]):
            found.add("prev_imprint")
    text = [(t, x) for t, x in blocks if x and t not in SKIP]
    mine, theirs = body_words(blocks), body_words(previous or [])
    if len(mine & theirs) < 0.03 * len(mine | theirs):
        found.add("overlap_low")
    if len(mine & theirs) > 0.12 * len(mine | theirs):
        found.add("overlap_high")
    if text and text[0][0] == "SectionHeader":
        found.add("first_heading")
    if sum(len(x) for x in before) < 30:
        found.add("prev_blank")
    if sum(len(x) for _, x in text) < 30:
        found.add("blank")
    if before and SENTENCE_END.search(before[-1]):
        found.add("prev_end")
    return found


def probability(found):
    return 1 / (1 + math.exp(-(PRIOR + sum(WEIGHTS[f] for f in found))))


def suggest(ocr_json, min_probability=MIN_PROBABILITY):
    """({cut after page: why}, page count): a cut for each page that probably starts a leaflet; why names the
    features that speak for it."""
    pages = page_blocks(ocr_json)
    cuts = {}
    for number in range(2, len(pages) + 1):
        found = features(pages[number - 1], pages[number - 2])
        if probability(found) >= min_probability:
            cuts[number - 1] = ", ".join(LABEL[f] for f in sorted(found) if WEIGHTS[f] > 0)
    return cuts, len(pages)
