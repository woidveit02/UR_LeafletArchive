import logging
import logging.config
import math
import random
import json
import pathlib

from .database.session import session
from .database.models import Room, Event

logger = logging.getLogger(__name__)

# Helper functions for app logic

# https://www.youtube.com/watch?v=9L77QExPmI0
def setup_logging():
    config_file = pathlib.Path(__file__).resolve().parent / 'logs' / 'config.json'

    with open(config_file, encoding='utf-8') as f:
        config = json.load(f)

    file_handler = config.get('handlers', {}).get('file')
    if file_handler and file_handler.get('filename'):
        log_path = pathlib.Path(file_handler['filename'])

        if not log_path.parent.exists():
            log_path = config_file.parent / log_path.name
            file_handler['filename'] = str(log_path)

        log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.config.dictConfig(config)

# Gets the building name for a given room, if it exists
def get_room_building(room):
    logger.info('Getting building for room')

    if getattr(room, 'building_rel', None) is not None:
        return room.building_rel.name
    
    return None

# Gets the location name for a given room, if it exists
def get_room_location(room):
    logger.info('Getting location for room')

    building_rel = getattr(room, 'building_rel', None)

    if building_rel is None:
        return None

    location_rel = getattr(building_rel, 'location_rel', None)

    if location_rel is not None:
        return location_rel.name

    return None

# Gets the location name for a given building, if it exists
def get_building_location(building):
    logger.info('Getting location for building')

    if getattr(building, 'location_rel', None) is not None:
        return building.location_rel.name
    
    return None

# Gets the n (=amt) nearest rooms to a given latitude and longitude
def get_nearest_rooms(latitude, longitude, amt):
    logger.info('Finding nearest rooms')
    rooms = session.query(Room).all()
    rooms_with_distance = []

    for room in rooms:
        if room.latitude is None or room.longitude is None:
            continue

        distance = math.sqrt((latitude - room.latitude) ** 2 + (longitude - room.longitude) ** 2)
        rooms_with_distance.append((distance, room))

    rooms_with_distance.sort(key=lambda entry: entry[0])

    return [{
        'id': room.id,
        'name': room.names[0] if room.names else None,
        'category': room.category,
        'location': get_room_location(room),
        'building': get_room_building(room),
        'level': room.level,
        'latitude': room.latitude,
        'longitude': room.longitude,
    } for _, room in rooms_with_distance[:amt]]

# Gets the occupancy status of a room, including a random event if occupied
# There is a 20% chance that the room is unoccupied, and an 80% chance that it is occupied.
def get_room_occupancy(room):
    logger.info('Checking room occupancy')

    events = session.query(Event).all()

    if random.random() < 0.2:
        return {
            'room_id': room.id,
            'room_name': room.names[0] if room.names else None,
            'occupied': False,
            'event': None,
        }

    event = random.choice(events)
    
    return {
        'room_id': room.id,
        'room_name': room.names[0] if room.names else None,
        'occupied': True,
        'event': {
            'id': event.id,
            'name': event.name,
            'description': event.description,
        },
    }