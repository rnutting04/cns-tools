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

    class Config:
        env_file = ENV_FILE
        env_file_encoding = "utf-8"

settings = Settings()