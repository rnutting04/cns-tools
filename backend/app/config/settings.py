# app/config.py
from pathlib import Path

from pydantic_settings import BaseSettings

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    SPACES_ENDPOINT: str
    SPACES_KEY: str
    SPACES_SECRET: str
    SPACES_BUCKET: str
    ANTHROPIC_API_KEY: str

    FRONTEND_URL: str = "http://localhost:5173"

    AUDIT_RETENTION_DAYS: int = 365

    # Celery / Redis. Defaults target a host-run worker against the
    # docker-compose Redis. In containers, override with redis://redis:6379/0.
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    # When True, tasks run inline in the calling process (used by the test suite).
    CELERY_TASK_ALWAYS_EAGER: bool = False

    class Config:
        env_file = ENV_FILE
        env_file_encoding = "utf-8"


settings = Settings()
