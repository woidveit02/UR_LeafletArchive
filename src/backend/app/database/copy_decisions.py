"""Reviewed copy groups (data/copy_decisions.jsonl). One line holds the full
state of one reviewed group. Anchors carry the exact page range, so a review
whose segments changed is not applied but listed for a new review."""
import json
import threading
from datetime import datetime, timezone

_lock = threading.Lock()


def anchor(a):
    return a["volume"], a["start_page"], a["end_page"]


def follow(lines, known):
    """The reviews with each page range that is gone moved to the one leaflet lying there now, as when its last page
    was marked blank later. With two leaflets there (a new cut) or none, the range stays and the review unresolved."""
    ranges = {}
    for volume, start, end in known:
        ranges.setdefault(volume, []).append((start, end))

    def moved(a):
        if anchor(a) in known:
            return a
        here = [(s, e) for s, e in ranges.get(a["volume"], []) if s <= a["end_page"] and e >= a["start_page"]]
        return {**a, "start_page": here[0][0], "end_page": here[0][1]} if len(here) == 1 else a
    return [{**r, "members": [moved(a) for a in r["members"]], "rejected": [moved(a) for a in r["rejected"]],
             "canonical": moved(r["canonical"])} if "members" in r else r for r in lines]


def append(path, line):
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({**line, "at": stamp}, ensure_ascii=False) + "\n")


def resolve(auto, lines, known):
    """auto: anchor -> (tsv group, tsv canonical); known: anchors of imported segments.
    Returns (groups, unresolved reviews). A group has members, canonical, checked
    and candidates: automatic hits that the review has not seen yet."""
    lines = sorted(lines, key=lambda e: e["at"])  # line order is random after a merge
    reverted = {e["revert"] for e in lines if "revert" in e}
    reviews, unresolved = [], []
    for r in lines:
        if "revert" in r or r["at"] in reverted:
            continue
        seen = {anchor(a) for a in r["members"] + r["rejected"]}
        (reviews if seen <= known else unresolved).append(r)

    latest = {}  # anchor -> its newest review
    for r in reviews:
        for a in r["members"] + r["rejected"]:
            latest[anchor(a)] = r
    confirmed = {a for a, r in latest.items() if a in map(anchor, r["members"])}

    # confirmed members of any review end up together, even across reviews
    parent = {a: a for a in confirmed}

    def root(a):
        while parent[a] != a:
            a = parent[a]
        return a

    canonical = {}
    for r in reviews:
        kept = [a for a in map(anchor, r["members"]) if a in confirmed]
        for a in kept[1:]:
            parent[root(a)] = root(kept[0])
    for r in reviews:
        if anchor(r["canonical"]) in confirmed:
            canonical[root(anchor(r["canonical"]))] = anchor(r["canonical"])

    checked = {}
    for a in confirmed:
        checked.setdefault(root(a), set()).add(a)
    candidates = {g: set() for g in checked}

    tsv = {}
    for a, (g, _) in auto.items():
        if a in known:
            tsv.setdefault(g, set()).add(a)
    groups = []
    for members in tsv.values():
        rest = members - confirmed
        for t in members & confirmed:
            seen = {anchor(a) for a in latest[t]["members"] + latest[t]["rejected"]}
            candidates[root(t)] |= rest - seen
        if len(rest) > 1:
            proposed = [a for a in rest if auto[a][1]]
            groups.append({"members": sorted(rest), "canonical": min(proposed or rest),
                           "checked": False, "candidates": []})

    for g, members in checked.items():
        if len(members) + len(candidates[g]) > 1:
            groups.append({"members": sorted(members),
                           "canonical": canonical.get(g, min(members)),
                           "checked": True, "candidates": sorted(candidates[g])})
    return groups, unresolved
