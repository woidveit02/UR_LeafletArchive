"""Lernt die Gewichte des Trennvorschlags neu und misst, wie gut er trennt, an den getrennten Bänden im Scan-Ordner.

    python scripts/learn_boundary_weights.py [--ordner SCANORDNER] [--pruefen]

Die Trennung eines Bandes steht in <stem>.segments.json neben dem Scan, sobald er in der App fertig getrennt ist, die
von Nr. 1 bis 14 in data/nr<vz>_metadata.json. Leerseiten und die Seitenwechsel an ihnen zählen nicht mit, die App lässt
sie vor dem Vorschlag aus. Wie die Seiten aussehen, misst looks.py der App einmal je Band und legt es wie die App als
<stem>.looks.json neben den Scan (für Nr. 1 bis 14 einige Minuten).

Ohne --pruefen: lernt WEIGHTS, PRIOR, IMAGE_WEIGHTS und CUE_WEIGHTS und gibt sie zum Einsetzen in
src/backend/app/boundaries.py aus, wenn sie dort anders stehen. Mit --pruefen: lernt reihum ohne einen Band, schlägt auf
ihm vor wie die App und zählt, wie viele Schnitte danach zu ändern sind, nur mit dem Text und mit Wortliste und Scan
(Bericht Kap. 4.5). Den Scan-Ordner findet scan_folder.py. Braucht die Pakete der App (PyMuPDF, numpy, scipy).
"""
import argparse
import json
import math
import sys
from collections import Counter, defaultdict

from scan_folder import ROOT, scan_dir, volumes

sys.path.append(str(ROOT / "src" / "backend" / "app"))  # last, so its modules hide no others
import boundaries  # noqa: E402
import looks  # noqa: E402

NAMES = ("WEIGHTS", "PRIOR", "IMAGE_WEIGHTS", "CUE_WEIGHTS")
# the words that may get a weight, picked from those that told cut and no cut apart best on Nr. 1 to 14: without names
# of people and streets, decoration and words of one topic, group or place, with all months and weekdays
CUE_CANDIDATES = {
    "end": "eigendruck selbstverlag selbstverlag. verantwortlich verantwortl. presserechtlich presserechtl. gez. tel. "
           "vorsitzender kollektiv aktionsgemeinschaft uhr euch montag dienstag mittwoch donnerstag freitag samstag "
           "sonntag einzelne lediglich wobei genommen natürlich indem einige tatsächlich voraussetzung dessen daraus "
           "mittel sowohl mindestens außerhalb wenden",
    "start": "ablage eingelaufen info flugblatt nachrichten abteilung abt. fachschafts studentenparlament "
             "kommilitoninnen gestern gestrigen amtsjahr blatt sache januar jan. februar feb. märz mrz. april apr. mai "
             "juni juli august aug. september sept. oktober okt. november nov nov. dezember dez. gerade natürlich "
             "gemacht konkreten hinaus allein sinne versuchen hinsicht sei etwas daher deshalb jedoch jeder darin "
             "völlig aufgaben wesentlichen verfügung ausdruck vorstellungen ist.",
}
MIN_SEEN = 10  # rarer words get no weight: too few cases to learn one


def finished_segments(v, ocr):
    seg = ocr.parent.parent / f"{v['stem']}.segments.json"
    if seg.is_file():
        doc = json.loads(seg.read_text(encoding="utf-8"))
        return doc["segments"] if doc.get("finished", True) else None
    meta = ROOT / "data" / f"nr{v['vz']:03d}_metadata.json"
    return json.loads(meta.read_text(encoding="utf-8")).get("segments") if meta.is_file() else None


def page_looks(v, scan):
    """The looks of the scan's pages as in the app, measured once and kept next to the scan; none without the scan."""
    if not scan.is_file():
        return []
    path, stamp = scan.with_name(f"{v['stem']}.looks.json"), int(scan.stat().st_mtime)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("version") == looks.VERSION and doc.get("scan") == stamp:
            return doc["pages"]
    except (OSError, ValueError):
        pass
    print(f"{v['label']}: Aussehen der Seiten messen …", flush=True)
    pages = looks.measure_scan(scan)
    path.write_text(json.dumps({"version": looks.VERSION, "scan": stamp, "pages": pages}, ensure_ascii=False),
                    encoding="utf-8")
    return pages


def load(folder):
    """[(label, pages, looks, first pages, blank pages)] of the volumes whose cuts are finished."""
    found = []
    for v, ocr in volumes(folder):
        segments = finished_segments(v, ocr)
        if not segments:
            continue
        pages = boundaries.page_blocks(ocr)
        seen = page_looks(v, ocr.parent.parent / f"{v['stem']}.pdf")
        found.append((v["label"], pages, seen if len(seen) == len(pages) else [None] * len(pages),
                      {s["start_page"] for s in segments if not s.get("no_content")},
                      {p for s in segments if s.get("no_content") for p in range(s["start_page"], s["end_page"] + 1)}))
    return found


def transitions(volume):
    """[(page, whether it starts a leaflet)] for page 2, 3, …, not at blank pages."""
    _, pages, _, starts, blank = volume
    return [(n, n in starts) for n in range(2, len(pages) + 1) if n not in blank and n - 1 not in blank]


def learn(found):
    """(WEIGHTS, PRIOR, IMAGE_WEIGHTS, CUE_WEIGHTS): per feature and word the log likelihood ratio of a first page
    against a following one, Laplace-smoothed; the prior from how many pages start a leaflet."""
    n, hits = Counter(), defaultdict(Counter)
    for volume in found:
        _, pages, seen, _, _ = volume
        for page, start in transitions(volume):
            blocks, previous = pages[page - 1], pages[page - 2]
            end, top = boundaries.cue_words(blocks, previous)
            n[start] += 1
            for key in (boundaries.features(blocks, previous) | boundaries.image_features(seen[page - 1], seen[page - 2])
                        | {("end", w) for w in end} | {("start", w) for w in top}):
                hits[key][start] += 1

    def weight(key, digits=3):
        return round(math.log((hits[key][True] + 1) / (n[True] + 2) / ((hits[key][False] + 1) / (n[False] + 2))), digits)

    cues = {side: {w: weight((side, w), 2) for w in words.split() if sum(hits[(side, w)].values()) >= MIN_SEEN}
            for side, words in CUE_CANDIDATES.items()}
    return ({f: weight(f) for f in boundaries.WEIGHTS}, round(math.log(n[True] / n[False]), 3),
            {f: weight(f) for f in boundaries.IMAGE_WEIGHTS}, cues)


def use(learned):
    for name, value in zip(NAMES, learned):
        setattr(boundaries, name, value)


def check(found):
    """Leave one volume out: learn without it, suggest on it with boundaries.explain, count the cuts to change."""
    kept = tuple(getattr(boundaries, name) for name in NAMES)
    counts = {"nur Text": Counter(), "Text, Wortliste und Scan": Counter()}
    for i, volume in enumerate(found):
        weights, prior, image, cues = learn(found[:i] + found[i + 1:])
        _, pages, seen, _, _ = volume
        for label, learned, with_looks in (("nur Text", (weights, prior, image, {"end": {}, "start": {}}), False),
                                           ("Text, Wortliste und Scan", (weights, prior, image, cues), True)):
            use(learned)
            for page, start in transitions(volume):
                scan = (seen[page - 1], seen[page - 2]) if with_looks else (None, None)
                p, _ = boundaries.explain(pages[page - 1], pages[page - 2], *scan)
                counts[label][(p >= boundaries.MIN_PROBABILITY, start)] += 1
    use(kept)
    for label, c in counts.items():
        tp, fp, fn = c[(True, True)], c[(True, False)], c[(False, True)]
        print(f"{label:<26}{100 * (fp + fn) / sum(c.values()):5.1f} Fehler je 100 Seitenwechsel, Präzision "
              f"{tp / max(tp + fp, 1):.2f}, Trefferquote {tp / max(tp + fn, 1):.2f} ({fp} zu viel, {fn} fehlen)")
    print(f"Ohne Vorschlag {tp + fn} Schnitte von Hand bei {sum(c.values())} Seitenwechseln.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ordner", help="Scan-Ordner (Standard: LEAFLET_PDF_HOST_DIR aus .env)")
    ap.add_argument("--pruefen", action="store_true", help="bandweise messen, wie gut der Vorschlag trennt")
    args = ap.parse_args(argv)
    found = load(scan_dir(args.ordner))
    if not found:
        raise SystemExit("Im Scan-Ordner liegt kein fertig getrennter Band.")
    print(f"{len(found)} Bände: {', '.join(label for label, *_ in found)}")
    if args.pruefen:
        check(found)
        return
    learned = learn(found)
    if learned == tuple(getattr(boundaries, name) for name in NAMES):
        print("Die Gewichte in boundaries.py sind schon die gelernten.")
        return
    print("\nIn src/backend/app/boundaries.py einsetzen:\n")
    for name, value in zip(NAMES, learned):
        print(f"{name} = {json.dumps(value, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
