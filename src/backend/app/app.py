import logging
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import pdf_service
from .database.session import session
from .database.models import Leaflet, LeafletIssuer, Volume, Organization, Page
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
    """'1973-06-26' -> '26.06.1973'"""
    try:
        y, m, d = iso.split("-")
        return f"{d}.{m}.{y}"
    except (AttributeError, ValueError):
        return iso or ""


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
    received = None if leaflet.received_uncertain else iso_to_text(
        leaflet.received_date)
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
    raise exc


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


@app.get("/leaflets")
def leaflet_list(request: Request, org: str | None = None,
                 jahr: str | None = None, typ: str | None = None,
                 reihe: str | None = None, ansicht: str = "liste"):
    logger.info('Opening leaflet list')

    query = (
        session.query(Leaflet)
        .join(Volume, Leaflet.volume_id == Volume.id)
    )

    if org:
        matching_ids = (
            session.query(LeafletIssuer.leaflet_id)
            .filter(LeafletIssuer.org_id == org,
                    LeafletIssuer.role == 'issuer')
        )
        query = query.filter(Leaflet.id.in_(matching_ids))

    if typ:
        query = query.filter(Leaflet.doc_type == typ)

    if reihe:
        query = query.filter(Leaflet.series == reihe)

    items = leaflet_items(
        query.order_by(Volume.vz, Leaflet.start_page, Leaflet.id).all())
    if jahr:
        items = [item for item in items if item['year'] == jahr]

    organizations = sorted(session.query(Organization), key=org_sort_key)
    org_options = [{
        'id': o.id,
        'label': f"{o.full_name} ({o.name})" if o.full_name else o.name,
    } for o in organizations]

    used_types = {t for (t,) in session.query(
        Leaflet.doc_type).distinct() if t}
    type_options = [{
        'id': key,
        'label': label
    } for key, label in DOC_TYPES.items() if key in used_types]

    series_options = sorted({s for (s,) in session.query(
        Leaflet.series).distinct() if s}, key=str.casefold)

    # years of all leaflets, so the options stay while a filter is set
    volume_years = {v.id: v.year for v in session.query(Volume)}
    years = sorted({leaflet_year(lf, volume_years[lf.volume_id])
                    for lf in session.query(Leaflet)})

    params = {k: v for k, v in request.query_params.items()
              if v and k != 'ansicht'}
    query_string = '?' + urlencode(params) if params else ''
    return templates.TemplateResponse(
        request, "leaflet_list.html",
        {"leaflets": items, "org_options": org_options, "selected_org": org,
         "type_options": type_options, "selected_type": typ,
         "series_options": series_options, "selected_series": reihe,
         "years": years, "selected_year": jahr,
         "filtered": any((org, jahr, typ, reihe)),
         "view": 'kacheln' if ansicht == 'kacheln' else 'liste',
         "switch_base": '/leaflets' + query_string})


@app.get("/leaflets/{leaflet_id}")
def leaflet_detail(request: Request, leaflet_id: int):
    logger.info('Opening leaflet details')

    leaflet = session.get(Leaflet, leaflet_id)

    if leaflet is None:
        raise HTTPException(404)

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
            name = f"{org.full_name} ({org.name})" if org.full_name else org.name
            issuer_display.append({'surface': name, 'org_id': i.org_id})
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

    siblings = [row.id for row in session.query(Leaflet.id)
                .filter_by(volume_id=leaflet.volume_id)
                .order_by(Leaflet.start_page)]
    pos = siblings.index(leaflet.id)

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
        'volume': volume.label if volume else '',
        'volume_year': volume.year if volume else None,
        'volume_title': volume.title if volume else '',
        'volume_collection': volume.collection if volume else None,
        'date_text': leaflet.date_text,
        'date_iso': leaflet.date_iso,
        'date': iso_to_text(leaflet.date_iso),
        'date_type': leaflet.date_type,
        'received': german_date(leaflet.received_date),
        'received_uncertain': leaflet.received_uncertain,
        'evidence': {
            'Titel': evidence_items([(leaflet.title_blocks, leaflet.title_quote)]),
            'Datum': evidence_items([(leaflet.date_blocks, leaflet.date_quote)]),
            'Eingang im Archiv': evidence_items([(leaflet.received_blocks, leaflet.received_quote)]),
            'Herausgeber': evidence_items([(i.blocks, i.quote) for i in issuers]),
            'Unterzeichnende': evidence_items([(i.blocks, i.quote) for i in signatories]),
        },
        'doc_type': DOC_TYPES.get(leaflet.doc_type, leaflet.doc_type),
        'pages': pages,
        'issuers': issuer_display,
        'signatories': [{'name': i.surface,
                         'details': '; '.join(d for d in (i.function, i.marker) if d)}
                        for i in signatories],
        'page_list': page_list,
        'has_pdf': has_pdf,
        'copies': copies,
    }

    return templates.TemplateResponse(
        request, "leaflet_details.html", {"leaflet": data})


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
    orgs = {o.id: (o.name, o.full_name or '')
            for o in session.query(Organization)}
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
    view = ansicht if has_scans and ansicht in (
        'kacheln', 'bandseiten') else 'liste'
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
def organization_list(request: Request):
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

    return templates.TemplateResponse(
        request, "organization_list.html", {"organizations": rows})


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
