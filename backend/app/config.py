"""
Pydantic-based settings loaded from environment variables / .env file.
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql://provledger:provledger@localhost:5432/provledger"

    # Security
    secret_key: str = "change-me-in-production"

    # CORS — stored as comma-separated string in env, parsed as list
    cors_origins: List[str] = ["http://localhost:3000"]

    # Embedding model backend: "resnet" | "clip" | "hash-only"
    embedding_model: str = "resnet"


settings = Settings()
