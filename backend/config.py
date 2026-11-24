"""
Application configuration for the Nebula simulation platform.
Loads settings using Pydantic Settings with support for environment overrides.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Metadata
    APP_NAME: str = "Nebula Simulation Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Server Configuration
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = DATA_DIR / "nebula.db"

    # CORS Settings (Allow local frontend access)
    CORS_ORIGINS: list[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Global settings instance
settings = Settings()

# Ensure the data directory exists
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)