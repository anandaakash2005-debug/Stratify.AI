"""
config/settings.py — Centralised environment & app settings
Loads from backend/.env with typed validation.
All backend configuration must come from environment variables.
"""

import logging
import re
import sys
from pathlib import Path
from functools import lru_cache
from typing import List

from pydantic import AliasChoices, AnyUrl, Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = Field("AI Startup Survival Intelligence Platform", description="Application display name")
    APP_ENV: str = Field(
        "development",
        validation_alias=AliasChoices("ENVIRONMENT", "APP_ENV"),
        description="Application environment (ENVIRONMENT; APP_ENV remains supported)",
    )
    DEBUG: bool = Field(True, description="Enable debug mode")
    API_VERSION: str = Field("v1", description="API version")

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(..., min_length=32, description="Secret key for signing and security")
    ALLOWED_ORIGINS: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins",
    )
    ALLOWED_HOSTS: List[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1"],
        description="Allowed trusted hosts",
    )

    # ── AI provider ───────────────────────────────────────────────────────────
    AI_PROVIDER: str = Field("ollama", description="AI provider: ollama or openrouter")
    OLLAMA_BASE_URL: AnyUrl = Field(
        "http://127.0.0.1:11434/v1",
        description="Local Ollama OpenAI-compatible URL",
    )
    OLLAMA_MODEL: str = Field("qwen3:1.7b", description="Local Ollama model")
    OLLAMA_API_KEY: str = Field("ollama", description="Placeholder API key for Ollama")
    ANALYSIS_TIMEOUT: int = Field(
        480,
        ge=1,
        description="Complete analysis request timeout in seconds",
    )
    OLLAMA_TIMEOUT: int = Field(
        420,
        ge=1,
        description="Local Ollama generation timeout in seconds",
    )
    OLLAMA_MAX_TOKENS: int = Field(
        2048,
        ge=1,
        description="Maximum output tokens for Ollama",
    )

    # ── OpenRouter ────────────────────────────────────────────────────────────
    OPENROUTER_API_KEY: str = Field("", description="OpenRouter API key")
    OPENROUTER_BASE_URL: AnyUrl = Field("https://openrouter.ai/api/v1", description="OpenRouter base API URL")
    PRIMARY_MODEL: str = Field(
        "",
        description="Explicit primary OpenRouter model ID; required when AI_PROVIDER=openrouter",
    )
    FALLBACK_MODELS: List[str] = Field(
        default_factory=list,
        description="Ordered list of fallback OpenRouter models tried if primary fails",
    )
    OPENROUTER_MAX_TOKENS: int = Field(4096, ge=1, description="Max tokens per OpenRouter request")
    OPENROUTER_TEMPERATURE: float = Field(0.1, ge=0.0, le=2.0, description="OpenRouter temperature")
    OPENROUTER_TIMEOUT: int = Field(90, ge=1, description="OpenRouter request timeout in seconds")

    # ── Supabase ─────────────────────────────────────────────────────────────────
    SUPABASE_URL: AnyUrl = Field(..., description="Supabase project URL")
    SUPABASE_ANON_KEY: str = Field(..., description="Supabase anon public key")
    SUPABASE_SERVICE_KEY: str = Field(..., description="Supabase service role key")

    # ── Rate limiting ─────────────────────────────────────────────────────────────
    RATE_LIMIT_ANALYZE: str = Field("10/minute", description="Analysis endpoint rate limit")
    RATE_LIMIT_DEFAULT: str = Field("60/minute", description="Default rate limit")

    # ── ML pipeline (future) ─────────────────────────────────────────────────────
    ML_SERVICE_URL: str = Field("", description="Internal ML service URL")
    ML_ENABLED: bool = Field(False, description="Enable internal ML service integration")

    @field_validator("AI_PROVIDER", mode="before")
    @classmethod
    def normalize_ai_provider(cls, value):
        provider = value.lower() if isinstance(value, str) else value
        if provider not in {"ollama", "openrouter"}:
            raise ValueError("AI_PROVIDER must be either 'ollama' or 'openrouter'.")
        return provider

    @model_validator(mode="after")
    def validate_configuration(self):
        data = self.__dict__
        required_vars = [
            "SECRET_KEY",
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY",
            "SUPABASE_SERVICE_KEY",
        ]
        if data.get("AI_PROVIDER") == "openrouter":
            required_vars.extend(["OPENROUTER_API_KEY", "PRIMARY_MODEL"])
        missing = [k for k in required_vars if not data.get(k)]
        if missing:
            raise ValueError(
                "Missing required backend configuration values: " + ", ".join(missing)
            )
        if data.get("AI_PROVIDER") == "openrouter" and len(data["OPENROUTER_API_KEY"]) < 10:
            raise ValueError("OPENROUTER_API_KEY must be at least 10 characters for OpenRouter.")
        if data.get("AI_PROVIDER") == "ollama" and data["ANALYSIS_TIMEOUT"] <= data["OLLAMA_TIMEOUT"]:
            raise ValueError("ANALYSIS_TIMEOUT must be greater than OLLAMA_TIMEOUT for Ollama.")
        if data.get("ML_ENABLED") and not data.get("ML_SERVICE_URL"):
            raise ValueError("ML_ENABLED is true but ML_SERVICE_URL is not configured.")

        if data.get("APP_ENV", "").strip().lower() in {"prod", "production"}:
            if data.get("DEBUG"):
                raise ValueError("DEBUG must be false in production.")
            if not data.get("ALLOWED_ORIGINS") or "*" in data["ALLOWED_ORIGINS"]:
                raise ValueError("Production ALLOWED_ORIGINS must be explicitly configured without wildcards.")
            if any(
                origin.strip().lower().startswith(("http://localhost", "https://localhost", "http://127.", "https://127."))
                for origin in data["ALLOWED_ORIGINS"]
            ):
                raise ValueError("Production ALLOWED_ORIGINS cannot contain localhost addresses.")
            if not data.get("ALLOWED_HOSTS") or "*" in data["ALLOWED_HOSTS"]:
                raise ValueError("Production ALLOWED_HOSTS must be explicitly configured without wildcards.")
            if any(host.strip().lower() in {"localhost", "127.0.0.1", "::1"} for host in data["ALLOWED_HOSTS"]):
                raise ValueError("Production ALLOWED_HOSTS cannot contain loopback hosts.")

        supabase_jwt_pattern = re.compile(
            r"^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*$"
        )
        invalid_keys = [
            key
            for key in ["SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY"]
            if data.get(key) and not supabase_jwt_pattern.match(data.get(key))
        ]
        if invalid_keys:
            raise ValueError(
                "Invalid Supabase API key format for: "
                + ", ".join(invalid_keys)
                + ". Use JWT-style Supabase keys from your project settings."
            )
        return self

    class Config:
        env_file = ENV_FILE
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton — call get_settings() everywhere."""
    return Settings()


try:
    settings = get_settings()
except ValidationError as exc:
    logging.error("Backend configuration validation failed. Please verify backend/.env and required environment variables.")
    logging.error("Invalid configuration fields: %s", [e["loc"] for e in exc.errors(include_input=False)])
    sys.exit(1)
