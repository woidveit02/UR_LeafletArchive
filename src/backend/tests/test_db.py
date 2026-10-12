import pytest
from sqlalchemy import text

from backend.app.database.models import Leaflet, Volume
from backend.app.database.session import session

# Tests if there is a connection to the database and if the session object is properly created.
def test_database_connection():
    assert session is not None, "Database session should not be None"

# Tests if a simple query can be executed on the database.
def test_database_query():
    result = session.execute(text("SELECT 1")).fetchone()
    assert result[0] == 1, "Database should return 1 for SELECT 1 query"

# Tests if the expected tables (rooms, buildings, locations, users, events) exist in the database.
@pytest.mark.built_db
def test_expected_tables_exist():
    table_names = {
        row[0]
        for row in session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
    }
    assert {"leaflets"}.issubset(table_names)

# Tests if the database contains at least one leaflet entry.
@pytest.mark.built_db
def test_database_contains_basic_seed_data():
    assert session.query(Leaflet).count() >= 1

# Tests if all Findmittel units 1967-1973 exist and imported leaflets point to one of them.
@pytest.mark.built_db
def test_volumes_from_findmittel():
    assert session.query(Volume).filter(Volume.vz <= 15).count() == 15
    leaflet = session.query(Leaflet).first()
    assert session.get(Volume, leaflet.volume_id).title
