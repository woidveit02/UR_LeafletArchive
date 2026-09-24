from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BACKEND_DIR / "leaflet_database.db"

engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}", echo=False)
Session = sessionmaker(bind=engine)
session = Session()
