import pytest

from backend.app.app import app
from backend.app.app_helper import get_room_building, get_room_location
from backend.app.database.models import Room
from backend.app.database.session import session


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as test_client:
        yield test_client

def login_and_get_token(client):
    response = client.post(
        '/api/login',
        json={
            'username': 'stewDunt',
            'password': 'vu3,W_6F[3;8J:R>1uWK17sc@rbqv?',
        },
    )
    assert response.status_code == 200
    return response.get_json()['token']

def test_api_login_success_returns_token(client):
    response = client.post(
        '/api/login',
        json={
            'username': 'stewDunt',
            'password': 'vu3,W_6F[3;8J:R>1uWK17sc@rbqv?',
        },
    )

    data = response.get_json()

    assert response.status_code == 200
    assert data['message'] == 'Login successful'
    assert data['token']


def test_api_login_invalid_credentials_returns_401(client):
    response = client.post(
        '/api/login',
        json={'username': 'stewDunt', 'password': 'wrong-password'},
    )

    assert response.status_code == 401
    assert response.get_json()['message'] == 'Invalid username or password'


def test_myrole_allows_guest_access_without_token(client):
    response = client.get('/api/myrole')

    assert response.status_code == 200
    assert response.get_json() == {
        'username': 'guest',
        'groups': ['guest'],
    }

def test_room_helpers_return_existing_names():
    room = session.query(Room).first()

    assert room is not None
    assert get_room_building(room) == room.building_rel.name
    assert get_room_location(room) == room.building_rel.location_rel.name


def test_nearby_rooms_returns_a_small_result_list(client):
    room = next(
        current_room
        for current_room in session.query(Room).all()
        if current_room.latitude is not None and current_room.longitude is not None
    )

    response = client.get(
        '/api/rooms/nearby',
        query_string={
            'latitude': room.latitude,
            'longitude': room.longitude,
            'amt': 2,
        },
    )

    data = response.get_json()

    assert response.status_code == 200
    assert len(data['rooms']) <= 2
    assert data['rooms'][0]['id'] == room.id


def test_room_occupancy_returns_basic_data_for_student(client):
    room = session.query(Room).first()
    token = login_and_get_token(client)

    response = client.get(
        f'/api/rooms/{room.id}/occupancy',
        headers={'Authorization': f'Bearer {token}'},
    )

    data = response.get_json()

    assert response.status_code == 200
    assert data['room_id'] == room.id
    assert data['room_name'] == room.names[0]
    assert 'occupied' in data
