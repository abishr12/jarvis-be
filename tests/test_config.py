from app.config import Settings


def test_settings_defaults():
    settings = Settings(_env_file=None)

    assert settings.app_env == "local"
    assert settings.cors_origins == ["http://localhost:3000"]


def test_settings_reads_app_env_from_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    settings = Settings(_env_file=None)

    assert settings.app_env == "production"
