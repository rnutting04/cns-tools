# C&S Tool Hub

A full-stack web app for managing **letter generation** (proxy votes, shareholder
communications), **user/association management**, and **audit logging**. The backend is
FastAPI + PostgreSQL with background letter rendering on Celery; the frontend is React +
MUI. Generated DOCX files are stored in an S3-compatible object store (MinIO locally).

This README covers getting a **local development** environment running. For testing
details see [TESTING.md](TESTING.md), and for architecture/conventions see
[CLAUDE.md](CLAUDE.md).

## Tech stack

- **Backend:** FastAPI, SQLAlchemy + Alembic, PostgreSQL 15
- **Background jobs:** Celery, Redis (broker + result backend)
- **Storage:** MinIO (S3-compatible) for generated DOCX files
- **Frontend:** React 19, TypeScript, MUI, Vite 8
- **Infra (local):** Docker Compose — Postgres, pgAdmin, MinIO, Redis

## Prerequisites

- **Docker** + **Docker Compose**
- **Python 3.12**
- **Node.js 20+** and npm
- **make**

## Quick start

From a fresh clone:

```bash
# 1. Copy the three environment files (defaults work out of the box for local dev)
cp .env.example .env                     # docker-compose credentials
cp backend/.env.example backend/.env     # backend (FastAPI + Celery) config
cp frontend/.env.example frontend/.env   # frontend (Vite) config

# 2. Backend: create a virtualenv and install dependencies
cd backend
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cd ..

# 3. Frontend: install dependencies
cd frontend
npm install
cd ..

# 4. Install pre-commit hooks (runs ruff + eslint on staged files automatically)
pre-commit install

# 5. Start Docker services (Postgres, MinIO, Redis, pgAdmin) and the API
make dev                # runs `docker compose up -d` then uvicorn on :8000

# 6. In a second shell — run migrations and seed initial data
make migrate            # alembic upgrade head
make seed               # creates the initial super_admin + sample data

# 7. In a second/third shell — start the Celery worker (background letter rendering)
make worker

# 8. In another shell — start the frontend dev server
cd frontend && npm run dev
```

Once running:

- Frontend → http://localhost:5173
- API docs (Swagger) → http://localhost:8000/docs

> **Note:** `make dev` runs uvicorn in the foreground, so steps 5–7 each need their own
> terminal. Stop the Docker services with `make stop` when you're done.

## Services & ports

| Service        | URL / Port                   | Default credentials                        | Purpose                          |
| -------------- | ---------------------------- | ------------------------------------------ | -------------------------------- |
| Backend API    | http://localhost:8000        | —                                          | FastAPI app (`/docs` for Swagger) |
| Frontend       | http://localhost:5173        | —                                          | Vite dev server                  |
| PostgreSQL     | localhost:5432               | `cs_user` / `localpassword`                | Application database             |
| pgAdmin        | http://localhost:5050        | `admin@admin.com` / `admin`                | DB admin UI                      |
| MinIO API      | http://localhost:9000        | `local_access_key` / `local_secret_key`    | S3-compatible object storage     |
| MinIO Console  | http://localhost:9001        | `local_access_key` / `local_secret_key`    | MinIO web console                |
| Redis          | localhost:6379               | —                                          | Celery broker + result backend   |

The DOCX storage bucket (`cs-tool-hub`) is created automatically on first use by the
storage layer ([backend/app/services/storage.py](backend/app/services/storage.py)).

## Environment variables

The project uses **three** `.env` files, each read by a different process. Every one has a
committed `.example` template with working local defaults.

| File             | Read by                | Key variables                                                                 |
| ---------------- | ---------------------- | ----------------------------------------------------------------------------- |
| `.env`           | Docker Compose         | `POSTGRES_*`, `PGADMIN_*`, `MINIO_ROOT_*`                                      |
| `backend/.env`   | FastAPI + Celery       | `DATABASE_URL`, `SECRET_KEY`, `SPACES_ENDPOINT`, `SPACES_KEY`, `SPACES_SECRET`, `SPACES_BUCKET` |
| `frontend/.env`  | Vite                   | `VITE_API_URL` (defaults to `http://localhost:8000`)                          |

The `SPACES_*` variables point the backend at MinIO locally: `SPACES_ENDPOINT` is the MinIO
API URL, and `SPACES_KEY`/`SPACES_SECRET` match the `MINIO_ROOT_*` credentials in the root
`.env`. In production these map to a real S3-compatible service (e.g. DigitalOcean Spaces).

## Common commands

Most workflows are wrapped by the root [makefile](makefile):

```bash
make dev            # docker compose up -d + uvicorn --reload on :8000
make worker         # start the Celery letter-generation worker
make migrate        # alembic upgrade head
make seed           # seed the database with initial data
make stop           # stop docker containers
make logs           # tail docker logs
make ps             # show container status
make test           # run backend + frontend test suites
make test-backend   # pytest only (needs docker services up)
make test-frontend  # vitest only
```

Running tools directly:

```bash
# Backend (from backend/)
venv/bin/python -m uvicorn app.main:app --reload --port 8000
venv/bin/alembic upgrade head
venv/bin/alembic revision --autogenerate -m "describe change"
ruff check . && ruff format --check .

# Frontend (from frontend/)
npm run dev          # Vite dev server
npm run build        # production build (tsc -b + vite build)
npm run typecheck    # tsc -b, no emit
npm run lint         # ESLint
```

## Testing

See [TESTING.md](TESTING.md) for full details. In short:

```bash
make test            # backend (pytest) + frontend (vitest)
make test-backend    # pytest — requires docker services running (make dev)
make test-frontend   # vitest
```

Backend integration tests run against a real PostgreSQL test database (created
automatically), so Docker services must be up first.

## Pre-commit hooks

Hooks run `ruff` (Python) and `eslint` (TypeScript) on staged files. Install once:

```bash
pip install -r backend/requirements-dev.txt   # provides pre-commit
pre-commit install                            # from the repo root
```

## Project structure

```
backend/app/
  main.py          — FastAPI app, CORS, router registration
  celery_app.py    — Celery app for background letter generation
  config/          — Pydantic settings + letter YAML configs
  models/          — SQLAlchemy ORM (User, Association, Template, AuditEvent, LetterJob…)
  routers/         — auth, user, association, templates, managers, audit
  schemas/         — Pydantic request/response models
  services/        — audit, renderers (DOCX), storage (MinIO/S3), letters/ (Celery tasks)
  utils/           — auth (JWT + bcrypt), field enrichment

frontend/src/
  App.tsx          — Root: theme provider + AuthProvider
  api/client.ts    — Axios instance (baseURL from VITE_API_URL)
  context/         — AuthContext, LetterJobsContext
  hooks/           — useApi (JWT injection, 401 handling), usePolling
  pages/           — One file per route
  types/index.ts   — Shared TypeScript interfaces
```

## Troubleshooting

- **Celery worker errors on WSL/macOS** — if the prefork pool misbehaves, run the worker
  with a solo pool: `cd backend && venv/bin/celery -A app.celery_app.celery_app worker --pool=solo`.
- **Migrations or tests fail to connect** — make sure the Docker services are up
  (`make dev` or `docker compose up -d`) before running `make migrate` / `make test-backend`.
- **Frontend can't reach the API** — confirm `VITE_API_URL` in `frontend/.env` matches the
  backend address (`http://localhost:8000`) and that the API is running.
