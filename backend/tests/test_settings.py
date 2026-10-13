import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def test_environment_prefix_and_port_validation(monkeypatch):
    monkeypatch.setenv("FASTAPIAPP_POSTGRES_DB_PASSWORD", "test-only")
    monkeypatch.setenv("FASTAPIAPP_SECRET_KEY", "test-only-secret-key-with-32-characters")
    monkeypatch.setenv("FASTAPIAPP_PORT", "8123")
    settings = Settings(_env_file=None)
    assert settings.port == 8123
    monkeypatch.setenv("FASTAPIAPP_PORT", "abc")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_env_demo_can_bootstrap_a_new_checkout():
    from app.config.settings import BACKEND_ROOT

    settings = Settings(_env_file=BACKEND_ROOT / "env.demo")
    assert len(settings.secret_key.get_secret_value()) >= 32
