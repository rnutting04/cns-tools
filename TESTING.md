# Testing

This repo has automated tests for both the FastAPI backend and the React
frontend, plus local pre-commit hooks and CI gates.

## Backend (pytest)

The backend tests use a **real Postgres** database (the models rely on
JSONB / INET / UUID columns), and mock S3/MinIO where storage is touched.

```bash
# 1. Start the local services (Postgres + MinIO)
make dev            # or: docker compose up -d postgres minio

# 2. Install runtime + dev/test dependencies
cd backend
venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# 3. Run the suite
venv/bin/python -m pytest                 # everything
venv/bin/python -m pytest -m unit         # fast, no DB/network
venv/bin/python -m pytest -m integration  # API routes against the test DB
venv/bin/python -m pytest --cov=app       # with coverage
```

How it works:

- A dedicated `cs_tool_hub_test` database is created automatically on first run
  (derived from `DATABASE_URL`, or set `TEST_DATABASE_URL` to override).
- Each test runs inside a transaction that is **rolled back** at teardown, so
  tests are isolated and never leak rows — even when the code under test calls
  `db.commit()`.
- Routes are exercised via FastAPI's `TestClient` with the `get_db` and
  `get_current_user` dependencies overridden (see `backend/tests/conftest.py`).
  `backend/tests/factories.py` builds `User` / `Association` / `Template` rows.

Layout: `backend/tests/unit/` (pure logic — auth, field enrichment, renderers,
config) and `backend/tests/integration/` (auth, users, associations, letter
generation, audit routes).

## Frontend (Vitest + React Testing Library)

```bash
cd frontend
npm install
npm test              # run once
npm run test:watch    # watch mode
npm run test:coverage # with coverage
npm run typecheck     # tsc -b (no emit)
```

Tests cover the token utilities, `AuthContext`, `ProtectedRoute`, `useApi`,
the password-change form, and the proxy-vote editor. The axios client is mocked
per-test with `vi.mock`.

## Pre-commit hooks

A single pre-commit framework drives both languages (backend and frontend share
one git repo). Hooks run on **staged files only**, so legacy code is cleaned up
incrementally as it is edited.

```bash
pip install -r backend/requirements-dev.txt   # provides `pre-commit`
pre-commit install                            # from the repo root
pre-commit run --all-files                     # optional: run against everything
```

- Backend: `ruff` lint (`--fix`) + `ruff format` on staged `backend/**.py`.
- Frontend: `eslint --fix` on staged `frontend/src/**.{ts,tsx}`.

## CI

`.github/workflows/ci.yml` runs on push to `main`/`dev` and on every PR:

- **frontend** — build, `typecheck`, and `test:coverage`.
- **backend** — Alembic migrations, ruff lint of the test suite, and `pytest`
  with coverage, against service Postgres + MinIO.

> Repo-wide `eslint` and `ruff` gates are not yet enforced in CI because the
> existing application code has pre-existing violations. The pre-commit hooks
> bring those files up to standard as they are touched; once the backlog is
> cleared, enable the commented `npm run lint` step and broaden `ruff check`.
