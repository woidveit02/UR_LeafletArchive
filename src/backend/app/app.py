import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
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


@app.exception_handler(StarletteHTTPException)
async def not_found(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            request, "404.html", {}, status_code=404)
    raise exc


@app.get("/")
def index(request: Request):
    logger.info('Opening index page')
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/leaflets")
def leaflet_list(request: Request):
    logger.info('Opening leaflet list')

    leaflets = session.query(Leaflet).all()
    volumes = {v.id: v.label for v in session.query(Volume).all()}
    orgs = {o.id: o.name for o in session.query(Organization).all()}

    issuers_by_leaflet = {}
    for i in session.query(LeafletIssuer).filter_by(role='issuer').all():
        name = orgs[i.org_id] if i.org_id else i.surface
        names = issuers_by_leaflet.setdefault(i.leaflet_id, [])
        if name not in names:
            names.append(name)

    rows = [{
        'id': leaflet.id,
        'title': leaflet.title,
        'volume': volumes.get(leaflet.volume_id, ''),
        'date_text': leaflet.date_text,
        'issuers': ', '.join(issuers_by_leaflet.get(leaflet.id, [])),
    } for leaflet in leaflets]

    return templates.TemplateResponse(
        request, "leaflet_list.html", {"leaflets": rows})


@app.get("/leaflets/{leaflet_id}")
def leaflet_detail(request: Request, leaflet_id: int):
    logger.info('Opening leaflet details')

    leaflet = session.get(Leaflet, leaflet_id)

    if leaflet is None:
        raise HTTPException(404)

    issuers = session.query(LeafletIssuer) \
        .filter_by(leaflet_id=leaflet_id).all()
    volume = session.get(Volume, leaflet.volume_id)

    issuer_display = []
    seen_org_ids = set()
    for i in issuers:
        if i.role != 'issuer':
            continue
        if i.org_id:
            if i.org_id in seen_org_ids:
                continue
            seen_org_ids.add(i.org_id)
            org = session.get(Organization, i.org_id)
            issuer_display.append({'surface': org.name, 'org_id': i.org_id})
        else:
            issuer_display.append({'surface': i.surface, 'org_id': None})

    if leaflet.start_page == leaflet.end_page:
        pages = f'Bandseite {leaflet.start_page}'
    else:
        pages = f'Bandseiten {leaflet.start_page}–{leaflet.end_page}'

    page_rows = session.query(Page).filter_by(leaflet_id=leaflet_id) \
        .order_by(Page.page_no).all()

    pdf_path = pdf_service.PDF_DIR / volume.label / f"{volume.stem}.pdf"
    has_pdf = pdf_path.is_file()
    page_list = []
    for i, p in enumerate(page_rows, start=1):
        width, height = (pdf_service.page_size(pdf_path, p.page_no)
                         if has_pdf else (None, None))
        page_list.append({'no': p.page_no, 'index': i,
                          'blocks': p.blocks or [],
                          'width': width, 'height': height})

    siblings = [row.id for row in session.query(Leaflet.id)
                .filter_by(volume_id=leaflet.volume_id)
                .order_by(Leaflet.start_page)]
    pos = siblings.index(leaflet.id)

    data = {
        'id': leaflet.id,
        'title': leaflet.title,
        'prev_id': siblings[pos - 1] if pos > 0 else None,
        'next_id': siblings[pos + 1] if pos + 1 < len(siblings) else None,
        'volume': volume.label if volume else '',
        'date_text': leaflet.date_text,
        'date_type': leaflet.date_type,
        'doc_type': leaflet.doc_type,
        'pages': pages,
        'issuers': issuer_display,
        'signatories': [i.surface for i in issuers if i.role == 'signatory'],
        'page_list': page_list,
        'has_pdf': has_pdf,
    }

    return templates.TemplateResponse(
        request, "leaflet_details.html", {"leaflet": data})


@app.get("/leaflets/{leaflet_id}/pages/{page_no}.png")
def leaflet_page_image(leaflet_id: int, page_no: int, dpi: int = 110):
    leaflet = session.get(Leaflet, leaflet_id)
    if leaflet is None or not (
            leaflet.start_page <= page_no <= leaflet.end_page):
        raise HTTPException(404)

    volume = session.get(Volume, leaflet.volume_id)
    pdf_path = pdf_service.PDF_DIR / volume.label / f"{volume.stem}.pdf"
    if not pdf_path.is_file():
        raise HTTPException(404)

    png = pdf_service.render_page(
        pdf_path, page_no, dpi=max(72, min(dpi, 300)))
    return Response(content=png, media_type="image/png")


@app.get("/organizations")
def organization_list(request: Request):
    logger.info('Opening organization list')

    organizations = session.query(Organization).all()

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
def organization_detail(request: Request, org_id: str):
    logger.info('Opening organization details')

    org = session.get(Organization, org_id)

    if org is None:
        raise HTTPException(404)

    issuer_rows = session.query(LeafletIssuer).filter_by(org_id=org_id).all()
    leaflet_ids = {i.leaflet_id for i in issuer_rows}
    leaflets = session.query(Leaflet) \
        .filter(Leaflet.id.in_(leaflet_ids)).all()

    data = {
        'id': org.id,
        'name': org.name,
        'full_name': org.full_name,
        'type': org.type,
        'variants': org.variants,
        'jahre': org.jahre,
        'vz': org.vz,
        'gnd_id': org.gnd_id,
        'notes': org.notes,
        'leaflets': leaflets,
    }

    return templates.TemplateResponse(
        request, "organization_details.html", {"org": data})
