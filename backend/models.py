from sqlalchemy import Column, String, Boolean, Integer, DateTime
import uuid
from datetime import datetime
from sqlalchemy.orm import DeclarativeMeta, declarative_base

Base: DeclarativeMeta = declarative_base()

class UserTable(Base):
    __tablename__ = "user"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

class AuditoriumState(Base):
    __tablename__ = "auditorium_state"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    auditorium_number = Column(Integer, unique=True, index=True, nullable=False)
    is_network_on = Column(Boolean, default=True, nullable=False)
    unlock_time = Column(DateTime, nullable=True)
