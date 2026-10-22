"""N-Gramme, Trends, Kollokationen und Belegstellen auf den OCR-Texten der Flugblattsammlung.

    python scripts/ngrams.py size
    python scripts/ngrams.py top -n 3 [--raw]
    python scripts/ngrams.py trend notstand vietnam "kampf gegen"
    python scripts/ngrams.py keyness [-n 2]
    python scripts/ngrams.py collocates spd --year 1972
    python scripts/ngrams.py kwic Berufsverbot

Liest die Texterkennung aus dem Scan-Ordner (--ordner, sonst LEAFLET_PDF_HOST_DIR aus .env) und das Jahr jedes
Bandes aus data/volumes.json. Der Text wird im Scan-Ordner unter .ngrams/ zwischengespeichert.
Anleitung: docs/handbuch/ngrams.md. Braucht nur die Standardbibliothek.
"""
import argparse
import html
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from scan_folder import scan_dir, volumes

YEARS, OCR, CACHE = {}, {}, Path(".ngrams")  # set by parse_args: stem -> year, stem -> OCR json
VOCAB = None  # words within a line; decides line-end hyphens
DROP_BLOCKS = {"PageHeader", "PageFooter", "PageNumber", "Picture", "Figure"}
STOPWORDS = {line.split("#")[0].strip().lower()
             for line in Path(__file__).with_name("stopwords_de.txt").read_text(encoding="utf-8").splitlines()} - {""}
WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")  # inner hyphens stay, a trailing one does not
HYPHEN_BREAK = re.compile(r"([^\W\d_]+)-\n([^\W\d_]+)")
ELLIPSIS_NEXT = {"und", "oder", "bzw", "beziehungsweise", "sowie", "resp"}  # "Sprach-\nund" keeps its hyphen


def load_text(stem, keep_headers=False):
    """The volume's text, pages separated by \\f; without headers, footers and pictures unless keep_headers."""
    cached = CACHE / f"{stem}{'.full' if keep_headers else ''}.txt"
    if not cached.is_file() or cached.stat().st_mtime < OCR[stem].stat().st_mtime:
        pages = []
        for page in json.loads(OCR[stem].read_text(encoding="utf-8"))["children"]:
            text = "\n".join(html.unescape(re.sub(r"<[^>]+>", "\n", b.get("html", "")))
                             for b in page.get("children", []) if keep_headers or b.get("block_type") not in DROP_BLOCKS)
            pages.append("\n".join(line.strip() for line in text.split("\n") if line.strip()))
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text("\n\f\n".join(pages), encoding="utf-8")
    return cached.read_text(encoding="utf-8")


def inline_vocab(stems):
    """Words standing within a line, so a hyphen at a line end is decided by the other places of the word."""
    return Counter(w.lower() for stem in stems for line in load_text(stem).split("\n") for w in WORD.findall(line))


def hyphen_decision(a, b, vocab):
    """'join' (Hilfskammer-|mensch), 'hyphen' (AStA-|Fraktion) or 'ellipsis' (Sprach-|und): the corpus first, then
    the form; capitals on both sides speak for a compound unless the text is all caps."""
    if b.lower() in ELLIPSIS_NEXT:
        return "ellipsis"
    if vocab is not None:
        joined, hyphened = vocab[(a + b).lower()], vocab[f"{a}-{b}".lower()]
        if joined or hyphened:
            return "join" if joined >= hyphened else "hyphen"
    return "hyphen" if a[:1].isupper() and b[:1].isupper() and not (a.isupper() and b.isupper()) else "join"


def dehyphenate(text, vocab=None):
    def repl(m):
        a, b = m.groups()
        return {"join": a + b, "hyphen": f"{a}-{b}", "ellipsis": f"{a}- {b}"}[hyphen_decision(a, b, vocab)]
    return HYPHEN_BREAK.sub(repl, text)


def tokenize(text, dehyph=True):
    text = unicodedata.normalize("NFC", dehyphenate(text, VOCAB) if dehyph else text)
    return [t.lower() for t in WORD.findall(text) if len(t) >= 3]


def collapse_runs(tokens, k=3):
    """Mastheads ('LSD - LSD - LSD'): a run of the same token is cut after k - 1."""
    return [w for i, w in enumerate(tokens) if i < k - 1 or len(set(tokens[i - k + 1:i + 1])) > 1]


def prepare(stem, raw=False):
    tokens = tokenize(load_text(stem, keep_headers=raw), dehyph=not raw)
    return tokens if raw else collapse_runs(tokens)


def ngram_counts(tokens, n, min_content=1):
    """N-grams with at least min_content words that are not stopwords."""
    return Counter(" ".join(g) for g in zip(*[tokens[i:] for i in range(n)])
                   if sum(w not in STOPWORDS for w in g) >= min_content)


def log_likelihood(a, b, size_a, size_b):
    """Dunning's G2, positive when the word is more frequent in a."""
    e1, e2 = size_a * (a + b) / (size_a + size_b), size_b * (a + b) / (size_a + size_b)
    g2 = (a * math.log(a / e1) if a else 0) + (b * math.log(b / e2) if b else 0)
    return 2 * g2 * (1 if a / size_a > b / size_b else -1)


def by_year(stems):
    buckets = defaultdict(list)
    for stem in stems:
        buckets[YEARS[stem]] += prepare(stem)
    return dict(sorted(buckets.items()))


def cmd_size(args):
    print(f"{'Jahr':<6}{'Seiten':>8}{'Token':>10}  Bände")
    for year in sorted({YEARS[s] for s in args.stems}):
        stems = [s for s in args.stems if YEARS[s] == year]
        print(f"{year:<6}{sum(load_text(s).count(chr(12)) + 1 for s in stems):>8}"
              f"{sum(len(prepare(s)) for s in stems):>10}  {', '.join(stems)}")


def cmd_top(args):
    tokens = [t for stem in args.stems for t in prepare(stem, args.raw)]
    counts = ngram_counts(tokens, args.n, 2 if args.n >= 3 else 1)
    print(f"{args.n}-Gramme ({'roh' if args.raw else 'bereinigt'}, {len(tokens)} Token):")
    for gram, n in counts.most_common(args.top):
        print(f"  {n:>6}  {gram}")


def cmd_trend(args):
    buckets = by_year(args.stems)
    counts = {y: {n: ngram_counts(t, n, 0 if n == 1 else 1) for n in {len(x.split()) for x in args.terms}}
              for y, t in buckets.items()}
    print("pro 10.000 Token" + " " * 10 + "".join(f"{y:>8}" for y in buckets))
    for term in args.terms:
        n = len(term.split())
        print(f"  {term:<24}" + "".join(f"{1e4 * counts[y][n][term.lower()] / len(t):>8.1f}" for y, t in buckets.items()))
    print(f"  {'Token je Jahr':<24}" + "".join(f"{len(t):>8}" for t in buckets.values()))


def cmd_keyness(args):
    buckets = by_year(args.stems)
    counts = {y: ngram_counts(t, args.n) for y, t in buckets.items()}
    total, size = sum(counts.values(), Counter()), sum(len(t) for t in buckets.values())
    for year, tokens in buckets.items():
        scored = sorted(((log_likelihood(a, total[g] - a, len(tokens), size - len(tokens)), g, a)
                         for g, a in counts[year].items() if a >= args.min_count), reverse=True)
        print(f"{year}: " + ", ".join(f"{g} ({a})" for _, g, a in scored[:args.top]))


def cmd_collocates(args):
    term = args.term.lower().split()
    years = {int(y) for y in args.year.split(",")} if args.year else set(YEARS.values())
    pages = [collapse_runs(tokenize(page)) for s in args.stems if YEARS[s] in years for page in load_text(s).split("\f")]
    corpus, near, per_page = Counter(t for p in pages for t in p), Counter(), []
    for tokens in pages:
        hits = [i for i in range(len(tokens) - len(term) + 1) if tokens[i:i + len(term)] == term]
        per_page.append(len(hits))
        for i in hits:
            near.update(tokens[max(0, i - args.window):i] + tokens[i + len(term):i + len(term) + args.window])
    hits = sum(per_page)
    if not hits:
        sys.exit(f"„{args.term}“ kommt nicht vor.")
    top10 = sum(sorted(per_page, reverse=True)[:10]) / hits
    print(f"„{args.term}“: {hits} Treffer auf {sum(map(bool, per_page))} von {len(pages)} Seiten; die 10 stärksten Seiten "
          f"stellen {100 * top10:.0f} %{' (Vorsicht: stark gebündelt)' if top10 > 0.5 else ''}")
    scored = sorted(((14 + math.log2(2 * a / (hits + corpus[w])), w, a) for w, a in near.items()
                     if a >= args.min_count and w not in STOPWORDS and w not in term), reverse=True)
    print(f"  {'Kollokat':<28}{'gem.':>6}{'gesamt':>8}{'logDice':>9}")
    for score, w, a in scored[:args.top]:
        print(f"  {w:<28}{a:>6}{corpus[w]:>8}{score:>9.1f}")


def cmd_kwic(args):
    for stem in args.stems:
        found = 0
        for number, page in enumerate(load_text(stem).split("\f"), 1):
            flat = re.sub(r"\s+", " ", dehyphenate(page))
            for m in list(re.finditer(re.escape(args.term), flat, re.IGNORECASE))[:args.limit - found]:
                found += 1
                print(f"[{YEARS[stem]} {stem} S. {number}] …{flat[max(0, m.start() - 45):m.start()]}"
                      f"[{m.group()}]{flat[m.end():m.end() + 45]}…")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ordner", help="Scan-Ordner (Standard: LEAFLET_PDF_HOST_DIR aus .env)")
    p.add_argument("--bands", default="", help="nur diese Bände, z. B. 0118_0002,0118_0009")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("size", help="Seiten und Token je Jahr").set_defaults(func=cmd_size)
    s = sub.add_parser("top", help="häufigste N-Gramme")
    s.add_argument("-n", type=int, default=2)
    s.add_argument("--top", type=int, default=20)
    s.add_argument("--raw", action="store_true", help="ohne Bereinigung, zum Vergleich")
    s.set_defaults(func=cmd_top)
    s = sub.add_parser("trend", help="Häufigkeit je Jahr, pro 10.000 Token")
    s.add_argument("terms", nargs="+", help="Wörter, Mehrwortausdrücke in Anführungszeichen")
    s.set_defaults(func=cmd_trend)
    s = sub.add_parser("keyness", help="was für ein Jahr typisch ist (G2 gegen die übrigen Jahre)")
    s.add_argument("-n", type=int, default=1)
    s.add_argument("--min-count", type=int, default=25)
    s.add_argument("--top", type=int, default=10)
    s.set_defaults(func=cmd_keyness)
    s = sub.add_parser("collocates", help="Wörter in der Nähe eines Ausdrucks (logDice)")
    s.add_argument("term")
    s.add_argument("--year", help="nur diese Jahre, z. B. 1972 oder 1971,1972")
    s.add_argument("-w", "--window", type=int, default=5)
    s.add_argument("--min-count", type=int, default=4)
    s.add_argument("--top", type=int, default=20)
    s.set_defaults(func=cmd_collocates)
    s = sub.add_parser("kwic", help="Belegstellen")
    s.add_argument("term")
    s.add_argument("--limit", type=int, default=10, help="Belege je Band")
    s.set_defaults(func=cmd_kwic)
    args = p.parse_args(argv)

    global CACHE, VOCAB
    folder = scan_dir(args.ordner)
    CACHE = folder / ".ngrams"
    for v, ocr in volumes(folder):
        YEARS[v["stem"]], OCR[v["stem"]] = v["year"], ocr
    args.stems = [b.strip() for b in args.bands.split(",") if b.strip()] or list(YEARS)
    if not YEARS or set(args.stems) - set(YEARS):
        sys.exit(f"Keine Texterkennung in {folder} für: {', '.join(sorted(set(args.stems) - set(YEARS))) or 'alle Bände'}")
    VOCAB = inline_vocab(args.stems)
    return args


if __name__ == "__main__":
    a = parse_args()
    a.func(a)
