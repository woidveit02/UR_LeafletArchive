import sqlalchemy.orm as orm
from .session import engine


class Base(orm.DeclarativeBase):
    pass
