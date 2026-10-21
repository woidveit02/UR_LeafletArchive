"""Title, date and issuers of each leaflet of a volume, extracted by a language model over OpenRouter.
Every value carries a quote and the ids of the OCR blocks it stands in, which the checks below hold against the text."""
import difflib
import hashlib
import json
import logging
import random
import re
import threading
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import requests

from . import copy_search, importer, keys, ocr, segments
from .database import corrections, fillDatabase
from .boundaries import RESPONSIBLE_LINE, STAMP_INLINE, is_stamp_block, page_blocks

logger = logging.getLogger(__name__)
JOB = "angaben"
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"  # the model of the volumes 1 to 14
MODELS_URL = "https://openrouter.ai/api/v1/models"
MODEL_ID = re.compile(r"^[\w.-]+/[\w.:-]+$")
OUT_TOKENS = 650  # answer tokens per leaflet and characters per prompt token, measured with Claude Opus 5.5 on volume 15
CHARS_PER_TOKEN = 2.0  # (152,668 prompt and 37,311 answer tokens for 56 leaflets); other models count differently

PROMPT_FILE = Path(__file__).with_name("metadata_prompt.txt")
API_URL = "https://openrouter.ai/api/v1/chat/completions"
BATCH_SIZE = 20
MAX_BATCH = 50
MAX_RETRIES = 5
FORMATS = ["schema_strict", "schema", "json_object"]  # not every model takes a strict schema; then the next one
ROUTING_ERROR = re.compile(r"No endpoints found|failed_routing_step|response_format", re.I)
PICTURE_LABEL = "Abbildung, maschinell beschrieben - nicht Text des Blatts"
STAMP_LABEL = "Archivvermerk - kein Datum des Blatts"
EMPTY = {"title_evidence": "", "title_blocks": [], "title": "", "title_type": "", "issuers": [], "date_evidence": "",
         "date_blocks": [], "date_text": "", "date_iso": "", "date_type": "undated", "doc_type": "unklar",
         "confidence": 0.0}

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {  # in the order of generation: evidence first, then the value
                    "id": {"type": "integer"},
                    "title_evidence": {"type": "string"},
                    "title_blocks": {"type": "array", "items": {"type": "string"}},
                    "title": {"type": "string"},
                    "title_type": {"type": "string", "enum": ["original", "incipit", ""]},
                    "series": {"type": "string"},
                    "issue": {"type": "string"},
                    "issuers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "evidence": {"type": "string"},
                                "blocks": {"type": "array", "items": {"type": "string"}},
                                "surface": {"type": "string"},
                                "role": {"type": "string", "enum": ["issuer", "signatory"]},
                                "function": {"type": "string"},
                                "marker": {"type": "string"},
                            },
                            "required": ["evidence", "blocks", "surface", "role", "function", "marker"],
                        },
                    },
                    "date_evidence": {"type": "string"},
                    "date_blocks": {"type": "array", "items": {"type": "string"}},
                    "date_text": {"type": "string"},
                    "date_iso": {"type": "string"},
                    "date_type": {"type": "string", "enum": ["issued", "event", "undated"]},
                    "doc_type": {"type": "string", "enum": ["flugblatt", "offener_brief", "einladung", "broschuere",
                                                            "zeitschrift", "protokoll", "unklar"]},
                    "confidence": {"type": "number"},
                },
                "required": ["id", "title_evidence", "title_blocks", "title", "title_type", "series", "issue", "issuers",
                             "date_evidence", "date_blocks", "date_text", "date_iso", "date_type", "doc_type",
                             "confidence"],
            },
        },
    },
    "required": ["results"],
}


# ---------- the text ----------

def blocks(pages, first, last):
    """(page, block id, type, text) of the blocks with text on the pages first to last."""
    return [(p, f"{p}-{i}", kind, text) for p in range(first, last + 1)
            for i, (kind, text) in enumerate(pages[p - 1] if p <= len(pages) else [], start=1) if text]


def segment_texts(pages, first, last):
    """pages: boundaries.page_blocks. -> (text for the model with block ids, text for the checks without ids, stamps
    and pictures, {block id: text})."""
    marked, plain, texts = {}, {}, {}
    for p, block_id, kind, text in blocks(pages, first, last):
        if is_stamp_block(kind, text):
            line = f"[{block_id}] [{STAMP_LABEL}: {' '.join(text.split())}]"
        elif kind == "Picture":
            line = f"[{block_id}] [{PICTURE_LABEL}: {' '.join(text.split())}]"
        else:
            text = STAMP_INLINE.sub("[Archivvermerk]", text)
            line = f"[{block_id}] {text}"
            plain.setdefault(p, []).append(text)
            texts[block_id] = text
        marked.setdefault(p, []).append(line)

    def joined(by_page):
        return "\n\n".join(f"--- Seite {p} ---\n" + "\n".join(lines) for p, lines in by_page.items())

    return joined(marked), joined(plain), texts


def custom_prompt_file():
    return fillDatabase.DATA_DIR / "metadata_prompt.txt"


def default_prompt():
    return PROMPT_FILE.read_text(encoding="utf-8").replace("\r\n", "\n")


def prompt_text():
    """The edited instructions if there are any, else the ones shipped."""
    try:
        return custom_prompt_file().read_text(encoding="utf-8").replace("\r\n", "\n") or default_prompt()
    except OSError:
        return default_prompt()


def save_prompt(text):
    """Keeps text as the instructions; the shipped ones (or nothing) delete the edited file."""
    text = text.replace("\r\n", "\n").strip("\n")
    if not text.strip() or text == default_prompt().strip("\n"):
        custom_prompt_file().unlink(missing_ok=True)
    else:
        custom_prompt_file().write_text(text + "\n", encoding="utf-8")


def build_prompt(year, batch, known_orgs=(), hints=None, template=None):
    """batch: [(segment id, first page, last page, text)]; hints: {segment id: remark of the checks}."""
    parts = [(template or default_prompt()).rstrip("\n") + "\n"]
    if known_orgs:
        parts.append("BEKANNTE GRUPPEN\n"
                     "Ist eine dieser Gruppen gemeint, benutze in `surface` genau diese Schreibweise.\n"
                     "Steht im Text eine andere Gruppe, nimm deren Wortlaut - die Liste ist nicht\n"
                     "abschließend.\n" + ", ".join(known_orgs) + "\n")
    parts.append(f"JAHRGANG DES BANDES: {year}\nEin Datum ohne Jahresangabe bezieht sich fast immer auf {year}.\n")
    parts.append("SEGMENTE\n\n" + "\n\n".join(
        f"=== Segment {sid} ({f'Seite {first}' if first == last else f'Seiten {first}-{last}'}) ===\n{text}"
        for sid, first, last, text in batch))
    if hints:
        parts.append("HINWEISE ZU EINZELNEN SEGMENTEN\n"
                     "Eine maschinelle Prüfung hat Folgendes bemerkt. Prüfe es am Text und nimm nur auf, "
                     "was der Text belegt:\n" + "\n".join(f"Segment {sid}: {text}" for sid, text in hints.items()))
    parts.append("Extrahiere jetzt ausschließlich die Segmente aus SEGMENTE oben, nach den "
                 "Regeln und Beispielen weiter oben. Segment-ids aus den BEISPIELEN gehören "
                 f"nicht in die Ausgabe. Erwartete ids in dieser Antwort: {', '.join(str(b[0]) for b in batch)}. "
                 "Genau ein JSON-Objekt pro id, in Eingabereihenfolge.")
    return "\n\n".join(parts)


# ---------- the model ----------

def strict_schema(schema):
    """additionalProperties false and every property required, as the strict mode wants it."""
    if isinstance(schema, dict):
        out = {k: strict_schema(v) for k, v in schema.items()}
        if out.get("type") == "object" and "properties" in out:
            out["additionalProperties"] = False
            out["required"] = list(out["properties"])
        return out
    if isinstance(schema, list):
        return [strict_schema(x) for x in schema]
    return schema


def call(key, model, prompt, state):
    """One request. -> (answer text, usage: tokens and cost in $). state remembers the answer format that worked."""
    start = FORMATS.index(state.get("format", FORMATS[0]))
    for i, form in enumerate(FORMATS[start:], start):
        body = {"model": model, "temperature": 0, "usage": {"include": True},
                "messages": [{"role": "user", "content": prompt}]}
        if form == "json_object":
            body["response_format"] = {"type": "json_object"}
            body["messages"][0]["content"] += ("\n\nANTWORTFORM\nAntworte ausschließlich mit JSON, ohne Vorspann und "
                                               "ohne Markdown-Codezaun, nach genau diesem JSON-Schema:\n"
                                               + json.dumps(SCHEMA, ensure_ascii=False, separators=(",", ":")))
        else:
            strict = form == "schema_strict"
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "flugblatt_metadaten", "strict": strict, "schema": strict_schema(SCHEMA) if strict else SCHEMA}}
            if strict:
                body["provider"] = {"require_parameters": True}
        response = requests.post(API_URL, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=600)
        if not response.ok and ROUTING_ERROR.search(response.text) and i < len(FORMATS) - 1:
            continue
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", data["error"]))
        state["format"] = form
        return data["choices"][0]["message"]["content"] or "", data.get("usage") or {}


class ParseError(ValueError):
    pass


def parse_results(raw):
    """{segment id: record} from an answer; models without a schema sometimes send a bare list or another key."""
    data = json.loads(re.sub(r"^\s*```(?:json)?|```\s*$", "", raw, flags=re.M).strip())
    items = data if isinstance(data, list) else None
    if isinstance(data, dict):
        items = next((data[k] for k in ("results", "segments", "data", "records", "items")
                      if isinstance(data.get(k), list)), [data] if "id" in data else None)
    if items is None:
        raise ParseError("keine Ergebnisliste in der Antwort")
    good = {}
    for item in items:
        try:
            good[int(item["id"])] = item
        except (TypeError, ValueError, KeyError):
            pass
    if not good:
        raise ParseError("keine verwertbaren Einträge in der Antwort")
    return good


def spent(usage):
    """Cost in $ and tokens of the requests so far; reasoning tokens are paid as answer but not part of it."""
    return {"cost": round(sum(u.get("cost") or 0 for u in usage), 4),
            "prompt_tokens": sum(u.get("prompt_tokens") or 0 for u in usage),
            "answer_tokens": sum(u.get("completion_tokens") or 0 for u in usage),
            "reasoning_tokens": sum((u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0 for u in usage)}


def extract(key, model, prompt, state, cost):
    """The records of one prompt, with retries on rate limits and server errors. cost: a list the usage goes into."""
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw, usage = call(key, model, prompt, state)
            cost.append(usage)
            return parse_results(raw)
        except (ParseError, json.JSONDecodeError) as error:  # at temperature 0 a second try mostly says the same
            last = error
            if attempt >= 2:
                break
        except requests.HTTPError as error:
            if error.response is not None and 400 <= error.response.status_code < 500 \
                    and error.response.status_code not in (408, 429):
                raise  # key, credit or model: another try does not help
            last = error
        except (requests.RequestException, RuntimeError) as error:
            last = error
        if attempt < MAX_RETRIES:
            time.sleep(min(60, 2 ** attempt) + random.uniform(0, 1))
    raise RuntimeError(f"Keine brauchbare Antwort nach mehreren Versuchen: {last}")


# ---------- after the answer ----------

def normalize_record(record):
    """A date of type "undated" is one the text only mentions: dropped (kept in _date_dropped). The same person or group
    twice in the same role becomes one entry."""
    if record.get("date_type") == "undated" and record.get("date_text"):
        record["_date_dropped"] = record["date_text"]
        record.update(date_text="", date_iso="", date_evidence="", date_blocks=[])
    merged = {}
    for iss in record.get("issuers") or []:
        if not (iss.get("surface") or "").strip():
            continue
        k = (iss["surface"].strip().lower(), iss.get("role"), (iss.get("function") or "").strip(),
             (iss.get("marker") or "").strip())
        if k in merged:
            blocks = merged[k].setdefault("blocks", [])
            blocks += [b for b in iss.get("blocks") or [] if b not in blocks]
        else:
            merged[k] = dict(iss)
    if record.get("issuers"):
        record["issuers"] = list(merged.values())
    return record


STAMP_DATE_PARTS = re.compile(
    r"(\d{1,2})\s*\.?\s*(JAN|FEB|MRZ|MÄR|MAR|APR|MAI|JUN|JUL|AUG|SEP|OKT|NOV|DEZ)[A-ZÄ]*\.?\s*(19\d\d)", re.I)
MONTH_NO = {"JAN": 1, "FEB": 2, "MRZ": 3, "MÄR": 3, "MAR": 3, "APR": 4, "MAI": 5, "JUN": 6,
            "JUL": 7, "AUG": 8, "SEP": 9, "OKT": 10, "NOV": 11, "DEZ": 12}


def stamp_dates(pages, first, last):
    """[(iso, block id, stamp text)] of the archive's receipt stamps on the pages, read without the model."""
    found = []
    for _, block_id, kind, text in blocks(pages, first, last):
        if is_stamp_block(kind, text):
            candidates = [text]
        elif kind != "Picture":
            candidates = [m.group(0) for m in STAMP_INLINE.finditer(text)]
        else:
            continue
        for cand in candidates:
            m = STAMP_DATE_PARTS.search(cand)
            if not m:
                continue
            try:
                iso = datetime(int(m.group(3)), MONTH_NO[m.group(2).upper()[:3]], int(m.group(1))).date().isoformat()
            except ValueError:
                continue
            found.append((iso, block_id, " ".join(cand.split())))
    return found


def add_received_date(record, stamps, volume_year):
    """The stamp's date as the date of receipt. A year more than one off the volume's is marked uncertain (the OCR misreads
    it). A stamp taken for the leaflet's own date is moved there."""
    if not stamps:
        return record
    volume_year = int(volume_year) if str(volume_year or "").isdigit() else None
    plausible = [s for s in stamps if abs(int(s[0][:4]) - volume_year) <= 1] if volume_year else stamps
    iso, block_id, text = min(plausible or stamps)
    record.update(received_date=iso, received_evidence=text, received_blocks=[block_id],
                  received_year_uncertain=not plausible)
    evidence = record.get("date_evidence") or ""
    from_stamp = bool(set(record.get("date_blocks") or []) & {s[1] for s in stamps}) or (
        evidence and any(evidence in s[2] for s in stamps))
    if record.get("date_iso") and from_stamp:
        record["_date_from_stamp"] = {k: record.get(k) for k in
                                      ("date_evidence", "date_blocks", "date_text", "date_iso", "date_type")}
        record.update(date_evidence="", date_blocks=[], date_text="", date_iso="", date_type="undated")
    return record


def cited_block_ids(record):
    ids = list(record.get("title_blocks") or []) + list(record.get("date_blocks") or [])
    for iss in record.get("issuers") or []:
        ids += iss.get("blocks") or []
    return ids


def foreign_block_ids(record, first, last):
    """Block ids outside the leaflet's pages: copied from a neighbour, or made up."""
    return [b for b in cited_block_ids(record)
            if not (m := re.fullmatch(r"(\d+)-\d+", str(b))) or not first <= int(m.group(1)) <= last]


# ---------- checks against the text ----------

def _norm(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s or "")).strip().lower()


def _squeeze(s):
    return re.sub(r"[^0-9a-zäöüß]+", "", unicodedata.normalize("NFC", s or "").lower())


def match_kind(quote, text, threshold=0.9):
    """"exakt", "unscharf" (close to a window of the same length) or None."""
    q, t = _norm(quote), _norm(text)
    if not q:
        return None
    if q in t:
        return "exakt"
    if len(s := _squeeze(quote)) >= 6 and s in _squeeze(text):  # "L. Zeise" for "L.Zeise": only spaces and punctuation differ
        return "exakt"
    n = len(q)
    if n < 8 or n > len(t):
        return None
    for i in range(0, len(t) - n + 1, max(1, n // 4)):
        if difflib.SequenceMatcher(None, q, t[i:i + n]).ratio() >= threshold:
            return "unscharf"
    return None


def grounded(quote, text, threshold=0.9):
    return not _norm(quote) or match_kind(quote, text, threshold) is not None


PERSON_NAME = re.compile(
    r"^(?:[A-ZÄÖÜ][a-zäöüß]+|[A-ZÄÖÜ]\.)\s+[A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?$"
    r"|^[A-ZÄÖÜ][a-zäöüß]+,\s+[A-ZÄÖÜ][a-zäöüß]+$")
ORG_HINT = re.compile(
    r"(?i)bund|ring|liste|gruppe|komitee|kommittee|ausschu|schaft|verband|partei|union|front|"
    r"zelle|fraktion|initiative|konferenz|referat|\brat\b|gemeinde|jugend|studenten|hochschul|"
    r"universit|fachbereich|fachschaft|aktion|kreis|kollektiv|vereinigung|kommission|senat|"
    r"basis|zentral|e\.\s?v\.|"
    r"demokratisch|liberal|christlich|sozial|marxist|kommunist|sozialistisch|\blinke\b|"
    r"\brote\b|\broter\b|\bmitte\b|unabhängig|studentisch|vertretung|kraft|\bdritte\b|"
    r"arbeit|assistent|katholisch|evangelisch|akademisch")
ADDRESS = re.compile(r"\d|(?i:str\.|straße|strasse|weg\b|platz\b|postfach|gasse|allee)")
NOT_A_NAME = re.compile(r"(?i)vorsitz|referent|sprecher|präsident|sekretär|beauftragt|"
                        r"^(regensburg|rgb|münchen|bonn|nürnberg|erlangen|würzburg|berlin)$")
NAME_PART = re.compile(r"^(?:[A-ZÄÖÜ]\.\s?|[A-ZÄÖÜ][a-zäöüß]+\s)*[A-ZÄÖÜ][a-zäöüß]{2,}$")
SPACED_WORD = re.compile(r"\b(?:[^\W\d_] ){3,}[^\W\d_]\b")


def looks_like_person(name):
    name = (name or "").strip()
    return bool(name) and not ORG_HINT.search(name) and not name.isupper() and bool(PERSON_NAME.match(name))


def unspace(text):
    """"V e r a n t w o r t l i c h" -> "Verantwortlich"."""
    return SPACED_WORD.sub(lambda m: m.group(0).replace(" ", ""), text or "")


def responsible_names(text):
    """People in lines starting with "Verantwortlich", "V.i.S.d.P." or "gez.", up to the first address."""
    names = []
    for m in RESPONSIBLE_LINE.finditer(unspace(text)):
        line = re.split(r"\s[/·]\s|;|\bDruck\b", m.group(1))[0]
        for part in re.split(r",|\bund\b|&", line):
            part = part.strip(" .:-()")
            if not part:
                continue
            if ADDRESS.search(part):
                break
            if NAME_PART.match(part) and not NOT_A_NAME.search(part) and not ORG_HINT.search(part):
                names.append(part)
    return names


def same_name(a, b):
    a, b = (re.sub(r"[^a-zäöüß]", "", (s or "").lower()) for s in (a, b))
    return bool(a and b) and (a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() >= 0.8)


def missing_signatories(record, text):
    return [name for name in responsible_names(text)
            if not any(same_name(name, i.get("surface")) for i in record.get("issuers") or [])]


def evidence_fields(record):
    """(label, value, quote, block ids) of every value that needs a quote."""
    return ([("title", record.get("title"), record.get("title_evidence"), record.get("title_blocks")),
             ("date", record.get("date_iso"), record.get("date_evidence"), record.get("date_blocks"))]
            + [(f"issuer {i.get('surface')!r}", i.get("surface"), i.get("evidence"), i.get("blocks"))
               for i in record.get("issuers") or []])


def check(record, text, year=None, blocks=None):
    """Problems of a record against its leaflet's text (without block ids); an empty list means plausible.
    blocks: {block id: text} of the leaflet."""
    problems = []
    for label, value, quote, ids in evidence_fields(record):
        if (value or "").strip() and not _norm(quote):
            problems.append("title: Incipit ohne Beleg" if label == "title" and record.get("title_type") == "incipit"
                            else f"{label}: Wert ohne Beleg")
    for label, _, quote, ids in evidence_fields(record) if blocks is not None else []:
        ids = ids or []
        unknown = [b for b in ids if b not in blocks]
        if unknown:
            problems.append(f"{label}: Block-id unbekannt oder Abbildung: {', '.join(unknown)}")
        elif quote and not ids:
            problems.append(f"{label}: Beleg ohne Block-id")
        elif quote and not grounded(quote, "\n".join(blocks[b] for b in ids)):
            problems.append(f"{label}: Beleg steht nicht in den genannten Blöcken")

    if record.get("title") and not grounded(record.get("title_evidence"), text):
        problems.append("title_evidence nicht im Text")
    if record.get("date_iso") and not grounded(record.get("date_evidence"), text):
        problems.append("date_evidence nicht im Text")
    for iss in record.get("issuers") or []:
        if not grounded(iss.get("evidence"), text):
            problems.append(f"issuer-evidence nicht im Text: {iss.get('surface')!r}")

    iso = record.get("date_iso") or ""
    if iso:
        if not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", iso):
            problems.append(f"date_iso nicht wohlgeformt: {iso!r}")
        elif year and iso[:4] != str(year):
            problems.append(f"date_iso {iso} passt nicht zum Jahrgang {year}")
        if record.get("date_type") in ("", "undated"):
            problems.append("date_iso gesetzt, aber date_type leer/undated")
        received = record.get("received_date") or ""
        if (record.get("date_type") == "issued" and len(iso) == 10 and received
                and not record.get("received_year_uncertain") and iso > received):
            problems.append(f"Erscheinungsdatum {iso} liegt nach dem Eingangsstempel {received}")

    title = _norm(record.get("title"))
    if (title and re.search(r"\b(the|and|of|for|against|student[s]?|university|flyer|leaflet)\b", title)
            and not grounded(record.get("title"), text, threshold=0.95)):
        problems.append("Titel wirkt übersetzt/erfunden (englische Wörter, kein Beleg)")
    if record.get("date_type") == "issued" and record.get("date_evidence"):
        q, t = _norm(record["date_evidence"]), _norm(text)
        pos = t.index(q) / len(t) if q and q in t else None
        if pos is not None and 0.15 < pos < 0.85:
            problems.append(f"date_type=issued, aber der Beleg steht mitten im Text (Position {pos:.0%}) "
                            "- vermutlich kein Erscheinungsdatum")

    for iss in record.get("issuers") or []:
        label = f"issuer {iss.get('surface')!r}"
        if iss.get("role") == "issuer" and looks_like_person(iss.get("surface")):
            problems.append(f"Person als issuer: {iss.get('surface')!r} - gehoert zu signatory")
        details = [("Funktion", iss.get("function")), ("Stichwort", iss.get("marker"))]
        if iss.get("role") != "signatory":
            problems += [f"{label}: {name} bei Organisation" for name, value in details if (value or "").strip()]
            continue
        evidence = unspace(iss.get("evidence"))
        for name, value in details + [("Name", iss.get("surface"))]:
            if (value or "").strip() and not match_kind(value, evidence):
                problems.append(f"{label}: {name} {value!r} nicht im Beleg")

    missing = missing_signatories(record, text)
    if missing:
        problems.append(f"Unterzeichner fehlt (Verantwortlich-Zeile): {', '.join(missing)}")
    names = responsible_names(text)
    unmarked = [i.get("surface") for i in record.get("issuers") or []
                if not (i.get("marker") or "").strip() and any(same_name(n, i.get("surface")) for n in names)]
    if unmarked:
        problems.append(f"Stichwort fehlt (Verantwortlich-Zeile): {', '.join(unmarked)}")

    series = record.get("series") or ""
    if series and _squeeze(series) not in _squeeze(text):
        problems.append(f"series nicht im Text: {series!r}")
    if record.get("issue") and not series:
        problems.append("Hinweis: issue gesetzt, aber keine series")
    return problems


# ---------- groups of the authority file ----------

def _fold(word):
    w = word.lower().replace("ß", "ss")
    return w[:-1] if len(w) >= 6 and w.endswith("s") else w  # "Deutschlands" finds "Deutschland"


def _tokens(text):
    return [(m.group(), _fold(m.group())) for m in re.finditer(r"[^\W_]+", unicodedata.normalize("NFC", text or ""))]


def registry(orgs):
    """orgs: [(id, short name, full name)] -> [(id, form tokens, is acronym)]. A one-word full name is mostly a parsing
    error of the finding aid ("Psychologie") and left out."""
    forms = []
    for org_id, name, full in orgs:
        for form in {name or ""} | ({full} if len((full or "").split()) > 1 else set()):
            toks = [t for _, t in _tokens(form)]
            if toks:
                forms.append((org_id, toks, form.isupper() and " " not in form and len(form) <= 6))
    return forms


def resolve(surface, forms):
    """The ids of the groups named in a spelling; overlapping matches go to the longer form."""
    toks = _tokens(surface)
    words = [t for _, t in toks]
    hits = []
    for org_id, form, acronym in forms:
        for i in range(len(words) - len(form) + 1):
            if words[i:i + len(form)] != form:
                continue
            if acronym and len(words) > 1 and not (sum(c.isupper() for c in toks[i][0]) >= 2 or len(toks[i][0]) >= 4):
                continue  # "als" is no AStA
            hits.append((i, i + len(form), org_id))
    taken, found = set(), []
    for start, end, org_id in sorted(hits, key=lambda h: h[0] - h[1]):
        span = set(range(start, end))
        if not span & taken:
            taken |= span
            if org_id not in found:
                found.append(org_id)
    return sorted(found)


LOCAL_ORGS = {"asta", "linke_asta_fraktion", "studentenschaft",
              "studentenparlament", "fachschaften", "fachschaften_fachbereiche", "studentische_vertretung",
              "rektor", "kanzler", "studentenwerk", "studentenwerk_regensburg"}
OTHER_PLACE = re.compile(
    r"(?i)würzburg|münchen|muenchen|erlangen|nürnberg|bamberg|augsburg|passau|landshut|"
    r"bayreuth|eichstätt|tübingen|heidelberg|freiburg|frankfurt|marburg|gießen|göttingen|"
    r"hamburg|berlin|bonn|köln|münster|bochum|mainz|kiel|saarbrücken|konstanz|stuttgart|"
    r"mannheim|karlsruhe|hannover|bremen|aachen|darmstadt|kassel|"
    r"julius[- ]*maximilian|ludwig[- ]*maximilian|\blmu\b|friedrich[- ]*alexander|"
    r"polytechnikum|pädagogische[n]? hochschule|\bPH\b|fachhochschule|ingenieurschule")
OWN_UNIVERSITY = re.compile(r"(?i)universität regensburg|uni[- ]regensburg|univ\. regensburg|\buni\b")


def match_issuers(record, forms):
    """org_ids on every issuer; entries naming the same groups become one, under the longer spelling. The AStA of
    another university is not the AStA here."""
    out, by_orgs = [], {}
    for iss in record.get("issuers") or []:
        if iss.get("role") != "issuer":
            out.append(iss)
            continue
        ids = resolve(iss.get("surface"), forms)
        where = f"{iss.get('surface', '')} {iss.get('evidence', '')}"
        if OTHER_PLACE.search(where) and not OWN_UNIVERSITY.search(where) and set(ids) & LOCAL_ORGS:
            iss = dict(iss, _other_institution=sorted(set(ids) & LOCAL_ORGS))
            ids = [i for i in ids if i not in LOCAL_ORGS]
        iss = dict(iss, org_ids=ids)
        k = tuple(ids)
        if not k or k not in by_orgs:
            if k:
                by_orgs[k] = iss
            out.append(iss)
            continue
        kept = by_orgs[k]
        if len(iss["surface"]) > len(kept["surface"]):
            kept["_merged"] = kept.get("_merged", []) + [kept["surface"]]
            kept.update(surface=iss["surface"], evidence=iss["evidence"])
        else:
            kept.setdefault("_merged", []).append(iss["surface"])
        blocks = kept.setdefault("blocks", [])
        blocks += [b for b in iss.get("blocks") or [] if b not in blocks]
    record["issuers"] = out
    return record


MONEY = re.compile(r"\bDM\s*[\d.,]|[\d.,]+\s*DM\b|satz\s+DM\b", re.I)
CREDITS = re.compile(r"(?i)^\W*(fotos?|fotografie|graphik|grafik|design|zeichnung|druck|satz)\b")


def edge_groups(record, pages, first, last, forms):
    """No issuer, but a short block at the start or end names a known group? -> [(block id, text)]"""
    if any(i.get("role") == "issuer" for i in record.get("issuers") or []):
        return []
    short = [(bid, unspace(" ".join(text.split()))) for _, bid, kind, text in blocks(pages, first, last)
             if kind != "Picture" and not is_stamp_block(kind, text)]
    found = []
    for bid, text in short[:3] + short[-3:]:
        if len(text) <= 70 and not MONEY.search(text) and not CREDITS.search(text) \
                and bid not in {b for b, _ in found} and resolve(text, forms):
            found.append((bid, text))
    return found


# ---------- a volume ----------

def recheck(done, segs, texts, pages, forms):
    """Leaflets to ask again, one by one: with block ids of another leaflet, missing from the answer, with people of the
    "Verantwortlich" line left out, or without issuer while a known group stands at the edge.
    -> [(id, foreign ids, missing names, groups at the edge)]"""
    out = []
    for s in segs:
        rec = done.get(s["id"])
        if rec is None:
            continue
        asked = rec.get("_foreign_blocks") or rec.get("_retried_missing")
        foreign = [] if asked else foreign_block_ids(rec, s["start_page"], s["end_page"])
        unsigned = [] if rec.get("_retried_signatory") else missing_signatories(rec, texts[s["id"]][1])
        edge = [] if rec.get("_retried_issuer") or not forms else edge_groups(rec, pages, s["start_page"],
                                                                                s["end_page"], forms)
        if foreign or (rec.get("_missing") and not asked) or unsigned or edge:
            out.append((s["id"], foreign, unsigned, edge))
    return out


def take_retry(old, new, foreign, unsigned, edge, text):
    """The record after asking again. A retry for missing people or groups counts only if it closes the gap."""
    if foreign:
        return {**new, "_foreign_blocks": foreign}
    if not (unsigned or edge):
        return {**new, "_retried_missing": True}
    gained = old.get("_missing") or (unsigned and len(missing_signatories(new, text)) < len(unsigned)) or \
        (edge and any(i.get("role") == "issuer" for i in new.get("issuers") or []))
    rec = dict(new if gained else old)
    if old.get("_missing"):
        rec["_retried_missing"] = True
    for flag in ("_foreign_blocks", "_retried_missing"):
        if old.get(flag):
            rec[flag] = old[flag]
    if unsigned:
        rec["_retried_signatory"] = True
    if edge:
        rec["_retried_issuer"] = [t for _, t in edge]
    return rec


def finish(done, segs, texts, pages, year, forms):
    """The records of all leaflets, cleaned, with date of receipt, checks and group ids."""
    results = []
    for s in segs:
        meta = dict(done.get(s["id"], EMPTY))
        meta.pop("id", None)
        if not s.get("no_content"):
            meta = add_received_date(normalize_record(meta), stamp_dates(pages, s["start_page"], s["end_page"]), year)
            meta["_grounding"] = check({**s, **meta}, texts[s["id"]][1], year, texts[s["id"]][2])
        results.append({**s, **meta})
    for r in results:
        if not r.get("no_content"):
            match_issuers(r, forms)
    return results


def run(segs, pages, year, key, model, known_orgs, forms, checkpoint, job=None, template=None, batch_size=BATCH_SIZE, seed=None):
    """Asks the model for every leaflet of segs (the segments of segments.json), batch_size at a time. Every answer is
    appended to checkpoint at once, so a new run asks only for what is missing. seed: {(first page, last page): answer}
    of an earlier run, taken over for the leaflets with the same pages. job: the dict the page polls."""
    job = job if job is not None else {}
    done = {}
    if checkpoint.is_file():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                done[rec["id"]] = rec
            except (json.JSONDecodeError, KeyError, TypeError):
                pass  # half a line after a hard stop

    def keep(records):
        with checkpoint.open("a", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
        done.update((r["id"], r) for r in records)

    segs = sorted(segs, key=lambda s: s["start_page"])
    keep([{**seed[s["start_page"], s["end_page"]], "id": s["id"]} for s in segs
          if s["id"] not in done and (s["start_page"], s["end_page"]) in (seed or {})])
    texts = {s["id"]: segment_texts(pages, s["start_page"], s["end_page"]) for s in segs}
    todo = [s for s in segs if s["id"] not in done and not s.get("no_content")]
    keep([{"id": s["id"], **EMPTY} for s in todo if not texts[s["id"]][0]])
    todo = [s for s in todo if texts[s["id"]][0]]
    batches = [todo[i:i + batch_size] for i in range(0, len(todo), batch_size)]
    state, cost = {}, []
    job.update(parts=[{"label": f"{len(b)} {'Flugblatt' if len(b) == 1 else 'Flugblätter'}", "state": "wartet"} for b in batches], cost=0.0,
               phase="Metadaten werden erzeugt", done=0, total=len(todo), unit="Flugblatt fertig" if len(todo) == 1 else "Flugblättern fertig")
    for part, batch in zip(job["parts"], batches):
        if job.get("cancel"):
            return None
        part["state"] = "läuft"
        prompt = build_prompt(year, [(s["id"], s["start_page"], s["end_page"], texts[s["id"]][0]) for s in batch],
                              known_orgs, template=template)
        try:
            got = extract(key, model, prompt, state, cost)
        except Exception:
            part["state"] = "fehler"
            raise
        keep([{**got.get(s["id"], {**EMPTY, "_missing": True}), "id": s["id"]} for s in batch])
        part["state"] = "fertig"
        job.update(cost=spent(cost)["cost"], done=job["done"] + len(batch))

    again = recheck(done, segs, texts, pages, forms)
    job.update(phase="Auffällige Flugblätter werden einzeln nachgefragt", done=0, total=len(again), unit="nachgefragt")
    for sid, foreign, unsigned, edge in again:
        if job.get("cancel"):
            return None
        job["done"] += 1
        hint = []
        if unsigned:
            hint.append(f"Die Verantwortlich-Zeile nennt {', '.join(unsigned)} - fehlen diese Personen als signatory?")
        if edge:
            where = "; ".join(f"„{text}“ (Block {bid})" for bid, text in edge)
            hint.append(f"Am Anfang oder Ende des Blatts steht {where}. Prüfe, ob diese Gruppe das Blatt herausgibt "
                        "(issuer) oder nur erwähnt, zitiert oder angesprochen wird.")
        s = next(x for x in segs if x["id"] == sid)
        prompt = build_prompt(year, [(sid, s["start_page"], s["end_page"], texts[sid][0])], known_orgs,
                              {sid: " ".join(hint)} if hint else None, template)
        try:
            new = extract(key, model, prompt, state, cost).get(sid)
        except Exception:  # the first answer stays
            continue
        if new is not None:
            keep([{**take_retry(done[sid], new, foreign, unsigned, edge, texts[sid][1]), "id": sid}])
        job["cost"] = spent(cost)["cost"]

    job.update(phase="Belege werden im Text geprüft", done=0, total=0)
    results = finish(done, segs, texts, pages, year, forms)
    flagged = sum(bool(r.get("_grounding")) for r in results if not r.get("no_content"))
    checked = sum(not r.get("no_content") for r in results)
    return {"created": datetime.now().isoformat(), "model": model, "backend": "openrouter",
            **spent(cost), "grounding": {"checked": checked, "flagged": flagged},
            "segments": results}


# ---------- in the app ----------

_models = {}


def models():
    """[(id, name, $ per prompt token, $ per answer token)] of the models that can answer in a schema, the strongest
    first by OpenRouter's ranking; asked once an hour. Empty when OpenRouter cannot be reached."""
    if time.time() - _models.get("at", 0) > 3600:
        try:
            data = requests.get(MODELS_URL, params={"sort": "intelligence-high-to-low",
                                                    "supported_parameters": "structured_outputs"}, timeout=10).json()["data"]
            _models.update(at=time.time(), list=[(m["id"], m.get("name") or m["id"], float(m["pricing"]["prompt"]),
                                                  float(m["pricing"]["completion"]))
                                                 for m in data if not m["id"].endswith(":batch")])  # no batch API here
        except (requests.RequestException, KeyError, TypeError, ValueError):
            _models["at"] = time.time() - 3000  # again in ten minutes
    return _models.get("list", [])


def top_models(used, n=8, default=DEFAULT_MODEL):
    """[(group, [(id, label)])] for the choice: the models of the released volumes (used: [(id, number of volumes)],
    most used first), the n strongest. Models OpenRouter no longer lists are left out;
    without the list (offline) all but the strongest stay."""
    names = {m[0]: m[1] for m in models()}
    count = dict(used)
    groups = [("Bisher verwendet", [i for i, _ in used] or [default]),
              ("Weitere Modelle", list(names)[:n])]
    seen, out = set(), []
    for label, ids in groups:
        ids = [i for i in ids if (i in names or not names) and i not in seen]
        seen.update(ids)
        if ids:
            out.append((label, [(i, names.get(i, i) + (f" · {count[i]} {'Band' if count[i] == 1 else 'Bände'}"
                                                       if i in count else "")) for i in ids]))
    return out


def result_path(volume):
    return importer.ocr_dir(volume) / "metadata.json"  # goes with the recognized text


def checkpoint_path(volume, segs):
    """Answers kept while running; other cuts give other leaflets, so their answers do not apply."""
    ranges = json.dumps([(s["start_page"], s["end_page"]) for s in segs])
    return importer.ocr_dir(volume) / f"metadata-{hashlib.sha1(ranges.encode()).hexdigest()[:8]}.jsonl"


def earlier(volume):
    """(model, prompt, {(first page, last page): answer}) of the last finished run: its answers per leaflet, as they were kept
    while it ran. After a new split a leaflet with the same pages needs no new answer."""
    try:
        doc = json.loads(result_path(volume).read_text(encoding="utf-8"))
        lines = checkpoint_path(volume, doc["segments"]).read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError, KeyError):
        return None, None, {}
    kept = {}
    for line in lines:
        try:
            kept[json.loads(line)["id"]] = json.loads(line)
        except (ValueError, KeyError, TypeError):
            pass
    return doc.get("model"), doc.get("prompt"), {(s["start_page"], s["end_page"]): kept[s["id"]]
                                                 for s in doc["segments"] if s["id"] in kept and not s.get("no_content")}


def prompt_id(template):
    return hashlib.sha1((template or "").encode()).hexdigest()[:8]


def leaflets(volume):
    return sorted((segments.load(volume) or {}).get("segments", []), key=lambda s: s["start_page"])


HINT_KINDS = [("Datum", r"date_|Erscheinungsdatum|Eingangsstempel"), ("Beleg", r"Beleg|evidence|Block"),
              ("Herausgeber", r"issuer|Unterzeichner|Stichwort|Person|Funktion|Name "),
              ("Titel", r"title|Titel"), ("Reihe", r"series|issue")]
KIND_ORDER = [k for k, _ in HINT_KINDS] + ["Sonstiges"]


def hint_kinds(record):
    """What the remarks of the checks on one leaflet are about, in the order of HINT_KINDS."""
    kinds = {next((k for k, rx in HINT_KINDS if re.search(rx, p)), "Sonstiges") for p in remarks(record)}
    return [k for k in KIND_ORDER if k in kinds]


FIELD = {"title": "Titel", "date": "Datum"}
HINT_TEXTS = [  # (message of the pipeline's check, the sentence for the reader); the first that fits wins
    (r"date_iso (\S+) passt nicht zum Jahrgang (\d{4})",
     lambda d, y: f"Datum {d} liegt {'vor' if int(d[-4:]) < int(y) else 'nach'} dem Jahr des Bandes ({y}). Das kommt vor, wenn ein Blatt erst später "
                  "abgeheftet wurde. Prüfen, wenn im Text ein anderes Jahr steht."),
    (r"Erscheinungsdatum (\S+) liegt nach dem Eingangsstempel (\S+)",
     lambda d, e: f"Erscheinungsdatum {d} liegt nach dem Eingangsstempel {e}. Das ist unwahrscheinlich, eines von beiden prüfen."),
    (r"date_type=issued, aber der Beleg steht mitten im Text", lambda: "Datum: Die Belegstelle steht mitten im Text, vermutlich ist es kein Erscheinungsdatum."),
    (r"date_type=undated, aber date_evidence", lambda: "Datum: Es gibt eine Belegstelle, obwohl das Blatt als undatiert gilt."),
    (r"Person als issuer: '(.*)'", lambda n: f"Herausgeber „{n}“ ist vermutlich eine Person und gehört zu den Unterzeichnenden."),
    (r"issuer '(.*)': Stichwort bei Organisation",
     lambda n: f"Herausgeber „{n}“: Ein Stichwort wie „Verantwortlich“ passt nicht zu einer Organisation, vermutlich ist es eine Person."),
    (r"issuer '(.*)': (?:Name|Funktion|Stichwort) '(.*)' nicht im Beleg", lambda n, w: f"Herausgeber „{n}“: „{w}“ steht nicht in der angegebenen Belegstelle."),
    (r"issuer-evidence nicht im Text: '(.*)'", lambda n: f"Herausgeber „{n}“: Die Belegstelle steht nicht im erkannten Text."),
    (r"issuer '(.*)': Block-id unbekannt",
     lambda n: f"Herausgeber „{n}“: Der Name stammt aus einem Bild (z. B. einem Logo) oder einem Block, den es nicht gibt. Die App zeigt deshalb keine Belegstelle. Auf dem Blatt prüfen, ob der Name dort steht."),
    (r"issuer '(.*)': Beleg steht nicht in den genannten",
     lambda n: f"Herausgeber „{n}“: Der zitierte Wortlaut steht nicht in den Textblöcken, die als Beleg angegeben sind."),
    (r"(title|date): Block-id unbekannt",
     lambda f: f"{FIELD[f]}: Die Angabe stammt aus einem Bild oder einem Block, den es nicht gibt. Die App zeigt deshalb keine Belegstelle."),
    (r"(title|date): Beleg steht nicht in den genannten",
     lambda f: f"{FIELD[f]}: Der zitierte Wortlaut steht nicht in den Textblöcken, die als Beleg angegeben sind."),
    (r"(title|date)_evidence nicht im Text", lambda f: f"{FIELD[f]}: Die Belegstelle steht nicht im erkannten Text."),
    (r"title: Incipit ohne Beleg|title_type=original ohne Belegzitat", lambda: "Titel: Zum Titel fehlt die Belegstelle."),
    (r"Titel wirkt übersetzt", lambda: "Titel: Er wirkt übersetzt oder erfunden (englische Wörter, kein Beleg im Text)."),
    (r"series nicht im Text: '(.*)'", lambda s: f"Reihe „{s}“ steht nicht im erkannten Text."),
    (r"issue gesetzt, aber keine series", lambda: "Reihe: Eine Nummer ist angegeben, aber keine Reihe."),
    (r"Unterzeichner fehlt \(Verantwortlich-Zeile\): (.*)", lambda n: f"In der Verantwortlich-Zeile steht {n}, bei den Unterzeichnenden fehlt der Name."),
    (r"Stichwort fehlt \(Verantwortlich-Zeile\): (.*)", lambda n: f"{n}: Das Stichwort aus der Verantwortlich-Zeile fehlt bei den Unterzeichnenden."),
]


def hint_text(message):
    """One remark of the checks in plain German; one that fits no rule is shown as it is."""
    message = re.sub(r"\b(\d{4})-(\d\d)(?:-(\d\d))?\b", lambda m: ".".join(g for g in (m[3], m[2], m[1]) if g), message)
    for rx, say in HINT_TEXTS:
        if m := re.search(rx, message):
            return say(*m.groups())
    return message


WEEKDAY = re.compile(r"\b(montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonnabend|sonntag|mo|di|mi|do|fr|sa|so)\b"
                     r"(?=[.,\s]*(?:den\s+)?\d)", re.I)
DAYS = {"mo": 0, "di": 1, "mi": 2, "do": 3, "fr": 4, "sa": 5, "so": 6}


def weekday_fits(iso, evidence):
    """Whether the weekday written beside a date ("Mittwoch, 8. 11. 72") is the weekday of that date."""
    try:
        day = datetime.fromisoformat(iso).weekday()
    except ValueError:
        return False
    return any((5 if m[1].lower() == "sonnabend" else DAYS[m[1][:2].lower()]) == day for m in WEEKDAY.finditer(evidence or ""))


def remarks(record):
    """The remarks of the checks worth a look: a date outside the year of the volume is none when the weekday written
    beside it fits, it is a leaflet of the year before that was filed later."""
    return [p for p in record.get("_grounding") or []
            if not ((m := re.match(r"date_iso (\d{4}-\d\d-\d\d) passt nicht zum Jahrgang", p)) and weekday_fits(m[1], record.get("date_evidence")))]


def hint_counts(records):
    """{kind: number of leaflets} for the remarks of the checks, in the order of HINT_KINDS."""
    kinds = [k for r in records for k in hint_kinds(r)]
    return {k: kinds.count(k) for k in KIND_ORDER if k in kinds}


PREPARE = "anlegen"


def create_leaflets(volume, job=None):
    """Step 6: the leaflets as a draft in the database, from the metadata of step 5, and their copies."""
    step = lambda i, state: job and (job["parts"][i].update(state=state, since=time.time()), job.update(done=i + (state == "fertig")))
    step(0, "läuft")
    doc = json.loads(result_path(volume).read_text(encoding="utf-8"))
    doc["source_pdf"] = f"{volume.stem}.pdf"  # the import finds the scan by it, as in the files of the pipeline
    (fillDatabase.DATA_DIR / f"nr{volume.vz:03d}_metadata.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    fillDatabase.import_volume(volume.vz)
    step(0, "fertig")
    step(1, "läuft")
    copy_search.add(volume)
    step(1, "fertig")


def start_create(volume):
    """create_leaflets in the background, so step 6 can show its progress; poll importer.JOBS[(vz, PREPARE)]."""
    now = time.time()
    job = importer.JOBS[(volume.vz, PREPARE)] = {
        "state": "running", "done": 0, "total": 2, "unit": "Teilen fertig", "error": "", "started": now,
        "parts": [{"label": "Flugblätter übernehmen", "state": "wartet", "since": now},
                  {"label": "Exemplare in allen Bänden suchen", "state": "wartet", "since": now}]}

    def go():
        try:  # ponytail: shares the app's one database session with the requests, as the other jobs do
            create_leaflets(volume, job)
            job["state"] = "done"
        except Exception as error:  # a thread must report, not die silently
            logger.exception("preparing the leaflets failed")
            job.update(state="error", error=f"Die Flugblätter ließen sich nicht vorbereiten: {error}")

    threading.Thread(target=go, daemon=True).start()


def flagged_leaflets(volume):
    """(leaflet, remarks in plain German, seen) for each created leaflet the checks found something on. seen: marked
    "Passt so", or corrected since. Not a copy whose group is checked: its details are those of the main copy, which is
    looked at there."""
    path = result_path(volume)  # a volume from before the import has only the file the database was filled from
    doc = json.loads((path if path.exists() else fillDatabase.DATA_DIR / f"nr{volume.vz:03d}_metadata.json").read_text(encoding="utf-8"))
    by_range = {(lf.start_page, lf.end_page): lf
                for lf in fillDatabase.session.query(fillDatabase.Leaflet).filter_by(volume_id=volume.id)
                if not (lf.copies_checked and lf.canonical_leaflet_id not in (None, lf.id))}
    checked = corrections.by_segment(corrections.load(fillDatabase.CHECKED))
    fixed = corrections.by_segment(corrections.load(fillDatabase.CORRECTIONS))

    def seen(lf):
        key = (volume.stem, lf.start_page, lf.end_page)
        return checked[key][-1]["seen"] if key in checked else key in fixed  # the last mark counts
    return [(by_range[r["start_page"], r["end_page"]], [hint_text(p) for p in remarks(r)], seen(by_range[r["start_page"], r["end_page"]]))
            for r in doc["segments"]
            if remarks(r) and not r.get("no_content") and (r["start_page"], r["end_page"]) in by_range]


def mark_seen(volume, leaflet, seen=True):
    """"Passt so" (or taking it back) for the remarks on a leaflet; kept by its pages, so preparing again keeps it."""
    corrections.append(fillDatabase.CHECKED, [{"volume": volume.stem, "start_page": leaflet.start_page,
                                               "end_page": leaflet.end_page, "field": "hints", "seen": seen}])


def status(volume):
    """State for the page: "none", "partial" (answers kept from an interrupted run), "stale" (the cuts changed since)
    or "done", with model, cost and how many leaflets the checks found something on."""
    segs = leaflets(volume)
    try:
        doc = json.loads(result_path(volume).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"state": "partial" if segs and checkpoint_path(volume, segs).is_file() else "none"}
    ranges = [(s["start_page"], s["end_page"]) for s in segs]
    named = [r for r in doc["segments"] if not r.get("no_content")]
    return {"state": "done" if [(r["start_page"], r["end_page"]) for r in doc["segments"]] == ranges else "stale",
            "model": doc.get("model"), "model_name": dict((m[0], m[1]) for m in models()).get(doc.get("model"), doc.get("model")),
            "cost": ocr.dollar(doc.get("cost") or 0), "count": len(named),
            "now": sum(not s.get("no_content") for s in segs),
            "same": len({(s["start_page"], s["end_page"]) for s in segs if not s.get("no_content")} & set(earlier(volume)[2])),
            "flagged": sum(bool(remarks(r)) for r in named), "hints": hint_counts(named)}


def prices(volume, fresh=False):
    """{model id: estimated price of a run in dollar as text} for the models OpenRouter lists. fresh: every leaflet is
    asked again, as after a finished run."""
    if not ocr.result_path(volume).is_file():
        return {}
    pages = page_blocks(ocr.result_path(volume))
    todo = [s for s in leaflets(volume) if not s.get("no_content")]
    before_model, _, before = earlier(volume) if not fresh else (None, None, {})

    def price(asked, p_in, p_out):
        chars = sum(len(segment_texts(pages, s["start_page"], s["end_page"])[0]) for s in asked)
        chars += len(prompt_text()) * -(-len(asked) // BATCH_SIZE)
        return "etwa " + ocr.dollar((chars / CHARS_PER_TOKEN * p_in + len(asked) * OUT_TOKENS * p_out) * 1.05)  # asking again
    return {m: price([s for s in todo if m != before_model or (s["start_page"], s["end_page"]) not in before], p_in, p_out)  # leaflets of the last run cost nothing
            for m, _, p_in, p_out in models()}


def start(volume, model, orgs, prompt="", batch_size=BATCH_SIZE):
    """Runs in the background (poll importer.JOBS[(vz, "angaben")]). orgs: [(id, short name, full name)]. prompt: the
    instructions as shown on the page (kept for the next volumes); empty for the saved ones."""
    key = keys.get("openrouter")
    if not key:
        raise ValueError("Es fehlt der Zugang zu OpenRouter. Bitte unten den API-Key eintragen.")
    if not MODEL_ID.match(model or ""):
        raise ValueError("Bitte ein Modell wählen, etwa „anthropic/claude-sonnet-4.5“.")
    if ocr.status(volume)["state"] != "done":
        raise ValueError("Zuerst den Text erkennen.")
    if not segments.status(volume)["confirmed"]:
        raise ValueError("Zuerst die Flugblätter trennen und die Einteilung abschließen.")
    if importer.running(volume, JOB):
        raise ValueError("Die Metadaten werden schon erzeugt. Bitte warten.")
    if not 1 <= batch_size <= MAX_BATCH:
        raise ValueError(f"Die Batchgröße muss zwischen 1 und {MAX_BATCH} liegen.")
    if prompt.strip():
        save_prompt(prompt)
    template = prompt_text()
    segs, year = leaflets(volume), volume.year
    again = status(volume)["state"] == "done"  # "Neu erzeugen": the answers kept for these leaflets would be taken over unasked
    if again:
        checkpoint_path(volume, segs).unlink(missing_ok=True)
    before_model, before_prompt, before = (None, None, {}) if again else earlier(volume)
    seed = before if before_model == model and before_prompt in (None, prompt_id(template)) else {}  # an answer of another model or prompt does not carry over
    job = importer.JOBS[(volume.vz, JOB)] = {"state": "running", "done": 0, "total": 0, "error": "",
                                            "started": time.time(), "parts": [], "unit": "Flugblättern fertig"}

    def go():
        try:
            doc = run(segs, page_blocks(ocr.result_path(volume)), year, key, model, [o[1] for o in orgs if o[1]],
                      registry(orgs), checkpoint_path(volume, segs), job,
                      template, batch_size, seed)
            if doc is None:
                job["state"] = "cancelled"
                return
            doc["prompt"] = prompt_id(template)
            result_path(volume).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
            job["state"] = "done"
        except Exception as error:  # report from the thread
            job.update(state="error", error=explain(error))

    threading.Thread(target=go, daemon=True).start()


def cancel(volume):
    """Stops after the request that is running; it is paid for."""
    job = importer.JOBS.get((volume.vz, JOB))
    if not job or job["state"] != "running":
        raise ValueError("Es werden gerade keine Metadaten erzeugt.")
    job["cancel"] = True


def explain(error):
    code = getattr(getattr(error, "response", None), "status_code", None)
    if code in (401, 403):
        return "OpenRouter hat den API-Key abgelehnt. Bitte unten einen anderen eintragen."
    if code == 402:
        return "Das Guthaben bei OpenRouter ist aufgebraucht. Bereits erzeugte Metadaten bleiben erhalten."
    if code in (400, 404):
        return f"OpenRouter kennt dieses Modell nicht, oder es kann so nicht antworten ({error.response.text[:200]})."
    logger.exception("metadata failed")
    return f"Die Metadaten wurden unterbrochen ({error}). Was schon erzeugt ist, bleibt erhalten; ein neuer Start setzt fort."
