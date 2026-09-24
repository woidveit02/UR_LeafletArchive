import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .database.session import session
from .database.models import Leaflet, LeafletIssuer, Volume, Organization
from .app_helper import setup_logging


# Logging Setup
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="UR Leaflet Archive")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


# Main page
@app.get("/")
def index(request: Request):
    logger.info('Opening index page')
    return templates.TemplateResponse(request, "index.html", {})


# Leaflet list page
@app.get("/leaflets")
def leaflet_list(request: Request):
    logger.info('Opening leaflet list')

    leaflets = session.query(Leaflet).all()

    return templates.TemplateResponse(
        request, "leaflet_list.html", {"leaflets": leaflets})


# Leaflet details page
@app.get("/leaflets/{leaflet_id}")
def leaflet_detail(request: Request, leaflet_id: int):
    logger.info('Opening leaflet details')

    leaflet = session.get(Leaflet, leaflet_id)

    if leaflet is None:
        return JSONResponse({'message': 'Leaflet not found'}, status_code=404)

    issuers = session.query(LeafletIssuer).filter_by(leaflet_id=leaflet_id).all()
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

    data = {
        'id': leaflet.id,
        'title': leaflet.title,
        'volume': volume.label if volume else '',
        'date_text': leaflet.date_text,
        'date_type': leaflet.date_type,
        'doc_type': leaflet.doc_type,
        'pages': f'{leaflet.start_page}-{leaflet.end_page}',
        'issuers': issuer_display,
        'signatories': [i.surface for i in issuers if i.role == 'signatory'],
    }

    return templates.TemplateResponse(
        request, "leaflet_details.html", {"leaflet": data})


# Organization list page
@app.get("/organizations")
def organization_list(request: Request):
    logger.info('Opening organization list')

    organizations = session.query(Organization).all()

    return templates.TemplateResponse(
        request, "organization_list.html", {"organizations": organizations})


# Organization details page
@app.get("/organizations/{org_id}")
def organization_detail(request: Request, org_id: str):
    logger.info('Opening organization details')

    org = session.get(Organization, org_id)

    if org is None:
        return JSONResponse(
            {'message': 'Organization not found'}, status_code=404)

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
