import logging
import re
import unicodedata
from collections import Counter
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
from .database import corrections, search
from .database.fillDatabase import (CORRECTIONS, VOLUMES, automatic_record,
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
    items = filtered_items(params)

    # counts over all leaflets, so the options stay while a filter is set
    leaflets = session.query(Leaflet).all()
    volume_years = {v.id: v.year for v in session.query(Volume)}
    org_counts = Counter(org for _, org in session.query(LeafletIssuer.leaflet_id, LeafletIssuer.org_id)
                         .filter(LeafletIssuer.role == 'issuer', LeafletIssuer.org_id.isnot(None))
                         .distinct())
    type_counts = Counter(lf.doc_type for lf in leaflets)
    series_counts = Counter(lf.series for lf in leaflets if lf.series)
    year_counts = Counter(leaflet_year(lf, volume_years[lf.volume_id]) for lf in leaflets)
    topic_counts = Counter(lf.topic_id for lf in leaflets if lf.topic_id is not None)

    org_options = [{
        'id': o.id,
        'label': (f"{o.name} – {o.full_name}" if o.full_name else o.name) + f" ({org_counts[o.id]})",
    } for o in sorted(session.query(Organization), key=org_sort_key)
        if org_counts[o.id] or o.id == selected.get('org')]
    type_options = [{'id': key, 'label': f"{label} ({type_counts[key]})"}
                    for key, label in DOC_TYPES.items() if type_counts[key]]
    series_options = [{'id': s, 'label': f"{s} ({n})"}
                      for s, n in sorted(series_counts.items(), key=lambda x: x[0].casefold())]
    topic_options = [{
        'id': topic.id,
        'label': f"{short_topic_title(topic.title)} ({topic_counts[topic.id]})",
        'full_title': topic.title,
    } for topic in session.query(Topic).order_by(Topic.id)
        if topic_counts[topic.id] or str(topic.id) == selected.get('thema')]
    years = [{'id': y, 'label': f"{y} ({n})"} for y, n in sorted(year_counts.items())]

    query_string = '?' + urlencode(params) if params else ''
    date_reset_params = [(k, v) for k, v in params if k != 'datum']
    if ansicht == 'kacheln':
        date_reset_params.append(('ansicht', 'kacheln'))
    return templates.TemplateResponse(
        request, "leaflet_list.html",
        {"leaflets": items, "total": len(leaflets), "org_options": org_options, "selected_org": selected.get('org'),
         "type_options": type_options, "selected_type": selected.get('typ'),
         "series_options": series_options, "selected_series": selected.get('reihe'),
         "topic_options": topic_options, "selected_topic": selected.get('thema'),
         "selected_sort": selected.get('sortierung'),
         "selected_q": selected.get('q', ''),
         "q_short": bool(selected.get('q')) and not search.tokens(selected['q']),
         "selected_dates": [v for k, v in params if k == 'datum'],
         "date_reset_url": '/leaflets' + ('?' + urlencode(date_reset_params)
                                           if date_reset_params else ''),
         "years": years, "selected_year": selected.get('jahr'),
         "filtered": sum(k != 'sortierung' for k, _ in params),
         "view": 'kacheln' if ansicht == 'kacheln' else 'liste',
         "switch_base": '/leaflets' + query_string,
         "detail_qs": query_string})


# filters and sorting of the leaflet list; the detail page pages through the same selection
LIST_PARAMS = ('q', 'org', 'jahr', 'typ', 'reihe', 'thema', 'datum', 'sortierung')


def list_params(request):
    """List parameters of the request, repeated ones (datum) included."""
    params = []
    for key, value in request.query_params.multi_items():
        if key == 'q':
            value = ' '.join(value.split())[:search.MAX_QUERY]
        if key in LIST_PARAMS and value:
            params.append((key, value))
    return params


def search_hits(query, q):
    """Restricts `query` to the full-text hits for `q`.

    Returns (query, ranked): with FTS hits the query also yields (rank, snippet) columns.
    Queries without a word of three characters cannot use the trigram index and
    fall back to a substring search in title and series.
    """
    match = search.match_expression(q)
    if match:
        hits = search.hits_subquery(match)
        return (query.join(hits, hits.c.leaflet_id == Leaflet.id)
                .add_columns(hits.c.rank, hits.c.snippet), True)
    pattern = search.like_pattern(q)
    return query.filter(or_(Leaflet.title.ilike(pattern, escape='\\'),
                            Leaflet.series.ilike(pattern, escape='\\'))), False


def attach_snippets(items, raw_snippets):
    """Adds 'snippet' (safe HTML) to the items; hits outside the OCR text show its beginning."""
    missing = [lid for lid, raw in raw_snippets.items() if not search.has_match(raw)]
    first_text = {}
    if missing:
        for leaflet_id, page_text in (session.query(Page.leaflet_id, Page.text)
                                      .filter(Page.leaflet_id.in_(missing))
                                      .order_by(Page.page_no)):
            first_text.setdefault(leaflet_id, page_text)
    for item in items:
        lid = item['leaflet'].id
        if lid in first_text:
            item['snippet'] = search.fallback_snippet(first_text[lid])
        elif lid in raw_snippets:
            item['snippet'] = search.render_snippet(raw_snippets[lid])


def filtered_items(params):
    one = dict(params)
    q = one.get('q', '')
    query = (
        session.query(Leaflet)
        .join(Volume, Leaflet.volume_id == Volume.id)
    )

    ranked = False
    if q:
        query, ranked = search_hits(query, q)
    if one.get('org'):
        matching_ids = (
            session.query(LeafletIssuer.leaflet_id)
            .filter(LeafletIssuer.org_id == one['org'],
                    LeafletIssuer.role == 'issuer')
        )
        query = query.filter(Leaflet.id.in_(matching_ids))
    if one.get('typ'):
        query = query.filter(Leaflet.doc_type == one['typ'])
    if one.get('reihe'):
        query = query.filter(Leaflet.series == one['reihe'])
    if one.get('thema'):
        query = query.filter(Leaflet.topic_id == one['thema'])
    datum = [v for k, v in params if k == 'datum']
    if datum:
        query = query.filter(Leaflet.date_type.in_(datum))

    sort = one.get('sortierung', '')
    by_relevance = ranked and not sort.startswith(('datum_', 'titel_'))
    order = [Volume.vz, Leaflet.start_page, Leaflet.id]
    if by_relevance:
        order = [literal_column('hits.rank')] + order
    rows = query.order_by(*order).all()
    raw_snippets = {}
    if ranked:
        raw_snippets = {row[0].id: row.snippet for row in rows}
        rows = [row[0] for row in rows]
    items = leaflet_items(rows)
    attach_snippets(items, raw_snippets)
    if one.get('jahr'):
        items = [item for item in items if item['year'] == one['jahr']]
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
                   f"{page_range(lf.start_page, lf.end_page)}"}
                  for lf, vol in rows]

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
        org_label(org) if org else None,
        chosen.get('reihe'),
        short_topic_title(chosen_topic.title) if chosen_topic else None,
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
        'corrected': leaflet.corrected or [],
        'automatic': automatic_text(leaflet),
    }

    org_names = [org_label(o) for o in sorted(session.query(Organization), key=org_sort_key)
                 ] if edit else []
    return templates.TemplateResponse(
        request, "leaflet_details.html",
        {"leaflet": data, "edit": edit, "error": error, "doc_types": DOC_TYPES,
         "date_types": DATE_TYPES, "org_names": org_names,
         "series_names": sorted({s for (s,) in session.query(Leaflet.series) if s})
         if edit else []},
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


@app.post("/leaflets/{leaflet_id}/bearbeiten")
async def leaflet_save(request: Request, leaflet_id: int):
    leaflet = leaflet_or_404(leaflet_id)
    raw = parse_qs((await request.body()).decode(), keep_blank_values=True)

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
    if error:
        return detail_page(request, leaflet, form, error)

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
    return back_to(request, leaflet_id)


@app.post("/leaflets/{leaflet_id}/zuruecksetzen")
async def leaflet_revert(request: Request, leaflet_id: int):
    """Back to the automatic values, for one field or all ("revert" line)."""
    leaflet = leaflet_or_404(leaflet_id)
    field = parse_qs((await request.body()).decode()).get('field', ['all'])[0]
    if field != 'all' and field not in corrections.FIELDS:
        raise HTTPException(400)
    key = segment(leaflet)
    corrections.append(CORRECTIONS, [{**key, 'field': 'revert', 'value': field}])
    reset_leaflet(leaflet)
    corrections.apply(leaflet, corrections.by_segment(corrections.load(CORRECTIONS)).get(
        tuple(key.values()), []))
    session.commit()
    return back_to(request, leaflet_id)


def back_to(request, leaflet_id):
    query = request.url.query
    return RedirectResponse(f"/leaflets/{leaflet_id}" + (f"?{query}" if query else ''),
                            status_code=303)


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
    return templates.TemplateResponse(
        request, "corrections.html", {"rows": rows, "fields": corrections.FIELDS})


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
    page = session.query(Page).filter_by(
        volume_id=leaflet.volume_id, page_no=page_no).first()
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
    issuers as printed, with an empty full name."""
    orgs = {o.id: (o.name, o.full_name or '') for o in session.query(Organization)}
    names = {}
    for i in session.query(LeafletIssuer).filter(LeafletIssuer.leaflet_id.in_(leaflet_ids),
                                                 LeafletIssuer.role == 'issuer'):
        name = orgs.get(i.org_id, (i.surface, ''))
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
                      if lf.copy_group else 0})
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
