# app/config/environment.py
from enum import Enum

from app.config.settings import settings


class Environment(str, Enum):
    """The deployment environment, parsed from settings.ENVIRONMENT.

    Only PRODUCTION delivers email to real recipients; every other environment
    (including any unrecognised value) redirects mail to LOCAL_EMAIL_TO. That
    means a missing or misspelled ENVIRONMENT fails safe — it never emails real
    users by accident.
    """

    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"

    @classmethod
    def current(cls) -> "Environment":
        value = (settings.ENVIRONMENT or "").strip().lower()
        try:
            return cls(value)
        except ValueError:
            # Unknown value: fail safe to a non-production environment so we
            # never deliver real mail from a misconfigured deployment.
            return cls.LOCAL

    @property
    def is_local(self) -> bool:
        return self is Environment.LOCAL

    @property
    def is_staging(self) -> bool:
        return self is Environment.STAGING

    @property
    def is_production(self) -> bool:
        return self is Environment.PRODUCTION

    @property
    def redirects_email(self) -> bool:
        """True for any non-production environment (local, staging, unknown)."""
        return self is not Environment.PRODUCTION
