from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateColumn

from .base import Base
from .search import ensure_search_index
from .session import engine
from . import models  # noqa: F401  registers tables on Base.metadata


def add_missing_columns(engine):
    """ALTER TABLE for columns that the models have and an older database lacks.

    create_all only creates missing tables, so a column added to a model would
    otherwise break every query until the database is rebuilt. Only adds, never
    drops or changes anything.
    """
    present = inspect(engine)
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if not present.has_table(table.name):
                continue
            have = {c["name"] for c in present.get_columns(table.name)}
            for column in table.columns:
                if column.name not in have:
                    ddl = CreateColumn(column).compile(dialect=engine.dialect)
                    connection.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {ddl}"))


def create_database():
    Base.metadata.create_all(engine)
    add_missing_columns(engine)
    ensure_search_index(engine)
