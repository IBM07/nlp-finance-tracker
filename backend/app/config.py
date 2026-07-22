# ==========================================
# config.py — Application Configuration
# ==========================================
# Single source of truth for all environment variables.
# Uses pydantic-settings to validate and type-check on startup.
# If a required variable is missing, the app will refuse to start
# with a clear error message — no silent failures.
# ==========================================

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    All environment variables are declared here.
    pydantic-settings reads them from the .env file (or real env).
    """

    # --- Groq LLM ---
    groq_api_key: str

    # --- Deepgram STT (voice input for the chat assistant) ---
    deepgram_api_key: str

    # --- Database ---
    # For local dev without Neon: set to "sqlite:///./student.db"
    # For production (Neon): "postgresql+psycopg2://user:pass@host/dbname?sslmode=require"
    database_url: str = "sqlite:///./student.db"

    # --- CORS ---
    # Comma-separated list of allowed frontend origins.
    # Example: "https://yourapp.pages.dev"
    # Use "*" for local development ONLY.
    allowed_origins: str = "*"

    # --- JWT (Phase 2 — placeholders so the app loads without errors) ---
    jwt_secret: str = "CHANGE_ME_BEFORE_DEPLOY"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,      # DATABASE_URL and database_url are equivalent
        extra="ignore",            # silently ignore unknown env vars
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        """Returns ALLOWED_ORIGINS as a Python list (splits on comma)."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings instance — reads .env exactly once.
    Use as a FastAPI dependency: Depends(get_settings)
    Or import directly: from app.config import get_settings; settings = get_settings()
    """
    return Settings()
