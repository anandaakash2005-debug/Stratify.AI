import pytest
from pydantic import ValidationError

from config.settings import Settings


def make_settings(**overrides):
    values = {
        "_env_file": None,
        "SECRET_KEY": "test-secret-key-that-is-long-enough",
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_ANON_KEY": "header.payload.signature",
        "SUPABASE_SERVICE_KEY": "header.payload.signature",
    }
    values.update(overrides)
    return Settings(**values)


def test_environment_name_and_legacy_app_env_are_supported():
    assert make_settings(ENVIRONMENT="development").APP_ENV == "development"
    assert make_settings(APP_ENV="development").APP_ENV == "development"


def test_production_configuration_requires_debug_disabled_and_public_hosts():
    settings = make_settings(
        ENVIRONMENT="production",
        DEBUG=False,
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY="test-openrouter-key",
        PRIMARY_MODEL="provider/model",
        ALLOWED_ORIGINS=["https://satquery-frontend.onrender.com"],
        ALLOWED_HOSTS=["satquery-api.onrender.com"],
    )

    assert settings.APP_ENV == "production"
    assert settings.DEBUG is False


@pytest.mark.parametrize(
    "overrides, message",
    [
        (
            {
                "ENVIRONMENT": "production",
                "DEBUG": True,
                "ALLOWED_ORIGINS": ["https://frontend.example"],
                "ALLOWED_HOSTS": ["api.example"],
            },
            "DEBUG must be false",
        ),
        (
            {
                "ENVIRONMENT": "production",
                "DEBUG": False,
                "ALLOWED_ORIGINS": ["*"],
                "ALLOWED_HOSTS": ["api.example"],
            },
            "ALLOWED_ORIGINS",
        ),
        (
            {
                "ENVIRONMENT": "production",
                "DEBUG": False,
                "ALLOWED_ORIGINS": ["https://frontend.example"],
                "ALLOWED_HOSTS": ["localhost"],
            },
            "ALLOWED_HOSTS",
        ),
    ],
)
def test_production_rejects_insecure_debug_or_host_configuration(overrides, message):
    with pytest.raises(ValidationError, match=message):
        make_settings(**overrides)


def test_openrouter_requires_an_explicit_model():
    with pytest.raises(ValidationError, match="PRIMARY_MODEL"):
        make_settings(
            AI_PROVIDER="openrouter",
            OPENROUTER_API_KEY="test-openrouter-key",
        )
