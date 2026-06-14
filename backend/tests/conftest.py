"""
Shared pytest fixtures.

Database strategy (real Postgres — matches production; the models use
JSONB / INET / UUID columns that SQLite does not emulate faithfully):

* A dedicated ``*_test`` database is created once per session, derived from
  ``TEST_DATABASE_URL`` or, failing that, the app's ``DATABASE_URL`` with a
  ``_test`` suffix.
* The schema is built with ``Base.metadata.create_all`` once per session.
* Every test runs inside a transaction that is rolled back at teardown, so
  tests are isolated and fast and never leak rows into each other — even when
  the code under test calls ``db.commit()`` (we use SQLAlchemy 2.0's
  ``join_transaction_mode="create_savepoint"``).

The FastAPI app is imported lazily inside the ``client`` fixture rather than at
module top-level. Importing it instantiates ``StorageService`` (which reaches
out to S3/MinIO), so keeping it lazy lets pure ``unit`` tests run with no
external services.
"""

import os
from urllib.parse import urlsplit, urlunsplit

import psycopg2
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Import every model module so all tables are registered on Base.metadata
# before create_all runs, regardless of which subset of tests is collected.
import app.models.association  # noqa: F401,E402
import app.models.audit_event  # noqa: F401,E402
import app.models.letter_job  # noqa: F401,E402
import app.models.template  # noqa: F401,E402
import app.models.user  # noqa: F401,E402
from app.config import settings
from app.database import Base, get_db
from app.dependencies import get_current_user
from tests import factories


def _test_database_url() -> str:
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return explicit
    parts = urlsplit(settings.DATABASE_URL)
    dbname = parts.path.lstrip("/") or "postgres"
    return urlunsplit((parts.scheme, parts.netloc, f"/{dbname}_test", parts.query, parts.fragment))


def _ensure_database_exists(url: str) -> None:
    """CREATE DATABASE the test DB if it does not already exist."""
    parts = urlsplit(url)
    dbname = parts.path.lstrip("/")
    admin_url = urlunsplit((parts.scheme, parts.netloc, "/postgres", "", ""))
    conn = psycopg2.connect(admin_url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        conn.close()


@pytest.fixture(scope="session")
def engine():
    url = _test_database_url()
    _ensure_database_exists(url)
    eng = create_engine(url)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture
def db_session(engine) -> Session:
    """A session wrapped in a transaction that is rolled back after the test."""
    connection = engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(
        bind=connection,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def app_instance():
    """The FastAPI app, imported lazily so unit tests avoid StorageService init."""
    from app.main import app

    return app


@pytest.fixture
def client(app_instance, db_session):
    """TestClient whose routes use the rolled-back ``db_session``."""
    from fastapi.testclient import TestClient

    app_instance.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app_instance) as c:
            yield c
    finally:
        app_instance.dependency_overrides.pop(get_db, None)


@pytest.fixture
def as_user(app_instance, db_session, client):
    """
    Factory: create a user of the given role and authenticate the client as them
    by overriding ``get_current_user``. Returns the created User.

    Usage:
        admin = as_user(role=UserRole.admin)
    """

    def _make(**kwargs):
        user = factories.create_user(db_session, **kwargs)
        app_instance.dependency_overrides[get_current_user] = lambda: user
        return user

    yield _make
    app_instance.dependency_overrides.pop(get_current_user, None)
