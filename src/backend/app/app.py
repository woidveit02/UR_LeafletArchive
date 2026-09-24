import os
import datetime
import logging
import jwt
from werkzeug.security import check_password_hash

from flask import Flask, render_template, request, jsonify, g, make_response
from flask_swagger_ui import get_swaggerui_blueprint

from .database.session import session
from .database.models import User, Room, Event, Location, Building
from .app_decorator import role_required
from .app_helper import get_room_building, get_room_location, get_building_location, get_nearest_rooms, get_room_occupancy, setup_logging

# Logging Setup
setup_logging()
logger = logging.getLogger(__name__)

# https://www.youtube.com/watch?v=-mN3VyJuCjM
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get(
                                        'SECRET_KEY',
                                        'change-me-in-production'
                                        )
app.json.ensure_ascii = False

# Swagger UI setup
# Swagger documentation file was generated using ai
# Prompt: "Erstelle mir eine Swagger Dokumentation basierend auf der app.py. Dokumentiere nur die API-Endpunkte und nicht die Flask-Routes"
# https://www.youtube.com/watch?v=iZ2Tah3IxQc
SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "woidveits RoomManager"
    }
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# ===============
# Main site pages
# ===============

# Main page
@app.route('/')
def index():
    logger.info('Opening index page')
    return render_template('index.html')


# Login page
# https://www.youtube.com/watch?v=duE5P1hG6sg
# https://www.youtube.com/watch?v=ZWEIeLiysp0
@app.route('/app/login', methods=['GET','POST'])
def login():
    logger.info('Opening login page')
    if request.method == 'GET':
        return render_template('login.html')
    
    username = request.form.get('username')
    password = request.form.get('password')

    user = session.query(User).filter_by(username=username).first()

    if user and password and check_password_hash(user.password, password):
        payload = {
            'user_id': user.id,
            'username': user.username,
            'groups': user.groups,
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        }
        token = jwt.encode(payload,
                           app.config['SECRET_KEY'],
                           algorithm='HS256')
        response = make_response(render_template('login.html',
                               success='Login erfolgreich.',
                               username=user.username))
        response.set_cookie('token', token, httponly=True)
        return response
    else:
        return render_template('login.html',
                               error='Ungueltiger Benutzername oder Passwort.'), 401

# Room list page
@app.route('/rooms', methods=['GET'])
@role_required('guest', 'student', 'employee', 'admin', app=app)
def room_list():
    logger.info('Opening room list')

    rooms = session.query(Room).all()

    return render_template('room_list.html', rooms=rooms)

# Building list page
@app.route('/buildings', methods=['GET'])
@role_required('guest', 'student', 'employee', 'admin', app=app)
def building_list():
    logger.info('Opening building list')

    buildings = session.query(Building).all()

    return render_template('building_list.html', buildings=buildings)

# Location list page
@app.route('/locations', methods=['GET'])
@role_required('guest', 'student', 'employee', 'admin', app=app)
def location_list():
    logger.info('Opening location list')

    locations = session.query(Location).all()

    return render_template('location_list.html', locations=locations)

# Room search page
@app.route('/rooms/search', methods=['GET'])
@role_required('guest', 'student', 'employee', 'admin', app=app)
def room_search():
    logger.info('Opening room search')

    query = (request.args.get('query') or '').strip()
    rooms = session.query(Room).all()

    if query:
        search_term = query.lower()
        rooms = [
            room for room in rooms
            if any(search_term in name.lower() for name in (room.names or []))
        ]

    return render_template('room_search.html', rooms=rooms)


# Room map page
@app.route('/rooms/map', defaults={'level': None}, methods=['GET'])
@app.route('/rooms/map/<int:level>', methods=['GET'])
@role_required('guest', 'student', 'employee', 'admin', app=app)
def room_map(level):
    logger.info('Opening room map')

    rooms_query = session.query(Room)

    if level is None:
        rooms = rooms_query.all()
    else:
        rooms = rooms_query.filter_by(level=level).all()

    room_markers = []

    for room in rooms:
        if room.latitude is None or room.longitude is None:
            continue

        room_markers.append({
            'id': room.id,
            'name': room.names[0] if room.names else 'Kein Name',
            'latitude': room.latitude,
            'longitude': room.longitude,
        })

    return render_template('room_map.html', rooms=room_markers, selected_level=level)


# Room details page
@app.route('/rooms/<int:room_id>', methods=['GET'])
@role_required('guest', 'student', 'employee', 'admin', app=app)
def room_detail(room_id):
    logger.info('Opening room details')

    room = session.get(Room, room_id)

    if room is None:
        return jsonify({'message': 'Room not found'}), 404

    data = {
        'id': room.id,
        'name': room.names[0] if room.names else None,
        'comment': room.comment,
        'category': room.category,
        'location': get_room_location(room),
        'building': get_room_building(room),
        'level': room.level,
        'longitude': room.longitude,
        'latitude': room.latitude,
        'seats_amount': room.seats_amount,
        'seats_arrangement': room.seats_arrangement,
        'outlet_amount': room.outlet_amount,
    }

    if g.current_roles & {'student', 'employee', 'admin'}:
        data.update({
            'projector': room.projector,
            'projector_resolution': room.projector_resolution,
            'lighting': room.lighting,
            'foto1': room.foto1,
            'foto2': room.foto2,
            'foto1_info': room.foto1_info,
            'foto2_info': room.foto2_info,
            'pdf': room.pdf,
        })

    return render_template(
        'room_details.html',
        room=data,
        nearby=get_nearest_rooms(room.latitude, room.longitude, 5),
        can_manage='admin' in g.current_roles,
    )

# Building details page
@app.route('/buildings/<int:building_id>', methods=['GET'])
@role_required('guest', 'student', 'employee', 'admin', app=app)
def building_detail(building_id):
    logger.info('Opening building details')

    building = session.get(Building, building_id)

    if building is None:
        return jsonify({'message': 'Building not found'}), 404

    data = {
        'id': building.id,
        'name': building.name,
        'location': get_building_location(building),
    }

    rooms = session.query(Room).filter_by(building_id=building.id).all()

    return render_template('building_details.html', building=data, rooms=rooms)

# Location details page
@app.route('/locations/<int:location_id>', methods=['GET'])
@role_required('guest', 'student', 'employee', 'admin', app=app)
def location_detail(location_id):
    logger.info('Opening location details')

    location = session.get(Location, location_id)

    if location is None:
        return jsonify({'message': 'Location not found'}), 404

    data = {
        'id': location.id,
        'name': location.name,
    }

    buildings = session.query(Building).filter_by(location_id=location.id).all()

    return render_template('location_details.html', location=data, buildings=buildings)

# ==================
# Backend API routes
# ==================

@app.route('/api/login', methods=['GET','POST'])
def api_login():
    logger.info('API login called')

    data = request.get_json(silent=True) or {}
    username = data.get('username')
    password = data.get('password')


    user = session.query(User).filter_by(username=username).first()

    if user and password and check_password_hash(user.password, password):
        payload = {
            'user_id': user.id,
            'username': user.username,
            'groups': user.groups,
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        }
        token = jwt.encode(payload,
                           app.config['SECRET_KEY'],
                           algorithm='HS256')
        return jsonify({'message': 'Login successful', 'token': token})
    else:
        return jsonify({'message': 'Invalid username or password'}), 401

# Role checking test route
@app.route('/api/myrole', methods=['GET'])
@role_required('guest', 'student', 'employee', 'admin', app=app)
def return_role():
    logger.info('Returning current role')
    return jsonify({
        'username': g.current_user.get('username'),
        'groups': sorted(g.current_roles),
    })

# Nearby rooms API route
@app.route('/api/rooms/nearby', methods=['GET'])
@role_required('guest', 'student', 'employee', 'admin', app=app)
def nearby_rooms():
    logger.info('Nearby rooms requested')

    latitude = request.args.get('latitude', type=float)
    longitude = request.args.get('longitude', type=float)
    amt = request.args.get('amt', default=5, type=int)

    if latitude is None or longitude is None:
        return jsonify({'message': 'Query parameters are missing'}), 400

    if amt is None or amt <= 0:
        return jsonify({'message': 'Query parameter amt must be a positive integer'}), 400

    results = get_nearest_rooms(latitude, longitude, amt)

    return jsonify({'rooms': results})

# Room occupancy API route
@app.route('/api/rooms/<int:room_id>/occupancy', methods=['GET'])
@role_required('student', 'employee', 'admin', app=app)
def room_occupancy(room_id):
    logger.info('Room occupancy requested')

    room = session.get(Room, room_id)

    if room is None:
        return jsonify({'message': 'Room not found'}), 404

    return jsonify(get_room_occupancy(room))


# Delete building API route
@app.route('/api/buildings/<int:building_id>', methods=['DELETE'])
@role_required('admin', app=app)
def delete_building(building_id):
    logger.info('Deleting building')

    building = session.get(Building, building_id)

    if building is None:
        return jsonify({'message': 'Building not found'}), 404

    try:
        session.delete(building)
        session.commit()
        return jsonify({'message': 'Building deleted successfully'})
    except Exception as e:
        session.rollback()
        return jsonify({'message': f'Database error: {str(e)}'}), 500

# Delete location API route
@app.route('/api/locations/<int:location_id>', methods=['DELETE'])
@role_required('admin', app=app)
def delete_location(location_id):
    logger.info('Deleting location')

    location = session.get(Location, location_id)

    if location is None:
        return jsonify({'message': 'Location not found'}), 404

    try:
        session.delete(location)
        session.commit()
        return jsonify({'message': 'Location deleted successfully'})
    except Exception as e:
        session.rollback()
        return jsonify({'message': f'Database error: {str(e)}'}), 500
    
# ======================
# Admin management pages
# ======================

# Management page
@app.route('/admin', methods=['GET'])
@role_required('admin', app=app)
def manager_page():
    logger.info('Opening admin page')
    return render_template('room_manager.html')

# Add room page
@app.route('/admin/add', methods=['GET'])
@role_required('admin', app=app)
def add_room_page():
    logger.info('Opening add room page')
    return render_template('room_manager_add.html')

# Edit room page
@app.route('/admin/edit', methods=['GET'])
@role_required('admin', app=app)
def edit_room_page():
    logger.info('Opening edit room page')

    room_id = request.args.get('room_id', type=int)
    room_data = None

    if room_id is not None:
        room = session.get(Room, room_id)

        if room is None:
            return render_template('room_manager_edit.html',
                                   error='Raum nicht gefunden'), 404

        room_data = {
            'id': room.id,
            'secondary_ids': ', '.join(str(item) for item in (room.secondary_ids or [])),
            'names': ', '.join(str(item) for item in (room.names or [])),
            'category': room.category or '',
            'comment': room.comment or '',
            'building_id': room.building_id if room.building_id is not None else '',
            'level': room.level if room.level is not None else '',
            'longitude': room.longitude if room.longitude is not None else '',
            'latitude': room.latitude if room.latitude is not None else '',
            'seats_amount': room.seats_amount if room.seats_amount is not None else '',
            'seats_arrangement': room.seats_arrangement or '',
            'outlet_amount': room.outlet_amount if room.outlet_amount is not None else '',
            'projector': room.projector or '',
            'projector_resolution': room.projector_resolution or '',
            'lighting': room.lighting or '',
            'foto1': room.foto1 or '',
            'foto2': room.foto2 or '',
            'foto1_info': room.foto1_info or '',
            'foto2_info': room.foto2_info or '',
            'pdf': room.pdf or '',
        }

    return render_template('room_manager_edit.html', room_data=room_data)

# Delete room page
@app.route('/admin/delete', methods=['GET'])
@role_required('admin', app=app)
def delete_room_page():
    logger.info('Opening delete room page')
    return render_template('room_manager_delete.html')

# ===================================
# Admin database import/export routes
# ===================================

# Database export API route
@app.route('/api/export', methods=['GET'])
@role_required('admin', app=app)
def export_database():
    logger.info('Exporting database')
    return jsonify({
        'locations': [{col.name: getattr(loc, col.name) for col in Location.__table__.columns} for loc in session.query(Location).all()],
        'buildings': [{col.name: getattr(bld, col.name) for col in Building.__table__.columns} for bld in session.query(Building).all()],
        'rooms': [{col.name: getattr(room, col.name) for col in Room.__table__.columns} for room in session.query(Room).all()],
        'users': [{col.name: getattr(user, col.name) for col in User.__table__.columns} for user in session.query(User).all()],
        'events': [{col.name: getattr(event, col.name) for col in Event.__table__.columns} for event in session.query(Event).all()],
    })

# Database import API route
@app.route('/api/import', methods=['POST'])
@role_required('admin', app=app)
def import_database():
    logger.info('Importing database')
    try:
        data = request.get_json()

        if not data:
            return jsonify({'message': 'Keine JSON-Daten vorhanden'}), 400
        
        for loc_data in data.get('locations', []):
            loc = Location(**{k: v for k, v in loc_data.items() if k != 'id'})
            session.add(loc)
        
        for bld_data in data.get('buildings', []):
            bld = Building(**{k: v for k, v in bld_data.items() if k != 'id'})
            session.add(bld)
        
        for room_data in data.get('rooms', []):
            room = Room(**{k: v for k, v in room_data.items() if k != 'id'})
            session.add(room)
        
        for user_data in data.get('users', []):
            user = User(**{k: v for k, v in user_data.items() if k != 'id'})
            session.add(user)
        
        for event_data in data.get('events', []):
            event = Event(**{k: v for k, v in event_data.items() if k != 'id'})
            session.add(event)
        
        session.commit()
        return jsonify({'message': 'Daten erfolgreich importiert'})
    
    except Exception as e:
        session.rollback()
        return jsonify({'message': f'Fehler beim Import: {str(e)}'}), 500
    
# ============================
# Admin room management routes
# ============================

# Create room
@app.route('/admin/rooms/add', methods=['POST'])
@role_required('admin', app=app)
def add_room():
    logger.info('Adding room')

    def split_list(val):
        return [s.strip() for s in val.split(',') if s.strip()] if val else []

    def to_int(val):
        try: return int(val)
        except (TypeError, ValueError): return None

    def to_float(val):
        try: return float(val)
        except (TypeError, ValueError): return None

    room = Room(
        secondary_ids=split_list(request.form.get('secondary_ids')),
        names=split_list(request.form.get('names')),
        category=request.form.get('category') or None,
        comment=request.form.get('comment') or None,
        building_id=to_int(request.form.get('building_id')),
        level=to_int(request.form.get('level')),
        longitude=to_float(request.form.get('longitude')),
        latitude=to_float(request.form.get('latitude')),
        seats_amount=to_int(request.form.get('seats_amount')),
        seats_arrangement=request.form.get('seats_arrangement') or None,
        outlet_amount=to_int(request.form.get('outlet_amount')),
        projector=request.form.get('projector') or None,
        projector_resolution=request.form.get('projector_resolution') or None,
        lighting=request.form.get('lighting') or None,
        foto1=request.form.get('foto1') or None,
        foto2=request.form.get('foto2') or None,
        foto1_info=request.form.get('foto1_info') or None,
        foto2_info=request.form.get('foto2_info') or None,
        pdf=request.form.get('pdf') or None,
    )

    try:
        session.add(room)
        session.commit()
    except Exception as e:
        session.rollback()
        return render_template('room_manager_add.html',
                               error=f'Datenbankfehler: {str(e)}')

    return render_template('room_manager_add.html',
                           success='Raum erfolgreich hinzugefügt!')


# Delete room
@app.route('/admin/rooms/delete', methods=['POST'])
@role_required('admin', app=app)
def delete_room():
    logger.info('Deleting room')

    room_id = request.form.get('room_id', type=int)

    room = session.get(Room, room_id)

    if room is None:
        return render_template('room_manager_delete.html',
                               error='Raum nicht gefunden'), 404

    try:
        session.delete(room)
        session.commit()
    except Exception as e:
        session.rollback()
        return render_template('room_manager_delete.html',
                               error=f'Datenbankfehler: {str(e)}')

    return render_template('room_manager_delete.html',
                           success='Raum erfolgreich gelöscht!')


# Update room
@app.route('/admin/rooms/edit', methods=['POST'])
@role_required('admin', app=app)
def update_room():
    logger.info('Updating room')

    room_id = request.form.get('room_id', type=int)

    room = session.get(Room, room_id)

    if room is None:
        return render_template('room_manager_edit.html',
                               error='Raum nicht gefunden'), 404

    updatable_fields = [
        'secondary_ids', 'names', 'category', 'comment', 'building_id',
        'level', 'longitude', 'latitude', 'seats_amount', 'seats_arrangement',
        'outlet_amount', 'projector', 'projector_resolution', 'lighting',
        'foto1', 'foto2', 'foto1_info', 'foto2_info', 'pdf',
    ]

    for field in updatable_fields:
        if request.form.get(field) not in ("", None):
            if field in ['secondary_ids', 'names']:
                setattr(room, field, [s.strip() for s in request.form.get(field).split(',') if s.strip()])
            elif field in ['building_id', 'level', 'seats_amount', 'outlet_amount']:
                try:
                    setattr(room, field, int(request.form.get(field)))
                except ValueError:
                    return render_template('room_manager_edit.html',
                                           error=f'Invalid integer value for {field}')
            elif field in ['longitude', 'latitude']:
                try:
                    setattr(room, field, float(request.form.get(field)))
                except ValueError:
                    return render_template('room_manager_edit.html',
                                           error=f'Invalid float value for {field}')
            else:
                setattr(room, field, request.form.get(field))

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        return render_template('room_manager_edit.html',
                               error=f'Datenbankfehler: {str(e)}')

    return render_template('room_manager_edit.html',
                           success='Raum erfolgreich bearbeitet!')