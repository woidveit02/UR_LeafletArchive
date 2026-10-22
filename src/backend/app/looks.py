"""What the scan of each page looks like, for the suggested cuts: paper colour, size, ink, blank pages, the archive's
blue marks and the punch holes.

Measured once per scan on a small colour image of each page (48 dpi) and kept in <stem>.looks.json next to the scan.
pipelines/01_pdf/page_looks.py loads this module, so the pipeline measures exactly what the app does.
"""
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pymupdf
from scipy import ndimage

VERSION = 2  # raise when a measure changes: kept files are made again
DPI = 48
PX = DPI / 36  # the hole sizes were found at 36 dpi
MM = DPI / 25.4
DARK = 70
STRIP = (0.01, 0.13)  # where the holes are, as a share of the page width from the edge
MIDDLE = (0.15, 0.85)  # and of its height
WORKERS = 4
CHUNK = 5  # small, so the progress moves steadily


def box(sl, h, w, left=0):
    """[x, y, width, height] of a slice as shares of the page; left: where the cut-out it is in begins."""
    return [round((left + sl[1].start) / w, 3), round(sl[0].start / h, 3),
            round((sl[1].stop - sl[1].start) / w, 3), round((sl[0].stop - sl[0].start) / h, 3)]


def inside(a, b):
    return a != b and b[0] <= a[0] and b[1] <= a[1] and a[0] + a[2] <= b[0] + b[2] and a[1] + a[3] <= b[1] + b[3]


def outermost(boxes):
    """The boxes not inside another one: the frame of a stamp, not also its text."""
    return [a for i, a in enumerate(boxes) if a not in boxes[:i] and not any(inside(a, b) for b in boxes)]


def hole_spots(mask):
    """Round, well filled spots of a hole's size in a strip at the side, not at the strip's edge (the scanner's)."""
    lab, _ = ndimage.label(mask)
    found = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        area = (lab[sl] == i).sum()
        if 18 * PX ** 2 <= area <= 130 * PX ** 2 and 5 * PX <= w <= 14 * PX and 5 * PX <= h <= 14 * PX \
                and abs(w - h) <= 4 * PX and area >= 0.55 * w * h and sl[1].start > 0 and sl[1].stop < mask.shape[1] \
                and MIDDLE[0] * len(mask) < sl[0].start < MIDDLE[1] * len(mask):
            found.append(sl)
    return found


def punched(spots):
    """The two holes of a filing punch among the spots: 80 mm apart, one above the other; bullet points in the margin
    are not."""
    for i, p in enumerate(spots):
        for q in spots[i + 1:]:
            if abs(abs(q[0].start - p[0].start) / MM - 80) < 12 and abs(q[1].start - p[1].start) / MM < 4:
                return [p, q]
    return []


def holes(gray):
    """("left" (the front of a sheet), "right" (its back), "both" or "none", [box of each hole]). The holes show the
    scanner's background: black in the newer scans, white in Nr. 1 to 12, so there brighter than the paper around."""
    h, w = gray.shape
    a, b = int(STRIP[0] * w), int(STRIP[1] * w)

    def side(x, strip):
        found = punched(hole_spots(strip < DARK)) or punched(hole_spots(strip - np.median(strip) > 15))
        return [box(sl, h, w, x) for sl in found]
    left, right = side(a, gray[:, a:b]), side(w - b, gray[:, w - b:w - a])
    return "both" if left and right else "left" if left else "right" if right else "none", left + right


def blue_spots(tint, marked):
    """(slice, width mm, height mm, blue pixels, how much bluer than the other ink) of the blue spots."""
    usual = np.median(tint[marked])
    blue = marked & (tint > 0.06)
    lab, _ = ndimage.label(ndimage.binary_dilation(blue, np.ones((5, 5))))
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        dots = (blue[sl] & (lab[sl] == i)).sum()
        if dots >= 15:
            yield sl, (sl[1].stop - sl[1].start) / MM, (sl[0].stop - sl[0].start) / MM, dots, \
                np.median(tint[sl][marked[sl]]) - usual


def measure(page):
    """The looks of one page."""
    pix = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csRGB)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.stride)[:, :pix.width * 3] \
        .reshape(pix.height, pix.width, 3).astype(float)
    h, w = img.shape[:2]
    gray = img.mean(axis=2)
    core = img[int(.1 * h):int(.9 * h), int(.1 * w):int(.9 * w)].reshape(-1, 3)
    paper = np.median(core[core.mean(axis=1) >= np.median(core.mean(axis=1))], axis=0)
    # share of the paper's light per channel: grey ink lowers all three alike, blue ink takes more red than blue
    t = img / np.maximum(paper, 1)
    tint = t[..., 2] - t[..., 0]
    marked = (t.mean(axis=2) < 0.85) & (gray > DARK)
    # the scanner's background and the holes: near black at the edge, or small near the sides
    dark, n = ndimage.label(gray < DARK)
    drop = np.zeros(n + 1, bool)
    for i, sl in enumerate(ndimage.find_objects(dark), 1):
        drop[i] = sl[0].start == 0 or sl[1].start == 0 or sl[0].stop == h or sl[1].stop == w or (
            sl[0].stop - sl[0].start < 0.05 * h and sl[1].stop - sl[1].start < 0.05 * w
            and (sl[1].stop < 0.15 * w or sl[1].start > 0.85 * w))
    ink = ((gray < 0.75 * paper.mean()) | (marked & (tint > 0.06))) & ~drop[dark]
    b = int(0.03 * min(h, w))
    inside = ink[b:h - b, b:w - b]
    rows, cols = np.nonzero(inside.sum(axis=1) >= 3)[0], np.nonzero(inside.sum(axis=0) >= 3)[0]
    margins = [rows[0] / len(inside), 1 - (rows[-1] + 1) / len(inside), cols[0] / inside.shape[1],
               1 - (cols[-1] + 1) / inside.shape[1]] if len(rows) and len(cols) else [1, 1, 1, 1]
    # strokes: pixels clearly darker than their surroundings, without the edges and the hole strips
    text = gray[int(.06 * w):h - int(.06 * w), int(.15 * w):int(.85 * w)]
    strokes = np.mean(ndimage.uniform_filter(text, 15) - text > 15)
    spots = list(blue_spots(tint, marked)) if marked.any() else []
    printed_blue = len(spots) > 4
    signs = [] if printed_blue else [sl for sl, bw, bh, dots, bluer in spots if sl[0].start < 0.3 * h and 5 <= bw <= 30
                                     and 5 <= bh <= 30 and dots >= 20 and bluer >= 0.08]
    stamps = [] if printed_blue else [sl for sl, bw, bh, _, bluer in spots if 18 <= bw <= 60 and 8 <= bh <= 35
                                      and bluer > 0.03]
    side, holes_at = holes(gray)
    return {"size": [round(page.rect.width), round(page.rect.height)], "paper": [round(float(c)) for c in paper],
            "ink": round(float(ink.mean()), 4), "margins": [round(float(m), 3) for m in margins],
            "blank": bool(strokes < 0.005), "sign": bool(signs), "stamp": bool(stamps), "holes": side,
            "spots": {"holes": holes_at, "blue": outermost([box(sl, h, w) for sl in signs + stamps])}}


def measure_range(pdf, first, last):
    with pymupdf.open(pdf) as doc:
        return [measure(doc[n]) for n in range(first, last)]


def measure_scan(pdf, progress=lambda done, total: None, workers=WORKERS):
    """The looks of every page of the scan, in order; progress(done, total) after each chunk of pages."""
    with pymupdf.open(pdf) as doc:
        total = doc.page_count
    parts, done = {}, 0
    # spawn, not fork: the app runs threads, and a forked child can hang on a lock one of them held
    with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("spawn")) as pool:
        running = {pool.submit(measure_range, pdf, a, min(a + CHUNK, total)): a for a in range(0, total, CHUNK)}
        try:
            for future in as_completed(running):  # reported as they finish, put in order at the end
                parts[running[future]] = future.result()
                done += len(parts[running[future]])
                progress(done, total)
        finally:
            pool.shutdown(cancel_futures=True)  # if progress raised: the pages not begun are dropped
    return [page for first in sorted(parts) for page in parts[first]]
