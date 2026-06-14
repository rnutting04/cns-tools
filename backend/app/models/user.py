# app/models/user.py
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    admin = "admin"
    manager = "manager"
    employee = "employee"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fname = Column(String(50), nullable=False)
    lname = Column(String(50), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.manager)
    password_hash = Column(String(255), nullable=False)
    password_change_required = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    associations = relationship("UserAssociation", back_populates="user")
