import json

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import topics
from backend.app.database import fillDatabase
from backend.app.database.base import Base
from backend.app.database.models import Leaflet, Topic, Volume


def unit(*rows):
    v = np.asarray(rows, dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


# Tests if a new leaflet takes the topic most of its nearest leaflets have, and is uncertain when they disagree.
def test_neighbour_topics(monkeypatch):
    monkeypatch.setattr(topics, "NEIGHBOURS", 2)
    known = unit([1, 0, 0], [0.95, 0.05, 0], [0, 1, 0], [0.05, 0.95, 0])
    near, between = topics.neighbour_topics(known, [3, 3, 7, 7], unit([1, 0.02, 0], [0.5, 0.5, 0]))
    assert near == (3, False) and between[1]


# Tests if the map point of a new leaflet is the mean of its nearest known leaflets.
def test_map_points(monkeypatch):
    monkeypatch.setattr(topics, "NEIGHBOURS", 2)
    known = unit([1, 0], [0.9, 0.1], [0, 1])
    assert topics.map_points(known, [(0, 0), (2, 2), (10, 10)], unit([1, 0.02])) == [(1.0, 1.0)]


# Tests if copies take the value of their main copy, and their own value wins.
def test_spread():
    main, copy, own = Leaflet(id=1), Leaflet(id=2, canonical_leaflet_id=1), Leaflet(id=3, canonical_leaflet_id=1)
    by_anchor = {("a", 1, 1): main, ("b", 2, 2): copy, ("b", 3, 3): own}
    assert topics.spread(by_anchor, {("a", 1, 1): 5, ("b", 3, 3): 6}) == {("a", 1, 1): 5, ("b", 2, 2): 5, ("b", 3, 3): 6}


@pytest.fixture
def topic_files(tmp_path, monkeypatch):
    """A database with two topics, their files in a temporary data folder and a candidate with three topics."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    volume = Volume(vz=1, stem="v", label="Nr. 001", year=1970)
    db.add(volume)
    db.flush()
    db.add_all([Leaflet(volume_id=volume.id, start_page=p, end_page=p) for p in range(1, 5)])
    db.commit()
    monkeypatch.setattr(fillDatabase, "session", db)
    monkeypatch.setattr(fillDatabase, "DATA_DIR", tmp_path)

    def rows(pairs):
        return [{"volume": "v", "start_page": p, "end_page": p, "topic": t, "uncertain": False} for p, t in pairs]

    def topic(i, title, source="llm_label"):
        return {"id": i, "title": title, "title_source": source, "llm_label": title, "words": []}

    (tmp_path / "topics.json").write_text(json.dumps({"run": "alt", "topics": [
        topic(0, "Wahlen von Hand", "manual"), topic(1, "Streik", "manual")], "leaflets": rows([(1, 0), (2, 0), (3, 1), (4, 1)])}))
    (tmp_path / "topic_map.json").write_text("[]")
    (tmp_path / "topics.kandidat.json").write_text(json.dumps({"run": "neu", "topics": [
        topic(0, "Hochschulwahlen"), topic(1, "Mensa"), topic(2, "Rest")], "leaflets": rows([(1, 0), (2, 0), (3, 1), (4, 2)])}))
    (tmp_path / "topic_map.kandidat.json").write_text(json.dumps([{"stem": "v", "start_page": 1, "end_page": 1, "x": 1.0, "y": 2.0}]))
    fillDatabase.fill_topics()
    return tmp_path, db


# Tests if the fields keep the model's titles, each new topic names the old one most of its leaflets come from,
# old topics that came apart are listed (topic 1 split into 1 and 2), and the list of a candidate topic has its leaflets.
def test_review(topic_files):
    rows = {t["id"]: t for t in topics.review()["topics"]}
    assert {i: r["title"] for i, r in rows.items()} == {0: "Hochschulwahlen", 1: "Mensa", 2: "Rest"}
    assert (rows[1]["old"], rows[1]["stay"], rows[1]["old_count"]) == ("Streik", 1, 2)
    assert [d["title"] for d in topics.review()["split"]] == ["Streik"]
    topic, found = topics.candidate_leaflets(0)
    assert topic["title"] == "Hochschulwahlen" and [lf.start_page for lf in found] == [1, 2]


# Tests if taking a candidate over replaces the topics, keeps a backup, drops the old topics and marks edited titles.
def test_accept(topic_files):
    tmp_path, db = topic_files
    topics.accept({0: "Wahlen von Hand", 1: "Mensa", 2: "Rest"})
    doc = json.loads((tmp_path / "topics.json").read_text())
    assert [(t["title"], t["title_source"]) for t in doc["topics"]] == [
        ("Wahlen von Hand", "manual"), ("Mensa", "llm_label"), ("Rest", "llm_label")]
    assert len(list(tmp_path.glob("topics.bis-*.json"))) == 1 and topics.load(topics.CANDIDATE) is None
    assert sorted(t.id for t in db.query(Topic)) == [0, 1, 2]
    assert db.query(Leaflet).filter_by(start_page=4).one().topic_id == 2
    assert db.query(Leaflet).filter_by(start_page=1).one().x == 1.0


# Tests if renaming changes the file and the database, and rejects an empty title.
def test_rename(topic_files):
    tmp_path, db = topic_files
    topics.rename(1, "  Streik  gegen das Hochschulgesetz ")
    assert json.loads((tmp_path / "topics.json").read_text())["topics"][1]["title"] == "Streik gegen das Hochschulgesetz"
    assert db.get(Topic, 1).title == "Streik gegen das Hochschulgesetz"
    with pytest.raises(ValueError):
        topics.rename(1, " ")


# Tests if a title model gone from OpenRouter is replaced by the strongest affordable one, not the strongest of all.
def test_label_model_choice(monkeypatch):
    costs = {"strong/expensive": 0.7, "good/cheap": 0.05, "weak/cheapest": 0.01}  # strongest first, as OpenRouter ranks
    monkeypatch.setattr(topics, "label_costs", lambda n: costs)
    monkeypatch.setattr(topics, "label_model_used", lambda: "good/cheap")
    assert topics.label_model_choice(40) == ("good/cheap", False)
    monkeypatch.setattr(topics, "label_model_used", lambda: "gone/model")
    assert topics.label_model_choice(40) == ("good/cheap", True)
    costs.pop("good/cheap")
    assert topics.label_model_choice(40) == ("weak/cheapest", True)


# Tests if the topic rows keep single years for a short span and use five-year spans for the whole collection.
def test_topic_year_buckets():
    from backend.app import app as leaflet_app
    few = {str(y): 100 for y in range(1968, 1974)}
    assert leaflet_app.topic_year_buckets(few) == {y: y for y in few}
    all_years = {str(y): 100 for y in range(1967, 2025)}
    spans = leaflet_app.topic_year_buckets(all_years)
    assert spans["1967"] == "1965–69" and spans["1999"] == "1995–99" and spans["2024"] == "2020–24"
    assert len(set(spans.values())) <= 12
