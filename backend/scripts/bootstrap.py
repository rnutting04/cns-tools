# backend/scripts/bootstrap.py
"""
Prod bootstrap: creates the initial super_admin if the users table is empty.

Idempotent — safe to re-run. If any users already exist, this does nothing.

Required env vars:
  BOOTSTRAP_ADMIN_EMAIL
  BOOTSTRAP_ADMIN_PASSWORD
  BOOTSTRAP_ADMIN_FNAME (optional, default "System")
  BOOTSTRAP_ADMIN_LNAME (optional, default "Admin")

Run once on first deploy:
  docker compose -f docker-compose.prod.yml run --rm backend python -m scripts.bootstrap
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from app.database import SessionLocal
from app.models.user import User, UserRole


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def bootstrap():
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL")
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")
    fname = os.environ.get("BOOTSTRAP_ADMIN_FNAME", "System")
    lname = os.environ.get("BOOTSTRAP_ADMIN_LNAME", "Admin")

    if not email or not password:
        print("ERROR: BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD must be set.")
        sys.exit(1)

    if len(password) < 12:
        print("ERROR: BOOTSTRAP_ADMIN_PASSWORD must be at least 12 characters.")
        sys.exit(1)

    db = SessionLocal()
    try:
        # Idempotency guard: only run if no users exist yet.
        user_count = db.query(User).count()
        if user_count > 0:
            print(f"Users already exist ({user_count}). Bootstrap skipped.")
            return

        admin = User(
            fname=fname,
            lname=lname,
            email=email,
            title="System Administrator",
            role=UserRole.super_admin,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"Created initial super_admin: {email}")
        print("IMPORTANT: Change this password immediately after first login.")
    finally:
        db.close()


if __name__ == "__main__":
    bootstrap()