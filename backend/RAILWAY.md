# Railway services

Railway's config files (`railway*.toml`, "Config as Code") are deprecated and
stop being read on **2026-12-01**. They're replaced by Infrastructure as Code:
`.railway/railway.ts` at the repo root, applied with `railway config plan` /
`railway config apply` (it is **not** applied on push). That file is the
source of truth; this page explains what each service is for.

Careful: anything missing from `.railway/railway.ts` (including Postgres,
Redis and the storage bucket) is **deleted** on apply. Always run
`railway config plan` first and stop if it shows anything "to destroy".

All backend services build from this repo with **Root Directory `/backend`**
and **Builder: Dockerfile** (`Dockerfile`), and share the same variables
(database, Redis, storage, secrets). The Dockerfile's default command starts
the API, so the workers and the scheduler **must** have their own start
command or they'll run the API instead of processing jobs.

| Service | Railway name | Start command (Settings → Deploy) | Replicas |
|---|---|---|---|
| API | imaginative-peace | `sh -c 'gunicorn app.main:app --bind 0.0.0.0:$PORT --workers 2 --worker-class uvicorn.workers.UvicornWorker --access-logfile - --error-logfile - --timeout 60'` | 1+ |
| Long-jobs worker (`default` queue: budgets, accounting runs) | incredible-compassion | `celery -A app.celery_app.celery_app worker -Q default --concurrency=4 --loglevel=info` | 1 |
| Light worker (`light` queue: letters, emails, nightly cleanup) | generous-curiosity | `celery -A app.celery_app.celery_app worker -Q light --concurrency=2 --loglevel=info` | 1 |
| Scheduler (Celery beat) | *new* | `celery -A app.celery_app.celery_app beat --loglevel=info --schedule /tmp/celerybeat-schedule` | **exactly 1** |
| Frontend | cns-tools | (Dockerfile default; Root Directory `/frontend`) | 1 |

API only:

- **Pre-deploy command:** `alembic upgrade head` (runs migrations on each deploy)
- **Healthcheck path:** `/health`, timeout 30 s

All backend services: **Restart policy** On Failure, max 10 retries.

## The scheduler

Celery beat only puts scheduled tasks (nightly cleanup, later reminder
emails) on the queue; the workers run them. Run **one** copy: two would queue
every task twice. It needs no domain and no volume, and uses almost no CPU or
memory. A healthy one logs `beat: Starting...`; the light worker logs a
`housekeeping: {...}` line after 3:15 AM Eastern each night.
