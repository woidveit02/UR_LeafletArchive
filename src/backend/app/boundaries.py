"""Cuts suggested from the recognized text and the look of the scan, without Datalab's segmentation and without cost.

Features are those of pipelines/01_pdf/check_boundaries.py with extended=True in the pipeline repo (regexes copied
from there): an archive stamp, a date in the header, a masthead, an imprint on the page before or little in common
with it speak for a new leaflet; a running page number, "b.w.", a hyphen at the end of the page before or
"Fortsetzung" against it. Words like "Eigendruck" at the end of the page before or "eingelaufen" at the top of the
page count too (pipelines/01_pdf/cue_words.py). From the scan (looks.py): another paper or size, the archive's stamp
and blue mark, and holes on the right, which make the page the back of a sheet. The weights come from
pipelines/01_pdf/app_boundaries.py --weights, which also checks that this module cuts where the pipeline does.
Measured volume by volume on Nr. 1 to 14, about 12 of 100 transitions need a correction, 20 from the text alone
(docs/korpus/schnittvorschlag.md).
"""
import html
import json
import math
import re

# weights (log likelihood ratios) and prior learned on Nr. 1 to 14 by app_boundaries.py --weights; ponytail: frozen,
# learn again there when the archive has grown considerably
WEIGHTS = {"stamp": 3.542, "headdate": 2.535, "masthead": 1.99, "prev_imprint": 1.865, "pagenum": -1.801,
           "prev_bw": -1.302, "prev_hyphen": -2.087, "cont_word": -1.394, "overlap_low": 0.966, "first_heading": 0.435,
           "prev_blank": 1.983, "overlap_high": -1.1, "blank": 0.229, "prev_end": -0.649}
PRIOR = -0.216
IMAGE_WEIGHTS = {"paper_other": 1.215, "paper_very_other": 2.664, "paper_same": -0.706, "size_other": 0.577,
                 "ink_other": 0.891, "margins_other": 0.879, "back": -2.411, "sign": 3.548, "stamp_seen": 3.08}
# per transition the strongest word for a cut and the strongest against it count; "end" is the end of the page
# before, "start" the top of the page
CUE_WEIGHTS = {
    "end": {"eigendruck": 2.64, "selbstverlag": 2.42, "selbstverlag.": 3.31, "verantwortlich": 2.09,
            "verantwortl.": 2.01, "presserechtlich": 1.6, "presserechtl.": 1.78, "gez.": 1.53, "tel.": 2.04,
            "vorsitzender": 1.74, "kollektiv": 2.09, "aktionsgemeinschaft": 2.09, "uhr": 1.62, "euch": 1.66,
            "montag": 1.74, "dienstag": 1.66, "mittwoch": 1.42, "donnerstag": 1.46, "freitag": 1.39, "samstag": 0.91,
            "einzelne": -2.23, "lediglich": -1.98, "wobei": -1.98, "genommen": -1.98, "natürlich": -1.94,
            "indem": -1.9, "einige": -1.8, "tatsächlich": -1.8, "voraussetzung": -1.86, "dessen": -1.68,
            "daraus": -1.73, "mittel": -1.78, "sowohl": -1.58, "mindestens": -1.58, "außerhalb": -1.52,
            "wenden": -1.73},
    "start": {"ablage": 4.54, "eingelaufen": 3.71, "info": 2.4, "flugblatt": 2.01, "nachrichten": 3.05,
              "abteilung": 2.67, "abt.": 1.72, "fachschafts": 2.89, "studentenparlament": 1.62,
              "kommilitoninnen": 2.26, "gestern": 2.58, "gestrigen": 2.05, "amtsjahr": 2.29, "blatt": 2.23,
              "sache": 1.92, "januar": 0.55, "jan.": 2.25, "februar": 1.13, "feb.": 2.57, "märz": -0.07,
              "april": 0.83, "mai": 1.17, "juni": 2.08, "juli": 2.02, "august": -0.99, "oktober": 0.57, "okt.": 1.42,
              "november": 2.01, "nov": 3.58, "nov.": 2.19, "dezember": 0.22, "dez.": 3.26, "gerade": -2.78,
              "natürlich": -2.56, "gemacht": -2.23, "konkreten": -2.18, "hinaus": -2.04, "allein": -1.98,
              "sinne": -1.98, "versuchen": -1.98, "hinsicht": -1.86, "sei": -1.86, "etwas": -1.77, "daher": -1.73,
              "deshalb": -1.71, "jedoch": -1.6, "jeder": -1.66, "darin": -1.66, "völlig": -1.69, "aufgaben": -1.73,
              "wesentlichen": -1.73, "verfügung": -1.68, "ausdruck": -1.58, "vorstellungen": -1.62, "ist.": -1.55}}
CUE_CHARS = 250
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
CUE_WORD = re.compile(r"[a-zäöüß]{3,}\.?")
SENTENCE_END = re.compile(r"[.!?:)\"“”]\s*$")

LABEL = {"stamp": "Eingangsstempel", "headdate": "Datum in der Kopfzeile", "masthead": "Kopfleiste",
         "prev_imprint": "Impressum auf der Seite davor", "overlap_low": "kaum gemeinsame Wörter mit der Seite davor",
         "first_heading": "Überschrift am Anfang", "prev_blank": "Seite davor fast leer", "blank": "Seite fast leer",
         "pagenum": "Seitenzahl", "prev_bw": "„b. w.“ auf der Seite davor",
         "prev_hyphen": "Trennstrich am Ende der Seite davor",
         "cont_word": "beginnt mit „Fortsetzung“", "overlap_high": "viele gemeinsame Wörter mit der Seite davor",
         "prev_end": "Seite davor endet mit Satzzeichen", "paper_other": "andere Papierfarbe",
         "paper_very_other": "deutlich andere Papierfarbe", "paper_same": "gleiche Papierfarbe",
         "size_other": "anderes Format",
         "ink_other": "viel mehr oder weniger Tinte", "margins_other": "andere Ränder",
         "back": "Löcher rechts: Rückseite",
         "sign": "blaues Zeichen des Archivs", "stamp_seen": "Stempel im Bild"}


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


def image_features(look, before):
    """The features of a page's scan, compared with the page before (looks.measure); none without both."""
    if not look or not before:
        return set()
    found = set()
    paper = math.dist(look["paper"], before["paper"])
    if paper > 50:
        found.add("paper_very_other")
    elif paper > 14:
        found.add("paper_other")
    elif paper < 4:
        found.add("paper_same")
    if max(abs(a - b) for a, b in zip(look["size"], before["size"])) > 15:
        found.add("size_other")
    if abs(math.log((look["ink"] + 1e-3) / (before["ink"] + 1e-3))) > 1.5:
        found.add("ink_other")
    if sum(abs(look["margins"][i] - before["margins"][i]) for i in (2, 3)) > 1:
        found.add("margins_other")
    if look["holes"] == "right":
        found.add("back")
    if look["sign"]:
        found.add("sign")
    if look["stamp"]:
        found.add("stamp_seen")
    return found


def cues(blocks, previous):
    """[(label, weight)] of the strongest word for a cut and the strongest against it."""
    def words(bl, part):
        return set(CUE_WORD.findall(part(" ".join(x for t, x in bl or [] if x and t not in SKIP)).lower()))
    end, start = CUE_WEIGHTS["end"], CUE_WEIGHTS["start"]
    found = [(f"„{w}“ am Ende der Seite davor", end[w]) for w in words(previous, lambda t: t[-CUE_CHARS:])
             if w in end] \
        + [(f"„{w}“ am Seitenanfang", start[w]) for w in words(blocks, lambda t: t[:CUE_CHARS]) if w in start]
    pro, con = max(found, key=lambda c: c[1], default=None), min(found, key=lambda c: c[1], default=None)
    return [c for c in (pro,) if c and c[1] > 0] + [c for c in (con,) if c and c[1] < 0]


def explain(blocks, previous, look=None, before=None):
    """(probability that the page starts a leaflet, [(label, weight)] of what speaks for and against it, strongest
    for first); without the looks of both pages from the text alone."""
    reasons = [(LABEL[f], WEIGHTS[f]) for f in features(blocks, previous)] \
        + [(LABEL[f], IMAGE_WEIGHTS[f]) for f in image_features(look, before)] + cues(blocks, previous)
    reasons.sort(key=lambda r: -r[1])
    return 1 / (1 + math.exp(-(PRIOR + sum(w for _, w in reasons)))), reasons


def probability(found):
    return 1 / (1 + math.exp(-(PRIOR + sum(WEIGHTS[f] for f in found))))


def assess(pages, looks=None):
    """[(probability, reasons)] for the transitions after page 1, 2, …, see explain; pages as from page_blocks,
    looks one per page or None."""
    looks = looks if looks and len(looks) == len(pages) else [None] * len(pages)
    return [explain(pages[n], pages[n - 1], looks[n], looks[n - 1]) for n in range(1, len(pages))]


def suggest(ocr_json, min_probability=MIN_PROBABILITY, looks=None):
    """({cut after page: why}, page count): a cut for each page that probably starts a leaflet; why names what
    speaks for it."""
    pages = page_blocks(ocr_json)
    cuts = {n: ", ".join(label for label, w in reasons if w > 0)
            for n, (p, reasons) in enumerate(assess(pages, looks), 1) if p >= min_probability}
    return cuts, len(pages)
