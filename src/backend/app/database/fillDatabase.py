import json
import os
from pathlib import Path

from .session import session
from .models import Leaflet

# Data dir: LEAFLET_DATA_DIR in Docker (mounted), else repo-root data/.
if os.environ.get("LEAFLET_DATA_DIR"):
    DATA_DIR = Path(os.environ["LEAFLET_DATA_DIR"])
else:
    DATA_DIR = Path(__file__).resolve().parents[4] / "data"

# Loads the data of the leaflets_test.json file and returns it.
def load_leaflet_data():

    leaflet_file = DATA_DIR / "leaflets.json"

    with open(leaflet_file, encoding="utf-8") as f:
        return json.load(f)

# Takes the data of all leaflets, extracts the relevant information and fills the Leaflet table of the database with it.
def fill_leaflet_database(leaflet_data):

    for leaflet in leaflet_data:
        id = leaflet['id']
        title = leaflet['title']
        organisation = leaflet['organisation']
        date = leaflet['date']
        caption = leaflet['caption']
        page_count = leaflet['page_count']
        buzzwords = leaflet['buzzwords']
        topics = leaflet['topics']
        signatures = leaflet['signatures']
        mentioned_names = leaflet['mentioned_names']
        mentioned_locations = leaflet['mentioned_locations']
        referenced_leaflets = leaflet['referenced_leaflets']

        session.add(Leaflet(id=id,
                            title=title,
                            organisation=organisation,
                            date=date,
                            caption=caption,
                            page_count=page_count,
                            buzzwords=buzzwords,
                            topics=topics,
                            signatures=signatures,
                            mentioned_names=mentioned_names,
                            mentioned_locations=mentioned_locations,
                            referenced_leaflets=referenced_leaflets))

        session.commit()


# Main function to fill the database with data from JSON files via calling every fill function.
def fill_database():
    leaflet_data = load_leaflet_data()
    fill_leaflet_database(leaflet_data)