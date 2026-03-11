"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "SocialMediaAgent"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/social_media_agent"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/social_media_agent"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Meta
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_redirect_uri: str = "http://localhost:8000/api/auth/meta/callback"
    facebook_graph_api_version: str = "v18.0"

    # AI Provider (groq | ollama | openai)
    # groq:   base_url = https://api.groq.com/openai/v1
    # ollama: base_url = http://localhost:11434/v1
    # openai: leave ai_base_url empty
    ai_provider: str = "groq"
    ai_base_url: str = "https://api.groq.com/openai/v1"
    # Groq-specific keys (preferred when provider=groq)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_vision_model: str = "llama-3.2-11b-vision-preview"
    # Fallback / OpenAI-compatible key (used when groq_api_key is empty)
    openai_api_key: str = ""
    openai_model: str = "gpt-4"

    # Image Generation — Pollinations.ai (free, no key required)
    image_generation_enabled: bool = True
    pollinations_model: str = "flux"
    pollinations_width: int = 1024
    pollinations_height: int = 1024

    # Scheduler
    daily_post_generation_hour: int = 6
    timezone: str = "UTC"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
