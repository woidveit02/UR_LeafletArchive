import logging
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from html import unescape
import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import literal_column, or_
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import pdf_service
from .database import copy_decisions, corrections, search
from .database.fillDatabase import (COPY_DECISIONS, CORRECTIONS, VOLUMES, automatic_record, copy_review,
                                    fill_copies,
                                    automatic_values, reset_leaflet, series_names)
from .database.session import session
from .database.models import (Leaflet, LeafletIssuer, Volume, Organization, Page,
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
            'issuers': names('issuer'), 'signatories': names('signatory')}
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
FEATURED = [(4, 101), (4, 234), (4, 263), (4, 180)]


@app.get("/")
def index(request: Request):
    logger.info('Opening index page')
    featured = [session.query(Leaflet).join(Volume)
                .filter(Volume.vz == vz, Leaflet.start_page == page).first()
                for vz, page in FEATURED]
    volume_years = {v.id: v.year for v in session.query(Volume)}
    per_year = Counter(leaflet_year(lf, volume_years[lf.volume_id])
                       for lf in session.query(Leaflet))
    years = [int(y) for y in per_year if y.isdigit()]
    # every year in the range, so gaps in the collection stay visible
    timeline = [(str(y), per_year[str(y)])
                for y in range(min(years), max(years) + 1)] if years else []
    stats = {
        'leaflets': sum(per_year.values()),
        'organizations': session.query(LeafletIssuer.org_id)
        .filter(LeafletIssuer.org_id.isnot(None)).distinct().count(),
        'volumes': len(volume_years),
        'volumes_done': session.query(Leaflet.volume_id).distinct().count(),
    }
    return templates.TemplateResponse(
        request, "index.html",
        {"stats": stats, "timeline": timeline,
         "featured": leaflet_items([lf for lf in featured if lf]),
         "max_count": max(per_year.values(), default=1)})


def date_sort_key(item):
    """Sort by the leaflet's date, else the archive stamp, else the year."""
    lf = item['leaflet']
    if iso_to_text(lf.date_iso):
        return lf.date_iso
    if not lf.received_uncertain and iso_to_text(lf.received_date):
        return lf.received_date
    return item['year']


def title_sort_key(item):
    """Title without leading quotes or dashes, case-insensitive, Ä sorted as A."""
    title = unicodedata.normalize('NFD', re.sub(r'^\W+', '', item['leaflet'].display_title or ''))
    return ''.join(c for c in title if not unicodedata.combining(c)).casefold()


@app.get("/themen")
def topic_list(request: Request):
    logger.info('Opening topic list')
    topic_year_counts = {}
    for leaflet, volume_year in session.query(Leaflet, Volume.year).join(
            Volume, Leaflet.volume_id == Volume.id).filter(
                Leaflet.topic_id.isnot(None)):
        year = leaflet_year(leaflet, volume_year)
        topic_year_counts.setdefault(leaflet.topic_id, Counter())[year] += 1

    years = sorted(
        {year for counts in topic_year_counts.values() for year in counts},
        key=int)
    topics = []
    for topic in session.query(Topic).order_by(Topic.id):
        year_counts = topic_year_counts.get(topic.id, Counter())
        max_count = max(year_counts.values(), default=1)
        topics.append({
            'id': topic.id,
            'title': topic.title,
            'words': topic.words or [],
            'title_note': TOPIC_TITLE_NOTES.get(topic.source),
            'count': sum(year_counts.values()),
            'years': [{
                'year': year,
                'count': year_counts.get(year, 0),
                'height': round(year_counts.get(year, 0) / max_count * 100),
            } for year in years],
        })
    topics.sort(key=lambda t: t['count'], reverse=True)  # stable: ties stay by id
    return templates.TemplateResponse(
        request, "topic_list.html", {"topics": topics, "years": years})


@app.get("/leaflets")
def leaflet_list(request: Request, ansicht: str = "liste"):
    logger.info('Opening leaflet list')
    params = list_params(request)
    selected = dict(params)
    items, counts = faceted_items(params)
    view = ansicht if ansicht in ('kacheln', 'fundstellen') else 'liste'
    found = passages(items, selected) if view == 'fundstellen' and selected.get('q') else []
    if view != 'fundstellen' and search.terms(selected.get('q', '')):
        attach_passages(items, selected['q'])

    def shown(key):
        """Values of a facet with hits, plus the selected one."""
        return {v for v, n in counts[key].items() if n and v} | (
            {selected[key]} if key in selected else set())

    def url(pairs):
        """List address for the parameter pairs, in the current view."""
        pairs = pairs + ([('ansicht', view)] if view != 'liste' else [])
        return '/leaflets' + ('?' + urlencode(pairs) if pairs else '')

    def toggle_url(key, value):
        """List address with `key` set to `value`, or without it if already chosen."""
        rest = [(k, v) for k, v in params if k != key]
        return url(rest + ([(key, value)] if selected.get(key) != value else []))

    def facet(key, label_of, sub_of=lambda v: ''):
        """Entries of a facet list: the selected one first, 'none' last, else by count."""
        values = sorted(shown(key), key=lambda v: (v != selected.get(key), v in SPECIAL,
                                                   -counts[key][v], label_of(v).casefold()))
        return [{'label': label_of(v), 'sub': sub_of(v), 'count': counts[key][v],
                 'url': toggle_url(key, v), 'active': v == selected.get(key),
                 'none': v in SPECIAL} for v in values]

    orgs = {o.id: o for o in session.query(Organization)}
    topics = {str(t.id): t for t in session.query(Topic)}

    labels = {
        'org': lambda o: {NO_ORG: 'kein Herausgeber erkannt', NOT_IN_REGISTER: 'nicht im Register'}.get(
            o, orgs[o].name if o in orgs else o),
        'thema': lambda t: 'ohne Thema' if t == NO_TOPIC else topics[t].title if t in topics else t,
        'typ': lambda t: DOC_TYPES.get(t, t),
        'datum': lambda d: DATE_TYPE_LABELS.get(d, d),
        'q': lambda v: f"„{v}“",
    }

    axis = sorted({str(v.year) for v in session.query(Volume)} | shown('jahr'))
    highest = max(counts['jahr'].values(), default=0) or 1
    facets = {
        'years': [{'year': y, 'count': counts['jahr'][y], 'url': toggle_url('jahr', y),
                   'height': round(counts['jahr'][y] / highest * 75),
                   'active': y == selected.get('jahr')} for y in axis],
        'orgs': facet('org', labels['org'], lambda o: orgs[o].full_name or '' if o in orgs else ''),
        'topics': facet('thema', labels['thema']),
        'types': facet('typ', labels['typ']),
        'series': facet('reihe', str),
        'dates': facet('datum', labels['datum']),
    }

    # chips above the results, each removes its own parameter
    active_filters = [{'label': short_topic_title(labels['thema'](v)) if k == 'thema'
                       else labels.get(k, str)(v),
                       'url': url([p for p in params if p != (k, v)])}
                      for k, v in params if k != 'sortierung']

    query_string = '?' + urlencode(params) if params else ''
    return templates.TemplateResponse(
        request, "leaflet_list.html",
        {"leaflets": items, "total": session.query(Leaflet).count(), "facets": facets,
         "hidden_params": [(k, v) for k, v in params if k in FACETS],
         "active_filters": active_filters, "reset_all_url": url([]),
         "clear_search_url": url([(k, v) for k, v in params if k != 'q']),
         "selected_sort": selected.get('sortierung'),
         "selected_q": selected.get('q', ''),
         "q_short": bool(selected.get('q')) and not search.terms(selected['q']),
         "filtered": sum(k not in ('q', 'sortierung') for k, _ in params),
         "view": view, "passages": found[:PASSAGE_LIMIT], "passage_count": len(found),
         "switch_base": '/leaflets' + query_string,
         "detail_qs": query_string})


PASSAGE_LIMIT = 500


def passages(items, params):
    """Occurrences of the search terms in the OCR text of the items, by date unless sorted otherwise."""
    texts = search.ocr_texts(session, [i['leaflet'].id for i in items])
    if not params.get('sortierung'):
        items = sorted(items, key=date_sort_key)
    return [{'item': item, 'n': n, 'left': left, 'hit': hit, 'right': right}
            for item in items
            for n, (left, hit, right) in enumerate(
                search.kwic(texts.get(item['leaflet'].id, ''), params['q']), start=1)]


# filters and sorting of the leaflet list; the detail page pages through the same selection
LIST_PARAMS = ('q', 'org', 'jahr', 'typ', 'reihe', 'thema', 'datum', 'sortierung')


def list_params(request):
    """List parameters of the request as (key, value) pairs."""
    params = []
    for key, value in request.query_params.multi_items():
        if key == 'q':
            value = ' '.join(value.split())[:search.MAX_QUERY]
        if key in LIST_PARAMS and value:
            params.append((key, value))
    return params


def search_hits(query, q):
    """Restricts `query` to the full-text hits for `q`.

    Returns (query, ranked): with FTS hits the query also yields a rank column.
    Queries without a word of three characters cannot use the trigram index and
    fall back to a substring search in title and series.
    """
    match = search.match_expression(q)
    if match:
        hits = search.hits_subquery(match)
        return (query.join(hits, hits.c.leaflet_id == Leaflet.id)
                .add_columns(hits.c.rank), True)
    pattern = search.like_pattern(q)
    return query.filter(or_(Leaflet.title.ilike(pattern, escape='\\'),
                            Leaflet.series.ilike(pattern, escape='\\'))), False


def attach_passages(items, q):
    """Adds 'snippets' (all passages as safe HTML) and 'hits' (their number) to the items;
    hits outside the OCR text show its beginning."""
    texts = search.ocr_texts(session, [i['leaflet'].id for i in items])
    for item in items:
        text = texts.get(item['leaflet'].id, '')
        found = search.kwic(text, q, width=35)  # one line in the result list
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
}


def filtered_items(params):
    return faceted_items(params)[0]


def faceted_items(params):
    """(items, counts): the selection, and per facet the counts over the items that
    match all other filters, so each option shows what choosing it would give."""
    chosen = {k: v for k, v in params if k in FACETS}
    items = searched_items(params)

    def matches(item, skip=None):
        return all(v in FACETS[k](item) for k, v in chosen.items() if k != skip)

    counts = {key: Counter(value for item in items if matches(item, key)
                           for value in FACETS[key](item))
              for key in FACETS}
    return [item for item in items if matches(item)], counts


def searched_items(params):
    """Items for the search and sort order of `params`; facets are left to the caller."""
    one = dict(params)
    q = one.get('q', '')
    query = (
        session.query(Leaflet)
        .join(Volume, Leaflet.volume_id == Volume.id)
    )

    ranked = False
    if q:
        query, ranked = search_hits(query, q)

    sort = one.get('sortierung', '')
    by_relevance = ranked and not sort.startswith(('datum_', 'titel_'))
    order = [Volume.vz, Leaflet.start_page, Leaflet.id]
    if by_relevance:
        order = [literal_column('hits.rank')] + order
    rows = query.order_by(*order).all()
    if ranked:
        rows = [row[0] for row in rows]
    items = leaflet_items(rows)
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
              else f"{short[lf.id]}, " + page_range(lf.start_page, lf.end_page).replace('Bandseiten ', 'S. ').replace('Bandseite ', 'S. ')}
             for lf in ordered]

    # coming from a filtered list: page through that selection, else through the volume
    selection = list_params(request)
    siblings = [i['leaflet'].id for i in filtered_items(selection)] if selection else []
    if leaflet.id not in siblings:
        selection = []
        siblings = [row.id for row in session.query(Leaflet.id)
                    .filter_by(volume_id=leaflet.volume_id)
                    .order_by(Leaflet.start_page)]
    pos = siblings.index(leaflet.id)
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
    )

    data = {
        'id': leaflet.id,
        'title': leaflet.display_title,
        'title_from_series': not leaflet.title and bool(leaflet.series),
        'series': leaflet.series_label,
        'volume_vz': volume.vz,
        'provenance_model': (volume.meta_model or '').split('/')[-1],
        'provenance_date': german_date(volume.meta_created),
        'prev_id': siblings[pos - 1] if pos > 0 else None,
        'next_id': siblings[pos + 1] if pos + 1 < len(siblings) else None,
        'position': pos + 1,
        'in_volume': len(siblings),
        'qs': '?' + urlencode(selection) if selection else '',
        'selection': ' · '.join(filter(None, selection_labels)),
        'highlight': [v for t in search.terms(chosen.get('q', '')) for v in search.variants(t)],
        'volume': volume.label if volume else '',
        'volume_year': volume.year if volume else None,
        'volume_title': volume.title if volume else '',
        'volume_collection': volume.collection if volume else None,
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
        'issuers': issuer_display,
        'signatories': [{'name': i.surface,
                         'details': '; '.join(d for d in (i.function, i.marker) if d)}
                        for i in signatories],
        'page_list': page_list,
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
        {"leaflet": data, "edit": edit, "error": error, **(edit_choices() if edit else {})},
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
    for k in ('title', 'date', 'series'):
        form[f'{k}_blocks'] = blocks(raw.get(f'{k}_blocks', [''])[0])
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
                        ('series', ['series', 'issue'])):
        keys = keys + [f'{field}_blocks']
        if [form[k] for k in keys] != [old[k] for k in keys]:
            value = {'date': {'iso': form['date_iso'], 'type': form['date_type']},
                     'series': {'name': form['series'], 'issue': form['issue']}
                     }.get(field, form[field])
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
            groups.setdefault(leaflet.copy_group, {'members': [], 'new': 0})['members'].append((leaflet, volume))
        if leaflet.copy_candidate_of:
            groups.setdefault(leaflet.copy_candidate_of, {'members': [], 'new': 0})['new'] += 1
    rows = []
    for key, group in groups.items():
        main = next(lf for lf, _ in group['members'] if lf.id == lf.canonical_leaflet_id)
        rows.append({'group': key, 'id': main.id, 'title': main.display_title, 'new': group['new'],
                     'state': 'neu' if group['new'] else 'geprueft' if main.copies_checked else 'offen',
                     'labels': [f"{v.label}, {page_range(lf.start_page, lf.end_page)}" + (' (Hauptexemplar)' if lf is main and main.copies_checked else '')
                                for lf, v in group['members']]})
    return rows


def review_queue(leaflet):
    """The groups still to check, seen from the leaflet's group: the main copies of the previous and the next
    one, the position of this group among them (None if it is checked) and their number."""
    rows = copy_rows()
    key = leaflet.copy_candidate_of or leaflet.copy_group
    here = next((i for i, r in enumerate(rows) if r['group'] == key), len(rows))
    todo = lambda r: r['state'] != 'geprueft'
    before, after = [r for r in rows[:here] if todo(r)], [r for r in rows[here + 1:] if todo(r)]
    current = here < len(rows) and todo(rows[here])
    return {'previous': before[-1]['id'] if before else None, 'next': after[0]['id'] if after else None,
            'position': len(before) + 1 if current else None, 'total': len(before) + len(after) + current}


@app.get("/exemplare")
def copy_list(request: Request, status: str = ''):
    """All groups of copies with the state of their review; each opens its comparison page."""
    rows = copy_rows()
    counts = Counter(r['state'] for r in rows)
    shown = [r for r in rows if r['state'] == status] if status in COPY_STATES else rows
    first = next((r['id'] for r in rows if r['state'] != 'geprueft'), None)
    return templates.TemplateResponse(
        request, "copy_list.html",
        {"rows": shown, "total": len(rows), "counts": counts, "states": COPY_STATES, "status": status, "first": first})


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


GAP = '<mark class="gap" data-diff="{}" title="Im anderen Duplikat nicht erkannt">∅</mark>'


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


COPY_MESSAGES = {'angaben': 'Angaben aktualisiert.', 'gespeichert': 'Prüfung gespeichert.',
                 'zurueckgenommen': 'Prüfung zurückgenommen, es gilt wieder der automatische Vorschlag.'}


def shorten(cards):
    """Sets the short name: the page range alone when all copies are in one volume (said once on the page)."""
    same = len({c['volume'] for c in cards}) == 1
    for c in cards:
        c['label'] = f"{c['volume']}, {c['range']}"
        c['short'] = c['range'] if same else c['label']
    return same


TAKE_KEYS = {'title': ['title'], 'date': ['date_iso', 'date_type'], 'series': ['series', 'issue'],
             'doc_type': ['doc_type'], 'issuers': ['issuers'], 'signatories': ['signatories']}


def field_text(values, field):
    """A field of current_values as shown, for comparing leaflets."""
    if field == 'date':
        return ' '.join(filter(None, [german_date(values['date_iso']), DATE_TYPES.get(values['date_type'], '')
                                      if values['date_iso'] else '']))
    if field == 'series':
        return ' '.join(filter(None, [values['series'], values['issue']]))
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
    """Compares the copies of a group side by side: confirm, exclude, choose the main copy, correct the details."""
    return copy_view(request, leaflet_or_404(leaflet_id), meldung, bool(offen))


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
         "offers": offers, "queue": review_queue(leaflet), "simple": len(cards) == 2 and not new, **edit_choices()},
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
    lists = [copy_blocks(by_id[i]) for i in ids]
    sides = ocr_pair(*lists) if len(ids) == 2 else ocr_group(lists)
    for card, side in zip(cards, sides):
        card['letter'] = letters[card['id']]
        card['ocr'] = side
    return {'cards': cards, 'max_pages': max(c['pages'] for c in cards), 'checked': checked}


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
    if not members:
        raise HTTPException(404)

    def ids(name):
        return {int(v) for v in form.get(name, []) if v.isdigit()}
    mine = {copy_decisions.anchor(segment(lf)) for lf in members + candidates}
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
    stay = verdict.startswith('edit:') or 'stay' in form  # choose the main copy and go on to its details
    if verdict:  # a pair: "main:<id>" or "edit:<id>" chooses that main copy, "different" says these are two leaflets
        members = copy_group_of(leaflet)[0]
        main = verdict[5:] if verdict.startswith(('main:', 'edit:')) else str(members[0].canonical_leaflet_id or members[0].id)
        form['main'] = [main]
        form['out'] = [str(lf.id) for lf in members if str(lf.id) != main] if verdict == 'different' else []
    following = None if 'revert' in form or stay else review_queue(leaflet)['next']
    save_copy_review(leaflet, form)
    if following:  # on to the next group that is not checked
        return RedirectResponse(f"/leaflets/{following}/exemplare", status_code=303)
    if not copy_group_of(leaflet)[0]:  # a leaflet that was excluded no longer has a comparison page
        return RedirectResponse(f"/leaflets/{leaflet_id}", status_code=303)
    message = 'zurueckgenommen' if 'revert' in form else 'gespeichert'
    return RedirectResponse(f"/leaflets/{leaflet_id}/exemplare?meldung={message}{'&offen=1' if stay else ''}", status_code=303)


@app.get("/korrekturen")
def correction_list(request: Request):
    """Corrections whose page range no longer matches a segment."""
    volumes = {v.stem: v for v in session.query(Volume) if v.stem}
    rows = []
    for (stem, start, end), entries in corrections.by_segment(
            corrections.load(CORRECTIONS)).items():
        volume = volumes.get(stem)
        overlaps = session.query(Leaflet).filter(
            Leaflet.volume_id == volume.id, Leaflet.start_page <= end,
            Leaflet.end_page >= start).order_by(Leaflet.start_page).all() if volume else []
        if any((lf.start_page, lf.end_page) == (start, end) for lf in overlaps):
            continue
        rows.append({'segment': f"{volume.label if volume else stem}, {page_range(start, end)}",
                     'entries': entries, 'overlaps': overlaps})
    copies = [{'at': r['at'], 'members': [
        f"{volumes[a['volume']].label if a['volume'] in volumes else a['volume']}, "
        f"{page_range(a['start_page'], a['end_page'])}" for a in r['members']]}
        for r in copy_review()[1]]
    return templates.TemplateResponse(
        request, "corrections.html", {"rows": rows, "copies": copies, "fields": corrections.FIELDS})


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


@app.get("/volumes")
def volume_list(request: Request):
    logger.info('Opening volume list')

    counts = {}
    for (volume_id,) in session.query(Leaflet.volume_id):
        counts[volume_id] = counts.get(volume_id, 0) + 1

    rows = [{
        'vz': v.vz,
        'label': v.label,
        'title': v.title,
        'group': v.group,
        'anchor': group_anchor(v.group),
        'collection': v.collection,
        'status': volume_status(v, counts.get(v.id, 0)),
    } for v in session.query(Volume).order_by(Volume.vz)]

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
        items.append({'leaflet': lf, 'vz': volume.vz,
                      'date': date, 'date_label': date_label,
                      'year': leaflet_year(lf, volume.year),
                      'thumb': has_pdf[lf.volume_id],
                      'issuers': issuers.get(lf.id, []),
                      'copies': group_sizes[lf.copy_group] - 1
                      if lf.copy_group else 0,
                      'copies_checked': bool(lf.copies_checked),
                      'copy_alternative': bool(lf.copy_group and lf.copies_checked) and lf.canonical_leaflet_id != lf.id})
    return items


def page_groups(volume, leaflets):
    """Consecutive pages of the volume, grouped by leaflet (None = no leaflet)."""
    pdf_path = volume_pdf(volume)
    by_id = {leaflet.id: leaflet for leaflet in leaflets}
    issuers = issuer_names(by_id)
    groups = []
    for p in session.query(Page).filter_by(volume_id=volume.id).order_by(Page.page_no):
        width, height = pdf_service.page_size(pdf_path, p.page_no)
        thumb = {'no': p.page_no, 'height': THUMB_HEIGHT,
                 'width': round(THUMB_HEIGHT * width / height)}
        if groups and groups[-1]['leaflet_id'] == p.leaflet_id:
            groups[-1]['pages'].append(thumb)
        else:
            groups.append({'leaflet_id': p.leaflet_id, 'leaflet': by_id.get(p.leaflet_id),
                           'issuers': ', '.join(short for short, _ in issuers.get(p.leaflet_id, [])),
                           'pages': [thumb]})
    return groups


@app.get("/volumes/{vz}")
def volume_detail(request: Request, vz: int, ansicht: str = "liste"):
    logger.info('Opening volume details')

    volume = volume_by_vz(vz)
    leaflets = session.query(Leaflet).filter_by(volume_id=volume.id) \
        .order_by(Leaflet.start_page).all()
    has_scans = bool(leaflets) and volume_pdf(volume).is_file()
    view = ansicht if has_scans and ansicht in ('kacheln', 'bandseiten') else 'liste'
    orgs = sorted((o for o in session.query(Organization)
                   if volume.vz in (o.vz or [])), key=org_sort_key)

    vzs = [row.vz for row in session.query(Volume.vz).order_by(Volume.vz)]
    pos = vzs.index(volume.vz)

    data = {
        'prev_vz': vzs[pos - 1] if pos > 0 else None,
        'next_vz': vzs[pos + 1] if pos + 1 < len(vzs) else None,
        'label': volume.label,
        'vz': volume.vz,
        'group': volume.group,
        'anchor': group_anchor(volume.group),
        'title': volume.title,
        'signature': volume.signature,
        'portal_url': volume.portal_url,
        'collection': volume.collection,
        'n_pages': volume.n_pages,
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


@app.get("/organizations")
def organization_list(request: Request, sortierung: str = ''):
    logger.info('Opening organization list')

    organizations = sorted(session.query(Organization), key=org_sort_key)

    leaflet_ids_by_org = {}
    issuer_rows = session.query(LeafletIssuer) \
        .filter(LeafletIssuer.org_id.isnot(None))
    for i in issuer_rows:
        leaflet_ids_by_org.setdefault(i.org_id, set()).add(i.leaflet_id)

    rows = [{
        'id': org.id,
        'name': org.name,
        'full_name': org.full_name,
        'count': len(leaflet_ids_by_org.get(org.id, set())),
    } for org in organizations]
    sort = sortierung if sortierung in ('anzahl_auf', 'name_auf', 'name_ab') else 'anzahl_ab'
    if sort.startswith('anzahl'):
        rows.sort(key=lambda r: r['count'], reverse=sort == 'anzahl_ab')  # stable: ties stay by name
    elif sort == 'name_ab':
        rows.reverse()

    return templates.TemplateResponse(
        request, "organization_list.html", {"organizations": rows, "sort": sort})


@app.get("/organizations/{org_id}")
def organization_detail(request: Request, org_id: str, ansicht: str = "liste"):
    logger.info('Opening organization details')

    org = session.get(Organization, org_id)

    if org is None:
        raise HTTPException(404)

    issuer_rows = session.query(LeafletIssuer).filter_by(org_id=org_id).all()
    leaflet_ids = {i.leaflet_id for i in issuer_rows}
    leaflets = leaflet_items(
        session.query(Leaflet).join(Volume, Leaflet.volume_id == Volume.id)
        .filter(Leaflet.id.in_(leaflet_ids)).order_by(Volume.vz, Leaflet.start_page).all())
    has_thumbs = any(item['thumb'] for item in leaflets)

    org_ids = [o.id for o in sorted(
        session.query(Organization), key=org_sort_key)]
    pos = org_ids.index(org.id)
    volumes = session.query(Volume).filter(Volume.vz.in_(org.vz or [])) \
        .order_by(Volume.vz).all()

    data = {
        'id': org.id,
        'prev_id': org_ids[pos - 1] if pos > 0 else None,
        'next_id': org_ids[pos + 1] if pos + 1 < len(org_ids) else None,
        'name': org.name,
        'full_name': org.full_name,
        'type': org.type,
        'variants': org.variants,
        'jahre': org.jahre,
        'volumes': volumes,
        'gnd_id': org.gnd_id,
        'notes': org.notes,
        'leaflets': leaflets,
        'view': 'kacheln' if ansicht == 'kacheln' and has_thumbs else 'liste',
        'has_thumbs': has_thumbs,
    }

    return templates.TemplateResponse(
        request, "organization_details.html", {"org": data})
