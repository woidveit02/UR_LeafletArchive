import json
import sys
from pathlib import Path

import pymupdf
import pytest

from backend.app import importer

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import scan_folder  # noqa: E402
import ngrams  # noqa: E402
import tiff_to_pdf  # noqa: E402
import learn_boundary_weights  # noqa: E402

PAGES = [  # (block type, text) per page: two leaflets, the second one stamped
    [("PageHeader", "AStA - AStA - AStA"), ("Text", "Aufruf zur Vollversammlung gegen das Hochschul-\ngesetz")],
    [("Text", "- 2 -"), ("Text", "Fortsetzung: Vollversammlung und Hochschulgesetz")],
    [("Picture", "Stempel eingegangen am 3. MAI 1972"), ("Text", "Der RCDS lädt ein zur Diskussion über Berufsverbote")],
]


@pytest.fixture
def folder(tmp_path, monkeypatch):
    """A scan folder with one volume, its OCR and its cuts, and the volumes.json that names it; tmp_path is also the repository."""
    monkeypatch.setattr(scan_folder, "ROOT", tmp_path)
    ocr = tmp_path / "Nr. 016 (1974)" / "0118_0016" / "0118_0016.json"
    ocr.parent.mkdir(parents=True)
    ocr.write_text(json.dumps({"children": [
        {"children": [{"block_type": t, "html": f"<p>{x}</p>"} for t, x in page]} for page in PAGES]}), encoding="utf-8")
    (ocr.parent.parent / "0118_0016.segments.json").write_text(json.dumps({"segments": [
        {"start_page": 1, "end_page": 2}, {"start_page": 3, "end_page": 3}]}), encoding="utf-8")
    entries = [{"vz": 15, "label": "Nr. 015 (1973)", "stem": None, "year": 1973},
               {"vz": 16, "label": "Nr. 016 (1974)", "stem": "0118_0016", "year": 1974}]
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "volumes.json").write_text(json.dumps(entries), encoding="utf-8")
    return tmp_path


# Tests if the scan folder comes from the argument, else from .env, and only volumes with OCR count.
def test_scan_dir_and_volumes(folder, tmp_path):
    (tmp_path / ".env").write_text("# Pfad\nLEAFLET_PDF_HOST_DIR=C:/daten\n", encoding="utf-8")
    assert scan_folder.scan_dir() == Path("C:/daten")
    assert scan_folder.scan_dir("anders") == Path("anders")
    assert [v["vz"] for v, _ in scan_folder.volumes(folder)] == [16]
    (tmp_path / ".env").unlink()
    with pytest.raises(SystemExit):
        scan_folder.scan_dir()


# Tests if a folder of TIFFs becomes one PDF with the settings of the import, and nothing is overwritten.
def test_tiff_to_pdf(tmp_path):
    assert (tiff_to_pdf.JPEG_QUALITY, tiff_to_pdf.DPI) == (importer.JPEG_QUALITY, importer.DPI)
    scans = tmp_path / "Nr. 016"
    scans.mkdir()
    for name, width in (("0002.tif", 80), ("0001.TIFF", 40), ("Thumbs.db", 0)):
        image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, 60), False).tobytes("png") if width else b""
        (scans / name).write_bytes(image)
    tiff_to_pdf.main([str(scans)])
    pdf = pymupdf.open(tmp_path / "Nr. 016.pdf")
    assert [round(page.rect.width * tiff_to_pdf.DPI / 72) for page in pdf] == [40, 80]
    pdf.close()
    with pytest.raises(SystemExit, match="gibt es schon"):
        tiff_to_pdf.main([str(scans)])
    with pytest.raises(SystemExit, match="keine TIFF"):
        tiff_to_pdf.main([str(tmp_path / "leer")])


# Tests if the weights are learned from the cuts: the stamp only on first pages, the page number only after them.
def test_learn_boundary_weights(folder):
    found = learn_boundary_weights.split_volumes(folder)
    assert [(label, starts) for label, _, starts in found] == [("Nr. 016 (1974)", {1, 3})]
    weights, prior = learn_boundary_weights.calibrate([(pages, starts) for _, pages, starts in found])
    assert weights["stamp"] > 0 > weights["pagenum"] and prior == 0
    assert set(weights) == set(learn_boundary_weights.boundaries.WEIGHTS)
    segments = folder / "Nr. 016 (1974)" / "0118_0016.segments.json"
    segments.write_text(json.dumps({"finished": False, "segments": [{"start_page": 1, "end_page": 3}]}), encoding="utf-8")
    assert learn_boundary_weights.split_volumes(folder) == []


# Tests if the n-gram tool reads the scan folder: years from volumes.json, hyphens joined, the text cached.
def test_ngrams(folder, monkeypatch, capsys):
    monkeypatch.setattr(ngrams, "YEARS", {})
    monkeypatch.setattr(ngrams, "OCR", {})
    args = ngrams.parse_args(["--ordner", str(folder), "size"])
    args.func(args)
    assert "1974         3        18  0118_0016" in capsys.readouterr().out
    assert (folder / ".ngrams" / "0118_0016.txt").is_file()
    args = ngrams.parse_args(["--ordner", str(folder), "kwic", "hochschulgesetz"])
    args.func(args)
    assert "[1974 0118_0016 S. 1]" in capsys.readouterr().out
    assert ngrams.hyphen_decision("Sprach", "und", None) == "ellipsis"
    assert ngrams.hyphen_decision("AStA", "Fraktion", None) == "hyphen"
    assert ngrams.collapse_runs(["lsd"] * 5 + ["aufruf"]) == ["lsd", "lsd", "aufruf"]
