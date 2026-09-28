from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All config comes from env vars (or backend/.env locally)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""
    # Only needed if your project still uses the legacy HS256 JWT secret.
    # New Supabase projects sign tokens with asymmetric keys (verified via JWKS).
    supabase_jwt_secret: str = ""
    storage_bucket: str = "observation-photos"

    # AI  (provider: "gemini" or "openai_compatible" e.g. Groq)
    ai_provider: str = "gemini"
    ai_api_key: str = ""
    ai_model: str = "gemini-2.5-flash"
    ai_base_url: str = ""  # only for openai_compatible, e.g. https://api.groq.com/openai/v1
    ai_timeout_seconds: float = 20.0
    ai_rate_limit_per_minute: int = 20

    # Web
    frontend_origin: str = "http://localhost:3000"  # comma-separated allowed
    max_upload_mb: int = 8
    signed_url_expiry_seconds: int = 3600

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.frontend_origin.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
