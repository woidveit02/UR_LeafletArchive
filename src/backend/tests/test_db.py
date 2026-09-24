from sqlalchemy import text

from backend.app.database.models import Building, Location, Room, User
from backend.app.database.session import session

# Tests if there is a connection to the database and if the session object is properly created.
def test_database_connection():
    assert session is not None, "Database session should not be None"

# Tests if a simple query can be executed on the database.
def test_database_query():
    result = session.execute(text("SELECT 1")).fetchone()
    assert result[0] == 1, "Database should return 1 for SELECT 1 query"

# Tests if the expected tables (rooms, buildings, locations, users, events) exist in the database.
def test_expected_tables_exist():
    table_names = {
        row[0]
        for row in session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
    }
    assert {"rooms", "buildings", "locations", "users", "events"}.issubset(table_names)

# Tests if the database contains at least one entry for each of the main models (Room, Building, Location, User).
def test_database_contains_basic_seed_data():
    assert session.query(Location).count() >= 1
    assert session.query(Building).count() >= 1
    assert session.query(Room).count() >= 1
    assert session.query(User).count() >= 1

# Tests if a room has an associated building and location, which are expected to be present in the database.
def test_room_has_building_and_location():
    room = session.query(Room).first()

    assert room is not None
    assert room.building_rel is not None
    assert room.building_rel.location_rel is not None
