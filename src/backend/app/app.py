import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .database.session import session
from .database.models import Leaflet
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

    data = {
        'id': leaflet.id,
        'title': leaflet.title,
        'organisation': leaflet.organisation,
        'date': leaflet.date,
        'caption': leaflet.caption,
        'page_count': leaflet.page_count,
        'buzzwords': leaflet.buzzwords,
        'topics': leaflet.topics,
        'signatures': leaflet.signatures,
        'mentioned_names': leaflet.mentioned_names,
        'mentioned_locations': leaflet.mentioned_locations,
        'referenced_leaflets': leaflet.referenced_leaflets
    }

    return templates.TemplateResponse(
        request, "leaflet_details.html", {"leaflet": data})
