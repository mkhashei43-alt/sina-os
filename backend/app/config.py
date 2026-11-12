"""Sina AI OS — application settings (env-driven)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore",
                                      protected_namespaces=("settings_",))

    # --- app ---
    app_name: str = "Sina AI OS"
    env: str = "dev"  # dev | prod
    debug: bool = False
    api_prefix: str = "/api"

    # --- database ---
    database_url: str = "sqlite+aiosqlite:///./data/sina.db"
    auto_create_tables: bool = True  # dev/test convenience; prod uses alembic

    # --- redis (event bus between api/worker) ---
    redis_url: str | None = None

    # --- auth ---
    jwt_secret: str = "change-me-in-env-please-32-bytes-min"
    access_token_minutes: int = 12 * 60
    admin_email: str = "admin@sina.local"
    admin_password: str = "admin123!change"
    seed_admin: bool = True

    # --- openrouter / LLM provider ---
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_referer: str = "https://sina-ai-os.local"
    default_model: str = "openai/gpt-4o-mini"
    coding_model: str = "anthropic/claude-sonnet-4.5"
    reasoning_model: str = "openai/o3-mini"
    llm_timeout_seconds: int = 120
    llm_max_retries: int = 3
    llm_max_tokens: int = 2048  # cap completion size (free tiers / small balances)
    # tried in order when the primary model errors out (429/404/402 from a free tier)
    model_fallbacks: str = ""

    # --- embeddings (optional semantic memory) ---
    embeddings_base_url: str | None = None  # OpenAI-compatible /embeddings endpoint
    embeddings_api_key: str | None = None
    embeddings_model: str = "text-embedding-3-small"

    # --- workspaces / execution ---
    workspace_root: str = "./data/sina-ai"
    exec_timeout_seconds: int = 120
    max_output_bytes: int = 200_000
    max_upload_mb: int = 25
    pip_allowlist: str = (
        "requests,httpx,fastapi,flask,uvicorn,pytest,numpy,pandas,beautifulsoup4,"
        "pydantic,sqlalchemy,rich,click,pyyaml,python-dateutil"
    )

    # --- agent loop ---
    max_agent_iterations: int = 24
    max_tool_calls_per_task: int = 40
    require_approval_levels: str = "confirm,admin"  # risk levels that pause for approval

    # --- telegram ---
    telegram_bot_token: str | None = None
    telegram_allowed_ids: str = ""  # comma separated numeric ids

    # --- کنسول وب داخلی (بدون نیاز به Node.js) ---
    serve_console: bool = True

    # --- نسخهٔ فروش (SaaS) ---
    platform_admin_emails: str = ""          # ایمیل‌های مدیر پلتفرم (با کاما جدا شود)
    signup_enabled: bool = True              # ثبت‌نام عمومی
    signup_trial_days: int = 7
    support_telegram: str = ""               # آیدی پشتیبانی برای نمایش در لندینگ
    support_email: str = ""
    sales_brand: str = "سینا کلود"

    # --- integrations secrets encryption ---
    secrets_encryption_key: str | None = None  # Fernet key; falls back to jwt-derived

    # --- rate limiting ---
    rate_limit_auth_per_min: int = 10
    rate_limit_default_per_min: int = 120
    rate_limit_signup_per_min: int = 5

    cors_origins: str = "*"

    @property
    def workspace_path(self) -> Path:
        p = Path(self.workspace_root).resolve()
        p.mkdir(parents=True, exist_ok=True)
        for sub in ("workspaces", "projects", "uploads", "downloads", "artifacts", "logs", "backups"):
            (p / sub).mkdir(parents=True, exist_ok=True)
        return p

    @property
    def approval_levels(self) -> set[str]:
        return {x.strip() for x in self.require_approval_levels.split(",") if x.strip()}

    @property
    def fallbacks(self) -> list[str]:
        return [x.strip() for x in self.model_fallbacks.split(",") if x.strip()]

    @property
    def pip_allow(self) -> set[str]:
        return {x.strip().lower() for x in self.pip_allowlist.split(",") if x.strip()}

    @property
    def telegram_ids(self) -> set[int]:
        out: set[int] = set()
        for x in self.telegram_allowed_ids.split(","):
            x = x.strip()
            if x.lstrip("-").isdigit():
                out.add(int(x))
        return out

    @property
    def cors_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
