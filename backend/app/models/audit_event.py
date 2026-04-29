# app/models/audit_event.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship

from app.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)
    
    # Who did it. Null = system event (migration, scheduled job, etc.)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # What happened. Dotted namespace: "user.created", "letter.generated", "auth.login"
    action = Column(String(64), nullable=False, index=True)
    
    # What it happened to. Type + ID. Null if not applicable.
    target_type = Column(String(32), nullable=True)
    target_id = Column(String(64), nullable=True)
    
    # Freeform structured details. Never put passwords or tokens here.
    event_metadata = Column(JSONB, nullable=False, default=dict)
    
    # Request context
    ip_address = Column(INET, nullable=True)
    user_agent = Column(String(512), nullable=True)
    
    actor = relationship("User")