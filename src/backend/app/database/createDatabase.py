from .base import Base
from .session import engine


def create_database():
    Base.metadata.create_all(engine)
