from .base import Base
from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship

# SQLAlchemy models for the application

# Model for a single room:
# A room can have multiple secondary IDs and names, which are stored as JSON arrays.
# Each room has one building.
class Room(Base):
    __tablename__ = "rooms"

    # Base Information
    id = Column(Integer, primary_key=True, index=True)
    secondary_ids = Column(JSON, default=list)
    names = Column(JSON, default=list)
    category = Column(String)
    comment = Column(String)

    # Location Information
    building_id = Column(Integer, ForeignKey("buildings.id"))
    building_rel = relationship("Building", back_populates="rooms")
    level = Column(Integer)
    longitude = Column(Float)
    latitude = Column(Float)

    # Seating Information
    seats_amount = Column(Integer)
    seats_arrangement = Column(String)

    # Equipment Information
    outlet_amount = Column(Integer)
    projector = Column(String)
    projector_resolution = Column(String)
    lighting = Column(String)

    # Pictures and Media
    foto1 = Column(String)
    foto2 = Column(String)
    foto1_info = Column(String)
    foto2_info = Column(String)
    pdf = Column(String)

# Model for a building:
# Each building belongs to one location and can have multiple rooms.
class Building(Base):
    __tablename__ = "buildings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)

    location_id = Column(Integer, ForeignKey("locations.id"))
    location_rel = relationship("Location", back_populates="buildings")
    
    rooms = relationship("Room", back_populates="building_rel")

# Model for a location:
# Each location can have multiple buildings.
class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)

    buildings = relationship("Building", back_populates="location_rel")

# Model for a user:
# Each user can belong to multiple groups.
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    email = Column(String, unique=True)
    password = Column(String)
    groups = Column(JSON, default=list)

# Model for an event:
# Events are only used for testing purposes and have no relation to rooms, buildings, or locations.
class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
