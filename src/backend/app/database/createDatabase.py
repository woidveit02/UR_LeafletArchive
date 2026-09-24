from .base import Base
from .session import engine
from . import models  # noqa: F401  registers tables on Base.metadata


def create_database():
    Base.metadata.create_all(engine)
