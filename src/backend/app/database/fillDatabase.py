import json
import random
from pathlib import Path
from werkzeug.security import generate_password_hash

from .session import session
from .models import Room, User, Event, Building, Location

# Path to the data directory, which contains the JSON files to fill the database with.
DATA_DIR = Path(__file__).resolve().parents[4] / "data"

# Loads the data of the raumdaten.json file and returns it.
def load_room_data():

    room_file = DATA_DIR / "raumdaten.json"

    with open(room_file, encoding="utf-8") as f:
        return json.load(f)

# Fills the Location table of the database with the location "Universität Regensburg".
def fill_location_database():

    location = Location(name="Universität Regensburg")
    session.add(location)
    session.commit()

    return location

# Takes the raw room data as a parameter, extracts all buildings and fills the Building table.
def fill_building_database(room_data, location):

    buildings = {}
    building_names = {room["bauwerk"] for room in room_data}

    for name in building_names:
        building = Building(name=name,location_id=location.id)
        session.add(building)
        session.commit()

        buildings[name] = building.id

    return buildings

# Takes the data of all rooms, extracts the relevant information and fills the Room table of the database with it.
def fill_room_database(room_data, buildings):

    for room in room_data:
        id = room['id']
        secondary_ids = [room['raumcode'],
                         room['urwalking_uid'],
                         room['urwalking_name']]
        names = [room['hoersaal']]
        category = room['hoersaalkategorie']
        comment = ""

        building_id = buildings.get(room['bauwerk'])
        level = room['level']
        longitude = room['longitude']
        latitude = room['latitude']

        seats_amount = room['plaetze']
        seats_arrangement = random.choice(["ansteigend",
                                   "frontal",
                                   "hufeisenförmig"]) # randomly assigned test data

        outlet_amount = random.randrange(0, 8)
        projector = random.choice(["Panasonic PT-RQ25KEJ",
                                   "Hisense PX3 Pro TriChroma 4K",
                                   "Hisense C2 Ultra"]) # randomly assigned test data
        projector_resolution = random.choice(["1920x1080",
                                              "3840x2160",
                                              "7680x4320"]) # randomly assigned test data
        lighting = random.choice(["Tageslicht",
                                  "abdunkelbar",
                                  "kein natürliches Licht",
                                  "LED-Beleuchtung"]) # randomly assigned test data

        foto1 = room['foto1']
        foto2 = room['foto2']
        foto1_info = room['fotoinfoterm1']
        foto2_info = room['fotoinfoterm2']
        pdf = room['pdf']

        session.add(Room(id=id,
                         secondary_ids=secondary_ids,
                         names=names,
                         category=category,
                         comment=comment,
                         building_id=building_id,
                         level=level,
                         longitude=longitude,
                         latitude=latitude,
                         seats_amount=seats_amount,
                         seats_arrangement=seats_arrangement,
                         outlet_amount=outlet_amount,
                         projector=projector,
                         projector_resolution=projector_resolution,
                         lighting=lighting,
                         foto1=foto1,
                         foto2=foto2,
                         foto1_info=foto1_info,
                         foto2_info=foto2_info,
                         pdf=pdf))

        session.commit()

# Takes the data of the userdaten.json file and fills the User table of the database with it.
def fill_user_database():

    user_file = DATA_DIR / "userdaten.json"

    with open(user_file, encoding="utf-8") as f:
        user_data = json.load(f)

    for user in user_data:
        id = user['id']
        username = user['username']
        email = user['email']
        password = user['password']
        groups = user['groups']

        # https://www.youtube.com/watch?v=8ebIEefhBpM
        hashed_password = generate_password_hash(password)

        session.add(User(id=id,
                         username=username,
                         email=email,
                         password=hashed_password,
                         groups=groups))

        session.commit()

# Takes the data of the eventdaten.json file and fills the Event table of the database with it.
def fill_event_database():

    event_file = DATA_DIR / "eventdaten.json"

    with open(event_file, encoding="utf-8") as f:
        event_data = json.load(f)

    for event in event_data:
        id = event['id']
        name = event['name']
        description = event['description']

        session.add(Event(id=id,
                          name=name,
                          description=description))

        session.commit()


# Main function to fill the database with data from JSON files via calling every fill function.
def fill_database():
    room_data = load_room_data()
    locations = fill_location_database()
    buildings = fill_building_database(room_data, locations)
    fill_room_database(room_data, buildings)
    fill_user_database()
    fill_event_database()
