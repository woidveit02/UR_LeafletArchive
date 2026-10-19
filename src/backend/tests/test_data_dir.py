from backend.app.database.fillDatabase import VOLUMES, check_data_dir, load_json

STEMS = {v["label"]: load_json(v["metadata_file"])["source_pdf"].removesuffix(".pdf")
         for v in VOLUMES}
LABEL = VOLUMES[0]["label"]
STEM = STEMS[LABEL]


# Builds a data folder with all imported volumes; returns the first volume's folder.
def make_volume(root):
    for label, stem in STEMS.items():
        (root / label / stem).mkdir(parents=True)
        (root / label / f"{stem}.pdf").touch()
        (root / label / stem / f"{stem}.json").write_text("{}")
    return root / LABEL


# A correctly linked data folder produces no warnings.
def test_complete_data_dir(tmp_path):
    make_volume(tmp_path)
    assert check_data_dir(tmp_path) == []


# An empty folder is what Docker creates when the path in .env is wrong.
def test_empty_data_dir(tmp_path):
    assert "empty" in check_data_dir(tmp_path)[0]


# Linking the volume folder itself instead of its parent.
def test_path_one_level_too_deep(tmp_path):
    vol_dir = make_volume(tmp_path)
    assert "too deep" in check_data_dir(vol_dir)[0]


# Linking the parent of the data folder.
def test_path_one_level_too_high(tmp_path):
    make_volume(tmp_path / "UR_LeafletArchive_data")
    assert "too high" in check_data_dir(tmp_path)[0]


# A volume folder without its OCR file.
def test_missing_ocr(tmp_path):
    vol_dir = make_volume(tmp_path)
    (vol_dir / STEM / f"{STEM}.json").unlink()
    problems = check_data_dir(tmp_path)
    assert len(problems) == 1 and "json" in problems[0]


# Without a working data folder every page says so and where to find the reason; with one, nothing is shown.
def test_pages_name_a_broken_data_folder(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.app import app, templates
    client = TestClient(app)
    monkeypatch.setitem(templates.env.globals, "data_problems", ["empty"])
    assert "docker compose logs backend" in client.get("/gibt-es-nicht").text
    monkeypatch.setitem(templates.env.globals, "data_problems", [])
    assert "Datenordner" not in client.get("/gibt-es-nicht").text
