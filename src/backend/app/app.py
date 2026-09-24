import os
import logging

from flask import Flask, render_template, request, jsonify, g, make_response

from .database.session import session
from .database.models import Leaflet
from .app_helper import setup_logging



# Logging Setup
setup_logging()
logger = logging.getLogger(__name__)

# https://www.youtube.com/watch?v=-mN3VyJuCjM
app = Flask(__name__)
app.json.ensure_ascii = False

# Swagger UI setup
# Swagger documentation file was generated using ai
# Prompt: "Erstelle mir eine Swagger Dokumentation basierend auf der app.py. Dokumentiere nur die API-Endpunkte und nicht die Flask-Routes"
# https://www.youtube.com/watch?v=iZ2Tah3IxQc
SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'


# Main page
@app.route('/')
def index():
    logger.info('Opening index page')
    return render_template('index.html')


# Room list page
@app.route('/leaflets', methods=['GET'])
def leaflet_list():
    logger.info('Opening leaflet list')

    leaflets = session.query(Leaflet).all()

    return render_template('leaflet_list.html', leaflets=leaflets)


# Leaflet details page
@app.route('/leaflets/<int:leaflet_id>', methods=['GET'])
def leaflet_detail(leaflet_id):
    logger.info('Opening leaflet details')

    leaflet = session.get(Leaflet, leaflet_id)

    if leaflet is None:
        return jsonify({'message': 'Leaflet not found'}), 404

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


    return render_template(
        'leaflet_details.html',
        leaflet=data
    )