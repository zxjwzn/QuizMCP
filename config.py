"""应用配置，从环境变量 / .env 文件加载。"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 认证配置
    quiz_password: str = "changeme"
    jwt_secret: str = "please-change-this-jwt-secret"
    jwt_expire_hours: int = 24

    # 数据库配置
    database_url: str = "sqlite+aiosqlite:///./data/quiz.db"

    # 服务器配置
    port: int = 8000
    host: str = "0.0.0.0"

    # 前端来源（用于开发环境中的 CORS）
    frontend_origin: str = "http://localhost:5173"


settings = Settings()
