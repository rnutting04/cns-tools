# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    SPACES_ENDPOINT: str
    SPACES_KEY: str
    SPACES_SECRET: str
    SPACES_BUCKET: str

    class Config:
        env_file = "../.env.local"
        env_file_encoding = "utf-8"

settings = Settings()