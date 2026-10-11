"""Full-text search over leaflets with SQLite FTS5 (trigram tokenizer).

The index holds one row per leaflet (rowid = leaflet id). The import builds it
once at the end (pages never change afterwards); triggers on `leaflets` and
`leaflet_issuers` keep it in step with manual corrections. `rebuild_search_index()`
indexes an existing database from scratch:

    python -m backend.app.database.search      (from the src folder)
"""
import re
import textwrap
import unicodedata

from markupsafe import Markup
from sqlalchemy import Float, Integer, bindparam, text

FTS = "leaflets_fts"
COLUMNS = ("title", "series", "publisher", "signatories", "ocr_text")
# bm25 weights per column (leaflet_id is unindexed): title and series count more
BM25_WEIGHTS = "0, 10.0, 8.0, 4.0, 4.0, 1.0"
# the fields a search can be limited to (parameter `feld`) -> index columns
FIELDS = {"titel": ("title",), "herausgeber": ("publisher",), "unterzeichner": ("signatories",),
          "reihe": ("series",), "text": ("ocr_text",)}
MIN_TOKEN = 3  # a trigram needs three characters
MAX_TOKENS = 8
MAX_QUERY = 200
FALLBACK_CHARS = 240


def _insert(where):
    """SQL indexing the leaflets matching `where`; line-end hyphenation ("Hochschul- gesetz") is joined."""
    return f"""INSERT INTO {FTS}(rowid, leaflet_id, {', '.join(COLUMNS)})
    SELECT l.id, l.id, coalesce(l.title, ''),
           trim(coalesce(l.series, '') || ' ' || coalesce(l.issue, '')),
           coalesce((SELECT group_concat(trim(coalesce(o.name, '') || ' ' ||
                                              coalesce(o.full_name, '') || ' ' ||
                                              coalesce(i.surface, '')), ' ; ')
                     FROM leaflet_issuers i LEFT JOIN organizations o ON o.id = i.org_id
                     WHERE i.leaflet_id = l.id AND i.role = 'issuer'), ''),
           coalesce((SELECT group_concat(i.surface, ' ; ') FROM leaflet_issuers i
                     WHERE i.leaflet_id = l.id AND i.role = 'signatory'), ''),
           coalesce((SELECT replace(group_concat(text, char(10)), '- ', '')
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
    columns = "surface, org_id, role, leaflet_id"
    yield trigger("i_ai", "INSERT", "leaflet_issuers", _reindex("new.leaflet_id"), pages_of("new"))
    yield trigger("i_au_old", f"UPDATE OF {columns}", "leaflet_issuers",
                  _reindex("old.leaflet_id"), pages_of("old"))
    yield trigger("i_au_new", f"UPDATE OF {columns}", "leaflet_issuers",
                  _reindex("new.leaflet_id"), pages_of("new"))
    yield trigger("i_ad", "DELETE", "leaflet_issuers", _reindex("old.leaflet_id"), pages_of("old"))


def ensure_search_index(engine):
    """Creates the FTS5 table and the sync triggers if missing."""
    with engine.begin() as conn:
        # an index without the newest column is dropped with its triggers and built again
        old = [r[1] for r in conn.exec_driver_sql(f"PRAGMA table_info({FTS})")]
        stale = bool(old) and old != ["leaflet_id", *COLUMNS]
        if stale:
            for (name,) in conn.exec_driver_sql(
                    f"SELECT name FROM sqlite_master WHERE type = 'trigger' AND name LIKE '{FTS}\\_%' ESCAPE '\\'").all():
                conn.exec_driver_sql(f"DROP TRIGGER {name}")
            conn.exec_driver_sql(f"DROP TABLE {FTS}")
        # remove_diacritics for trigrams needs SQLite >= 3.45 (the container has 3.46)
        conn.exec_driver_sql(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {FTS} USING fts5(leaflet_id UNINDEXED, "
            f"{', '.join(COLUMNS)}, tokenize='trigram remove_diacritics 1')")
        for statement in _triggers():
            conn.exec_driver_sql(statement)
        if stale:
            conn.exec_driver_sql(_insert(""))


def rebuild_search_index(engine):
    """Reindexes all leaflets in one transaction; returns the number of indexed leaflets."""
    ensure_search_index(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(f"DELETE FROM {FTS}")
        conn.exec_driver_sql(_insert(""))
        return conn.exec_driver_sql(f"SELECT count(*) FROM {FTS}").scalar()


OPERATORS = {"AND", "OR", "NOT", "NEAR"}


def terms(query):
    """Search terms of user input: phrases in double quotes and single words, at least MIN_TOKEN long.

    Outside quotes only letters/digits count and operator words are dropped, so typing
    "streik NOT" or "OR" never changes the query logic.
    """
    query = unicodedata.normalize("NFKC", query[:MAX_QUERY])
    phrases = [" ".join(p.split()) for p in re.findall(r'"([^"]*)"', query)]
    words = [w for w in re.findall(r"\w+", re.sub(r'"[^"]*"', " ", query))
             if w.upper() not in OPERATORS]
    unique = dict.fromkeys(t for t in phrases + words if len(t) >= MIN_TOKEN)
    return list(unique)[:MAX_TOKENS]


def variants(term):
    """Spellings searched for a term: "daß" also finds "dass" and the other way round."""
    low = term.lower()
    return list(dict.fromkeys([low, low.replace("ß", "ss"), low.replace("ss", "ß")]))


def match_expression(query, columns=None):
    """FTS5 MATCH string for user input, or None if no term is long enough.

    Every term becomes a quoted string, so `*`, parentheses, `-`, `:` and the operators
    AND/OR/NOT/NEAR lose their FTS5 meaning; terms are combined by AND (explicit, as FTS5
    does not join parenthesised groups implicitly).
    """
    parts = []
    for term in terms(query):
        quoted = [f'"{v}"' for v in variants(term)]
        parts.append(f"({' OR '.join(quoted)})")
    expression = " AND ".join(parts) or None
    return f"{{{' '.join(columns)}}} : ({expression})" if expression and columns else expression


def combine(rows):
    """MATCH string for rows of (operator, expression): AND, OR or NOT, applied from top to bottom;
    rows without an expression (no word of three characters) are left out."""
    result = None
    for operator, expression in rows:
        if expression:
            result = f"({expression})" if result is None else f"({result} {operator} ({expression}))"
    return result


def like_pattern(query):
    """Substring pattern for queries too short for trigrams (title and series only)."""
    cleaned = query.strip()[:MAX_QUERY]
    escaped = cleaned.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def hits_subquery(match):
    """Subquery (leaflet_id, rank) of FTS hits, ready to be joined to leaflets; bm25 is lower for better hits."""
    statement = text(
        f"SELECT CAST(leaflet_id AS INTEGER) AS leaflet_id, bm25({FTS}, {BM25_WEIGHTS}) AS rank "
        f"FROM {FTS} WHERE {FTS} MATCH :match"
    ).bindparams(match=match).columns(leaflet_id=Integer, rank=Float)
    return statement.subquery("hits")


def ocr_texts(session, leaflet_ids):
    """{leaflet id: OCR text as indexed, hyphenation joined}; faster than reading `pages`."""
    statement = text(f"SELECT rowid, ocr_text FROM {FTS} WHERE rowid IN :ids").bindparams(
        bindparam("ids", expanding=True))
    return dict(session.execute(statement, {"ids": list(leaflet_ids)}).all()) if leaflet_ids else {}


# a word repeated three times or more ("LSD LSD LSD"), shortened in passages
RUNS = re.compile(r"\b(\w+)(?:\W+\1\b){2,}", re.I)


def kwic(text, query, width=60):
    """(left, hit, right) for each occurrence of the search terms in `text`, with up to
    `width` characters of context in whole words; hyphenation is joined as in the index."""
    words = sorted({v for t in terms(query) for v in variants(t)}, key=len, reverse=True)
    if not words:
        return []
    pattern = re.compile("|".join(re.escape(w).replace(r"\ ", r"\s+") for w in words), re.I)
    flat = " ".join((text or "").split()).replace("- ", "")
    found = []
    for m in pattern.finditer(flat):
        left, right = flat[max(0, m.start() - width):m.start()], flat[m.end():m.end() + width]
        if m.start() > width:
            left = left.split(" ", 1)[-1]
        if m.end() + width < len(flat):
            right = right.rsplit(" ", 1)[0]
        found.append((RUNS.sub(r"\1 …", left), m.group(), RUNS.sub(r"\1 …", right)))
    return found


def passage_html(left, hit, right):
    """One kwic passage as safe HTML with the hit marked."""
    return Markup("… {}<mark>{}</mark>{} …").format(left, hit, right)


def fallback_snippet(ocr_text):
    """Beginning of the OCR text, for hits that lie only in title, series or issuer."""
    return Markup.escape(textwrap.shorten(ocr_text or "", FALLBACK_CHARS, placeholder=" …"))


if __name__ == "__main__":
    from .session import engine
    print(f"{rebuild_search_index(engine)} leaflets indexed")
