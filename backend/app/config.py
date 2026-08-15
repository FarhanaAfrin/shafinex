"""Runtime configuration. Everything comes from env vars (Render dashboard / .env)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # sqlite fallback keeps local dev zero-setup; Neon URL is injected in prod.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'local.db'}"

    # Single-user auth: one password, one signing secret.
    app_password: str = "change-me"
    secret_key: str = "dev-secret-change-me"
    token_ttl_days: int = 30

    # Where the built Vue app lives. Served by FastAPI so there is one URL, no CORS.
    static_dir: Path = REPO_DIR / "frontend" / "dist"

    # Allow a separate Vite dev server during local development.
    dev_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    log_level: str = "INFO"

    @property
    def normalized_database_url(self) -> str:
        """Neon hands out `postgres://`; SQLAlchemy 2 wants an explicit driver."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def dev_origin_list(self) -> list[str]:
        return [o.strip() for o in self.dev_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
