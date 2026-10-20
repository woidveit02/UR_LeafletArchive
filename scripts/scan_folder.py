"""The scan folder (UR_LeafletArchive_data) and the volumes in it, for the scripts next to this file."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def scan_dir(path=None):
    """path, else LEAFLET_PDF_HOST_DIR from .env."""
    if path:
        return Path(path)
    env = ROOT / ".env"
    for line in env.read_text(encoding="utf-8").splitlines() if env.is_file() else []:
        key, _, value = line.partition("=")
        if key.strip() == "LEAFLET_PDF_HOST_DIR" and value.strip():
            return Path(value.strip().strip('"'))
    sys.exit("Der Scan-Ordner fehlt: mit --ordner angeben oder LEAFLET_PDF_HOST_DIR in .env eintragen.")


def volumes(folder):
    """[(entry of volumes.json, its OCR json)] of the volumes whose text recognition lies in the folder."""
    found = []
    for v in json.loads((ROOT / "data" / "volumes.json").read_text(encoding="utf-8")):
        ocr = Path(folder) / v["label"] / v["stem"] / f"{v['stem']}.json" if v.get("stem") else None
        if ocr and ocr.is_file():
            found.append((v, ocr))
    return found
