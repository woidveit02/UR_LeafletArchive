from .base import Base
from sqlalchemy import (Column, Integer, String, Float, Text, JSON, Boolean,
                        ForeignKey)


class Volume(Base):
    __tablename__ = "volumes"

    id = Column(Integer, primary_key=True)
    vz = Column(Integer, unique=True)
    stem = Column(String, unique=True, nullable=True)
    label = Column(String)
    year = Column(Integer)
    title = Column(String)
    group = Column(String)
    signature = Column(String)
    collection = Column(String, nullable=True)
    digitized = Column(Boolean, default=True)
    portal_url = Column(String, nullable=True)
    meta_model = Column(String, nullable=True)
    meta_created = Column(String, nullable=True)
    n_pages = Column(Integer, nullable=True)


class Page(Base):
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True)
    volume_id = Column(Integer, ForeignKey("volumes.id"))
    page_no = Column(Integer)
    text = Column(Text, default="")
    blocks = Column(JSON, default=list)
    leaflet_id = Column(Integer, ForeignKey("leaflets.id"), nullable=True)


class Leaflet(Base):
    __tablename__ = "leaflets"

    id = Column(Integer, primary_key=True)
    volume_id = Column(Integer, ForeignKey("volumes.id"))
    start_page = Column(Integer)
    end_page = Column(Integer)
    title = Column(String)
    title_type = Column(String)
    date_text = Column(String)
    date_iso = Column(String)
    date_type = Column(String)
    doc_type = Column(String)
    confidence = Column(Float)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True)
    name = Column(String)
    full_name = Column(String)
    type = Column(String)
    variants = Column(JSON)
    jahre = Column(JSON)
    vz = Column(JSON)
    gnd_id = Column(String)
    notes = Column(String)


class LeafletIssuer(Base):
    __tablename__ = "leaflet_issuers"

    id = Column(Integer, primary_key=True)
    leaflet_id = Column(Integer, ForeignKey("leaflets.id"))
    surface = Column(String)
    role = Column(String)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True)
