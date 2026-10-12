"""The tests never touch the real database: LEAFLET_DB points to a temporary file before the app is imported.
The few tests that read a built database (marked built_db) run on a copy of the file named in LEAFLET_BUILT_DB, else they are skipped."""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

os.environ["LEAFLET_DB"] = str(Path(tempfile.mkdtemp(prefix="leaflet-tests-")) / "leaflet_database.db")
if os.environ.get("LEAFLET_BUILT_DB"):
    shutil.copy(os.environ["LEAFLET_BUILT_DB"], os.environ["LEAFLET_DB"])

from backend.app.database import session  # noqa: E402

assert session.DB_PATH.parent != session.BACKEND_DIR, "the tests must not use the real database"


def pytest_collection_modifyitems(items):
    if os.environ.get("LEAFLET_BUILT_DB"):
        return
    skip = pytest.mark.skip(reason="needs a built database: set LEAFLET_BUILT_DB to a copy of leaflet_database.db")
    for item in items:
        if "built_db" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def no_trend_cache():
    from backend.app import app as leaflet_app
    leaflet_app.TREND_CACHE.clear()
