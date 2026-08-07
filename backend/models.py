from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name       = Column(String, nullable=False)
    email      = Column(String, nullable=False, unique=True, index=True)
    password   = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    notes = relationship("Note", back_populates="owner", cascade="all, delete-orphan")


class Note(Base):
    __tablename__ = "notes"

    id         = Column(Integer, primary_key=True, autoincrement=True, index=True)
    title      = Column(String, nullable=False)
    content    = Column(Text, nullable=False)
    tag        = Column(String, nullable=True)
    severity   = Column(String, nullable=True)   # "P0", "P1", "P2", "P3", or None
    owner_id   = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="notes")
