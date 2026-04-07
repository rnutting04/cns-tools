# app/models/letter_job.py
import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class JobStatus(str, enum.Enum):
    pending = "pending"
    complete = "complete"
    failed = "failed"


class LetterJob(Base):
    __tablename__ = "letter_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=False)
    association_id = Column(UUID(as_uuid=True), ForeignKey("associations.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    field_values = Column(JSON, nullable=False, default=dict)
    output_path = Column(String(500), nullable=True)
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.pending)
    created_at = Column(DateTime, default=datetime.utcnow)

    template = relationship("Template", back_populates="letter_jobs")
    association = relationship("Association")
    creator = relationship("User")
