"""Lernt die Gewichte des Trennvorschlags neu, aus den getrennten Bänden im Scan-Ordner.

    python scripts/learn_boundary_weights.py [--ordner SCANORDNER]

Liest je Band die Texterkennung und die Trennung (<stem>.segments.json) und vergleicht die gelernten Gewichte mit
denen in src/backend/app/boundaries.py. Weichen sie ab, stehen am Ende WEIGHTS und PRIOR zum Einsetzen dort.
Ohne --ordner gilt LEAFLET_PDF_HOST_DIR aus .env. Braucht nur die Standardbibliothek.
"""
import argparse
import importlib.util
import json
import math
from collections import Counter

from scan_folder import ROOT, scan_dir, volumes

spec = importlib.util.spec_from_file_location("boundaries", ROOT / "src" / "backend" / "app" / "boundaries.py")
boundaries = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boundaries)


def calibrate(split_volumes):
    """(weights, prior) from [(pages of page_blocks, start pages)]: per feature the log likelihood ratio of a first
    page against a following one, Laplace-smoothed, as the weights in boundaries.py were learned."""
    n, hits = Counter(), {"start": Counter(), "inner": Counter()}
    for pages, starts in split_volumes:
        for number in range(2, len(pages) + 1):
            kind = "start" if number in starts else "inner"
            n[kind] += 1
            hits[kind].update(boundaries.features(pages[number - 1], pages[number - 2]))
    weights = {f: round(math.log((hits["start"][f] + 1) / (n["start"] + 2) / ((hits["inner"][f] + 1) / (n["inner"] + 2))), 3)
               for f in boundaries.WEIGHTS}
    return weights, round(math.log(n["start"] / n["inner"]), 3)


def split_volumes(folder):
    """[(label, pages, start pages)] of the volumes whose cuts were finished."""
    found = []
    for v, ocr in volumes(folder):
        seg = ocr.parent.parent / f"{v['stem']}.segments.json"
        doc = json.loads(seg.read_text(encoding="utf-8")) if seg.is_file() else {}
        if doc.get("segments") and doc.get("finished", True):
            found.append((v["label"], boundaries.page_blocks(ocr), {s["start_page"] for s in doc["segments"]}))
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ordner", help="Scan-Ordner (Standard: LEAFLET_PDF_HOST_DIR aus .env)")
    args = ap.parse_args(argv)
    found = split_volumes(scan_dir(args.ordner))
    if not found:
        raise SystemExit("Im Scan-Ordner liegt kein fertig getrennter Band.")
    print(f"{len(found)} Bände: {', '.join(label for label, _, _ in found)}")
    weights, prior = calibrate([(pages, starts) for _, pages, starts in found])
    changed = {f: (boundaries.WEIGHTS[f], w) for f, w in weights.items() if w != boundaries.WEIGHTS[f]}
    for f, (old, new) in changed.items():
        print(f"  {f:<14}{old:>8} -> {new}")
    if not changed and prior == boundaries.PRIOR:
        print("Die Gewichte in boundaries.py sind schon die gelernten.")
        return
    if prior != boundaries.PRIOR:
        print(f"  {'PRIOR':<14}{boundaries.PRIOR:>8} -> {prior}")
    print("\nIn src/backend/app/boundaries.py einsetzen:\n")
    print("WEIGHTS = {" + ", ".join(f'"{f}": {w}' for f, w in weights.items()) + "}")
    print(f"PRIOR = {prior}")


if __name__ == "__main__":
    main()
