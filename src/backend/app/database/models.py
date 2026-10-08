from .base import Base
from sqlalchemy import (Column, Integer, String, Float, Text, JSON, Boolean,
                        ForeignKey)


RELEASED = "freigegeben"
DRAFT = "entwurf"  # an imported volume, hidden everywhere until it is released


class Volume(Base):
    __tablename__ = "volumes"

    id = Column(Integer, primary_key=True)
    status = Column(String, nullable=False, default=RELEASED, server_default=RELEASED)
    vz = Column(Integer, unique=True)
    stem = Column(String, unique=True, nullable=True)
    label = Column(String)
    year = Column(Integer)
    title = Column(String)
    group = Column(String)
    signature = Column(String)
    digitized = Column(Boolean, default=True)
    portal_url = Column(String, nullable=True)
    meta_model = Column(String, nullable=True)
    meta_created = Column(String, nullable=True)
    n_pages = Column(Integer, nullable=True)

    @property
    def name(self):
        """"Nr. 007, Flugblätter 1972. RCDS": the number tells apart units with the same title."""
        return f"Nr. {self.vz:03d}, {self.title}"


class Page(Base):
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True)
    volume_id = Column(Integer, ForeignKey("volumes.id"))
    page_no = Column(Integer)
    text = Column(Text, default="")
    blocks = Column(JSON, default=list)
    leaflet_id = Column(Integer, ForeignKey("leaflets.id"), nullable=True, index=True)


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    source = Column(String, nullable=False)
    words = Column(JSON, nullable=False)


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
    series = Column(String)
    issue = Column(String)
    received_date = Column(String)  # archive stamp
    received_uncertain = Column(Boolean)
    doc_type = Column(String)
    confidence = Column(Float)
    # evidence: OCR block ids (e.g. ["5-1"]) and the quoted text
    title_blocks = Column(JSON)
    date_blocks = Column(JSON)
    received_blocks = Column(JSON)
    title_quote = Column(String)
    date_quote = Column(String)
    received_quote = Column(String)
    series_blocks = Column(JSON)  # only from manual corrections
    series_quote = Column(String)
    # copies of the same leaflet share a group: find_copies.py proposes, copy_decisions.jsonl decides
    copy_group = Column(Integer)
    canonical_leaflet_id = Column(Integer, ForeignKey("leaflets.id"))  # main copy of the group
    copies_checked = Column(Boolean, default=False, server_default="0", nullable=False)
    copy_candidate_of = Column(Integer)  # copy_group of a checked group that new automatic hit may join
    corrected = Column(JSON, default=list)  # field names corrected by hand
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)
    topic_uncertain = Column(Boolean, default=False, server_default="0",
                             nullable=False)
    # fixed 2D layout from the embeddings (topic_map.py), for the point-cloud overlay
    x = Column(Float, nullable=True)
    y = Column(Float, nullable=True)

    @property
    def series_label(self):
        if not self.series:
            return ""
        return f"{self.series}, {self.issue}" if self.issue else self.series

    @property
    def display_title(self):
        return self.title or self.series_label


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
    leaflet_id = Column(Integer, ForeignKey("leaflets.id"), index=True)
    surface = Column(String)
    role = Column(String)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    blocks = Column(JSON)
    quote = Column(String)
    function = Column(String)
    marker = Column(String)  # e.g. "V.i.S.d.P.", "gez."
    other_institution = Column(String)  # e.g. "asta" for the AStA Würzburg
