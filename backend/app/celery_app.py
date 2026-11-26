# app/celery_app.py
"""
Celery application for background letter generation.

This module deliberately imports only ``settings`` — never the FastAPI app —
so the worker process starts without pulling in HTTP routing. Tasks live in
``app.services.letters.tasks`` and are registered via ``conf.imports``.

Run the worker with:

    celery -A app.celery_app.celery_app worker --loglevel=info --concurrency=2

and the scheduler (exactly one, or scheduled tasks run once per copy):

    celery -A app.celery_app.celery_app beat --loglevel=info
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "cns_tools",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    # Serialization — JSON only, no pickle.
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Reliability: re-deliver if a worker dies mid-task (tasks are idempotent).
    task_acks_late=True,
    # Reject (re-queue) the message if the worker process is lost so stuck-pending
    # jobs don't require a cleanup service. Requires task_acks_late=True to work.
    task_reject_on_worker_lost=True,
    # Fair dispatch for long-running render tasks instead of greedy prefetch.
    worker_prefetch_multiplier=1,
    # Guard against runaway renders.
    task_time_limit=120,
    task_soft_time_limit=90,
    # Keep the result backend from growing unbounded.
    result_expires=3600,
    # Eager mode for tests: run tasks inline and surface their exceptions.
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=True,
    # Where to find @celery_app.task definitions.
    imports=(
        "app.services.letters.tasks",
        "app.services.budget.tasks",
        "app.services.email.tasks",
        "app.services.financials.tasks",
        "app.services.maintenance.tasks",
    ),
    # Queue routing: quick tasks go to the light worker, heavy tasks to default.
    task_default_queue="default",
    task_routes={
        "app.services.letters.tasks.*": {"queue": "light"},
        "app.services.email.tasks.*": {"queue": "light"},
        "app.services.maintenance.tasks.*": {"queue": "light"},
    },
    # Scheduled tasks. Celery beat (one process, see RAILWAY.md and
    # `make beat`) only enqueues them; the workers run them. Crontab times are
    # Eastern, where the associations are.
    timezone="America/New_York",
    beat_schedule={
        "purge-old-data": {
            "task": "app.services.maintenance.tasks.purge_old_data",
            "schedule": crontab(hour=3, minute=15),
        },
    },
)
