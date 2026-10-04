"""Full-text search over leaflets with SQLite FTS5 (trigram tokenizer).

The index holds one row per leaflet (rowid = leaflet id). Triggers keep it in
step with `leaflets`, `pages` and `leaflet_issuers`, so imports and manual
corrections update it inside their own transaction. `rebuild_search_index()`
indexes an existing database from scratch:

    python -m backend.app.database.search      (from the src folder)
"""
import html
import re
import unicodedata

from markupsafe import Markup
from sqlalchemy import Float, Integer, String, text

FTS = "leaflets_fts"
COLUMNS = ("title", "series", "publisher", "ocr_text")
OCR_COLUMN = COLUMNS.index("ocr_text") + 1  # leaflet_id is column 0
# bm25 weights per column (leaflet_id is unindexed): title and series count more
BM25_WEIGHTS = "0, 10.0, 8.0, 4.0, 1.0"
MIN_TOKEN = 3  # a trigram needs three characters
MAX_TOKENS = 8
MAX_QUERY = 200
# `remove_diacritics` for the trigram tokenizer needs SQLite >= 3.45
TOKENIZERS = ("trigram remove_diacritics 1", "trigram")
# control characters cannot occur in OCR text, so the markers cannot be forged
MARK_OPEN, MARK_CLOSE = "\x02", "\x03"
SNIPPET_TOKENS = 64  # FTS5 maximum; a trigram token is only ~1 character wide
FALLBACK_CHARS = 240


def _insert(where):
    """SQL indexing the leaflets matching `where`."""
    return f"""INSERT INTO {FTS}(rowid, leaflet_id, {', '.join(COLUMNS)})
    SELECT l.id, l.id, coalesce(l.title, ''),
           trim(coalesce(l.series, '') || ' ' || coalesce(l.issue, '')),
           coalesce((SELECT group_concat(trim(coalesce(o.name, '') || ' ' ||
                                              coalesce(o.full_name, '') || ' ' ||
                                              coalesce(i.surface, '')), ' ; ')
                     FROM leaflet_issuers i LEFT JOIN organizations o ON o.id = i.org_id
                     WHERE i.leaflet_id = l.id AND i.role = 'issuer'), ''),
           coalesce((SELECT group_concat(text, char(10))
                     FROM (SELECT text FROM pages WHERE leaflet_id = l.id
                           ORDER BY page_no)), '')
    FROM leaflets l {where}"""


def _reindex(key):
    """SQL replacing the index row of leaflet `key` (an expression like new.id)."""
    return f"DELETE FROM {FTS} WHERE rowid = {key}; {_insert('WHERE l.id = ' + key)};"


def _triggers():
    def trigger(name, event, table, body, when=""):
        return (f"CREATE TRIGGER IF NOT EXISTS {FTS}_{name} AFTER {event} ON {table} "
                f"{when} BEGIN {body} END")

    def pages_of(ref):
        return f"WHEN {ref}.leaflet_id IS NOT NULL"

    yield trigger("l_ai", "INSERT", "leaflets", _reindex("new.id"))
    yield trigger("l_au", "UPDATE OF title, series, issue", "leaflets", _reindex("new.id"))
    yield trigger("l_ad", "DELETE", "leaflets", f"DELETE FROM {FTS} WHERE rowid = old.id;")
    for short, table, columns in (("p", "pages", "text, leaflet_id"),
                                  ("i", "leaflet_issuers", "surface, org_id, role, leaflet_id")):
        yield trigger(f"{short}_ai", "INSERT", table, _reindex("new.leaflet_id"),
                      pages_of("new"))
        yield trigger(f"{short}_au_old", f"UPDATE OF {columns}", table,
                      _reindex("old.leaflet_id"), pages_of("old"))
        yield trigger(f"{short}_au_new", f"UPDATE OF {columns}", table,
                      _reindex("new.leaflet_id"), pages_of("new"))
        yield trigger(f"{short}_ad", "DELETE", table, _reindex("old.leaflet_id"),
                      pages_of("old"))


def ensure_search_index(engine):
    """Creates the FTS5 table and the sync triggers if missing; True if the table is new."""
    with engine.begin() as conn:
        exists = conn.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE name = ?", (FTS,)).first()
        if not exists:
            for i, tokenizer in enumerate(TOKENIZERS):
                try:
                    conn.exec_driver_sql(
                        f"CREATE VIRTUAL TABLE {FTS} USING fts5(leaflet_id UNINDEXED, "
                        f"{', '.join(COLUMNS)}, tokenize='{tokenizer}')")
                    break
                except Exception:
                    if i == len(TOKENIZERS) - 1:
                        raise
        for statement in _triggers():
            conn.exec_driver_sql(statement)
    return not exists


def rebuild_search_index(engine):
    """Reindexes all leaflets in one transaction; returns the number of indexed leaflets."""
    ensure_search_index(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(f"DELETE FROM {FTS}")
        conn.exec_driver_sql(_insert(""))
        return conn.exec_driver_sql(f"SELECT count(*) FROM {FTS}").scalar()


def index_is_stale(engine):
    """True if leaflets exist that are not indexed (e.g. a database from before the search)."""
    with engine.connect() as conn:
        return conn.exec_driver_sql(
            f"SELECT (SELECT count(*) FROM leaflets) != (SELECT count(*) FROM {FTS})").scalar()


OPERATORS = {"AND", "OR", "NOT", "NEAR"}


def tokens(query):
    """Searchable words of user input: letters/digits only, at least MIN_TOKEN long.

    Operator words are dropped, so typing "streik NOT" or "OR" never changes the query logic.
    """
    words = re.findall(r"\w+", unicodedata.normalize("NFKC", query[:MAX_QUERY]))
    unique = dict.fromkeys(w for w in words
                           if len(w) >= MIN_TOKEN and w.upper() not in OPERATORS)
    return list(unique)[:MAX_TOKENS]


def match_expression(query):
    """FTS5 MATCH string for user input, or None if no word is long enough.

    Every word becomes a quoted string, so quotes, `*`, parentheses, `-`, `:` and
    the operators AND/OR/NOT/NEAR lose their FTS5 meaning; words are combined by AND.
    """
    return " ".join(f'"{w}"' for w in tokens(query)) or None


def like_pattern(query):
    """Substring pattern for queries too short for trigrams (title and series only)."""
    cleaned = query.strip()[:MAX_QUERY]
    escaped = cleaned.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def hits_subquery(match):
    """Subquery (leaflet_id, rank, snippet) of FTS hits, ready to be joined to leaflets.

    bm25 is lower for better hits; snippet() shows the OCR text around the match.
    """
    statement = text(
        f"SELECT CAST(leaflet_id AS INTEGER) AS leaflet_id, "
        f"bm25({FTS}, {BM25_WEIGHTS}) AS rank, "
        f"snippet({FTS}, {OCR_COLUMN}, :open, :close, ' … ', {SNIPPET_TOKENS}) AS snippet "
        f"FROM {FTS} WHERE {FTS} MATCH :match"
    ).bindparams(match=match, open=MARK_OPEN, close=MARK_CLOSE).columns(
        leaflet_id=Integer, rank=Float, snippet=String)
    return statement.subquery("hits")


def render_snippet(raw):
    """snippet() output -> safe HTML: the text is escaped, only our markers become <mark>."""
    parts = re.split(f"({MARK_OPEN}|{MARK_CLOSE})", " ".join((raw or "").split()))
    out = "".join("<mark>" if p == MARK_OPEN else "</mark>" if p == MARK_CLOSE
                  else html.escape(p) for p in parts)
    return Markup(out)


def has_match(raw):
    return MARK_OPEN in (raw or "")


def fallback_snippet(ocr_text):
    """Beginning of the OCR text, for hits that lie only in title, series or issuer."""
    flat = " ".join((ocr_text or "").split())
    if not flat:
        return Markup("")
    cut = flat[:FALLBACK_CHARS].rsplit(" ", 1)[0] if len(flat) > FALLBACK_CHARS else flat
    return Markup(html.escape(cut) + (" …" if len(flat) > FALLBACK_CHARS else ""))


if __name__ == "__main__":
    from .session import engine
    print(f"{rebuild_search_index(engine)} leaflets indexed")
