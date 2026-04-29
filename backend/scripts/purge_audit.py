#!/usr/bin/env python3
"""
Purge audit events older than AUDIT_RETENTION_DAYS (default 365).

Run manually or from a cron job / docker-compose scheduled service:

  docker compose exec backend python scripts/purge_audit.py

  # Override retention period for a one-off run:
  AUDIT_RETENTION_DAYS=90 python scripts/purge_audit.py
"""
import sys
from pathlib import Path

# Allow running from repo root or from the backend directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.settings import settings
from app.database import SessionLocal
from app.services.audit_retention import purge_old_events


def main() -> None:
    days = settings.AUDIT_RETENTION_DAYS
    db = SessionLocal()
    try:
        deleted = purge_old_events(db, days)
        print(f"Purged {deleted} audit event(s) older than {days} days.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
