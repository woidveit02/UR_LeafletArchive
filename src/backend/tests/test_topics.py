import json
from pathlib import Path

from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

import backend.app.app as leaflet_app
from backend.app.database import fillDatabase
from backend.app.database.base import Base
from backend.app.database.models import Leaflet, Topic, Volume


def test_fill_topics_imports_labels_and_uncertain_assignments(
        tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine)()
    monkeypatch.setattr(fillDatabase, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fillDatabase, "session", test_session)

    volume = Volume(stem="0118_0001")
    test_session.add(volume)
    test_session.flush()
    uncertain_leaflet = Leaflet(
        volume_id=volume.id, start_page=1, end_page=2)
    unassigned_leaflet = Leaflet(
        volume_id=volume.id, start_page=3, end_page=3)
    test_session.add_all([uncertain_leaflet, unassigned_leaflet])
    test_session.commit()

    (tmp_path / "topics.json").write_text(json.dumps({
        "topics": [{
            "id": 7, "title": "Streiks und Proteste",
            "title_source": "manual", "words": ["streik", "protest"],
        }],
        "leaflets": [
            {
                "volume": "0118_0001", "start_page": 1, "end_page": 2,
                "topic": 7, "uncertain": True,
            },
            {
                "volume": "0118_0001", "start_page": 3, "end_page": 3,
                "topic": None, "uncertain": False,
            },
        ],
    }), encoding="utf-8")

    fillDatabase.fill_topics()

    imported_topic = test_session.get(Topic, 7)
    assert imported_topic.title == "Streiks und Proteste"
    assert imported_topic.source == "manual"
    assert imported_topic.words == ["streik", "protest"]
    assert test_session.get(Leaflet, uncertain_leaflet.id).topic_id == 7
    imported_uncertain = test_session.get(Leaflet, uncertain_leaflet.id)
    assert imported_uncertain.topic_uncertain is True
    assert test_session.get(Leaflet, unassigned_leaflet.id).topic_id is None
    imported_unassigned = test_session.get(Leaflet, unassigned_leaflet.id)
    assert imported_unassigned.topic_uncertain is False

    fillDatabase.fill_topics()
    assert test_session.query(Topic).count() == 1
    test_session.close()
    engine.dispose()


def test_fill_topics_does_nothing_when_file_is_missing(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine)()
    monkeypatch.setattr(fillDatabase, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fillDatabase, "session", test_session)

    fillDatabase.fill_topics()

    assert test_session.query(Topic).count() == 0
    test_session.close()
    engine.dispose()


def test_topic_pages_filter_and_page_through_topic_selection(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine)()
    monkeypatch.setattr(leaflet_app, "session", test_session)
    # outside Docker the templates are not mounted into the app folder
    frontend_templates = (
        Path(__file__).resolve().parents[2] / "frontend" / "templates")
    if frontend_templates.is_dir():
        monkeypatch.setattr(
            leaflet_app, "templates",
            Jinja2Templates(directory=frontend_templates))

    topic = Topic(id=0, title="Streiks und Proteste " + "an der Universität " * 5,
                  source="llm_label", words=["streik", "protest"])
    other_topic = Topic(id=1, title="Studium", source="auto_label",
                        words=["studium"])
    volume = Volume(vz=1, stem="sample", label="Band 1", year=1967)
    test_session.add_all([topic, other_topic, volume])
    test_session.flush()
    first = Leaflet(volume_id=volume.id, start_page=1, end_page=1,
                    title="Erstes Blatt", date_iso="", topic_id=0,
                    topic_uncertain=True)
    second = Leaflet(volume_id=volume.id, start_page=2, end_page=2,
                     title="Zweites Blatt", date_iso="1968-01-01", topic_id=0)
    unrelated = Leaflet(volume_id=volume.id, start_page=3, end_page=3,
                        title="Anderes Thema", date_iso="1968-01-01",
                        topic_id=1)
    test_session.add_all([first, second, unrelated])
    test_session.commit()

    def request(path, query_string=b""):
        return Request({
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query_string,
            "headers": [],
            "server": ("test", 80),
            "client": ("test", 1),
            "root_path": "",
            "app": leaflet_app.app,
            "router": leaflet_app.app.router,
        })

    topics_response = leaflet_app.topic_list(request("/themen"))
    topics_html = topics_response.body.decode()
    assert "Streiks und Proteste" in topics_html
    assert "Schlüsselwörter:" in topics_html and "streik, protest" in topics_html
    assert 'href="/leaflets?thema=0&amp;jahr=1967"' in topics_html
    assert 'href="/leaflets?thema=0&amp;jahr=1968"' in topics_html
    assert "1967: 1 Flugblatt" in topics_html

    query = b"thema=0&jahr=1967"
    year_response = leaflet_app.leaflet_list(
        request("/leaflets", query), ansicht="liste")
    year_html = year_response.body.decode()
    assert "Erstes Blatt" in year_html
    assert "Zweites Blatt" not in year_html

    query = b"thema=0"
    list_response = leaflet_app.leaflet_list(
        request("/leaflets", query), ansicht="liste")
    list_html = list_response.body.decode()
    assert "Erstes Blatt" in list_html
    assert "Zweites Blatt" in list_html
    assert "Anderes Thema" not in list_html
    assert "…" in list_html  # long title is shortened in the filter

    detail_response = leaflet_app.leaflet_detail(
        request(f"/leaflets/{first.id}", query), first.id)
    detail_html = detail_response.body.decode()
    assert "(unsicher)" in detail_html
    assert "Titel von einem Sprachmodell erzeugt" in detail_html
    assert f'href="/leaflets/{second.id}?thema=0"' in detail_html

    test_session.close()
    engine.dispose()
