import logging
import math
import re
import time
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from html import unescape
from itertools import combinations
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, literal_column, or_
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import export, importer, keys, metadata, ocr, organizations, pdf_service, segments, topics
from .database import copy_decisions, corrections, fillDatabase, search
from .database.fillDatabase import (COPY_DECISIONS, CORRECTIONS, VOLUMES, automatic_record, copy_review,
                                    fill_copies,
                                    automatic_values, reset_leaflet, series_names)
from .database.session import DB_PATH, session
from .database.models import (DRAFT, RELEASED, Leaflet, LeafletIssuer, Volume, Organization, Page,
                              Topic)
from .app_helper import setup_logging


setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="UR Leaflet Archive")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


DOC_TYPES = {
    'flugblatt': 'Flugblatt', 'offener_brief': 'Offener Brief', 'einladung': 'Einladung',
    'broschuere': 'Broschüre', 'zeitschrift': 'Zeitschrift', 'protokoll': 'Protokoll',
    'unklar': 'unklar',
}
DATE_TYPES = {'issued': 'Erscheinungsdatum', 'event': 'Datum einer Veranstaltung',
              'undated': 'undatiert'}
TOPIC_TITLE_NOTES = {'llm_label': 'Titel von einem Sprachmodell erzeugt'}
SHORT_TOPIC_LENGTH = 60


def short_topic_title(title):
    """Long model-generated titles are cut at a word boundary for compact UI."""
    if len(title) <= SHORT_TOPIC_LENGTH:
        return title
    return title[:SHORT_TOPIC_LENGTH].rsplit(' ', 1)[0] + ' …'


def evidence_items(pairs):
    """(block ids, quote) pairs -> unique items that have block ids."""
    items, seen = [], set()
    for blocks, quote in pairs:
        key = tuple(blocks or [])
        if key and key not in seen:
            seen.add(key)
            items.append({'blocks': list(key), 'quote': quote or ''})
    return items


def page_range(start, end):
    """Position in the digitized volume: 'Bandseite 90' or 'Bandseiten 6–7'."""
    return f"Bandseite {start}" if start == end else f"Bandseiten {start}–{end}"


templates.env.globals['page_range'] = page_range
templates.env.globals['FONDS_URL'] = \
    "https://www.archivportal-d.de/item/NFTD57JPRHJOTMAI46F4P3EQ6NA5DKLZ"


LOCAL = ZoneInfo("Europe/Berlin")


def german_date(iso):
    """'1973-06-26' -> '26.06.1973', '1969-12' -> '12.1969', '1969' -> '1969'"""
    return '.'.join(reversed((iso or '').split('-')))


def german_to_iso(text):
    """'17.12.1969', '12.1969', '1969' (or ISO) -> ISO date; None if invalid."""
    parts = text.split('-') if '-' in text else text.split('.')[::-1]
    if not 1 <= len(parts) <= 3 or not all(p.isdigit() for p in parts) or len(parts[0]) != 4:
        return None
    nums = [int(p) for p in parts]
    try:
        datetime.date(*nums, *[1] * (3 - len(nums)))  # checks month and day
    except ValueError:
        return None
    return '-'.join([parts[0]] + [f"{n:02d}" for n in nums[1:]])


templates.env.globals['german_date'] = german_date
templates.env.globals['DOC_TYPES'] = DOC_TYPES
templates.env.globals['DATE_TYPES'] = DATE_TYPES
# the fields a search can be limited to (the keys of search.FIELDS), for the field selection and the suggestions
templates.env.globals['search_fields'] = [('titel', 'Titel'), ('herausgeber', 'Herausgeber'), ('unterzeichner', 'Unterzeichnende'),
                                          ('reihe', 'Reihe'), ('text', 'Volltext')]


MONTHS = ['Jan.', 'Feb.', 'März', 'Apr.', 'Mai', 'Juni', 'Juli', 'Aug.', 'Sept.', 'Okt.',
          'Nov.', 'Dez.']


def iso_to_text(iso):
    """'1968-11-14' -> '14. Nov. 1968', '1968-02' -> 'Feb. 1968'; None if malformed."""
    parts = (iso or '').split('-')
    try:
        text = str(int(parts[0]))
        if len(parts) > 1:
            text = f"{MONTHS[int(parts[1]) - 1]} {text}"
        if len(parts) > 2:
            text = f"{int(parts[2])}. {text}"
    except (ValueError, IndexError):
        return None
    return text


def leaflet_year(leaflet, volume_year):
    """Year of the leaflet's date, else the year of its volume."""
    year = (leaflet.date_iso or '')[:4]
    return year if year.isdigit() else str(volume_year)


def list_date(leaflet, fallback_year=None):
    """(date, label) for lists: the leaflet's date, else the archive stamp
    (unless its year is uncertain), else the volume year."""
    text = iso_to_text(leaflet.date_iso)
    if text:
        is_event = leaflet.date_type == 'event' and leaflet.doc_type != 'protokoll'
        return text, 'Veranstaltung' if is_event else ''
    received = None if leaflet.received_uncertain else iso_to_text(leaflet.received_date)
    if received:
        return received, 'Eingang'
    return (str(fallback_year) if fallback_year else ''), ''


def provenance(volume):
    if not volume or not volume.meta_model:
        return None
    return f"{volume.meta_model.split('/')[-1]}, {german_date(volume.meta_created)}"


def volume_pdf(volume):
    return pdf_service.PDF_DIR / volume.label / f"{volume.stem}.pdf"


def leaflet_pdf(leaflet):
    pdf_path = volume_pdf(session.get(Volume, leaflet.volume_id))
    if not pdf_path.is_file():
        raise HTTPException(404)
    return pdf_path


def org_label(org):
    return f"{org.full_name} ({org.name})" if org.full_name else org.name


def automatic_text(leaflet):
    """Corrected field -> value as extracted automatically, for display."""
    if not leaflet.corrected:
        return {}
    r = automatic_record(leaflet)
    auto = automatic_values(r, series_names(VOLUMES))
    names = lambda role: ', '.join(i['surface'] for i in r.get('issuers', [])
                                   if i['role'] == role)
    text = {'title': auto['title'],
            'date': german_date(auto['date_iso']) or auto['date_text'],
            'series': ', '.join(v for v in (auto['series'], auto['issue']) if v),
            'doc_type': DOC_TYPES.get(auto['doc_type'], auto['doc_type']),
            'issuers': names('issuer'), 'signatories': names('signatory'),
            'received': german_date(auto['received_date'])}
    return {f: text[f] for f in leaflet.corrected if f in text}


def org_sort_key(org):
    # full name first, umlauts sorted like their base letters
    name = (org.full_name or org.name).casefold()
    return name.translate(str.maketrans("äöüß", "aous"))


def group_anchor(group):
    return (group or "").lower().replace(" ", "-")


@app.exception_handler(StarletteHTTPException)
async def not_found(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            request, "404.html", {}, status_code=404)
    return await http_exception_handler(request, exc)


# (volume vz, start page): stable across database rebuilds, unlike ids
FEATURED = [(9, 120), (9, 498), (11, 17), (4, 131), (14, 406), (6, 421), (5, 554), (6, 113), (14, 209), (3, 129), (5, 594), (4, 235)]


def released_leaflets():
    """Query of the leaflets of released volumes; drafts show up nowhere else."""
    return session.query(Leaflet).join(Volume, Leaflet.volume_id == Volume.id).filter(Volume.status == RELEASED)


def featured_leaflets():
    found = [released_leaflets().filter(Volume.vz == vz, Leaflet.start_page == page).first() for vz, page in FEATURED]
    return [lf for lf in found if lf]


@app.get("/")
def index(request: Request):
    logger.info('Opening index page')
    volumes = session.query(Volume).filter_by(status=RELEASED).order_by(Volume.vz).all()
    volume_years = {v.id: v.year for v in volumes}
    # a leaflet with duplicates counts once: the other copies of its group are left out
    unique = [lf for lf in released_leaflets() if lf.copy_group is None or lf.canonical_leaflet_id == lf.id]
    per_year = Counter(leaflet_year(lf, volume_years[lf.volume_id]) for lf in unique)
    years = [int(y) for y in per_year if y.isdigit()]
    # every year in the range, so gaps in the collection stay visible
    timeline = [(str(y), per_year[str(y)])
                for y in range(min(years), max(years) + 1)] if years else []
    done = {v for (v,) in released_leaflets().with_entities(Leaflet.volume_id).distinct()}
    stats = {
        'leaflets': sum(per_year.values()),
        'organizations': session.query(LeafletIssuer.org_id)
        .filter(LeafletIssuer.org_id.isnot(None)).distinct().count(),
        'volumes': len(volumes),
        'volumes_done': len(done),
        'first_year': min(volume_years.values(), default=''),
        'last_year': max(volume_years.values(), default=''),
        'missing': [v.label for v in volumes if v.id not in done],
    }
    return templates.TemplateResponse(
        request, "index.html",
        {"stats": stats, "timeline": timeline,
         "featured": leaflet_items(featured_leaflets()),
         "max_count": max(per_year.values(), default=1)})


def date_sort_key(item):
    """Sort by the leaflet's date, else the archive stamp, else the year."""
    lf = item['leaflet']
    if iso_to_text(lf.date_iso):
        return lf.date_iso
    if not lf.received_uncertain and iso_to_text(lf.received_date):
        return lf.received_date
    return item['year']


def text_sort_key(text):
    """Text without leading quotes or dashes, case-insensitive, Ä sorted as A."""
    text = unicodedata.normalize('NFD', re.sub(r'^\W+', '', text or ''))
    return ''.join(c for c in text if not unicodedata.combining(c)).casefold()


def title_sort_key(item):
    return text_sort_key(item['leaflet'].display_title)


def topic_overview(defs, topic_of, uncertain_of, point_of, param='thema'):
    """What a list of topics shows: per topic a bar per year bucket on one shared scale, its top issuers and its map
    points, plus the counts above. defs: [{id, title, words, source}]; topic_of, uncertain_of, point_of: per list item
    (the released leaflets, each once) its topic, whether that is uncertain, its map point; param: the list filter of
    a topic ('thema', or 'kandidat' for a topic of a new run)."""
    items = unique(faceted_items([])[0])
    buckets = topic_year_buckets(Counter(i['year'] for i in items))
    counts_all = Counter(buckets[i['year']] for i in items)
    totals = {b: counts_all[b] for b in sorted(counts_all)}
    by_topic = {}
    for item in items:
        by_topic.setdefault(topic_of(item), []).append(item)
    org_names = {o.id: o.name for o in session.query(Organization).filter(Organization.id.in_(
        {o for i in items for o in i['orgs'] if o not in SPECIAL}))}

    def point(i):
        issuers = ', '.join(org_names[o] for o in i['orgs'] if o in org_names)
        x, y = point_of(i)
        return [x, y, i['leaflet'].id, i['leaflet'].display_title, issuers, i['year'], bool(uncertain_of(i))]

    def year_url(topic_id, bucket):
        pairs = [(param, topic_id)]
        pairs += [('jahr', bucket)] if bucket.isdigit() else [('sortierung', 'datum_auf')]  # several years: sorted by date
        return '/leaflets?' + urlencode(pairs)

    rows = []
    for topic in defs:
        topic_items = by_topic.get(topic['id'], [])
        counts = Counter(buckets[i['year']] for i in topic_items)
        shares = {b: counts[b] / totals[b] for b in totals if counts[b]}
        rows.append((topic, topic_items, counts, shares))
    highest_share = max((s for _, _, _, shares in rows for s in shares.values()), default=1)

    topics_out = []
    for topic, topic_items, counts, shares in rows:
        top_orgs = Counter(o for i in topic_items for o in i['orgs'] if o not in SPECIAL).most_common(3)
        topics_out.append({
            **topic,
            'words': topic.get('words') or [],
            'title_note': TOPIC_TITLE_NOTES.get(topic.get('source')),
            'count': len(topic_items),
            'url': '/leaflets?' + urlencode([(param, topic['id'])]),
            'uncertain': sum(1 for i in topic_items if uncertain_of(i)),
            'top_orgs': [{'label': org_names.get(o, o), 'count': n,
                         'url': '/leaflets?' + urlencode([(param, topic['id']), ('org', o)])}
                        for o, n in top_orgs],
            'years': [{
                'year': b,
                'count': counts[b],
                'total': totals[b],
                'share': f"{shares.get(b, 0) * 100:.1f}".replace('.', ','),
                'height': round(shares.get(b, 0) / highest_share * 100),
                'url': year_url(topic['id'], b),
            } for b in totals],
            'points': [point(i) for i in topic_items if point_of(i)[0] is not None],
        })
    map_data = {'param': param,
                'no_topic': [point(i) for i in by_topic.get(None, []) if point_of(i)[0] is not None],
                'topics': [{'id': t['id'], 'title': t['title'], 'count': t['count'], 'points': t['points']}
                           for t in sorted(topics_out, key=lambda t: -t['count']) if t['points']]}
    uncertain_count = sum(1 for i in items if uncertain_of(i))
    no_topic_count = len(by_topic.get(None, []))
    overview = {
        'uncertain': uncertain_count,
        'uncertain_url': '/leaflets?' + urlencode([('unsicher', 'ja')]),
        'no_topic': no_topic_count,
        'no_topic_url': '/leaflets?' + urlencode([('thema', NO_TOPIC)]),
        'certain': len(items) - uncertain_count - no_topic_count,
    }
    return {"topics": topics_out, "years": list(totals), "map_data": map_data, "overview": overview}


def current_topic_overview():
    defs = [{'id': t.id, 'title': t.title, 'words': t.words, 'source': t.source} for t in session.query(Topic).order_by(Topic.id)]
    return topic_overview(defs, lambda i: i['leaflet'].topic_id, lambda i: i['leaflet'].topic_uncertain,
                          lambda i: (i['leaflet'].x, i['leaflet'].y))


def candidate_topic_overview():
    """The overview of the new run's topics, from its files: by volume and page range, like the run itself."""
    candidate, points = topics.load(topics.CANDIDATE), topics.load(topics.CANDIDATE_MAP) or []
    stems = {v.id: v.stem for v in session.query(Volume)}
    anchor = lambda i: (stems.get(i['leaflet'].volume_id), i['leaflet'].start_page, i['leaflet'].end_page)
    assigned = {(r['volume'], r['start_page'], r['end_page']): (r['topic'], r['uncertain']) for r in candidate['leaflets']}
    xy = {(r['stem'], r['start_page'], r['end_page']): (r['x'], r['y']) for r in points}
    return topic_overview(candidate['topics'], lambda i: assigned.get(anchor(i), (None, False))[0],
                          lambda i: assigned.get(anchor(i), (None, False))[1], lambda i: xy.get(anchor(i), (None, None)),
                          param='kandidat')


@app.get("/themen")
def topic_list(request: Request, sortierung: str = ''):
    """Per topic: a bar per year bucket on one shared scale and its top issuers, plus a shared map of all topics."""
    logger.info('Opening topic list')
    view = current_topic_overview()
    if sortierung == 'alpha':
        view['topics'].sort(key=lambda t: text_sort_key(t['title']))
    else:
        view['topics'].sort(key=lambda t: t['count'], reverse=True)  # stable: ties stay by id
    order = [t['id'] for t in view['topics']]
    view['map_data']['topics'].sort(key=lambda t: order.index(t['id']))  # the map's colours follow the list
    return templates.TemplateResponse(request, "topic_list.html", {**view, "sort": sortierung})


TREND_TERMS = 4
MIN_YEAR_SIZE = 20  # smaller years join the next one, a single leaflet would swing their share
MIN_SEMESTER = 5  # a semester with fewer dated leaflets gets no share: "1 of 1" is 100 %
MONTH_NAMES = ('Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember')
MAX_NUR = 700  # leaflet ids in an address (about 5 KB): the lines of a request are limited, 8 KB at most
MULTIPLE = '_mehrere'  # a leaflet of several of the issuers shown in a chart
MIN_ORG_SIZE = 10  # issuers with fewer leaflets get no share, "1 of 1 = 100 %" says nothing


def copy_key(item):
    return item['leaflet'].copy_group or -item['leaflet'].id


def unique(items):
    """One item per copy group (the one with the earliest year), so copies count once."""
    first = {}
    for item in items:
        key = copy_key(item)
        if key not in first or item['year'] < first[key]['year']:
            first[key] = item
    return list(first.values())


MAX_YEAR_BARS = 12  # more bars than this get too narrow in a topic row: then five-year spans


def topic_year_buckets(totals):
    """{year: label} for the bars of the topic rows: the years (small ones joined), or five-year spans ('1970–74')
    once the collection spans too many years for single bars."""
    buckets = year_buckets(totals)
    if len(set(buckets.values())) <= MAX_YEAR_BARS:
        return buckets
    return {y: f"{int(y) // 5 * 5}–{(int(y) // 5 * 5 + 4) % 100:02d}" if str(y).isdigit() else y for y in totals}


def year_buckets(totals):
    """{year: label}: a year with fewer than MIN_YEAR_SIZE leaflets joins the next ('1967/68')."""
    buckets, pending = {}, []
    for year in sorted(totals):
        pending.append(year)
        if sum(totals[y] for y in pending) >= MIN_YEAR_SIZE or year == max(totals):
            label = year if len(pending) == 1 else f"{pending[0]}/{year[2:]}"
            buckets.update(dict.fromkeys(pending, label))
            pending = []
    return buckets


def wilson_low(hits, total, z=1.96):
    """Lower end of the 95 % Wilson interval of hits out of total: a small group has a wide interval and a low end."""
    p = hits / total
    return (p + z * z / (2 * total) - z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))) / (1 + z * z / total)


def leaflet_forms(term, items):
    """Leaflet id -> the words of a single-word term that the title and text of any copy of it contain
    ("gesetz" also finds Hochschulgesetz). The copies are searched as well: one of them may be the only hit."""
    if ' ' in term or '"' in term:
        return {}
    groups = {i['leaflet'].copy_group for i in items if i['leaflet'].copy_group is not None}
    copies = defaultdict(list)  # copy group -> (leaflet id, title)
    for group, leaflet_id, title in session.query(Leaflet.copy_group, Leaflet.id, Leaflet.title).filter(Leaflet.copy_group.in_(groups)):
        copies[group].append((leaflet_id, title or ''))
    members = {i['leaflet'].id: copies.get(i['leaflet'].copy_group) or [(i['leaflet'].id, i['leaflet'].title or '')] for i in items}
    texts = defaultdict(list)
    for leaflet_id, text in session.query(Page.leaflet_id, Page.text).filter(Page.leaflet_id.in_([m[0] for ms in members.values() for m in ms])):
        texts[leaflet_id].append(text or '')
    wanted = search.variants(term)
    return {own: {w for w in set(re.findall(r"\w+", ' '.join(t for lid, title in ms for t in [title, *texts[lid]]).replace('- ', '').lower()))
                  if any(v in w for v in wanted)}
            for own, ms in members.items()}


def trend_url(terms, filters, ohne, tab=0):
    """The trends page for these terms, the tab of one of them open; `ohne` (term -> forms) are left out of the count of that term."""
    return '/trends?' + urlencode([('begriffe', ', '.join(terms)), *filters,
                                   *(('ohne', f"{t}:{f}") for t in terms for f in sorted(ohne.get(t.lower(), ()))),
                                   *([('tab', tab)] if tab else [])])


def semester(iso):
    """(year, 0 for the summer semester April-September or 1 for the winter semester October-March, which starts in that year)."""
    year, month = int(iso[:4]), int(iso[5:7])
    return (year, 0) if 4 <= month <= 9 else (year if month >= 10 else year - 1, 1)


def semester_label(sem):
    year, winter = sem
    return f"WS {year % 100:02}/{(year + 1) % 100:02}" if winter else f"SS {year % 100:02}"


TREND_CACHE = {}  # (term, filters, state of the database) -> (items, forms): switching a tab or a form does not search again


def database_stamp():
    """Changes with every commit to the database file (also in its journal)."""
    return tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in (DB_PATH, DB_PATH.with_name(DB_PATH.name + '-wal')))


def term_profile(term, filters, buckets, totals, org_totals, chosen, span, sem_totals, terms, ohne, partial):
    """Counts per year bucket, first and last dated leaflet, top issuers and topics of a term."""
    if not search.terms(term):
        return {'term': term, 'short': True}
    # the copy chosen for the totals, even if only another copy matches: copies differ in issuers
    key = (term.lower(), tuple(filters), database_stamp())
    if key not in TREND_CACHE:
        found = list({copy_key(i): chosen[copy_key(i)] for i in faceted_items(filters + [('q', term), ('duplikate', '1'), ('text', '1')])[0]}.values())
        if len(TREND_CACHE) >= 32:
            TREND_CACHE.clear()
        TREND_CACHE[key] = found, leaflet_forms(term, found)
    items, forms = TREND_CACHE[key]
    # a leaflet counts if it has a form that is not left out
    form_counts = Counter(f for fs in forms.values() for f in fs)
    left_out = ohne.get(term.lower(), set())
    if left_out:
        items = [i for i in items if forms[i['leaflet'].id] - left_out]
    counts = Counter(buckets[i['year']] for i in items)
    dated = sorted((i for i in items if i['leaflet'].date_iso), key=lambda i: i['leaflet'].date_iso)
    org_counts = Counter(o for i in items for o in i['orgs'] if o not in SPECIAL)
    orgs = org_counts.most_common()  # the page shows the first five and folds the rest
    unregistered = sum(NOT_IN_REGISTER in i['orgs'] for i in items)
    no_org = sum(NO_ORG in i['orgs'] for i in items)
    # issuers per year: each leaflet once, under the first of these issuers it has
    ranked = [o for o, _ in Counter(o for i in items for o in i['orgs'] if o != NO_ORG).most_common(5)]

    def stack(i):
        mine = [o for o in ranked if o in i['orgs']]
        return MULTIPLE if len(mine) > 1 else mine[0] if mine else None

    stacks = Counter((stack(i), buckets[i['year']]) for i in items)
    sems = Counter(semester(i['leaflet'].date_iso) for i in items if len(i['leaflet'].date_iso or '') >= 7)
    names = {o.id: o.name for o in session.query(Organization).filter(
        Organization.id.in_([o for o, _ in orgs] + ranked))}
    names[NOT_IN_REGISTER] = 'nicht im Register'
    topics = Counter(i['leaflet'].topic_id for i in items if i['leaflet'].topic_id).most_common(15)
    titles = {t.id: t.title for t in session.query(Topic).filter(Topic.id.in_([t for t, _ in topics]))}

    ids = ','.join(str(i['leaflet'].id) for i in items) or '0'
    scope = ('nur', ids) if left_out else ('q', term)  # with forms left out the list shows the leaflets that were counted

    def list_url(*pairs):
        return '/leaflets?' + urlencode(filters + [scope, *(() if left_out else (('text', '1'),)), *pairs])

    def year_url(bucket, *pairs):
        # a merged bucket cannot be a year filter: the list sorted by date starts with it
        return list_url(('jahr', bucket) if '/' not in bucket else ('sortierung', 'datum_auf'), *pairs)

    peak = max(((counts[b] / totals[b], b) for b in totals if totals[b]), default=(0, ''))
    top = [names.get(o, o) for o, _ in orgs[:3]]
    lead = f"{len(items)} {'Flugblatt' if len(items) == 1 else 'Flugblätter'}"
    if items:
        percent = f"{round(peak[0] * 100, 1):g}".replace('.', ',')
        lead += f". Höchster Anteil {peak[1]}: {percent} % ({counts[peak[1]]} von {totals[peak[1]]})"
    if top:
        lead += ". Am häufigsten von " + (', '.join(top[:-1]) + ' und ' + top[-1] if len(top) > 1 else top[0])
    return {
        'term': term, 'total': len(items), 'url': list_url(), 'lead': lead + '.', 'left_out_n': len(left_out),
        'counts': [counts[b] for b in totals],
        'shares': [round(counts[b] / totals[b] * 100, 1) for b in totals],
        'urls': [year_url(b) for b in totals],
        'by_org': [{'label': 'mehrere Herausgeber' if o == MULTIPLE else names.get(o, o) if o else 'andere', 'org': o,
                    'counts': [stacks[o, b] for b in totals],
                    'urls': [year_url(b, ('org', o)) if o and o != MULTIPLE else year_url(b) for b in totals]}
                   for o in ranked + [MULTIPLE, None]],
        # a semester cannot be filtered in the list: its bar opens the year, sorted by date
        # the share of the leaflets dated to that semester; one with too few dated leaflets has none (a gap, not a zero)
        'sems': {'counts': [sems[m] for m in span], 'shares': [round(sems[m] / sem_totals[m] * 100, 1) if sem_totals[m] >= MIN_SEMESTER else None for m in span],
                 'urls': [list_url(('jahr', str(m[0])), ('sortierung', 'datum_auf')) for m in span],
                 # hits dated only to the year, or not at all
                 'rest': len(items) - sum(sems.values())},
        'sem_dated': sum(sems.values()),
        'ids': {i['leaflet'].id for i in items},
        'forms': [{'label': f, 'count': n, 'off': f in left_out, 'title': f"in {n} Flugblättern",
                   'url': '/leaflets?' + urlencode(filters + [('q', f)]),
                   'toggle': trend_url(terms, filters, {**ohne, term.lower(): left_out ^ {f}}, terms.index(term))}
                  for f, n in form_counts.most_common(60)],
        'first': dated[0] if dated else None, 'last': dated[-1] if len(dated) > 1 else None,
        # one row per issuer: the hits, and the share of its own leaflets with the lower end of its interval (from MIN_ORG_SIZE leaflets)
        'org_max': max((o for o in (n / org_totals[o_id] for o_id, n in orgs if org_totals[o_id] >= MIN_ORG_SIZE)), default=1),
        'org_table': [{'label': names.get(o, o), 'count': n, 'url': list_url(('org', o)),
                       'total': org_totals[o] if org_totals[o] >= MIN_ORG_SIZE else 0,
                       'share': n / org_totals[o] if org_totals[o] >= MIN_ORG_SIZE else None,
                       'low': wilson_low(n, org_totals[o]) if org_totals[o] >= MIN_ORG_SIZE else None} for o, n in orgs],
        # what the issuer list leaves out
        'orgs_other': [{'label': label, 'url': url} for label, url in (
            (f"{unregistered} nicht im Register", list_url(('org', NOT_IN_REGISTER))),
            (f"{no_org} ohne Herausgeber", list_url(('org', NO_ORG))))
            if not label.startswith('0 ')],
        'topics': [{'label': titles.get(t, str(t)), 'count': n,
                    'url': list_url(('thema', str(t)))} for t, n in topics],
    }


@app.get("/trends")
def trends(request: Request, begriffe: str = ''):
    """Compares up to four search terms over the years, as share of the leaflets per year."""
    logger.info('Opening trends')
    terms = [t for t in (' '.join(t.split())[:search.MAX_QUERY] for t in begriffe.split(','))
             if t][:TREND_TERMS]
    filters = [(k, v) for k, v in list_params(request) if k in FACETS and k != 'jahr']
    everything = unique(faceted_items(filters)[0])
    buckets = year_buckets(Counter(i['year'] for i in everything))
    counts = Counter(buckets[i['year']] for i in everything)
    totals = {b: counts[b] for b in sorted(counts)}
    org_totals = Counter(o for i in everything for o in i['orgs'])
    labels = facet_labels()
    ohne = {}
    for value in request.query_params.getlist('ohne'):  # "term:form": that form is not counted for that term
        term, _, form = value.rpartition(':')
        if term and form:
            ohne.setdefault(term.lower(), set()).add(form.lower())
    chips = [{'label': short_topic_title(labels.get(k, str)(v)),
              'url': trend_url(terms, [p for p in filters if p != (k, v)], ohne)}
             for k, v in filters]
    chosen = {copy_key(i): i for i in everything}
    sem_totals = Counter(semester(i['leaflet'].date_iso) for i in everything if len(i['leaflet'].date_iso or '') >= 7)
    # the axis runs from the first to the last semester with enough dated leaflets; the thinner ones at the edges are not shown
    enough = [m for m in sem_totals if sem_totals[m] >= MIN_SEMESTER] or list(sem_totals)
    first, last = min(enough, default=(0, 0)), max(enough, default=(0, -1))
    span = [(y, w) for y in range(first[0], last[0] + 1) for w in (0, 1) if first <= (y, w) <= last]
    before, after = (sum(n for m, n in sem_totals.items() if m < first),
                     sum(n for m, n in sem_totals.items() if m > last))
    cut_note = ' und '.join(part for part in (f"{before} datierte Flugblätter vor {semester_label(first)}" if before else '',
                                              f"{after} datierte Flugblätter nach {semester_label(last)}" if after else '') if part)
    # the archive ends within the last semester: its share rests on part of it
    latest = max((i['leaflet'].date_iso for i in everything if len(i['leaflet'].date_iso or '') >= 7), default='')
    partial = bool(latest) and (latest[5:7] not in ('03', '09'))
    rows = [term_profile(t, filters, buckets, totals, org_totals, chosen, span, sem_totals, terms, ohne, partial) for t in terms]
    # what two terms have in common: the leaflets both counted
    together = []
    for a, b in combinations([r for r in rows if r.get('total')], 2):
        both = sorted(a['ids'] & b['ids'])
        together.append({'terms': (a['term'], b['term']), 'count': len(both),
                         'url': '/leaflets?' + urlencode(filters + [('nur', ','.join(map(str, both)) or '0')])})
    for row in rows:
        row['remove_url'] = trend_url([t for t in terms if t != row['term']], filters, ohne)
    chart = {'years': list(totals), 'totals': list(totals.values()),
             'sems': {'labels': [semester_label(m) + ('*' if partial and m == semester(latest) else '') for m in span],
                      'totals': [sem_totals[m] for m in span], 'gap': [sem_totals[m] < MIN_SEMESTER for m in span]},
             'terms': [{k: r.get(k) for k in ('term', 'counts', 'shares', 'urls', 'by_org', 'sems')} for r in rows],
             }
    return templates.TemplateResponse(
        request, "trends.html",
        {"tab": min(int(request.query_params.get('tab', '0')) if request.query_params.get('tab', '0').isdigit() else 0, max(len(rows) - 1, 0)),
         "cut_note": f"Im Semesterverlauf nicht gezeigt, zu wenige für einen Anteil: {cut_note}." if cut_note else '',
         "tab_urls": [trend_url(terms, filters, ohne, n) for n in range(len(rows))],
         "begriffe": ', '.join(terms), "filters": filters, "chips": chips, "rows": rows,
         "min_org_size": MIN_ORG_SIZE, "min_semester": MIN_SEMESTER,
         "partial_until": f"{MONTH_NAMES[int(latest[5:7]) - 1]} {latest[:4]}" if partial else '',
         "together": together, "chart": chart})


def candidate_title(topic_id):
    doc = topics.load(topics.CANDIDATE) or {"topics": []}
    return next((t["title"] for t in doc["topics"] if str(t["id"]) == topic_id), topic_id)


def facet_labels():
    """Display label per facet parameter, shared by the list and the trends page."""
    orgs = {o.id: o for o in session.query(Organization)}
    topics = {str(t.id): t for t in session.query(Topic)}
    return {
        'org': lambda o: {NO_ORG: 'kein Herausgeber erkannt', NOT_IN_REGISTER: 'nicht im Register'}.get(
            o, orgs[o].name if o in orgs else o),
        'thema': lambda t: 'ohne Thema' if t == NO_TOPIC else topics[t].title if t in topics else t,
        'typ': lambda t: DOC_TYPES.get(t, t),
        'datum': lambda d: DATE_TYPE_LABELS.get(d, d),
        'unsicher': lambda v: 'unsichere Themenzuordnung',
        'kandidat': lambda v: candidate_title(v),
        'q': lambda v: f"„{v}“",
    }


@app.get("/leaflets")
def leaflet_list(request: Request, ansicht: str = "liste", seite: str = "1", pro_seite: str = ""):
    logger.info('Opening leaflet list')
    params = list_params(request)
    selected = dict(params)
    picked = chosen_values(params)
    items, counts = faceted_items(params)
    view = ansicht if ansicht in ('kacheln', 'fundstellen') else 'liste'
    # the words to mark in the texts: those of the search field and of the rows that are not excluded
    marked = ' '.join([selected.get('q', '')] + [row[2] for row in map(search_row, (v for k, v in params if k == 's')) if row[0] != 'nicht'])
    found = passages(items, {**selected, 'q': marked}) if view == 'fundstellen' and marked else []
    # the counts, the CSV and the detail page's paging cover the whole selection, the page shows a part of it
    size = int(pro_seite) if pro_seite in map(str, PAGE_SIZES) else PAGE_SIZE
    pages = max(1, -(-len(items) // size))
    page = min(max(int(seite) if seite.isdigit() else 1, 1), pages)
    shown_items = items[(page - 1) * size:page * size]
    if view != 'fundstellen' and search.terms(marked):
        attach_passages(shown_items, marked, 35 if view == 'kacheln' else 70)
    elif view == 'liste':  # without a search the beginning of the text says what the leaflet is about
        previews = text_previews([i['leaflet'].id for i in shown_items])
        for item in shown_items:
            item['preview'] = shorten_preview(previews.get(item['leaflet'].id, ''))

    def shown(key):
        """Values of a facet with hits, plus the selected one."""
        return {v for v, n in counts[key].items() if n and v} | (
            set(picked.get(key, ())))

    def url(pairs):
        """List address for the parameter pairs, in the current view."""
        pairs = pairs + ([('ansicht', view)] if view != 'liste' else []) + ([('pro_seite', size)] if size != PAGE_SIZE else [])
        return '/leaflets' + ('?' + urlencode(pairs) if pairs else '')

    def toggle_url(key, value):
        """List address with `value` added to the values chosen for `key`, or removed if it is chosen."""
        return url([p for p in params if p != (key, value)] + ([] if value in picked.get(key, ()) else [(key, value)]))

    def facet(key, label_of, sub_of=lambda v: ''):
        """Entries of a facet list: the selected one first, 'none' last, else by count."""
        values = sorted(shown(key), key=lambda v: (v not in picked.get(key, ()), v in SPECIAL,
                                                   -counts[key][v], label_of(v).casefold()))
        return [{'label': label_of(v), 'sub': sub_of(v), 'count': counts[key][v],
                 'url': toggle_url(key, v), 'active': v in picked.get(key, ()),
                 'none': v in SPECIAL} for v in values]

    orgs = {o.id: o for o in session.query(Organization)}
    labels = facet_labels()

    axis = sorted({str(v.year) for v in session.query(Volume).filter_by(status=RELEASED)} | shown('jahr'))
    highest = max(counts['jahr'].values(), default=0) or 1
    facets = {
        'years': [{'year': y, 'count': counts['jahr'][y], 'url': toggle_url('jahr', y),
                   'height': round(counts['jahr'][y] / highest * 75),
                   'active': y in picked.get('jahr', ())} for y in axis],
        'orgs': facet('org', labels['org'], lambda o: orgs[o].full_name or '' if o in orgs else ''),
        # "uncertain" sits with the special entries of the topic list, it is a filter on the topic
        'topics': facet('thema', labels['thema']) + [{**e, 'none': True} for e in facet('unsicher', labels['unsicher'])],
        'types': facet('typ', labels['typ']),
        'series': facet('reihe', str),
        'dates': facet('datum', labels['datum']),
    }

    # chips above the results, each removes its own parameter
    # the search itself stands in the rows above the results, the chips are for the filters
    kinds = {'jahr': 'Jahr', 'org': 'Herausgeber', 'thema': 'Thema', 'typ': 'Typ', 'reihe': 'Reihe', 'datum': 'Datierung',
             'kandidat': 'Neues Thema, noch nicht übernommen'}
    groups = {}  # one chip per facet, its values joined by "oder", each with its own ×
    for k, v in params:
        if k not in ('q', 'feld', 's', 'sortierung', 'duplikate'):
            label = short_topic_title(labels['thema'](v)) if k == 'thema' else labels.get(k, str)(v)
            groups.setdefault(k, {'kind': kinds.get(k, ''), 'entries': []})['entries'].append(
                {'label': label, 'url': url([p for p in params if p != (k, v)])})
    active_filters = list(groups.values())
    one_row = [{'operator': '', 'field': selected.get('feld', ''), 'term': selected.get('q', '')}]
    search_lines = one_row + [dict(zip(('operator', 'field', 'term'), search_row(v))) for k, v in params if k == 's']
    reading = ''
    if len(search_lines) > 2:  # with three conditions the order of the connectives matters: show how they are read
        reading = search_lines[0]['term']
        for line in search_lines[1:]:
            reading = f"({reading} {line['operator'].upper()} {line['term']})"


    query_string = '?' + urlencode(params) if params else ''
    return templates.TemplateResponse(
        request, "leaflet_list.html",
        {"leaflets": shown_items, "count": len(items), "page": page, "pages": pages,
         "prev_url": url(params + [('seite', page - 1)]) if page > 1 else '',
         "next_url": url(params + [('seite', page + 1)]) if page < pages else '',
         "facets": facets, "show_duplicates": 'duplikate' in selected,
         "total": released_leaflets().filter(or_(Leaflet.copy_group.is_(None), Leaflet.canonical_leaflet_id == Leaflet.id)
                                                if 'duplikate' not in selected else True).count(),
         "hidden_params": [(k, v) for k, v in params if k in FACETS],
         "active_filters": active_filters, "reset_all_url": url([]),
         "clear_search_url": url([(k, v) for k, v in params if k not in ('q', 'feld', 's')]),
         "search_active": any(line['term'] for line in search_lines), "search_lines": search_lines, "reading": reading, "operators": [(k, k.upper()) for k in BOOLEAN],
         "selected_sort": selected.get('sortierung'),
         "selected_q": selected.get('q', ''),
         "q_short": bool(selected.get('q')) and not search.terms(selected['q']),
         "filtered": sum(k not in ('q', 'feld', 's', 'sortierung', 'duplikate') for k, _ in params),
         "view": view, "passages": found[:PASSAGE_LIMIT], "passage_count": len(found),
         "trends_url": '/trends?' + urlencode([('begriffe', selected.get('q', ''))] + [
             (k, v) for k, v in params if k in FACETS and k != 'jahr']),
         "switch_base": '/leaflets' + query_string + (('&' if params else '?') + f'pro_seite={size}' if size != PAGE_SIZE else ''),
         "size": size, "page_sizes": PAGE_SIZES,
         "detail_from": '?' + urlencode(params + ([('pro_seite', size)] if size != PAGE_SIZE else [])
                                        + ([('ansicht', view)] if view != 'liste' else []) + [('ergebnisse', '1')])})


PASSAGE_LIMIT = 500
PAGE_SIZE = 100
PAGE_SIZES = (25, 50, 100, 250, 500)


def passages(items, params):
    """Occurrences of the search terms in the OCR text of the items, by date unless sorted otherwise."""
    texts = search.ocr_texts(session, [text_id(i) for i in items])
    if not params.get('sortierung'):
        items = sorted(items, key=date_sort_key)
    return [{'item': item, 'n': n, 'left': left, 'hit': hit, 'right': right}
            for item in items
            for n, (left, hit, right) in enumerate(
                search.kwic(texts.get(text_id(item), ''), params['q']), start=1)]


PREVIEW_MIN = 40  # characters a block needs to count as running text
PREVIEW_CHARS = 180  # about two lines of the list
SPACED = re.compile(r'\b(?:[^\W\d_] ){2,}[^\W\d_]\b')  # "R o s s": letter-spaced typewriter lettering


def tidy_preview(text):
    """Typesetting of the recognised text made readable: spaced-out words joined, no space before a closing mark
    or after an opening bracket. Only the preview is changed, not the stored text."""
    text = SPACED.sub(lambda m: m.group().replace(' ', ''), text)
    text = re.sub(r'\s+([,;:.!?)\]])', r'\1', text)
    return re.sub(r'([(\[])\s+', r'\1', text)


def shorten_preview(text, width=PREVIEW_CHARS):
    """The text cut at a word boundary, without a dangling mark in front of the "…"."""
    if len(text) <= width:
        return text + ' …' if text.endswith(':') else text  # a colon announces what follows in the next block
    return text[:width].rsplit(' ', 1)[0].rstrip(' ,;:(-–') + ' …'
MAX_REPEATED = 0.5  # a block of which fewer words are different is a banner ("STREIK ?? STREIK !! STREIK ??")


def running_text(plain, title):
    """Whether a block reads as text: long enough, not a banner of repeated words, not the title again."""
    words = re.findall(r'\w+', plain.casefold())
    if len(plain) < PREVIEW_MIN or len(set(words)) < MAX_REPEATED * len(words):
        return False
    # spaced-out letters ("a k t i o n s") and strings like "aaaaa sssss" are lettering the recognition could not read
    if sum(map(len, words)) < 2.5 * len(words) or sum(len(w) > 2 and len(set(w)) == 1 for w in words) >= 3:
        return False
    shown, wanted = ' '.join(words), ' '.join(re.findall(r'\w+', (title or '').casefold()))
    return not wanted or SequenceMatcher(None, shown[:len(wanted)], wanted).ratio() < 0.85


def text_previews(leaflet_ids):
    """{leaflet id: text}: the first running text block (not a header, banner, footer or the title) on the first two
    pages of the leaflet; a leaflet without one has no preview."""
    pages = (session.query(Page.leaflet_id, Page.blocks, Leaflet.title).join(Leaflet, Leaflet.id == Page.leaflet_id)
             .filter(Page.leaflet_id.in_(leaflet_ids), Page.page_no <= Leaflet.start_page + 1).order_by(Page.page_no))
    found = {}
    for leaflet_id, blocks, title in pages:
        if leaflet_id in found:
            continue
        for block in blocks or []:
            plain = ' '.join(unescape(re.sub(r'<[^>]+>', ' ', block.get('html', ''))).split()).replace('- ', '')
            if block.get('type') in ('Text', 'ListGroup') and running_text(plain, title):
                found[leaflet_id] = tidy_preview(plain)
                break
    return found


def text_id(item):
    """The leaflet whose text matched: the item's own, or the other copy of its group that the search found."""
    return item.get('text_id', item['leaflet'].id)


# filters and sorting of the leaflet list; the detail page pages through the same selection
LIST_PARAMS = ('q', 'feld', 's', 'text', 'nur', 'org', 'jahr', 'typ', 'reihe', 'thema', 'datum', 'unsicher', 'sortierung', 'duplikate',
               'kandidat')  # kandidat: a topic of a new run that is not taken over yet


BOOLEAN = {'und': 'AND', 'oder': 'OR', 'nicht': 'NOT'}
MAX_ROWS = 8


def search_row(value):
    """(operator, field, term) of an extra search row "und|titel|streik", or None if it is not valid."""
    operator, _, rest = value.partition('|')
    field, _, term = rest.partition('|')
    term = ' '.join(term.split())[:search.MAX_QUERY]
    return (operator, field, term) if operator in BOOLEAN and (not field or field in search.FIELDS) and term else None


def list_params(request):
    """List parameters of the request as (key, value) pairs."""
    params = []
    for key, value in request.query_params.multi_items():
        if key == 'q':
            value = ' '.join(value.split())[:search.MAX_QUERY]
        if key == 's':  # further search rows
            row = search_row(value)
            value = '|'.join(row) if row and sum(k == 's' for k, _ in params) < MAX_ROWS else ''
        if key in LIST_PARAMS and value and (key != 'feld' or value in search.FIELDS):
            params.append((key, value))
    return params


def search_rows(params):
    """[(operator, index columns, term)]: the search field first, then the further rows."""
    one = dict(params)
    # feld: only that field; text=1 (trends page): not in the issuers' names
    first = search.FIELDS.get(one.get('feld')) or (('title', 'ocr_text') if one.get('text') else None)
    rows = [('AND', first, one['q'])] if one.get('q') else []
    for key, value in params:
        if key == 's':
            operator, field, term = search_row(value)
            rows.append((BOOLEAN[operator], search.FIELDS.get(field), term))
    return rows


def search_hits(query, rows):
    """Restricts `query` to the full-text hits for the search `rows`.

    Returns (query, ranked): with FTS hits the query also yields a rank column.
    Queries without a word of three characters cannot use the trigram index and
    fall back to a substring search in title and series.
    """
    match = search.combine([(operator, search.match_expression(term, columns)) for operator, columns, term in rows])
    if match:
        hits = search.hits_subquery(match)
        return (query.join(hits, hits.c.leaflet_id == Leaflet.id)
                .add_columns(hits.c.rank), True)
    pattern = search.like_pattern(rows[0][2])
    return query.filter(or_(Leaflet.title.ilike(pattern, escape='\\'),
                            Leaflet.series.ilike(pattern, escape='\\'))), False


def attach_passages(items, q, width=70):
    """Adds 'snippets' (all passages as safe HTML) and 'hits' (their number) to the items;
    hits outside the OCR text show its beginning."""
    texts = search.ocr_texts(session, [text_id(i) for i in items])
    for item in items:
        text = texts.get(text_id(item), '')
        found = search.kwic(text, q, width=width)  # two lines in the result list
        item['snippets'] = [search.passage_html(*p) for p in found] or [search.fallback_snippet(text)]
        item['hits'] = len(found)


DATE_TYPE_LABELS = {'issued': 'Erscheinungsdatum', 'event': 'Veranstaltungsdatum', 'undated': 'Undatiert'}

# facet filters of the list: parameter -> values of a list item
NO_ORG, NOT_IN_REGISTER, NO_TOPIC = 'keiner', 'nicht_im_register', 'keins'
SPECIAL = (NO_ORG, NOT_IN_REGISTER, NO_TOPIC)
FACETS = {
    'org': lambda item: item['orgs'],
    'jahr': lambda item: [item['year']],
    'typ': lambda item: [item['leaflet'].doc_type],
    'reihe': lambda item: [item['leaflet'].series],
    'thema': lambda item: [NO_TOPIC if item['leaflet'].topic_id is None
                           else str(item['leaflet'].topic_id)],
    'datum': lambda item: [item['leaflet'].date_type],
    'unsicher': lambda item: ['ja'] if item['leaflet'].topic_uncertain else [],
}


def filtered_items(params):
    return faceted_items(params)[0]


def chosen_values(params):
    """{facet: [values]} of the list parameters: several values of one facet are alternatives."""
    chosen = {}
    for k, v in params:
        if k in FACETS:
            chosen.setdefault(k, []).append(v)
    return chosen


def faceted_items(params):
    """(items, counts): the selection, and per facet the counts over the items that
    match all other filters, so each option shows what choosing it would give."""
    chosen = chosen_values(params)
    items = searched_items(params)

    def matches(item, skip=None):  # one value of each chosen facet is enough, every chosen facet must match
        return all(any(v in FACETS[k](item) for v in values) for k, values in chosen.items() if k != skip)

    counts = {key: Counter(value for item in items if matches(item, key)
                           for value in FACETS[key](item))
              for key in FACETS}
    return [item for item in items if matches(item)], counts


def main_copies(hits):
    """(the main copy of each group among the hits, once and in the order of the hits; {main id: id of the other copy
    whose text matched}, only where the main copy itself did not match)."""
    groups = {lf.copy_group for lf in hits if lf.copy_group}
    mains = {lf.copy_group: lf for lf in released_leaflets().filter(
        Leaflet.copy_group.in_(groups), Leaflet.canonical_leaflet_id == Leaflet.id)} if groups else {}
    listed, via, own = {}, {}, set()
    for lf in hits:
        main = mains.get(lf.copy_group, lf) if lf.copy_group else lf
        listed.setdefault(main.id, main)
        if lf.id == main.id:
            own.add(main.id)
        else:
            via.setdefault(main.id, lf.id)
    return list(listed.values()), {k: v for k, v in via.items() if k not in own}


def searched_items(params):
    """Items for the search and sort order of `params`; facets are left to the caller."""
    one = dict(params)
    rows = search_rows(params)
    query = released_leaflets()
    # a group of copies is listed once, by its main copy, unless all copies are asked for; a search looks in all
    # copies, so that a gap in the main copy's text does not hide the group (as on the trends page)
    through_copies = bool(rows) and not one.get('duplikate') and not one.get('nur')
    if not one.get('duplikate') and not through_copies:
        query = query.filter(or_(Leaflet.copy_group.is_(None), Leaflet.canonical_leaflet_id == Leaflet.id))

    ranked = False
    if rows:
        query, ranked = search_hits(query, rows)
    if one.get('kandidat', '').isdigit():  # the leaflets of a topic of a new run, before it is taken over
        query = query.filter(Leaflet.id.in_([lf.id for lf in topics.candidate_leaflets(int(one['kandidat']))[1]]))
    if one.get('nur'):  # exactly these leaflets (ids): the trends page lists what its charts counted
        query = query.filter(Leaflet.id.in_([int(n) for n in one['nur'].split(',') if n.isdigit()][:MAX_NUR]))

    sort = one.get('sortierung', '')
    if not sort and not ranked:  # without a search the list runs by date; "band" is the order of the archive
        sort = 'datum_auf'
    by_relevance = ranked and not sort
    order = [Volume.vz, Leaflet.start_page, Leaflet.id]
    if by_relevance:
        order = [literal_column('hits.rank')] + order
    found = query.order_by(*order).all()
    if ranked:
        found = [row[0] for row in found]
    matched = {}
    if through_copies:
        found, matched = main_copies(found)
    items = leaflet_items(found)
    for item in items:
        if item['leaflet'].id in matched:
            item['text_id'] = matched[item['leaflet'].id]
    # issuer facet values: register ids, NOT_IN_REGISTER for an unmatched issuer, NO_ORG for none
    orgs = {}
    for leaflet_id, org_id in (session.query(LeafletIssuer.leaflet_id, LeafletIssuer.org_id)
                               .filter(LeafletIssuer.role == 'issuer')):
        orgs.setdefault(leaflet_id, set()).add(org_id or NOT_IN_REGISTER)
    for item in items:
        item['orgs'] = orgs.get(item['leaflet'].id, {NO_ORG})
    if sort.startswith(('datum_', 'titel_')):
        key = date_sort_key if sort.startswith('datum_') else title_sort_key
        items.sort(key=key, reverse=sort.endswith('_ab'))
    return items


@app.get("/leaflets.csv")
def leaflet_list_csv(request: Request):
    """The leaflets of the list, with its filters and order, as a table for Excel or pandas."""
    ids = [item['leaflet'].id for item in filtered_items(list_params(request))]
    content = export.files(only=ids, pages=False, link=str(request.base_url).rstrip('/'))['flugblaetter.csv']
    filename = f"flugblaetter-liste-{datetime.date.today():%Y-%m-%d}.csv"
    return Response(content=content.encode('utf-8'), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/leaflets/{leaflet_id}")
def leaflet_detail(request: Request, leaflet_id: int,
                   bearbeiten: str | None = None):
    logger.info('Opening leaflet details')
    leaflet = leaflet_or_404(leaflet_id)
    edit = current_values(leaflet) if bearbeiten is not None else None
    return detail_page(request, leaflet, edit)


def detail_page(request, leaflet, edit=None, error=None):
    """Detail page; with `edit` (form values) the fields become inputs."""
    leaflet_id = leaflet.id
    rows = session.query(LeafletIssuer).filter_by(leaflet_id=leaflet_id).all()
    issuers = [i for i in rows if i.role == 'issuer']
    signatories = [i for i in rows if i.role == 'signatory']
    volume = session.get(Volume, leaflet.volume_id)

    issuer_display = []
    seen_org_ids = set()
    for i in issuers:
        if i.org_id:
            if i.org_id in seen_org_ids:
                continue
            seen_org_ids.add(i.org_id)
            org = session.get(Organization, i.org_id)
            issuer_display.append({'surface': org_label(org), 'short': org.name,
                                   'full': org.full_name, 'org_id': i.org_id})
        elif i.other_institution and session.get(Organization, i.other_institution):
            issuer_display.append({'surface': session.get(Organization, i.other_institution).name,
                                   'org_id': None, 'other_institution': True, 'printed': i.surface})
        else:
            issuer_display.append({'surface': i.surface, 'org_id': None})

    pages = page_range(leaflet.start_page, leaflet.end_page)

    page_rows = session.query(Page).filter_by(leaflet_id=leaflet_id) \
        .order_by(Page.page_no).all()

    pdf_path = volume_pdf(volume)
    has_pdf = pdf_path.is_file()
    page_list = []
    for i, p in enumerate(page_rows, start=1):
        width, height = (pdf_service.page_size(pdf_path, p.page_no)
                         if has_pdf else (None, None))
        page_list.append({'no': p.page_no, 'index': i,
                          'blocks': p.blocks or [],
                          'width': width, 'height': height})

    # long leaflets get a page strip, and an outline if the OCR found headings
    outline = []
    for p in page_list:
        for n, b in enumerate(p['blocks'], 1):
            text = re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', b.get('html', '')))).strip()
            if b.get('type') == 'SectionHeader' and text:
                level = re.match(r'<h([1-6])', b['html'].lstrip())
                outline.append({'text': text if len(text) <= 90 else text[:89] + '…', 'page': p['index'],
                                'target': f"{p['no']}-{n}", 'level': min(int(level.group(1)), 3) if level else 1})

    copies = []
    if leaflet.copy_group:
        rows = session.query(Leaflet, Volume).join(Volume).filter(
            Leaflet.copy_group == leaflet.copy_group,
            Leaflet.id != leaflet.id).order_by(Volume.vz, Leaflet.start_page)
        copies = [{'id': lf.id, 'label': f"{vol.label}, "
                   f"{page_range(lf.start_page, lf.end_page)}",
                   'main': lf.id == leaflet.canonical_leaflet_id}
                  for lf, vol in rows]

    members, candidates = copy_group_of(leaflet)  # the group with the letters of the comparison page
    letters = copy_letters(members, candidates)
    ordered = sorted(members + candidates, key=lambda lf: letters[lf.id])
    volume_of = {lf.id: session.get(Volume, lf.volume_id).label for lf in ordered}
    one_volume = len(set(volume_of.values())) == 1  # then the pages are enough: the volume stands in the row "Band"
    short = {i: label.split(' (')[0] for i, label in volume_of.items()}  # "Nr. 002 (1968)" -> "Nr. 002", if that tells them apart
    if len(set(short.values())) < len(set(volume_of.values())):
        short = volume_of
    group = [{'id': lf.id, 'letter': letters[lf.id], 'self': lf.id == leaflet.id, 'new': lf in candidates,
              'main': bool(lf.copies_checked) and lf.id == lf.canonical_leaflet_id,
              'label': page_range(lf.start_page, lf.end_page) if one_volume
              else f"{short[lf.id]}, {short_pages(lf)}"}
             for lf in ordered]

    # coming from a filtered list or from the result list itself (ergebnisse=1): page through those results, else
    # through the volume
    selection = list_params(request)
    from_results = 'ergebnisse' in request.query_params
    from_featured = 'auswahl' in request.query_params  # coming from the selection on the start page
    siblings = ([lf.id for lf in featured_leaflets()] if from_featured
                else [i['leaflet'].id for i in filtered_items(selection)] if selection or from_results else [])
    if leaflet.id not in siblings:
        selection, from_results, from_featured = [], False, False
        siblings = [row.id for row in session.query(Leaflet.id)
                    .filter_by(volume_id=leaflet.volume_id)
                    .order_by(Leaflet.start_page)]
    pos = siblings.index(leaflet.id)
    # the view of the list is carried along (the list checks the values), so that the way back leads to the same page
    shown = [(k, v) for k, v in request.query_params.items() if k in ('pro_seite', 'ansicht')]
    size = int(dict(shown).get('pro_seite', PAGE_SIZE)) if dict(shown).get('pro_seite') in map(str, PAGE_SIZES) else PAGE_SIZE
    on_page = 1 if dict(shown).get('ansicht') == 'fundstellen' else pos // size + 1
    pairs = selection + shown + ([('seite', on_page)] if on_page > 1 else [])
    back_url = '/leaflets' + ('?' + urlencode(pairs) if pairs else '') + f'#l{leaflet.id}' if from_results else ''
    chosen = dict(selection)
    org = session.get(Organization, chosen['org']) if 'org' in chosen else None
    chosen_topic = (session.query(Topic)
                    .filter(Topic.id == chosen['thema']).first()
                    if 'thema' in chosen else None)
    topic = None
    if leaflet.topic_id is not None:
        topic = session.get(Topic, leaflet.topic_id)
    selection_labels = (
        f"„{chosen['q']}“" if 'q' in chosen else None,
        DOC_TYPES.get(chosen.get('typ')),
        org_label(org) if org else {NO_ORG: 'ohne Herausgeber', NOT_IN_REGISTER: 'Herausgeber nicht im Register'}.get(chosen.get('org')),
        chosen.get('reihe'),
        short_topic_title(chosen_topic.title) if chosen_topic
        else 'ohne Thema' if chosen.get('thema') == NO_TOPIC else None,
        chosen.get('jahr'),
        f"neues Thema „{candidate_title(chosen['kandidat'])}“" if 'kandidat' in chosen else None,
    )

    data = {
        'id': leaflet.id,
        'title': leaflet.display_title,
        'title_from_series': not leaflet.title and bool(leaflet.series),
        'series': leaflet.series_label,
        'volume_vz': volume.vz,
        'draft': volume.status != RELEASED,
        'provenance_model': (volume.meta_model or '').split('/')[-1],
        'provenance_date': german_date(volume.meta_created),
        'ocr_label': ocr.describe(volume.ocr_mode, volume.ocr_created),
        'prev_id': siblings[pos - 1] if pos > 0 else None,
        'next_id': siblings[pos + 1] if pos + 1 < len(siblings) else None,
        'position': pos + 1,
        'in_volume': len(siblings),
        'qs': '?auswahl=1' if from_featured else '?' + urlencode(selection + (shown + [('ergebnisse', '1')] if from_results else [])) if selection or from_results else '',
        'featured': from_featured,
        'back_url': back_url,
        'selection': ' · '.join(filter(None, selection_labels)),
        'highlight': [v for t in search.terms(chosen.get('q', '')) for v in search.variants(t)],
        'volume': volume.name if volume else '',
        'volume_year': volume.year if volume else None,
        'date_text': leaflet.date_text,
        'date_iso': leaflet.date_iso,
        'date': iso_to_text(leaflet.date_iso),
        'date_type': leaflet.date_type,
        'received': iso_to_text(leaflet.received_date),
        'received_uncertain': leaflet.received_uncertain,
        'evidence': {
            'Titel': evidence_items([(leaflet.title_blocks, leaflet.title_quote)]),
            'Datum': evidence_items([(leaflet.date_blocks, leaflet.date_quote)]),
            'Reihe': evidence_items([(leaflet.series_blocks, leaflet.series_quote)]),
            'Eingang im Archiv': evidence_items([(leaflet.received_blocks, leaflet.received_quote)]),
            'Herausgeber': evidence_items([(i.blocks, i.quote) for i in issuers]),
            'Unterzeichnende': evidence_items([(i.blocks, i.quote) for i in signatories]),
        },
        'doc_type': DOC_TYPES.get(leaflet.doc_type, leaflet.doc_type),
        'topic': topic.title if topic else None,
        'topic_note': TOPIC_TITLE_NOTES.get(topic.source) if topic else None,
        'topic_uncertain': leaflet.topic_uncertain,
        'pages': pages,
        'start_page': leaflet.start_page,
        'issuers': issuer_display,
        'signatories': [{'name': i.surface,
                         'details': '; '.join(d for d in (i.function, i.marker) if d)}
                        for i in signatories],
        'page_list': page_list,
        'outline': outline if len(outline) >= 3 and len(page_list) >= 4 else [],
        'has_pdf': has_pdf,
        'copies': copies,
        'group': group if len(group) > 1 else [],
        'copy_main': leaflet.canonical_leaflet_id == leaflet.id,  # the main copy of its group
        'copies_checked': bool(leaflet.copies_checked),
        'corrected': leaflet.corrected or [],
        'automatic': automatic_text(leaflet),
    }

    return templates.TemplateResponse(
        request, "leaflet_details.html",
        {"leaflet": data, "edit": edit, "error": error, "hints": hint_queue(leaflet, volume, reviewing(request)), **(edit_choices() if edit else {})},
        status_code=400 if error else 200)


def leaflet_or_404(leaflet_id):
    leaflet = session.get(Leaflet, leaflet_id)
    if leaflet is None:
        raise HTTPException(404)
    return leaflet


def current_values(leaflet):
    issuers, seen = [], set()
    for i in session.query(LeafletIssuer).filter_by(
            leaflet_id=leaflet.id, role='issuer').order_by(LeafletIssuer.id):
        if i.org_id and i.org_id not in seen:
            seen.add(i.org_id)
            issuers.append({'org': i.org_id, 'name': org_label(session.get(Organization, i.org_id)),
                            'blocks': list(i.blocks or [])})
    signatories = [{'name': i.surface,
                    'details': '; '.join(d for d in (i.function, i.marker) if d),
                    'blocks': list(i.blocks or [])}
                   for i in session.query(LeafletIssuer).filter_by(
                       leaflet_id=leaflet.id, role='signatory').order_by(LeafletIssuer.id)]
    return {'title': leaflet.title or '', 'title_blocks': list(leaflet.title_blocks or []),
            'date_iso': leaflet.date_iso or '', 'date_type': leaflet.date_type or 'undated',
            'date_blocks': list(leaflet.date_blocks or []),
            'series': leaflet.series or '', 'issue': leaflet.issue or '',
            'series_blocks': list(leaflet.series_blocks or []),
            'received_iso': leaflet.received_date or '', 'received_blocks': list(leaflet.received_blocks or []),
            'doc_type': leaflet.doc_type or 'unklar', 'issuers': issuers,
            'signatories': signatories}


def edit_choices():
    """The suggestions of the issuer and series inputs of the metadata form."""
    return {'org_names': [org_label(o) for o in sorted(session.query(Organization), key=org_sort_key)],
            'series_names': sorted({s for (s,) in session.query(Leaflet.series) if s})}


def segment(leaflet):
    """Key of a correction line: the leaflet's exact page range."""
    return {'volume': session.get(Volume, leaflet.volume_id).stem,
            'start_page': leaflet.start_page, 'end_page': leaflet.end_page}


def save_corrections(leaflet, changes):
    """Append (field, value, evidence blocks) to corrections.jsonl and apply them."""
    entries = [{**segment(leaflet), 'field': f, 'value': v,
                **({'blocks': blocks} if blocks else {})}
               for f, v, blocks in changes]
    corrections.append(CORRECTIONS, entries)
    corrections.apply(leaflet, entries)
    session.commit()


def read_metadata_form(leaflet, raw):
    """(values, error) of a submitted metadata form; raw: the parsed body, field -> list of values."""

    def blocks(value):
        # evidence picked in the scan: block ids on this leaflet's pages only
        return [b for b in value.split()
                if re.fullmatch(r"\d+-\d+", b)
                and leaflet.start_page <= int(b.split('-')[0]) <= leaflet.end_page]

    def rows(*names):
        # repeated row fields arrive as parallel lists; rows without a first value are dropped
        return [[v.strip() for v in row] for row in zip(*(raw.get(n, []) for n in names))
                if row[0].strip()]

    form = {k: raw.get(k, [''])[0].strip()
            for k in ('title', 'date', 'date_type', 'series', 'issue', 'doc_type')}
    for k in ('title', 'date', 'series', 'received'):
        form[f'{k}_blocks'] = blocks(raw.get(f'{k}_blocks', [''])[0])
    form['received'] = raw.get('received', [''])[0].strip()
    form['received_iso'] = german_to_iso(form['received']) if form['received'] else ''
    if 'received' not in raw:  # a form without the field leaves the stamp as it is
        form['received_iso'], form['received_blocks'] = leaflet.received_date or '', list(leaflet.received_blocks or [])
    org_ids = {org_label(o): o.id for o in session.query(Organization)}
    form['issuers'] = [{'org': org_ids.get(name), 'name': name, 'blocks': blocks(b)}
                       for name, b in rows('issuer', 'issuer_blocks')]
    form['signatories'] = [{'name': name, 'details': details, 'blocks': blocks(b)}
                           for name, details, b in rows('signatory_name', 'signatory_details',
                                                        'signatory_blocks')]
    form['date_iso'] = german_to_iso(form['date']) if form['date'] else ''
    if not form['date']:
        form['date_type'] = 'undated'

    unknown = [i['name'] for i in form['issuers'] if not i['org']]
    if form['date_iso'] is None:
        error = "Datum bitte als TT.MM.JJJJ, MM.JJJJ oder JJJJ angeben, z. B. 17.12.1969."
    elif form['received_iso'] is None:
        error = "Eingang bitte als TT.MM.JJJJ, MM.JJJJ oder JJJJ angeben."
    elif form['date_iso'] and form['date_type'] == 'undated':
        error = "Bitte die Art des Datums wählen."
    elif unknown:
        error = f"Nicht im Register: {', '.join(unknown)}. Bitte einen Eintrag aus der Liste wählen."
    elif form['date_type'] not in DATE_TYPES or form['doc_type'] not in DOC_TYPES:
        error = "Ungültige Auswahl."
    else:
        error = None
    return form, error


def save_metadata(leaflet, form):
    """Appends the fields that differ from the current values to corrections.jsonl and applies them."""
    # a field counts as corrected when its value or its evidence changed
    old = current_values(leaflet)
    changes = []
    for field, keys in (('title', ['title']), ('date', ['date_iso', 'date_type']),
                        ('series', ['series', 'issue']), ('received', ['received_iso'])):
        keys = keys + [f'{field}_blocks']
        if [form[k] for k in keys] != [old[k] for k in keys]:
            value = {'date': {'iso': form['date_iso'], 'type': form['date_type']},
                     'series': {'name': form['series'], 'issue': form['issue']},
                     'received': form['received_iso']}.get(field, form.get(field))
            changes.append((field, value, form[f'{field}_blocks']))
    if form['doc_type'] != old['doc_type']:
        changes.append(('doc_type', form['doc_type'], []))
    issuers = lambda items: {i['org']: i['blocks'] for i in items}
    if issuers(form['issuers']) != issuers(old['issuers']):
        changes.append(('issuers', [{'org': o, 'blocks': b}
                                    for o, b in issuers(form['issuers']).items()], []))
    if form['signatories'] != old['signatories']:
        changes.append(('signatories', form['signatories'], []))
    if changes:
        save_corrections(leaflet, changes)


@app.post("/leaflets/{leaflet_id}/bearbeiten")
async def leaflet_save(request: Request, leaflet_id: int):
    leaflet = leaflet_or_404(leaflet_id)
    form, error = read_metadata_form(leaflet, parse_qs((await request.body()).decode(), keep_blank_values=True))
    if error:
        return detail_page(request, leaflet, form, error)
    save_metadata(leaflet, form)
    return back_to(request, leaflet_id)


def revert_metadata(leaflet, field):
    """Back to the automatic values, for one field or all ("revert" line)."""
    if field != 'all' and field not in corrections.FIELDS:
        raise HTTPException(400)
    key = segment(leaflet)
    corrections.append(CORRECTIONS, [{**key, 'field': 'revert', 'value': field}])
    reset_leaflet(leaflet)
    corrections.apply(leaflet, corrections.by_segment(corrections.load(CORRECTIONS)).get(
        tuple(key.values()), []))
    session.commit()


@app.post("/leaflets/{leaflet_id}/zuruecksetzen")
async def leaflet_revert(request: Request, leaflet_id: int):
    leaflet = leaflet_or_404(leaflet_id)
    revert_metadata(leaflet, parse_qs((await request.body()).decode()).get('field', ['all'])[0])
    return back_to(request, leaflet_id)


def back_to(request, leaflet_id):
    query = request.url.query
    return RedirectResponse(f"/leaflets/{leaflet_id}" + (f"?{query}" if query else ''),
                            status_code=303)


COPY_STATES = {'offen': 'Nicht geprüft', 'geprueft': 'Geprüft', 'neu': 'Neue Treffer'}


def copy_rows():
    """One row per group of copies in archive order: its main copy's id, title, review state and members."""
    groups = {}
    for leaflet, volume in session.query(Leaflet, Volume).join(Volume).filter(or_(
            Leaflet.copy_group.isnot(None), Leaflet.copy_candidate_of.isnot(None))).order_by(
            Volume.vz, Leaflet.start_page):
        if leaflet.copy_group:
            groups.setdefault(leaflet.copy_group, {'members': [], 'new': 0, 'hit_vz': set()})['members'].append((leaflet, volume))
        if leaflet.copy_candidate_of:
            group = groups.setdefault(leaflet.copy_candidate_of, {'members': [], 'new': 0, 'hit_vz': set()})
            group['new'] += 1
            group['hit_vz'].add(volume.vz)
    rows = []
    for key, group in groups.items():
        main = next(lf for lf, _ in group['members'] if lf.id == lf.canonical_leaflet_id)
        first, volume = group['members'][0]
        rows.append({'group': key, 'id': main.id, 'title': main.display_title, 'new': group['new'],
                     'state': 'neu' if group['new'] else 'geprueft' if main.copies_checked else 'offen',
                     'order': (volume.vz, first.start_page), 'volumes': {v.vz for _, v in group['members']} | group['hit_vz'],
                     'anchors': [(v.stem, lf.start_page, lf.end_page) for lf, v in group['members']],
                     'labels': [f"{v.label}, {page_range(lf.start_page, lf.end_page)}" + (' (Hauptexemplar)' if lf is main and main.copies_checked else '')
                                for lf, v in group['members']]})
    return rows


def reviewing(request):
    """The released volume whose step 6 was opened last: its pages get the review bar too."""
    value = request.cookies.get('pruefen', '')
    return int(value) if value.isdigit() else 0


def review_queue(leaflet, open_vz=0):
    """The groups still to check, seen from the leaflet's group: the main copies of the previous and the next
    one, the position of this group among them (None if it is checked) and their number. A group with a leaflet
    of a volume not released yet goes through that volume's groups only: they are checked in its step 6."""
    rows = copy_rows()
    key = leaflet.copy_candidate_of or leaflet.copy_group
    here = next((i for i, r in enumerate(rows) if r['group'] == key), len(rows))
    drafts = {vz for (vz,) in session.query(Volume.vz).filter(Volume.status != RELEASED)}
    band = min(rows[here]['volumes'] & (drafts | {open_vz}), default=0) if here < len(rows) else 0
    if band:
        rows = [r for r in rows if band in r['volumes']]
        here = next(i for i, r in enumerate(rows) if r['group'] == key)
    todo = lambda r: r['state'] != 'geprueft'
    before, after = [r for r in rows[:here] if todo(r)], [r for r in rows[here + 1:] if todo(r)]
    current = here < len(rows) and todo(rows[here])
    return {'previous': before[-1]['id'] if before else None, 'next': after[0]['id'] if after else None,
            'position': len(before) + 1 if current else None, 'total': len(before) + len(after) + current, 'band': band}


def hint_queue(leaflet, volume, open_vz=0):
    """For a leaflet of a volume not released yet: its place among the leaflets the checks remarked on."""
    if volume.status == RELEASED and volume.vz != open_vz:
        return None
    flagged = metadata.flagged_leaflets(volume)
    ids = [lf.id for lf, _, seen in flagged if not seen]  # the ones still to look at
    mine = next((f for f in flagged if f[0].id == leaflet.id), None)
    here = ids.index(leaflet.id) if leaflet.id in ids else None
    after = [i for i in ids if i > leaflet.id] if here is None else ids[here + 1:]  # ids follow the pages
    before = [i for i in ids if i < leaflet.id] if here is None else ids[:here]
    return {'vz': volume.vz, 'total': len(ids), 'position': None if here is None else here + 1,
            'texts': mine[1] if mine else [], 'flagged': bool(mine), 'seen': bool(mine and mine[2]),
            'previous': before[-1] if before else None, 'next': after[0] if after else None}


@app.post("/leaflets/{leaflet_id}/hinweis")
async def hint_seen(request: Request, leaflet_id: int):
    """"Passt so" for the remarks of the checks on a leaflet of a volume not released yet, and on to the next one."""
    leaflet = leaflet_or_404(leaflet_id)
    volume = session.get(Volume, leaflet.volume_id)
    if volume.status == RELEASED and volume.vz != reviewing(request):
        raise HTTPException(404)
    seen = parse_qs((await request.body()).decode()).get('seen', ['1'])[0] == '1'
    queue = hint_queue(leaflet, volume, reviewing(request))
    metadata.mark_seen(volume, leaflet, seen)
    following = queue['next'] or queue['previous']
    if not seen:
        return RedirectResponse(f"/leaflets/{leaflet_id}", status_code=303)
    return RedirectResponse(f"/leaflets/{following}" if following else f"/import/{volume.vz}?schritt=pruefen", status_code=303)


def latest_reviews():
    """anchor -> the newest review in force that saw it."""
    lines = corrections.load(COPY_DECISIONS)
    reverted = {e['revert'] for e in lines if 'revert' in e}
    latest = {}
    for e in sorted((e for e in lines if 'revert' not in e and e['at'] not in reverted), key=lambda e: e['at']):
        for a in e['members'] + e['rejected']:
            latest[copy_decisions.anchor(a)] = e
    return latest


def separated_rows(latest):
    """One row per leaflet that the review in force split off its group: the leaflet, the ones it was split from, the review date."""
    leaflets = {(v.stem, lf.start_page, lf.end_page): (lf, v) for lf, v in session.query(Leaflet, Volume).join(Volume)}

    def card(a):
        lf, v = leaflets[a]
        return {'id': lf.id, 'leaflet': lf, 'label': f"{v.label}, {page_range(lf.start_page, lf.end_page)}",
                'order': (v.vz, lf.start_page)}
    return [{**card(a), 'state': 'getrennt', 'at': e['at'],
             'from': [card(m) for m in map(copy_decisions.anchor, e['members']) if m in leaflets]}
            for a, e in latest.items() if a in leaflets and a in map(copy_decisions.anchor, e['rejected'])]


def review_date(at):
    """In German time; a stamp without zone is UTC, the clock of the container that wrote it."""
    t = datetime.datetime.fromisoformat(at)
    t = (t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)).astimezone(LOCAL)
    return t.strftime("%d.%m.%Y, %H:%M")


REVIEW_KINDS = {**COPY_STATES, 'getrennt': 'Getrennt'}
REVIEW_SORTS = {'': 'Reihenfolge im Archiv', 'neu': 'Prüfdatum, neueste zuerst', 'alt': 'Prüfdatum, älteste zuerst'}


@app.get("/exemplare")
def copy_list(request: Request, status: str = '', sortierung: str = '', band: int = 0):
    """All groups of copies with the state of their review; each opens its comparison page. A leaflet that a
    review split off is listed as checked; the checked rows can be sorted by review date. band= keeps the
    groups with a copy in that volume."""
    latest = latest_reviews()
    rows = [r for r in copy_rows() if not band or band in r['volumes']]
    for r in rows:
        r['at'] = r['state'] == 'geprueft' and max((latest[a]['at'] for a in r['anchors'] if a in latest), default=None)
    first = next((r['id'] for r in rows if r['state'] != 'geprueft'), None)
    rows = sorted(rows + [r for r in separated_rows(latest) if not band or r['order'][0] == band], key=lambda r: r['order'])
    for r in rows:
        r['date'] = r['at'] and review_date(r['at'])
    checked = lambda r: r['state'] in ('geprueft', 'getrennt')
    counts = Counter('geprueft' if checked(r) else r['state'] for r in rows)
    if not status and counts['offen']:  # without a choice the groups still to review come first
        status = 'offen'
    shown = [r for r in rows if r['state'] == status or status == 'geprueft' and checked(r)] if status in COPY_STATES else rows
    if status == 'geprueft' and sortierung in ('neu', 'alt'):
        shown.sort(key=lambda r: r['at'] or '', reverse=sortierung == 'neu')
    return templates.TemplateResponse(
        request, "copy_list.html",
        {"rows": shown, "total": len(rows), "counts": counts, "states": COPY_STATES, "kinds": REVIEW_KINDS,
         "sorts": REVIEW_SORTS, "status": status, "sort": sortierung, "first": first, "band": band})


def copy_group_of(leaflet):
    """(members, candidates) of the group the leaflet belongs to, or may join as a new hit."""
    group = leaflet.copy_candidate_of or leaflet.copy_group
    if not group:
        return [], []

    def rows(column):
        return session.query(Leaflet).join(Volume).filter(column == group).order_by(
            Volume.vz, Leaflet.start_page).all()
    return rows(Leaflet.copy_group), rows(Leaflet.copy_candidate_of)


def deviating(cards, key):
    """Ids of the copies whose value differs from the most common one; all of them if two values tie.
    A missing value contradicts nothing, so copies without one are left out."""
    cards = [c for c in cards if c[key]]
    counts = Counter(c[key] for c in cards).most_common()
    if len(counts) < 2:
        return set()
    if counts[0][1] == counts[1][1]:
        return {c['id'] for c in cards}
    return {c['id'] for c in cards if c[key] != counts[0][0]}


TAG = re.compile(r'(<[^>]*>)')
WORD = re.compile(r'\S+')
MAX_DIFF_WORDS = 4000  # the word comparison grows quadratically; longer texts are shown unmarked


def block_words(html_text):
    """The words of the text nodes of one OCR block (its html is already sanitized)."""
    return [w for part in TAG.split(html_text) if not part.startswith('<') for w in WORD.findall(part)]


def word_key(word):
    """Words are compared without case and punctuation."""
    return re.sub(r'\W+', '', unescape(word)).casefold() or word


GAP = '<mark class="gap" data-diff="{}" title="Im anderen Exemplar nicht erkannt">∅</mark>'


def mark_block(html_text, start, marks, gaps):
    """The block's html with the words whose running index is in `marks` wrapped in <mark>, tagged with the
    number of their deviation. `gaps` puts a gap marker before a word: the other copy has words here."""
    index = start
    out = []
    for part in TAG.split(html_text):
        if part.startswith('<'):
            out.append(part)
            continue

        def wrap(match):
            nonlocal index
            i, index = index, index + 1
            word = f'<mark data-diff="{marks[i]}">{match.group()}</mark>' if i in marks else match.group()
            return (GAP.format(gaps[i]) + ' ' if i in gaps else '') + word
        out.append(WORD.sub(wrap, part))
    return ''.join(out), index


def word_units(words):
    """[(key, display indices)]: a word hyphenated at the line end joins the next word, so that
    'Literaturwissen- schaften' and 'Literaturwissenschaften' are the same."""
    units, i = [], 0
    while i < len(words):
        word = words[i]
        if i + 1 < len(words) and len(word) > 1 and word.endswith('-') and word[-2].isalnum():
            units.append((word_key(word[:-1]) + word_key(words[i + 1]), [i, i + 1]))
            i += 2
        else:
            units.append((word_key(word), [i]))
            i += 1
    return units


def prepare_words(blocks):
    """The words of one leaflet's OCR blocks: their units (see word_units), the block of each word, the evidence ids."""
    words = [w for _, _, b in blocks for w in block_words(b['html'])]
    return {'blocks': blocks, 'words': words, 'units': word_units(words),
            'owner': [i for i, (_, _, b) in enumerate(blocks) for _ in block_words(b['html'])],
            'ids': [f"{page_no}-{number}" for page_no, number, _ in blocks]}  # evidence image ids


def word_diff(left, right):
    """Compares two prepared leaflets: per side the words of a deviation and the places where only the other has words
    (word index -> number of the deviation), the number of deviations, and per side which block of the other leaflet
    holds most of the matching words of each block."""
    sides = (left, right)
    marks, gaps, votes, count = [{}, {}], [{}, {}], [defaultdict(Counter), defaultdict(Counter)], 0

    def first(side, n):  # the first word of a unit; the end of the text for the unit after the last
        units = sides[side]['units']
        return units[n][1][0] if n < len(units) else len(sides[side]['words'])
    if max(len(left['words']), len(right['words'])) <= MAX_DIFF_WORDS:
        keys = [[key for key, _ in s['units']] for s in sides]
        for tag, i1, i2, j1, j2 in SequenceMatcher(None, keys[0], keys[1], autojunk=False).get_opcodes():
            if tag == 'equal':
                for k in range(i2 - i1):
                    a, b = first(0, i1 + k), first(1, j1 + k)
                    votes[0][left['owner'][a]][right['owner'][b]] += 1
                    votes[1][right['owner'][b]][left['owner'][a]] += 1
                continue
            count += 1
            for side, (lo, hi) in enumerate(((i1, i2), (j1, j2))):
                for n in range(lo, hi):
                    marks[side].update({d: count for d in sides[side]['units'][n][1]})
            if i1 == i2:
                gaps[0][first(0, i1)] = count
            if j1 == j2:
                gaps[1][first(1, j1)] = count
    return marks, gaps, votes, count


def render_blocks(prep, marks, gaps, partners):
    """The blocks of a prepared leaflet as rows: the marked words in the html, the gap markers, and for each other
    leaflet (`partners`: column, its evidence ids, the votes) the block that holds most of the matching words."""
    index, rows = 0, []
    for i, (page_no, number, block) in enumerate(prep['blocks']):
        html_text, index = mark_block(block['html'], index, marks, gaps)
        rows.append({'page': page_no, 'type': block['type'], 'html': html_text, 'marked': '<mark' in html_text,
                     'id': prep['ids'][i], 'box': block.get('box'), 'partners': {col: ids[top[0][0]] for col, ids, votes in partners
                                                        if (top := votes[i].most_common(1))}})
    if index in gaps and rows:  # words of the other copy at the very end
        head, _, tail = rows[-1]['html'].rpartition('</')
        rows[-1]['html'] = f"{head} {GAP.format(gaps[index])}</{tail}" if head else rows[-1]['html']
        rows[-1]['marked'] = True
    return rows


def ocr_pair(left, right):
    """The OCR blocks of two copies, structured. The words of a deviation are marked on both sides and carry its
    number; where only the other copy has words, a gap marker stands. Each block names its partner, the
    block of the other copy that holds most of its matching words."""
    a, b = prepare_words(left), prepare_words(right)
    marks, gaps, votes, count = word_diff(a, b)
    return [{'blocks': render_blocks(prep, marks[side], gaps[side], [(1 - side, other['ids'], votes[side])]),
             'differs': len(marks[side]), 'words': len(prep['words']), 'diffs': count}
            for side, (prep, other) in enumerate(((a, b), (b, a)))]


def ocr_group(block_lists):
    """The OCR blocks of three or more copies. Every pair is compared; a word is marked in a copy if it deviates there from
    more than half of the others, so the odd one out is marked and not the rest (likewise a gap). A block names its partner
    block in each of the other copies."""
    preps = [prepare_words(blocks) for blocks in block_lists]
    n = len(preps)
    marked, gapped, votes = [Counter() for _ in preps], [Counter() for _ in preps], {}
    for i in range(n):
        for j in range(i + 1, n):
            marks, gaps, pair_votes, _ = word_diff(preps[i], preps[j])
            for side, k in enumerate((i, j)):
                marked[k].update(dict.fromkeys(marks[side], 1))
                gapped[k].update(dict.fromkeys(gaps[side], 1))
            votes[i, j], votes[j, i] = pair_votes
    sides = []
    for i, prep in enumerate(preps):
        marks = {k: 1 for k, c in marked[i].items() if 2 * c > n - 1}
        gaps = {k: 1 for k, c in gapped[i].items() if 2 * c > n - 1}
        partners = [(j, preps[j]['ids'], votes[i, j]) for j in range(n) if j != i]
        sides.append({'blocks': render_blocks(prep, marks, gaps, partners), 'differs': len(marks), 'words': len(prep['words']),
                      'diffs': sum(1 for k in marks if k - 1 not in marks) + len(gaps)})
    return sides


def copy_blocks(leaflet):
    """(page number, block number on the page, OCR block) of the leaflet's pages, pictures left out."""
    pages = session.query(Page).filter_by(leaflet_id=leaflet.id).order_by(Page.page_no)  # indexed
    return [(p.page_no, number, b) for p in pages for number, b in enumerate(p.blocks or [], 1)
            if b.get('type') != 'Picture']


COPY_MESSAGES = {'angaben': 'Metadaten aktualisiert.', 'gespeichert': 'Prüfung gespeichert.',
                 'zurueckgenommen': 'Prüfung zurückgenommen, es gilt wieder der automatische Vorschlag.',
                 'getrennt': 'Als verschiedene Flugblätter gespeichert.'}


def shorten(cards):
    """Sets the short name: the page range alone when all copies are in one volume (said once on the page)."""
    same = len({c['volume'] for c in cards}) == 1
    for c in cards:
        c['label'] = f"{c['volume']}, {c['range']}"
        c['short'] = c['range'] if same else c['label']
    return same


TAKE_KEYS = {'title': ['title'], 'date': ['date_iso', 'date_type'], 'series': ['series', 'issue'],
             'doc_type': ['doc_type'], 'issuers': ['issuers'], 'signatories': ['signatories'],
             'received': ['received_iso']}


def field_text(values, field):
    """A field of current_values as shown, for comparing leaflets."""
    if field == 'date':
        return ' '.join(filter(None, [german_date(values['date_iso']), DATE_TYPES.get(values['date_type'], '')
                                      if values['date_iso'] else '']))
    if field == 'series':
        return ' '.join(filter(None, [values['series'], values['issue']]))
    if field == 'received':
        return german_date(values['received_iso'])
    if field == 'doc_type':
        return '' if values['doc_type'] == 'unklar' else DOC_TYPES.get(values['doc_type'], '')
    if field in ('issuers', 'signatories'):
        return ', '.join(i['name'] for i in values[field])
    return values[field]


def field_blocks(values, field):
    if field in ('issuers', 'signatories'):
        return [b for i in values[field] for b in i['blocks']]
    return values.get(f'{field}_blocks', [])


def copy_letters(members, candidates):
    """A, B, C ... for the leaflets of a group in archive order, new hits last. A letter stays with its leaflet
    when the main copy changes."""
    return {lf.id: chr(65 + i) for i, lf in enumerate(members + candidates)}


def copy_card(leaflet, main_id):
    volume = session.get(Volume, leaflet.volume_id)
    values = current_values(leaflet)
    return {'volume': volume.label, 'range': page_range(leaflet.start_page, leaflet.end_page), 'id': leaflet.id, 'page': leaflet.start_page, 'pages': leaflet.end_page - leaflet.start_page + 1,
            'main': leaflet.id == main_id,
            'title': leaflet.title or '', 'date': iso_to_text(leaflet.date_iso) or '',
            'issuers': ', '.join(i['name'] for i in values['issuers']),
            'signatories': ', '.join(i['name'] for i in values['signatories']),
            'series': leaflet.series_label or '', 'received': iso_to_text(leaflet.received_date) or ''}


@app.get("/leaflets/{leaflet_id}/exemplare")
def copy_page(request: Request, leaflet_id: int, meldung: str = '', offen: int = 0):
    """Compares the copies of a group side by side: confirm, exclude, choose the main copy, correct the details.
    A leaflet that a review split off its group gets that review, to take it back or go on."""
    leaflet = leaflet_or_404(leaflet_id)
    if copy_group_of(leaflet)[0]:
        return copy_view(request, leaflet, meldung, bool(offen))
    split = [r for r in separated_rows(latest_reviews()) if leaflet.id in [r['id']] + [f['id'] for f in r['from']]]
    if not split:
        raise HTTPException(404)
    split = max(split, key=lambda r: r['at'])
    split['date'] = review_date(split['at'])
    here = (session.get(Volume, leaflet.volume_id).vz, leaflet.start_page)
    following = next((r['id'] for r in copy_rows() if r['state'] != 'geprueft' and r['order'] > here), None)
    return templates.TemplateResponse(request, "copy_split.html", {
        "leaflet": leaflet, "split": split, "next": following, "message": COPY_MESSAGES.get(meldung)})


def copy_view(request, leaflet, meldung='', offen=False, form=None, error=None):
    """The comparison page. `offen`: the details form is open; `form`, `error`: its rejected values."""
    members, candidates = copy_group_of(leaflet)
    if not members:
        raise HTTPException(404)
    checked = bool(members[0].copies_checked)
    main_id = members[0].canonical_leaflet_id if checked else None  # no main copy before the review
    cards = [copy_card(lf, main_id) for lf in members]
    new = [copy_card(lf, None) for lf in candidates]
    letters = copy_letters(members, candidates)
    for c in cards + new:
        c['letter'] = letters[c['id']]
    left = main_id or members[0].id  # the details of the group are those of its main copy
    main = next(lf for lf in members if lf.id == left)
    details = {'uid': main.id, 'edit': form or current_values(main), 'pickable': True,  # evidence of the main copy's pages
               'automatic': automatic_text(main), 'corrected': main.corrected or [], 'open': offen, 'error': error}
    ordered = [c['id'] for c in cards + new]
    first = ordered[:3]  # the compared leaflets: the first three, the others can be shown; the main copy always is
    if checked and left not in first:
        first = first[:2] + [left]
    shown = [i for i in ordered if i in first]
    # what all copies share is said once; a field that varies is shown in the rows, and a copy that
    # deviates from the usual value is where it is decided whether it is the same leaflet
    fields = {'title': 'Titel', 'date': 'Datum', 'issuers': 'Herausgeber', 'signatories': 'Unterzeichnende',
              'series': 'Reihe', 'received': 'Eingang'}
    values = {key: {c[key] for c in cards + new} for key in fields}
    shorten(cards + new)
    # a field that differs between the leaflets is marked on every card: at the odd one out and where it is missing
    differs = {key: (deviating(cards + new, key) | {c['id'] for c in cards + new if not c[key]}) if len(values[key]) > 1 else set()
               for key in fields}
    # what the other copies say differently than the main copy, for taking over
    mine, offers = current_values(main), {}
    short = {c['id']: c['short'] for c in cards}
    for lf in members:
        theirs = current_values(lf) if checked and lf is not main else None
        for field in TAKE_KEYS if theirs else ():
            text = field_text(theirs, field)
            if text and ' '.join(text.split()).casefold() != ' '.join(field_text(mine, field).split()).casefold():
                offers.setdefault(field, []).append({'id': lf.id, 'label': short[lf.id], 'letter': letters[lf.id], 'value': text,
                                                     'blocks': ','.join(field_blocks(theirs, field))})
    return templates.TemplateResponse(
        request, "leaflet_copies.html",
        {"leaflet": leaflet, "cards": cards, "new": new, "differs": differs, "left": left,
         "fields": fields, "message": COPY_MESSAGES.get(meldung),
         "pair": copy_compare(leaflet, shown), "shown": shown, "checked": checked, "details": details,
         "offers": offers, "queue": review_queue(leaflet, reviewing(request)), "simple": len(cards) == 2 and not new, **edit_choices()},
        status_code=400 if error else 200)


def main_copy_or_404(leaflet_id):
    """The leaflet if it is the main copy of its group; the details of a group are saved there."""
    leaflet = leaflet_or_404(leaflet_id)
    members = copy_group_of(leaflet)[0]
    if not members or leaflet.id != (members[0].canonical_leaflet_id or members[0].id):
        raise HTTPException(404)
    return leaflet


@app.post("/leaflets/{leaflet_id}/exemplare/angaben")
async def copy_details_save(request: Request, leaflet_id: int):
    """Saves the details of the group at its main copy."""
    leaflet = main_copy_or_404(leaflet_id)
    form, error = read_metadata_form(leaflet, parse_qs((await request.body()).decode(), keep_blank_values=True))
    if error:
        return copy_view(request, leaflet, '', True, form, error)
    save_metadata(leaflet, form)
    return back_to_copies(leaflet_id)


def take_metadata(leaflet, other, field):
    """Copies one field of another leaflet to this one. Its evidence lies on the other leaflet's pages, so none is taken."""
    old, new = current_values(leaflet), current_values(other)
    form = {**old, **{k: new[k] for k in TAKE_KEYS[field]}}
    if f'{field}_blocks' in form:
        form[f'{field}_blocks'] = []
    if field in ('issuers', 'signatories'):
        form[field] = [{**i, 'blocks': []} for i in new[field]]
    save_metadata(leaflet, form)


@app.post("/leaflets/{leaflet_id}/exemplare/uebernehmen")
async def copy_details_take(request: Request, leaflet_id: int):
    """Takes one field of a duplicate of the group over to its main copy."""
    leaflet = main_copy_or_404(leaflet_id)
    field, _, other_id = parse_qs((await request.body()).decode()).get('take', [''])[0].partition(':')
    other = session.get(Leaflet, int(other_id)) if other_id.isdigit() else None
    if field not in TAKE_KEYS or other is None or other.id == leaflet.id or other.copy_group != leaflet.copy_group:
        raise HTTPException(400)
    take_metadata(leaflet, other, field)
    return back_to_copies(leaflet_id)


@app.post("/leaflets/{leaflet_id}/exemplare/zuruecksetzen")
async def copy_details_revert(request: Request, leaflet_id: int):
    leaflet = main_copy_or_404(leaflet_id)
    revert_metadata(leaflet, parse_qs((await request.body()).decode()).get('field', ['all'])[0])
    return back_to_copies(leaflet_id)


def back_to_copies(leaflet_id):
    return RedirectResponse(f"/leaflets/{leaflet_id}/exemplare?meldung=angaben&offen=1", status_code=303)


def copy_compare(leaflet, ids):
    """The leaflets `ids` of the group side by side, as columns in that order: cards with their OCR deviations (see
    ocr_pair and ocr_group)."""
    members, candidates = copy_group_of(leaflet)
    by_id = {lf.id: lf for lf in members + candidates}
    if len(ids) < 2 or len(set(ids)) != len(ids) or not set(ids) <= by_id.keys():
        raise HTTPException(404)
    checked = bool(members[0].copies_checked)
    main_id = members[0].canonical_leaflet_id if checked else None
    cards = [copy_card(by_id[i], main_id) for i in ids]
    shorten(cards)
    letters = copy_letters(members, candidates)
    for card in cards:  # the page shape of each scan, to reserve its space before it has loaded
        pdf = volume_pdf(session.get(Volume, by_id[card['id']].volume_id))
        size = pdf_service.page_size(pdf, card['page']) if pdf.is_file() else None
        card['ratio'] = round(size[0] / size[1], 4) if size else None
    ratios = [c['ratio'] for c in cards if c['ratio']]
    lists = [copy_blocks(by_id[i]) for i in ids]
    sides = ocr_pair(*lists) if len(ids) == 2 else ocr_group(lists)
    for card, side in zip(cards, sides):
        card['letter'] = letters[card['id']]
        card['ocr'] = side
    # upright scans get the same height, that of the tallest: they all reserve the same space
    return {'cards': cards, 'max_pages': max(c['pages'] for c in cards), 'checked': checked,
            'ratio': min([r for r in ratios if r < 1] or ratios, default=None)}


@app.get("/leaflets/{leaflet_id}/exemplare/paar")
def copy_pair_page(request: Request, leaflet_id: int, ids: str):
    """The comparison part of the page, loaded again when other leaflets are shown."""
    shown = list(dict.fromkeys(int(i) for i in ids.split(',') if i.isdigit()))
    pair = copy_compare(leaflet_or_404(leaflet_id), shown)
    return templates.TemplateResponse(request, "leaflet_copy_pair.html", {"pair": pair})


def save_copy_review(leaflet, form):
    """Appends the review of the leaflet's group (or the revert of its newest review) and
    rebuilds the groups. form: parsed form fields; unticked new hits count as seen, not as members."""
    members, candidates = copy_group_of(leaflet)
    if not members and 'revert' not in form:
        raise HTTPException(404)

    def ids(name):
        return {int(v) for v in form.get(name, []) if v.isdigit()}
    mine = {copy_decisions.anchor(segment(lf)) for lf in members + candidates or [leaflet]}  # a split-off leaflet: its own review
    lines = corrections.load(COPY_DECISIONS)
    done = {e['revert'] for e in lines if 'revert' in e}
    reviews = [e for e in lines if 'revert' not in e and e['at'] not in done  # the reviews in force for this group
               and mine & {copy_decisions.anchor(a) for a in e['members'] + e['rejected']}]
    if 'revert' in form:
        if reviews:
            copy_decisions.append(COPY_DECISIONS, {'revert': max(e['at'] for e in reviews)})
    else:
        out, add = ids('out'), ids('add')
        kept = [lf for lf in members if lf.id not in out] + [lf for lf in candidates if lf.id in add]
        rejected = [lf for lf in members + candidates if lf not in kept]
        main = next((lf for lf in kept if lf.id in ids('main')), None)
        if main is None:
            raise HTTPException(400, "Das Hauptexemplar muss zur Gruppe gehören.")
        rejected = [segment(lf) for lf in rejected]
        seen = {copy_decisions.anchor(a) for a in rejected + [segment(lf) for lf in kept]}
        for e in reviews:  # what an earlier review of the group rejected stays rejected, it is not a new hit
            for a in e['rejected']:
                if copy_decisions.anchor(a) not in seen:
                    seen.add(copy_decisions.anchor(a))
                    rejected.append(a)
        copy_decisions.append(COPY_DECISIONS, {
            'members': [segment(lf) for lf in kept], 'rejected': rejected, 'canonical': segment(main)})
    fill_copies()


@app.post("/leaflets/{leaflet_id}/exemplare")
async def copy_save(request: Request, leaflet_id: int):
    leaflet = leaflet_or_404(leaflet_id)
    form = parse_qs((await request.body()).decode())
    verdict = form.pop('verdict', [''])[0]
    onward = verdict.startswith('next:') or 'next' in form  # save and go on to the next group to check
    if verdict:  # a pair: "main:<id>" or "next:<id>" chooses that main copy, "different" says these are two leaflets
        members = copy_group_of(leaflet)[0]
        main = verdict[5:] if verdict.startswith(('main:', 'next:')) else str(members[0].canonical_leaflet_id or members[0].id)
        form['main'] = [main]
        form['out'] = [str(lf.id) for lf in members if str(lf.id) != main] if verdict == 'different' else []
    queue = review_queue(leaflet, reviewing(request))
    following = (queue['next'] or (queue['previous'] if queue['band'] else None)) if onward else None
    save_copy_review(leaflet, form)
    if following:
        return RedirectResponse(f"/leaflets/{following}/exemplare", status_code=303)
    if onward and queue['band']:  # nothing left to check in the volume: back to its step 6
        return RedirectResponse(f"/import/{queue['band']}?schritt=pruefen", status_code=303)
    message = 'zurueckgenommen' if 'revert' in form else 'gespeichert' if copy_group_of(leaflet)[0] else 'getrennt'
    return RedirectResponse(f"/leaflets/{leaflet_id}/exemplare?meldung={message}", status_code=303)


def correction_rows(volumes, saved):
    """The saved corrections per page range, with the leaflet they apply to; None when the range no longer
    matches a segment."""
    rows = []
    in_volume = defaultdict(list)  # one query for all the leaflets instead of one per correction
    for leaflet in session.query(Leaflet).order_by(Leaflet.start_page):
        in_volume[leaflet.volume_id].append(leaflet)
    for (stem, start, end), entries in saved.items():
        volume = volumes.get(stem)
        overlaps = [lf for lf in in_volume[volume.id] if lf.start_page <= end and lf.end_page >= start] if volume else []
        rows.append({'stem': stem, 'start': start, 'end': end, 'segment': f"{volume.label if volume else stem}, {page_range(start, end)}",
                     'place': f"Band {volume.vz:03d} · {page_range(start, end)}" if volume else f"{stem}, {page_range(start, end)}",
                     'entries': entries, 'overlaps': overlaps,
                     'leaflet': next((lf for lf in overlaps if (lf.start_page, lf.end_page) == (start, end)), None)})
    return rows


def correction_text(e):
    """(label, value) of a correction line as a reader sees it: organizations by name, dates in words."""
    field, value = e['field'], e['value']
    if field == 'revert':
        return 'Rücknahme', 'alle früheren Korrekturen' if value == 'all' else corrections.FIELDS.get(value, value)
    if field == 'date':
        value = (iso_to_text(value['iso']) or value['iso']) + (f" ({value['type']})" if value.get('type') else '')
    elif field == 'series' and isinstance(value, dict):  # early lines hold the name alone
        value = ', '.join(filter(None, [value['name'], value['issue']]))
    elif field == 'issuers':
        value = ', '.join((org.full_name or org.name) if (org := session.get(Organization, i.get('org') or '')) else i.get('org') or i['name']
                          for i in value)
    elif field == 'signatories':
        value = ', '.join(i['name'] for i in value)
    return corrections.FIELDS.get(field, field), value


def in_force(entries):
    """The correction in force per field, in the order apply() leaves them: the last line not reverted wins."""
    return list({e['field']: e for e in corrections.active(entries)}.values())


@app.get("/korrekturen")
def correction_list(request: Request):
    volumes = {v.stem: v for v in session.query(Volume) if v.stem}
    rows = correction_rows(volumes, corrections.by_segment(corrections.load(CORRECTIONS)))
    for r in rows:
        r['now'] = [correction_text(e) for e in in_force(r['entries'])]
        r['history'] = [(*correction_text(e), german_date(e['at'])) for e in r['entries']]
        r['at'] = german_date(max(e['at'] for e in r['entries']))
    copies = [{'at': review_date(r['at']), 'members': [
        f"{volumes[a['volume']].label if a['volume'] in volumes else a['volume']}, "
        f"{page_range(a['start_page'], a['end_page'])}" for a in r['members']]}
        for r in copy_review()[1]]
    return templates.TemplateResponse(
        request, "corrections.html", {"rows": [r for r in rows if not r['leaflet'] and r['now']], "copies": copies,
                                      "saved": sorted((r for r in rows if r['leaflet']), key=lambda r: max(e['at'] for e in r['entries']), reverse=True)})


@app.post("/korrekturen/zuordnen")
def correction_move(volume: str = Form(...), start: int = Form(...), end: int = Form(...), target: int = Form(0)):
    """The corrections in force for a page range that fits no leaflet any more go to a leaflet there (target), or are
    dropped (no target); the old lines stay in the file, cancelled by a revert."""
    entries = in_force(corrections.by_segment(corrections.load(CORRECTIONS)).get((volume, start, end), []))
    if not entries:
        raise HTTPException(404)
    if target:
        leaflet = leaflet_or_404(target)
        if session.get(Volume, leaflet.volume_id).stem != volume or not leaflet.start_page <= end or not leaflet.end_page >= start:
            raise HTTPException(400)
        save_corrections(leaflet, [(e['field'], e['value'], e.get('blocks', [])) for e in entries])
    corrections.append(CORRECTIONS, [{'volume': volume, 'start_page': start, 'end_page': end, 'field': 'revert', 'value': 'all'}])
    return RedirectResponse("/korrekturen", 303)


@app.get("/leaflets/{leaflet_id}/pages/{page_no}.png")
def leaflet_page_image(leaflet_id: int, page_no: int, dpi: int = 110):
    leaflet = session.get(Leaflet, leaflet_id)
    if leaflet is None or not (
            leaflet.start_page <= page_no <= leaflet.end_page):
        raise HTTPException(404)

    png = pdf_service.render_page(
        leaflet_pdf(leaflet), page_no, dpi=max(72, min(dpi, 300)))
    return Response(content=png, media_type="image/png")


@app.get("/leaflets/{leaflet_id}/evidence.png")
def evidence_image(leaflet_id: int, blocks: str):
    """Scan detail around the given OCR blocks, e.g. blocks=2-1,2-2."""
    leaflet = session.get(Leaflet, leaflet_id)
    ids = [b.split("-") for b in blocks.split(",") if "-" in b]
    if leaflet is None or not ids or not all(p.isdigit() and i.isdigit() for p, i in ids):
        raise HTTPException(404)
    page_no = int(ids[0][0])
    if not leaflet.start_page <= page_no <= leaflet.end_page:
        raise HTTPException(404)
    page = session.query(Page).filter_by(leaflet_id=leaflet.id, page_no=page_no).first()  # indexed, unlike volume and page
    boxes = [page.blocks[int(i) - 1]["box"] for p, i in ids
             if int(p) == page_no and 0 < int(i) <= len(page.blocks or [])]
    if not boxes:
        raise HTTPException(404)
    left = min(b[0] for b in boxes) - 2
    top = min(b[1] for b in boxes) - 0.6
    right = max(b[0] + b[2] for b in boxes) + 2
    bottom = max(b[1] + b[3] for b in boxes) + 0.6
    # keep some context to the sides of small blocks, but not the next lines
    grow_x = max(0, 40 - (right - left)) / 2
    grow_y = max(0, 3 - (bottom - top)) / 2
    left, right, top, bottom = left - grow_x, right + \
        grow_x, top - grow_y, bottom + grow_y

    png = pdf_service.render_clip(leaflet_pdf(leaflet), page_no,
                                  [left, top, right - left, bottom - top])
    return Response(content=png, media_type="image/png")


def volume_status(volume, n_leaflets):
    if n_leaflets:
        noun = "Flugblatt" if n_leaflets == 1 else "Flugblätter"
        return f"{n_leaflets} {noun}"
    if volume.digitized:
        return "digitalisiert"
    return "nicht digitalisiert"


@app.get("/import")
def import_list(error: str = ''):
    return RedirectResponse('/verwaltung' + (f"?{urlencode({'error': error})}" if error else ''), 301)


@app.get("/verwaltung")
def admin_page(request: Request, error: str = ''):
    """Where each volume stands, with the open duplicates and corrections, and the imports in progress."""
    leaflets = Counter(vid for (vid,) in session.query(Leaflet.volume_id))
    volumes = session.query(Volume).order_by(Volume.vz).all()
    # the page table is big and has no index on the volume: count only where the volume does not know its pages
    unknown = [v.id for v in volumes if not v.n_pages and v.status == RELEASED and leaflets[v.id]]
    pages = Counter(dict(session.query(Page.volume_id, func.count()).filter(Page.volume_id.in_(unknown))
                         .group_by(Page.volume_id))) if unknown else Counter()
    groups = copy_rows()
    open_groups = [g for g in groups if g['state'] != 'geprueft']
    fix_rows = correction_rows({v.stem: v for v in volumes if v.stem}, corrections.by_segment(corrections.load(CORRECTIONS)))
    fixes = Counter(r['leaflet'].volume_id for r in fix_rows if r['leaflet'] and corrections.active(r['entries']))
    added = {e["vz"] for e in importer.load_entries() if e.get("added")}
    steps = list(importer.STEPS)
    drafts = []
    for v in volumes:
        if v.status == RELEASED and leaflets[v.id]:
            continue
        step = resume_step(v)
        # an archive unit without scans has nothing to delete: it would stay in the list as "not digitized"
        drafts.append({"vz": v.vz, "title": v.title, "step": importer.STEPS[step], "n": steps.index(step) + 1,
                       "deletable": bool(v.stem) or v.vz in added})
    return templates.TemplateResponse(request, "admin.html", {
        "volumes": [{"vz": v.vz, "title": v.title, "leaflets": leaflets[v.id], "pages": v.n_pages or pages[v.id],
                     "groups": sum(v.vz in g['volumes'] for g in groups),
                     "open": sum(v.vz in g['volumes'] for g in open_groups), "fixes": fixes[v.id]}
                    for v in volumes if v.status == RELEASED and leaflets[v.id]],
        "drafts": drafts, "n_steps": len(steps), "units": importer.free_units(),
        "groups": len(groups), "open": len(open_groups),
        "fixes": sum(fixes.values()), "unmatched": sum(not r['leaflet'] and bool(in_force(r['entries'])) for r in fix_rows),
        "topics": session.query(Topic).count(), "candidate": len((topics.load(topics.CANDIDATE) or {"topics": []})["topics"]),
        "error": error})


@app.get("/import/neu")
def import_new(request: Request, error: str = '', vz: int = 0):
    """The first step of an import, before the volume exists: which unit of the archive it is. vz= preselects
    one; a unit that is already added is not offered, creating it is refused in new_volume as well."""
    units = importer.free_units()
    if vz and not any(u["vz"] == vz for u in units):
        error, vz = error or f"Nr. {vz:03d} ist schon angelegt.", 0
    return templates.TemplateResponse(request, "import_volume.html", {
        "volume": None, "units": units, "chosen": vz, "error": error,
        "steps": importer.STEPS, "step_help": importer.STEP_HELP, "step": "band", "pages": None, "split": None, "running": False})


@app.post("/import/neu")
def import_create(vz: int = Form(...), portal_url: str = Form('')):
    try:
        volume = importer.new_volume(vz, portal_url)
    except ValueError as error:
        return RedirectResponse('/import/neu?' + urlencode({'error': str(error)}), 303)
    return RedirectResponse(f"/import/{volume.vz}?schritt=scans", 303)


def editable(vz):
    """The volume, for a change in the steps before 6: its draft leaflets are taken back, step 6 makes them again
    from what changes now. Corrections and reviews stay, they are kept in their own files."""
    volume = import_volume_or_404(vz)
    if importer.n_leaflets(volume):
        if volume.status != DRAFT:
            raise HTTPException(409)
        importer.withdraw(volume)
        importer.JOBS.pop((vz, metadata.PREPARE), None)
    return volume


def import_volume_or_404(vz):
    volume = session.query(Volume).filter_by(vz=vz).first()
    if volume is None:
        raise HTTPException(404)
    return volume


def import_page(request, vz, step, error='', status_code=200, uploaded=False):
    volume = import_volume_or_404(vz)
    created = importer.n_leaflets(volume)
    if created and volume.status == RELEASED and step not in ('pruefen', 'themen') or step not in importer.STEPS:
        raise HTTPException(404)
    prepare = importer.JOBS.get((vz, metadata.PREPARE), {})
    flagged = metadata.flagged_leaflets(volume) if step == 'pruefen' and created else []
    if step == 'pruefen' and not created and prepare.get('state') not in ('running', 'error')             and metadata.status(volume)['state'] == 'done':
        metadata.start_create(volume)  # a draft, made again after a change in the steps before
        prepare = importer.JOBS[(vz, metadata.PREPARE)]
    pages = importer.page_count(volume) if volume.stem else None
    stamp = importer.scan_stamp(volume)  # a new scan gets new image addresses
    split = {"pages": pages, "thumb": f"/import/{vz}/seiten/{{n}}.jpg?v={stamp}",
             "large": f"/import/{vz}/seiten/{{n}}.jpg?gross=1&v={stamp}",
             **segments.status(volume),
             "saveUrl": f"/import/{vz}/trennen",
             "textUrl": f"/import/{vz}/vorschlag-text", "listUrl": f"/import/{vz}/liste", "name": volume.stem} if step == 'trennen' and pages else None
    text = ocr.status(volume)
    meta = metadata.status(volume) if step == 'angaben' and text['state'] == 'done' and segments.status(volume)['confirmed'] else None
    used = Counter(v.meta_model for v in session.query(Volume).filter_by(status=RELEASED) if v.meta_model).most_common() if meta else []
    waiting = {'scans': None if pages else 'Zuerst die Scans hochladen.',  # why "Weiter" does not work yet
               'ocr': None if text['state'] == 'done' else 'Zuerst den Text erkennen oder ein fertiges Ergebnis als ZIP laden.',
               'trennen': None if segments.status(volume)['confirmed'] else 'Zuerst die Prüfung abschließen.',
               'angaben': None if meta and meta['state'] == 'done' else 'Zuerst die Metadaten erzeugen.'}.get(step)
    done = ['band'] + (['scans'] if pages else []) + (['ocr'] if text['state'] == 'done' else []) \
        + (['trennen'] if segments.status(volume)['confirmed'] else [])
    done += ['angaben'] if 'trennen' in done and metadata.status(volume)['state'] == 'done' else []
    response = templates.TemplateResponse(request, "import_volume.html", {"waiting": waiting, "done": done,
        "volume": volume, "pages": pages, "error": error, "steps": importer.STEPS, "step_help": importer.STEP_HELP, "step": step, "split": split,
        "running": importer.running(volume), "ocr": text, "stamp": stamp, "uploaded": uploaded,
        "ocr_job": importer.JOBS.get((vz, ocr.JOB)) if step == 'ocr' else None,
        "ocr_key": keys.info('datalab') if step == 'ocr' else None,
        "meta": meta, "meta_job": importer.JOBS.get((vz, metadata.JOB)) if meta else None,
        "meta_key": keys.info('openrouter') if meta else None,
        "default_model": (used[0][0] if used else metadata.DEFAULT_MODEL) if meta else None,
        "model_names": [m[:2] for m in metadata.models()] if meta else [],
        "model_top": metadata.top_models(used) if meta else [],
        "model_prices": metadata.prices(volume) if meta else {},
        "prompt_text": metadata.prompt_text() if meta else '', "prompt_default": metadata.default_prompt() if meta else '',
        "batch_size": metadata.BATCH_SIZE, "max_batch": metadata.MAX_BATCH,
        "created": created, "prepare": prepare if step == 'pruefen' and not created else {}, "flagged": flagged,
        "hints_open": sum(not f[2] for f in flagged), "hints_first": next((f[0].id for f in flagged if not f[2]), None),
        "new_issuers": organizations.unmatched(vz) if step == 'pruefen' and created else [],
        "copies": copy_counts(volume) if step == 'pruefen' and created else None,
        "topic_state": topics.status(volume) if step == 'themen' and created else None,
        "topic_job": importer.JOBS.get((vz, topics.ASSIGN)) if step == 'themen' else None,
        "topic_key": keys.info('openrouter') if step == 'themen' else None},
        status_code=status_code)
    if volume.status == RELEASED and step == 'pruefen':
        response.set_cookie('pruefen', str(vz), samesite='lax')
    return response


def copy_counts(volume):
    """How many leaflets of the volume have copies, how many groups with them are not checked, and the first of those."""
    leaflets = session.query(Leaflet).filter_by(volume_id=volume.id)
    todo = [r for r in copy_rows() if volume.vz in r['volumes'] and r['state'] != 'geprueft']
    return {'found': sum(bool(lf.copy_group or lf.copy_candidate_of) for lf in leaflets),
            'open': len(todo), 'first': todo[0]['id'] if todo else None}


def resume_step(volume):
    """The step an unfinished import goes on with: the first one that is not done yet."""
    if importer.n_leaflets(volume):
        return 'pruefen'
    if not (importer.page_count(volume) if volume.stem else None):
        return 'scans'
    if ocr.status(volume)['state'] != 'done':
        return 'ocr'
    if not segments.status(volume)['confirmed']:
        return 'trennen'
    return 'pruefen' if metadata.status(volume)['state'] == 'done' else 'angaben'


@app.get("/import/{vz}")
def import_volume_page(request: Request, vz: int, schritt: str = '', hochgeladen: int = 0):
    return import_page(request, vz, schritt or resume_step(import_volume_or_404(vz)), uploaded=bool(hochgeladen))


@app.post("/import/{vz}/band")
def import_band(vz: int, portal_url: str = Form('')):
    volume = import_volume_or_404(vz)
    if importer.n_leaflets(volume):
        raise HTTPException(404)
    importer.set_portal_url(volume, portal_url)
    return RedirectResponse(f"/import/{vz}?schritt=scans", 303)


@app.post("/import/{vz}/loeschen")
def import_discard(vz: int):
    try:
        importer.discard(import_volume_or_404(vz))
    except ValueError as error:
        return RedirectResponse('/verwaltung?' + urlencode({'error': str(error)}), 303)
    return RedirectResponse("/verwaltung", 303)


@app.post("/import/{vz}/vorbereiten")
def import_prepare_again(vz: int):
    editable(vz)  # takes the leaflets back, if there are any
    importer.JOBS.pop((vz, metadata.PREPARE), None)
    return RedirectResponse(f"/import/{vz}?schritt=pruefen", 303)


def in_holdings(org_id):
    """(number of leaflets, first year, last year) of an organization in the released volumes."""
    years = sorted(leaflet_year(lf, year) for lf, year in released_leaflets().add_columns(Volume.year)
                   .join(LeafletIssuer, LeafletIssuer.leaflet_id == Leaflet.id).filter(LeafletIssuer.org_id == org_id).distinct())
    return len(years), years[0] if years else None, years[-1] if years else None


@app.get("/import/{vz}/herausgeber")
def import_issuers(request: Request, vz: int, nr: int = 0, blatt: int = 0, fehler: str = ''):
    """One issuer the register does not know at a time, with its place in the scan and the organizations it may be."""
    volume = import_volume_or_404(vz)
    groups = organizations.unmatched(vz)
    if not groups:
        return RedirectResponse(f"/import/{vz}?schritt=pruefen#herausgeber", 303)
    nr = min(max(nr, 0), len(groups) - 1)
    group = groups[nr]
    blatt = min(max(blatt, 0), len(group['issuers']) - 1)
    leaflet, issuer = group['issuers'][blatt]
    others = [org_label(session.get(Organization, i.org_id)) if i.org_id else i.surface
              for i in session.query(LeafletIssuer).filter_by(leaflet_id=leaflet.id, role='issuer') if i.id != issuer.id]
    return templates.TemplateResponse(request, "issuer_review.html", {
        "volume": volume, "group": group, "nr": nr, "total": len(groups), "blatt": blatt, "error": fehler,
        "leaflet": leaflet, "issuer": issuer, "date": iso_to_text(leaflet.date_iso), "others": others,
        "pages": page_range(leaflet.start_page, leaflet.end_page),
        "candidates": [(org, form, *in_holdings(org.id)) for org, form in organizations.candidates(group['surface'])],
        "org_names": [org_label(o) for o in sorted(session.query(Organization), key=org_sort_key)]})


@app.post("/import/{vz}/herausgeber")
def import_issuer(vz: int, surface: str = Form(...), choice: str = Form(...), other: str = Form(''),
                  full_name: str = Form(''), nr: int = Form(0)):
    import_volume_or_404(vz)
    key = organizations.key(surface)
    group = next((g for g in organizations.unmatched(vz) if organizations.key(g['surface']) == key), None)
    if group is None:
        raise HTTPException(404)
    if choice == 'andere':
        choice = {org_label(o): o.id for o in session.query(Organization)}.get(other.strip())
        if not choice:
            return RedirectResponse(f"/import/{vz}/herausgeber?" + urlencode(
                {'nr': nr, 'fehler': f"„{other.strip()}“ steht nicht im Register. Bitte einen Eintrag aus der Liste wählen."}), 303)
    if choice in ('person', 'erwaehnt'):  # not an issuer: corrected on each leaflet, like in the edit form
        for leaflet, issuer in group['issuers']:
            kept = [{'org': i.org_id, 'blocks': list(i.blocks or [])} if i.org_id else {'name': i.surface, 'blocks': list(i.blocks or [])}
                    for i in session.query(LeafletIssuer).filter_by(leaflet_id=leaflet.id, role='issuer').order_by(LeafletIssuer.id)
                    if i.org_id or organizations.key(i.surface) != key]
            changes = [('issuers', kept, [])]
            if choice == 'person':
                changes.append(('signatories', current_values(leaflet)['signatories']
                                + [{'name': surface.strip(), 'details': '', 'blocks': list(issuer.blocks or [])}], []))
            save_corrections(leaflet, changes)
    elif choice == 'neu' or session.get(Organization, choice):
        organizations.decide(surface, choice, full_name)
    else:
        raise HTTPException(400)
    return RedirectResponse(f"/import/{vz}/herausgeber?nr={nr}", 303)


@app.post("/import/{vz}/freigeben")
def import_release(vz: int):
    volume = import_volume_or_404(vz)
    if volume.status != DRAFT or not importer.n_leaflets(volume):
        raise HTTPException(409)
    fillDatabase.release_volume(vz)
    return RedirectResponse("/verwaltung", 303)


@app.post("/import/{vz}/zuruecknehmen")
def import_take_back(vz: int):
    """A released volume becomes a draft again, so the steps before 6 can change it; it is hidden until released anew."""
    if import_volume_or_404(vz).status != RELEASED:
        raise HTTPException(409)
    fillDatabase.release_volume(vz, DRAFT)
    return RedirectResponse(f"/import/{vz}?schritt=pruefen", 303)


@app.post("/import/{vz}/scans")
def import_scans(request: Request, vz: int, scans: list[UploadFile] = File(default=[]),
                 folder: list[UploadFile] = File(default=[])):
    script = request.headers.get('accept') == 'application/json'  # the upload form's script, not a plain post
    try:
        importer.start_scans(editable(vz), [(f.filename, f.file) for f in scans + folder if f.filename])
    except ValueError as error:
        if script:
            return JSONResponse({'error': str(error)}, status_code=400)
        return import_page(request, vz, 'scans', str(error), 400)
    if script:
        return JSONResponse({'ok': True})
    return RedirectResponse(f"/import/{vz}?schritt=scans", 303)


@app.get("/import/{vz}/status")
def import_status(vz: int, job: str = 'scans'):
    # now: the app's clock, so the page can count elapsed times without trusting its own
    return JSONResponse({**importer.JOBS.get((vz, job), {'state': 'idle'}), 'now': time.time()})


@app.get("/import/{vz}/seiten/{page_no}.jpg")
def import_page_thumb(vz: int, page_no: int, gross: bool = False):
    """A page of the uploaded scan, for choosing the cuts (large: to read it); the volume has no leaflets yet,
    so there is no n_pages."""
    volume = import_volume_or_404(vz)
    pages = importer.page_count(volume) if volume.stem else None
    if not pages or not 1 <= page_no <= pages:
        raise HTTPException(404)
    jpg = pdf_service.render_thumb(importer.scan_path(volume), page_no, height=1400 if gross else 2 * THUMB_HEIGHT)
    return Response(content=jpg, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@app.post("/import/{vz}/trennen")
async def import_cuts(request: Request, vz: int):
    """Saves what was chosen on the page: {"cuts": [page, ...], "excluded": [page, ...], "suggested": [page, ...],
    "reviewed": [page, ...], "hints": [page, ...], "finish": bool}, each cut the last page of a leaflet, each excluded page left out of every
    leaflet, "suggested" the cuts nobody has decided, "reviewed" the transitions found to belong together, "hints" the
    transitions where the text suggests an overlooked cut."""
    volume = editable(vz)
    pages = importer.page_count(volume) if volume.stem else None
    body = await request.json()
    cuts, excluded, suggested, reviewed, hints = body.get('cuts'), *(body.get(k, []) for k in ('excluded', 'suggested', 'reviewed', 'hints'))
    fits = pages and all(isinstance(v, list) and all(isinstance(p, int) for p in v) for v in (cuts, excluded, suggested, reviewed, hints)) \
        and all(1 <= c < pages for c in cuts + suggested + reviewed + hints) and all(1 <= p <= pages for p in excluded)
    if not fits:
        return JSONResponse({'error': 'Die Trennungen passen nicht zu den hochgeladenen Seiten.'}, status_code=400)
    doc = segments.save(volume, cuts, pages, excluded=excluded, suggested=suggested, reviewed=reviewed,
                        hints=hints, finished=bool(body.get('finish')))
    return JSONResponse({'ok': True, 'count': sum(not s.get('no_content') for s in doc['segments'])})


@app.post("/import/{vz}/liste")
def import_list_file(vz: int, liste: UploadFile = File(...)):
    """Reads a list of leaflets (one page range per line) and answers with the cuts and with "hints": transitions where
    the text makes a cut likely that the list lacks (null without usable text). Nothing is saved."""
    volume = import_volume_or_404(vz)
    pages = importer.page_count(volume) if volume.stem else None
    if not pages:
        return JSONResponse({'error': 'Es sind noch keine Scans hochgeladen.'}, status_code=400)
    raw = liste.file.read(1_000_000)
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:  # a CSV saved by Excel
        text = raw.decode('cp1252', errors='replace')
    try:
        cuts, excluded = segments.parse_list(text, pages)
        return JSONResponse({'cuts': cuts, 'excluded': excluded, 'hints': segments.missed_cuts(volume, cuts, excluded, pages)})
    except ValueError as error:
        return JSONResponse({'error': str(error)}, status_code=400)


@app.post("/import/{vz}/ocr")
def import_ocr(vz: int, mode: str = Form(ocr.DEFAULT_MODE), captions: str = Form('yes'), size: int = Form(ocr.BATCH_PAGES),
               again: bool = Form(False)):
    try:
        ocr.start(editable(vz), mode, again, captions=captions != 'no', size=size)
    except ValueError as error:
        return JSONResponse({'error': str(error)}, status_code=400)
    return JSONResponse({'ok': True})


@app.post("/import/{vz}/angaben")
def import_metadata(vz: int, model: str = Form(''), prompt: str = Form(''), batch: int = Form(metadata.BATCH_SIZE)):
    orgs = [(o.id, o.name, o.full_name) for o in session.query(Organization)]
    try:
        metadata.start(editable(vz), model.strip(), orgs, prompt, batch)
    except ValueError as error:
        return JSONResponse({'error': str(error)}, status_code=400)
    return JSONResponse({'ok': True})


@app.post("/import/{vz}/angaben/abbrechen")
def import_metadata_cancel(vz: int):
    try:
        metadata.cancel(import_volume_or_404(vz))
    except ValueError as error:
        return JSONResponse({'error': str(error)}, status_code=400)
    return JSONResponse({'ok': True})


@app.post("/import/{vz}/themen")
def import_topics(vz: int):
    try:
        topics.start_assign(import_volume_or_404(vz))
    except ValueError as error:
        return JSONResponse({'error': str(error)}, status_code=400)
    return JSONResponse({'ok': True})


@app.get("/verwaltung/themen/neu")
def topics_recompute_page(request: Request, error: str = ''):
    job = importer.JOBS.get((0, topics.RECOMPUTE), {})
    current = topics.load(topics.TOPICS)
    review = None if job.get('state') == 'running' else topics.review()
    view = {}
    if review:  # the rows of /themen, for the new run, with where most of each topic's leaflets come from
        view = candidate_topic_overview()
        origin = {r['id']: r for r in review['topics']}
        for t in view['topics']:
            r = origin.get(t['id'], {})
            if r.get('old'):
                t['note_label'] = 'Meiste Flugblätter aus dem bisherigen Thema'
                t['note'] = f"{r['stay']} von {r['old_count']} aus „{r['old']}“"
        view['topics'].sort(key=lambda t: t['count'], reverse=True)
    return templates.TemplateResponse(request, "topics_new.html", {
        "job": job, "review": review, **view, "error": error,
        "n_topics": len(current['topics']) if current else 40, "key": keys.info('openrouter'),
        "model_top": metadata.top_models([], default=topics.label_model_used()), "model_names": [m[:2] for m in metadata.models()],
        "model_prices": topics.label_prices(len(current['topics']) if current else 40),
        **dict(zip(("chosen", "model_gone"), topics.label_model_choice(len(current['topics']) if current else 40))),
        "used_model": topics.label_model_used()})


@app.get("/verwaltung/themen/neu/status")
def topics_recompute_status():
    return JSONResponse({**importer.JOBS.get((0, topics.RECOMPUTE), {'state': 'idle'}), 'now': time.time()})


@app.post("/verwaltung/themen/neu")
def topics_recompute(n_topics: int = Form(40), model: str = Form(topics.LABEL_MODEL)):
    try:
        topics.start_recompute(n_topics, model.strip())
    except ValueError as error:
        return JSONResponse({'error': str(error)}, status_code=400)
    return JSONResponse({'ok': True})


@app.post("/verwaltung/themen/neu/uebernehmen")
async def topics_accept(request: Request):
    form = await request.form()
    try:
        topics.accept({int(k.removeprefix('titel-')): v for k, v in form.items() if k.startswith('titel-')})
    except ValueError as error:
        return RedirectResponse('/verwaltung/themen/neu?' + urlencode({'error': str(error)}), 303)
    return RedirectResponse('/themen', 303)


@app.post("/verwaltung/themen/neu/verwerfen")
def topics_discard():
    topics.discard()
    return RedirectResponse('/verwaltung/themen/neu', 303)


@app.get("/verwaltung/api-keys")
def keys_admin(request: Request, error: str = '', gespeichert: int = 0):
    return templates.TemplateResponse(request, "keys_admin.html", {
        "keys": {s: keys.info(s) for s in keys.SERVICES}, "error": error, "saved": gespeichert})


@app.post("/verwaltung/api-keys")
def keys_admin_save(key: str = Form(''), forget: bool = Form(False), service: str = Form('')):
    if service not in keys.SERVICES:
        raise HTTPException(status_code=400)
    try:
        keys.forget(service) if forget else keys.save(service, key)
    except ValueError as error:
        return RedirectResponse('/verwaltung/api-keys?' + urlencode({'error': str(error)}), 303)
    return RedirectResponse('/verwaltung/api-keys?gespeichert=1', 303)


@app.get("/verwaltung/themen")
def topics_admin(request: Request, error: str = '', gespeichert: int = 0):
    current = topics.load(topics.TOPICS)
    view = current_topic_overview()
    view['topics'].sort(key=lambda t: t['count'], reverse=True)
    return templates.TemplateResponse(request, "topics_admin.html", {
        "topics": view['topics'], "years": view['years'], "error": error, "saved": gespeichert,
        "run_date": german_date(m.group()) if current and (m := re.search(r"\d{4}-\d{2}-\d{2}", current['run'])) else None,
        **topic_volumes(current), "candidate": topics.load(topics.CANDIDATE) is not None})


def topic_volumes(doc):
    """The volumes the topic run computed, and those assigned later in step 7 (with the day)."""
    if not doc:
        return {"run_volumes": [], "later": []}
    later = doc.get("assigned_later", {})
    by_stem = {v.stem: v for v in session.query(Volume) if v.stem}
    stems = sorted({r["volume"] for r in doc["leaflets"]} - set(later), key=lambda st: by_stem[st].vz if st in by_stem else 0)
    numbers = [by_stem[st].vz for st in stems if st in by_stem]
    spans, start = [], None  # 1, 2, 3, 5 -> "001–003, 005"
    for i, n in enumerate(numbers):
        start = n if start is None else start
        if i + 1 == len(numbers) or numbers[i + 1] != n + 1:
            spans.append(f"{start:03d}" if start == n else f"{start:03d}–{n:03d}")
            start = None
    return {"run_volumes": [by_stem[st] for st in stems if st in by_stem], "run_span": ", ".join(spans),
            "later": sorted(((by_stem[st], german_date(day)) for st, day in later.items() if st in by_stem), key=lambda p: p[0].vz)}


@app.post("/verwaltung/themen/{topic_id}")
def topic_rename(topic_id: int, title: str = Form('')):
    try:
        topics.rename(topic_id, title)
    except ValueError as error:
        return RedirectResponse('/verwaltung/themen?' + urlencode({'error': str(error)}) + f'#thema-{topic_id}', 303)
    return RedirectResponse(f'/verwaltung/themen?gespeichert=1#thema-{topic_id}', 303)


@app.get("/import/{vz}/ocr/seiten/{page_no}.json")
def import_ocr_page(vz: int, page_no: int):
    """The recognized blocks of one page, for checking them against the scan."""
    volume = import_volume_or_404(vz)
    blocks = ocr.page_blocks(volume, page_no) if ocr.status(volume)['state'] == 'done' else None
    if blocks is None:
        raise HTTPException(404)
    return JSONResponse({'no': page_no, 'blocks': blocks})


@app.post("/import/{vz}/ocr/abbrechen")
def import_ocr_cancel(vz: int):
    try:
        ocr.cancel(import_volume_or_404(vz))
    except ValueError as error:
        return JSONResponse({'error': str(error)}, status_code=400)
    return JSONResponse({'ok': True})


@app.get("/verwaltung/export")
def admin_export_page(request: Request):
    volumes = session.query(Volume).filter_by(status=RELEASED).order_by(Volume.vz).all()
    counts = Counter(vid for (vid,) in session.query(Leaflet.volume_id))
    return templates.TemplateResponse(request, "export.html", {
        "volumes": [{"vz": v.vz, "title": v.title, "leaflets": counts[v.id]} for v in volumes if counts[v.id]]})


@app.get("/verwaltung/export.zip")
def admin_export(band: list[int] = Query(default=[]), exemplare: str = '', personen: str = '', seiten: str = ''):
    filename = f"flugblaetter-export-{datetime.date.today():%Y-%m-%d}.zip"
    content = export.zip_bytes(bands=band, main_only=exemplare == 'haupt', persons=personen != 'ohne', pages=seiten == '1')
    return Response(content=content, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/import/{vz}/ocr.zip")
def import_ocr_zip(vz: int):
    volume = import_volume_or_404(vz)
    if ocr.status(volume)['state'] != 'done':
        raise HTTPException(404)
    return Response(content=ocr.zip_result(volume), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{volume.stem}-ocr.zip"'})


@app.post("/import/{vz}/ocr-hochladen")
def import_ocr_upload(request: Request, vz: int, ergebnis: UploadFile = File(...)):
    volume = editable(vz)
    try:
        ocr.import_zip(volume, ergebnis.file)
    except ValueError as error:
        return import_page(request, vz, 'ocr', str(error), 400)
    return RedirectResponse(f"/import/{vz}?schritt=ocr", 303)


@app.post("/import/{vz}/schluessel")
def import_key(request: Request, vz: int, key: str = Form(''), forget: bool = Form(False), service: str = Form('datalab'),
               step: str = Form('ocr')):
    import_volume_or_404(vz)
    if service not in keys.SERVICES or step not in importer.STEPS:
        raise HTTPException(status_code=400)
    try:
        keys.forget(service) if forget else keys.save(service, key)
    except ValueError as error:
        return import_page(request, vz, step, str(error), 400)
    return RedirectResponse(f"/import/{vz}?schritt={step}", 303)


@app.post("/import/{vz}/vorschlag-text")
def import_suggest_from_text(vz: int):
    try:
        count = segments.suggest_from_text(import_volume_or_404(vz))
    except ValueError as error:
        return JSONResponse({'error': str(error)}, status_code=400)
    return JSONResponse({'ok': True, 'count': count})


@app.get("/volumes")
def volume_list(request: Request):
    logger.info('Opening volume list')

    counts = {}
    for (volume_id,) in session.query(Leaflet.volume_id):
        counts[volume_id] = counts.get(volume_id, 0) + 1

    rows = [{
        'vz': v.vz,
        'label': v.name,
        'title': v.title,
        'group': v.group,
        'anchor': group_anchor(v.group),
        'status': volume_status(v, counts.get(v.id, 0)),
    } for v in session.query(Volume).filter_by(status=RELEASED).order_by(Volume.vz)]

    return templates.TemplateResponse(
        request, "volume_list.html", {"volumes": rows})


def volume_by_vz(vz):
    volume = session.query(Volume).filter_by(vz=vz).first()
    if volume is None:
        raise HTTPException(404)
    return volume


THUMB_HEIGHT = 150


def issuer_names(leaflet_ids):
    """{leaflet id: [("AStA", "Allgemeiner Studentenausschuss"), ...]}; unresolved
    issuers as printed, with None as full name."""
    orgs = {o.id: (o.name, o.full_name or '') for o in session.query(Organization)}
    names = {}
    for i in session.query(LeafletIssuer).filter(LeafletIssuer.leaflet_id.in_(leaflet_ids),
                                                 LeafletIssuer.role == 'issuer'):
        name = orgs.get(i.org_id, (i.surface, None))
        if name not in names.setdefault(i.leaflet_id, []):
            names[i.leaflet_id].append(name)
    return names


def leaflet_items(leaflets):
    """Leaflets -> dicts for the macros in _leaflets.html."""
    volumes = {v.id: v for v in session.query(Volume).filter(
        Volume.id.in_({lf.volume_id for lf in leaflets}))}
    has_pdf = {vid: volume_pdf(v).is_file() for vid, v in volumes.items()}
    issuers = issuer_names([lf.id for lf in leaflets])
    group_sizes = Counter(g for (g,) in session.query(Leaflet.copy_group)
                          .filter(Leaflet.copy_group.isnot(None)))
    items = []
    for lf in leaflets:
        volume = volumes[lf.volume_id]
        date, date_label = list_date(lf, volume.year)
        items.append({'leaflet': lf, 'vz': volume.vz, 'place': f"Band {volume.vz:03d} · {page_range(lf.start_page, lf.end_page)}",
                      'date': date, 'date_label': date_label,
                      'year': leaflet_year(lf, volume.year),
                      'thumb': has_pdf[lf.volume_id],
                      'issuers': issuers.get(lf.id, []),
                      'copies': group_sizes[lf.copy_group] - 1
                      if lf.copy_group else 0,
                      'copies_checked': bool(lf.copies_checked),
                      'copy_alternative': bool(lf.copy_group and lf.copies_checked) and lf.canonical_leaflet_id != lf.id})
    return items


def short_pages(leaflet):
    return page_range(leaflet.start_page, leaflet.end_page).replace('Bandseiten ', 'S. ').replace('Bandseite ', 'S. ')


def page_groups(volume, leaflets):
    """Consecutive pages of the volume, grouped by leaflet (leaflet None: left out when splitting)."""
    by_id = {leaflet.id: leaflet for leaflet in leaflets}
    issuers = issuer_names(by_id)
    # duplicates point to their main copy
    mains = {lf.id: (lf, vol) for lf, vol in session.query(Leaflet, Volume).join(Volume).filter(
        Leaflet.id.in_({lf.canonical_leaflet_id for lf in leaflets
                        if lf.copies_checked and lf.canonical_leaflet_id not in (None, lf.id)}))}
    groups = []
    for p in session.query(Page).filter_by(volume_id=volume.id).order_by(Page.page_no):
        if groups and groups[-1]['leaflet_id'] == p.leaflet_id:
            groups[-1]['pages'].append(p.page_no)
        else:
            leaflet = by_id.get(p.leaflet_id)
            main = mains.get(leaflet.canonical_leaflet_id) if leaflet and leaflet.copies_checked else None
            groups.append({'leaflet_id': p.leaflet_id, 'leaflet': leaflet,
                           'main': {'id': main[0].id, 'label': f"{main[1].label.split(' (')[0]}, {short_pages(main[0])}"}
                           if main else None,
                           'issuers': ', '.join(short for short, _ in issuers.get(p.leaflet_id, [])),
                           'pages': [p.page_no]})
    return groups


@app.get("/volumes/{vz}")
def volume_detail(request: Request, vz: int, ansicht: str = ""):
    logger.info('Opening volume details')

    volume = volume_by_vz(vz)
    leaflets = session.query(Leaflet).filter_by(volume_id=volume.id) \
        .order_by(Leaflet.start_page).all()
    has_scans = bool(leaflets) and volume_pdf(volume).is_file()
    view = (ansicht if ansicht in ('liste', 'kacheln') else 'bandseiten') if has_scans else 'liste'
    orgs = sorted((o for o in session.query(Organization)
                   if volume.vz in (o.vz or [])), key=org_sort_key)

    vzs = [row.vz for row in session.query(Volume.vz).order_by(Volume.vz)]
    pos = vzs.index(volume.vz)

    data = {
        'prev_vz': vzs[pos - 1] if pos > 0 else None,
        'next_vz': vzs[pos + 1] if pos + 1 < len(vzs) else None,
        'label': volume.name,
        'vz': volume.vz,
        'draft': volume.status != RELEASED,
        'review': volume.status != RELEASED or volume.vz == reviewing(request),
        'group': volume.group,
        'anchor': group_anchor(volume.group),
        'signature': volume.signature,
        'portal_url': volume.portal_url,
        'n_pages': volume.n_pages,
        'n_excluded': session.query(Page).filter_by(volume_id=volume.id, leaflet_id=None).count(),  # left out when splitting
        'status': volume_status(volume, len(leaflets)),
        'provenance': provenance(volume),
        'organizations': orgs,
        'leaflets': leaflet_items(leaflets),
        'has_scans': has_scans,
        'view': view,
        'page_groups': page_groups(volume, leaflets) if view == 'bandseiten' else [],
    }

    return templates.TemplateResponse(
        request, "volume_details.html", {"volume": data})


@app.get("/volumes/{vz}/pages/{page_no}.jpg")
def volume_page_thumb(vz: int, page_no: int):
    volume = volume_by_vz(vz)
    pdf_path = volume_pdf(volume)
    if not pdf_path.is_file() or not 1 <= page_no <= (volume.n_pages or 0):
        raise HTTPException(404)
    jpg = pdf_service.render_thumb(pdf_path, page_no, height=2 * THUMB_HEIGHT)
    return Response(content=jpg, media_type="image/jpeg",
                    headers={"Cache-Control": "max-age=86400"})


@app.get("/volumes/{vz}/{start_page}")
def leaflet_permalink(vz: int, start_page: int):
    volume = volume_by_vz(vz)
    leaflet = session.query(Leaflet) \
        .filter_by(volume_id=volume.id, start_page=start_page).first()
    if leaflet is None:
        raise HTTPException(404)
    return RedirectResponse(f"/leaflets/{leaflet.id}")


@app.get("/volumes/{vz}/images/{name}")
def volume_image(vz: int, name: str):
    volume = volume_by_vz(vz)
    if not re.fullmatch(r"[0-9a-f]+_img\.(jpg|png)", name):
        raise HTTPException(404)

    path = pdf_service.PDF_DIR / volume.label / volume.stem / name
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)


FEW_DOCUMENTS = 5  # issuers with fewer documents are folded away in the list
BAR_SCALE_FLOOR = 5  # a bar is at least this many documents high on its scale: one document is a short bar, not a full one


def issuer_years(items):
    """org id (or NO_ORG, NOT_IN_REGISTER) -> {year: documents}, every document once."""
    years = defaultdict(Counter)
    for item in items:
        for org in set(item['orgs']):
            years[org][item['year']] += 1
    return years


def year_span(*counters):
    """Every year from the first to the last of these counters, so gaps stay visible."""
    found = sorted(int(y) for c in counters for y in c if y.isdigit())
    return [str(y) for y in range(found[0], found[-1] + 1)] if found else []


@app.get("/organizations")
def organization_list(request: Request, sortierung: str = ''):
    logger.info('Opening organization list')
    items = unique(faceted_items([])[0])
    years = issuer_years(items)
    span = year_span(*years.values())
    rows = []
    for org in sorted(session.query(Organization), key=org_sort_key):
        per_year = years.get(org.id, Counter())
        found = sorted(per_year)
        rows.append({'id': org.id, 'name': org.name, 'full_name': org.full_name, 'count': sum(per_year.values()),
                     'first': found[0] if found else '', 'last': found[-1] if found else '',
                     'bars': [(y, per_year[y]) for y in span], 'peak': max([*per_year.values(), BAR_SCALE_FLOOR]),
                     'search': ' '.join([org.name, org.full_name or '', *(org.variants or [])]).casefold()})
    sort = sortierung if sortierung in ('anzahl_auf', 'name_auf', 'name_ab', 'erst_auf', 'erst_ab') else 'anzahl_ab'
    if sort.startswith('anzahl'):
        rows.sort(key=lambda r: r['count'], reverse=sort == 'anzahl_ab')  # stable: ties stay by name
    elif sort.startswith('erst'):
        rows.sort(key=lambda r: r['first'] or '9999', reverse=sort == 'erst_ab')
    elif sort == 'name_ab':
        rows.reverse()
    used = [r for r in rows if r['count']]
    big = [r for r in used if r['count'] >= FEW_DOCUMENTS]
    return templates.TemplateResponse(
        request, "organization_list.html",
        {"organizations": big, "few": [r for r in used if r['count'] < FEW_DOCUMENTS], "unused": len(rows) - len(used),
         "span": span, "sort": sort, "total": len(items), "n_orgs": len(used),
         "no_org": sum(years[NO_ORG].values()), "unknown": sum(years[NOT_IN_REGISTER].values())})


@app.get("/organizations/{org_id}")
def organization_detail(request: Request, org_id: str, ansicht: str = "liste", sortierung: str = ""):
    logger.info('Opening organization details')

    org = session.get(Organization, org_id)

    if org is None:
        raise HTTPException(404)

    all_items = unique(faceted_items([])[0])
    sort = sortierung if sortierung in ('datum_ab', 'titel_auf', 'titel_ab', 'band') else 'datum_auf'
    key = {'datum': date_sort_key, 'titel': title_sort_key, 'band': lambda i: (i['vz'], i['leaflet'].start_page)}[sort.split('_')[0]]
    items = sorted((i for i in all_items if org_id in i['orgs']), key=key, reverse=sort.endswith('_ab'))
    per_year = Counter(i['year'] for i in items)
    # an undated document has the year of its volume only
    undated = Counter(i['year'] for i in items if not (i['leaflet'].date_iso or '')[:4].isdigit())
    topic_ids = Counter(i['leaflet'].topic_id for i in items if i['leaflet'].topic_id is not None)
    topics = {t.id: t for t in session.query(Topic).filter(Topic.id.in_(topic_ids))}
    partners = Counter(o for i in items for o in set(i['orgs']) if o != org_id and o not in SPECIAL + (MULTIPLE,))
    names = {o.id: o for o in session.query(Organization).filter(Organization.id.in_(partners))}
    has_thumbs = any(item['thumb'] for item in items)

    org_ids = [o.id for o in sorted(
        session.query(Organization), key=org_sort_key)]
    pos = org_ids.index(org.id)
    volumes = session.query(Volume).filter(Volume.vz.in_(org.vz or []))         .order_by(Volume.vz).all()

    data = {
        'id': org.id,
        'prev_id': org_ids[pos - 1] if pos > 0 else None,
        'next_id': org_ids[pos + 1] if pos + 1 < len(org_ids) else None,
        'name': org.name,
        'full_name': org.full_name,
        'type': org.type,
        'variants': [v for v in org.variants or [] if v not in (org.name, org.full_name)],
        'jahre': ' – '.join(dict.fromkeys([min(org.jahre), max(org.jahre)])) if org.jahre else '',
        'outside': [(y, n) for y, n in sorted(per_year.items()) if org.jahre and y not in org.jahre],
        'volumes': volumes,
        'notes': org.notes,
        'leaflets': items,
        'count': len(items),
        'period': ' – '.join(dict.fromkeys([min(per_year), max(per_year)])) if per_year else '',
        'bars': [(y, per_year[y], undated[y]) for y in year_span(Counter(i['year'] for i in all_items))],
        'peak': max([*per_year.values(), BAR_SCALE_FLOOR]),
        'topics': [{'title': short_topic_title(topics[t].title), 'count': n,
                    'url': '/leaflets?' + urlencode([('org', org_id), ('thema', t)])} for t, n in topic_ids.most_common(5)],
        'partners': [{'id': o, 'label': org_label(names[o]), 'count': n} for o, n in partners.most_common(5) if o in names],
        'view': 'kacheln' if ansicht == 'kacheln' and has_thumbs else 'liste',
        'has_thumbs': has_thumbs,
        'sort': sort,
    }

    return templates.TemplateResponse(
        request, "organization_details.html", {"org": data})
