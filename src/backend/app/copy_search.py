"""Copies of a new volume's leaflets in the other volumes, as the project's search over all volumes (find_copies.py) found them: the same
text despite OCR noise (5-gram Jaccard). find_copies.py compares all volumes and needs embeddings to pick the pairs;
one volume against the rest is few enough pairs to compare directly. The hits become rows of copies.tsv, so the
reviews in copy_decisions.jsonl stay as they are and a hit to a checked group shows as a new hit there."""
import csv
import html
import re
from collections import Counter

from .database import fillDatabase
from .database.models import Leaflet, Page, Volume

NAME = "copies.tsv"
SKIP = {"Picture", "Figure", "PictureGroup", "FigureGroup", "PageHeader", "PageFooter"}  # as in leaflet_topics.py
STAMPS = re.compile(r"\bAblage\s*[\d\s()]{2,8}(?:\d{1,2}\.?\s*[A-ZÄ]{3,5}\.?\s*19\d\d)?|\bz\.\s?K\.|\bErbitte Rückgabe")
COPY, MIN_CHARS = 0.75, 150  # the thresholds of find_copies.py
NEAR = 0.3  # shared rare words for a pair to be compared exactly; far below what copies share, so none is lost
RARE = 0.05  # words in more leaflets than this share say little and only slow the first look down
WORD = re.compile(r"[a-zäöüß0-9]{3,}")


def shingles(text, n=5):
    norm = re.sub(r"\s+", " ", re.sub(r"[^a-zäöüß0-9]+", " ", text.lower())).strip()
    return {norm[i:i + n] for i in range(max(1, len(norm) - n + 1))}


def words(leaflets):
    """anchor -> the words of the leaflet's stored page text, a quick first look."""
    text = {(v, n): t or "" for v, n, t in fillDatabase.session.query(Page.volume_id, Page.page_no, Page.text)}
    return {a: set(WORD.findall(" ".join(text.get((lf.volume_id, n), "") for n in range(lf.start_page, lf.end_page + 1)).lower()))
            for a, lf in leaflets.items()}


def texts(leaflets):
    """anchor -> the text find_copies.py compares: no pictures, headers, footers or archive stamps."""
    pages = {(v, n): blocks for v, n, blocks in fillDatabase.session.query(Page.volume_id, Page.page_no, Page.blocks)
             .filter(Page.volume_id.in_({lf.volume_id for lf in leaflets.values()}))}
    out = {}
    for a, lf in leaflets.items():
        parts = [html.unescape(re.sub(r"<[^>]+>", " ", b.get("html") or ""))
                 for n in range(lf.start_page, lf.end_page + 1) for b in pages.get((lf.volume_id, n)) or []
                 if b.get("type") not in SKIP]
        out[a] = re.sub(r"\s+", " ", STAMPS.sub(" ", " ".join(parts))).strip()
    return out


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def read():
    path = fillDatabase.DATA_DIR / NAME
    if not path.is_file():
        return ["gruppe", "kanonisch", "band", "seiten", "segment_id", "zeichen", "anfang"], []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return reader.fieldnames, list(reader)


def write(fields, rows):
    groups = {}
    for r in rows:
        groups.setdefault(r["gruppe"], []).append(r)
    with open(fillDatabase.DATA_DIR / NAME, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(r for r in rows if len(groups[r["gruppe"]]) > 1)  # a group a removed volume leaves alone is none


def span(first, last):
    return f"{first}" if first == last else f"{first}-{last}"


def mine(row, volume):
    """A row of the volume, or of an older leaflet that only the volume's search put into a group."""
    return row["band"] == volume.label or row["segment_id"] == f"+{volume.stem}"


def remove(volume):
    """Takes the volume's rows out of copies.tsv, and groups left with one leaflet."""
    fields, rows = read()
    write(fields, [r for r in rows if not mine(r, volume)])
    fillDatabase.fill_copies()


def add(volume):
    """Finds the copies of the volume's leaflets and writes them into copies.tsv. Returns the number of its
    leaflets with a copy."""
    fields, rows = read()
    rows = [r for r in rows if not mine(r, volume)]
    stems = dict(fillDatabase.session.query(Volume.label, Volume.stem))
    labels = {s: label for label, s in stems.items()}
    anchor = lambda r: (stems.get(r["band"]), int(r["seiten"].partition("-")[0]), int(r["seiten"].partition("-")[2] or r["seiten"]))
    group_of = {anchor(r): r["gruppe"] for r in rows}

    leaflets = {(stem, lf.start_page, lf.end_page): lf
                for lf, stem in fillDatabase.session.query(Leaflet, Volume.stem).join(Volume)}
    new = [a for a in leaflets if a[0] == volume.stem]
    order = {a: i for i, a in enumerate(new)}
    near = words(leaflets)
    df = Counter(w for ws in near.values() for w in ws)
    near = {a: {w for w in ws if df[w] <= max(RARE * len(near), 20)} for a, ws in near.items()}
    index = {}
    for a, ws in near.items():
        for w in ws:
            index.setdefault(w, []).append(a)
    pairs = []
    for i, a in enumerate(new):
        shared = Counter(b for w in near[a] for b in index[w] if order.get(b, len(new)) > i)  # each new pair once
        pairs += [(a, b) for b, n in shared.items() if n / (len(near[a]) + len(near[b]) - n) >= NEAR]
    known = {a: t for a, t in texts({a: leaflets[a] for pair in pairs for a in pair}).items() if len(t) >= MIN_CHARS}
    grams = {a: shingles(t) for a, t in known.items()}
    parent = {}

    def root(a):
        while parent.get(a, a) != a:
            a = parent[a]
        return a

    for a, b in pairs:
        if a in grams and b in grams and jaccard(grams[a], grams[b]) >= COPY:
            parent[root(a)] = root(b)

    components = {}
    for a in parent.keys() | {p for p in parent.values()}:
        components.setdefault(root(a), set()).add(a)
    numbers = [int(r["gruppe"]) for r in rows]
    for members in sorted(components.values(), key=min):  # stable numbers for the same result
        existing = sorted({group_of[a] for a in members if a in group_of}, key=int)
        number = existing[0] if existing else str(max(numbers, default=0) + 1)
        numbers.append(int(number))
        longest = max(members, key=lambda a: len(known[a]))
        for a in sorted(members):
            if a in group_of:
                continue
            rows.append({"gruppe": number, "kanonisch": "ja" if not existing and a == longest else "",
                         "band": labels[a[0]], "seiten": span(a[1], a[2]),
                         "segment_id": "" if a[0] == volume.stem else f"+{volume.stem}",
                         "zeichen": len(known[a]), "anfang": known[a][:90]})
    write(fields, rows)
    fillDatabase.fill_copies()
    return sum(1 for a in new if any(a in m for m in components.values()))
