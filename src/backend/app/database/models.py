from .base import Base
from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship

# SQLAlchemy models for the application

# Model for a single leaflet:
class Leaflet(Base):
    __tablename__ = "leaflets"

    # Base Information
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    organisation = Column(String)
    date = Column(String)
    caption = Column(String)
    page_count = Column(Integer)
    buzzwords = Column(JSON)
    topics = Column(JSON)
    signatures = Column(JSON)  
    mentioned_names = Column(JSON)
    mentioned_locations = Column(JSON)
    referenced_leaflets = Column(JSON)
    


    


