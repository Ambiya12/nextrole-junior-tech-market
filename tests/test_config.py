from pathlib import Path

import pytest
from pydantic import ValidationError

from nextrole.config import Settings


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.data_dir == Path("data")
    assert settings.log_level == "INFO"
    assert settings.database_url is None


def test_settings_use_the_nextrole_environment_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXTROLE_ENVIRONMENT", "test")
    monkeypatch.setenv("NEXTROLE_DATA_DIR", "tmp/job-data")
    monkeypatch.setenv("NEXTROLE_LOG_LEVEL", "DEBUG")

    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.data_dir == Path("tmp/job-data")
    assert settings.log_level == "DEBUG"


def test_settings_reject_unknown_log_levels(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXTROLE_LOG_LEVEL", "VERBOSE")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
