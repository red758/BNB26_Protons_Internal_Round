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
    DATABASE_URL: str = "postgresql://provledger:provledger@localhost:5432/provledger"

    # Security
    SECRET_KEY: str = "change-me-in-production"

    # CORS — stored as comma-separated string in env, parsed as list
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Embedding model backend: "resnet" | "clip" | "hash-only"
    EMBEDDING_MODEL: str = "resnet"

    # Gemini API Key for VLM predictions
    GEMINI_API_KEY: str = ""

    @property
    def database_url(self) -> str:
        return self.DATABASE_URL

    @property
    def secret_key(self) -> str:
        return self.SECRET_KEY

    @property
    def cors_origins(self) -> List[str]:
        return self.CORS_ORIGINS


settings = Settings()
