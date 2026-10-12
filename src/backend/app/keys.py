"""API keys of the online services: from the .env, else saved from the page next to the scans (outside the repository)."""
import os
import re

from . import importer
from .database import fillDatabase

SERVICES = {  # name: (variable in the .env, where the key is created)
    "datalab": ("DATALAB_API_KEY", "auf datalab.to unter „API Keys“"),
    "openrouter": ("OPENROUTER_API_KEY", "auf openrouter.ai unter „Keys“")}


def path(service):
    return fillDatabase.PDF_DIR / f".{service}-key"


def get(service):
    """The .env wins over the key saved from the page."""
    key = os.getenv(SERVICES[service][0], "").strip()
    if key:
        return key
    try:
        return path(service).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def info(service):
    """What the page may show of the key: its source and last four characters."""
    key = get(service)
    return {"hint": key[-4:], "from_env": bool(os.getenv(SERVICES[service][0], "").strip())} if key else None


def save(service, key):
    key = key.strip()
    if len(key) < 10 or re.search(r"\s", key):
        raise ValueError(f"Das sieht nicht nach einem API-Key aus. Er steht {SERVICES[service][1]}.")
    target = path(service)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # only the app's user may read it
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(key)
    except OSError as error:
        raise ValueError(importer.storage_problem(error, target)) from error


def forget(service):
    path(service).unlink(missing_ok=True)
