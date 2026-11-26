# app/models/accounting_job.py
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.letter_job import JobStatus


class AccountingJob(Base):
    """A combined multi-association report (e.g. every association's balance
    sheet in one PDF) being run through an accounting tool in the background.

    ``results`` fills in one association at a time so the page can show
    progress; the uploaded PDF is deleted from storage once the run ends.
    """

    __tablename__ = "accounting_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tool = Column(String(30), nullable=False)  # fdic | revenue_threshold | receivables | cd_maturity
    filename = Column(String(255), nullable=False)
    input_path = Column(String(500), nullable=True)  # cleared once processed

    total_pages = Column(Integer, nullable=True)
    pages_done = Column(Integer, nullable=False, default=0)
    current_association = Column(String(255), nullable=True)
    # [{"association", "first_page", "last_page", "flagged", "result"}, ...]
    results = Column(JSON, nullable=False, default=list)
    error_detail = Column(String(500), nullable=True)

    # Reuses the jobstatus enum already in the DB (create_type=False).
    status = Column(
        SAEnum(JobStatus, name="jobstatus", create_type=False),
        nullable=False,
        default=JobStatus.pending,
    )

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    finished_at = Column(DateTime, nullable=True)

    creator = relationship("User")
