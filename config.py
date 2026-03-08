"""Application configuration loaded from environment variables / .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Auth
    quiz_password: str = "changeme"
    jwt_secret: str = "please-change-this-jwt-secret"
    jwt_expire_hours: int = 24

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/quiz.db"

    # Server
    port: int = 8000
    host: str = "0.0.0.0"

    # Frontend origin (for CORS in dev)
    frontend_origin: str = "http://localhost:5173"


settings = Settings()
