"""Tests for sources module."""

from pathlib import Path

import pytest
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from pydantic_settings_export.sources import TomlSettings

# =============================================================================
# Tests for TomlSettings without toml file
# =============================================================================


def test_toml_settings_without_toml_file() -> None:
    """Test TomlSettings works without toml file."""

    class Settings(TomlSettings):
        field: str = Field(default="value")

    settings = Settings()

    assert settings.field == "value"


def test_toml_settings_default_values() -> None:
    """Test TomlSettings uses default values when no toml file."""

    class Settings(TomlSettings):
        field1: str = Field(default="default1")
        field2: int = Field(default=42)

    settings = Settings()

    assert settings.field1 == "default1"
    assert settings.field2 == 42


# =============================================================================
# Tests for TomlSettings with toml file
# =============================================================================


def test_toml_settings_with_toml_file(tmp_path: Path) -> None:
    """Test TomlSettings loads from toml file."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text('[tool.test]\nfield = "from_toml"\n')

    class Settings(TomlSettings):
        model_config = SettingsConfigDict(
            toml_file=toml_file,
            pyproject_toml_table_header=("tool", "test"),
        )
        field: str = Field(default="default")

    settings = Settings()

    assert settings.field == "from_toml"


def test_toml_settings_with_nonexistent_toml_file(tmp_path: Path) -> None:
    """Test TomlSettings handles nonexistent toml file gracefully."""
    nonexistent = tmp_path / "nonexistent.toml"

    class Settings(TomlSettings):
        model_config = SettingsConfigDict(
            toml_file=nonexistent,
            pyproject_toml_table_header=("tool", "test"),
        )
        field: str = Field(default="default")

    # Should use default value when file doesn't exist
    settings = Settings()

    assert settings.field == "default"


# =============================================================================
# Tests for TomlSettings with pyproject.toml
# =============================================================================


def test_toml_settings_with_pyproject(tmp_path: Path) -> None:
    """Test TomlSettings loads from pyproject.toml."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.myapp]\nfield = "from_pyproject"\n')

    class Settings(TomlSettings):
        model_config = SettingsConfigDict(
            toml_file=pyproject,
            pyproject_toml_table_header=("tool", "myapp"),
        )
        field: str = Field(default="default")

    settings = Settings()

    assert settings.field == "from_pyproject"


def test_toml_settings_with_nested_table(tmp_path: Path) -> None:
    """Test TomlSettings loads from nested toml table."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text('[tool.myapp.database]\nhost = "localhost"\nport = 5432\n')

    class Settings(TomlSettings):
        model_config = SettingsConfigDict(
            toml_file=toml_file,
            pyproject_toml_table_header=("tool", "myapp", "database"),
        )
        host: str = Field(default="127.0.0.1")
        port: int = Field(default=3306)

    settings = Settings()

    assert settings.host == "localhost"
    assert settings.port == 5432


# =============================================================================
# Tests for TomlSettings priority
# =============================================================================


def test_toml_settings_toml_overrides_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test toml file values override environment variables.

    In TomlSettings, the priority order is:
    1. init_settings (highest)
    2. toml file
    3. env_settings
    4. dotenv_settings
    5. file_secret_settings (lowest)
    """
    toml_file = tmp_path / "config.toml"
    toml_file.write_text('[tool.test]\nfield = "from_toml"\n')

    monkeypatch.setenv("FIELD", "from_env")

    class Settings(TomlSettings):
        model_config = SettingsConfigDict(
            toml_file=toml_file,
            pyproject_toml_table_header=("tool", "test"),
        )
        field: str = Field(default="default")

    settings = Settings()

    # Toml has higher priority than env in TomlSettings
    assert settings.field == "from_toml"


def test_toml_settings_init_overrides_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test init values override both env and toml."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text('[tool.test]\nfield = "from_toml"\n')

    monkeypatch.setenv("FIELD", "from_env")

    class Settings(TomlSettings):
        model_config = SettingsConfigDict(
            toml_file=toml_file,
            pyproject_toml_table_header=("tool", "test"),
        )
        field: str = Field(default="default")

    settings = Settings(field="from_init")

    # Init should override everything
    assert settings.field == "from_init"


# =============================================================================
# Tests for TomlSettings with multiple fields
# =============================================================================


def test_toml_settings_partial_override(tmp_path: Path) -> None:
    """Test TomlSettings with partial override from toml."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text('[tool.test]\nfield1 = "overridden"\n')

    class Settings(TomlSettings):
        model_config = SettingsConfigDict(
            toml_file=toml_file,
            pyproject_toml_table_header=("tool", "test"),
        )
        field1: str = Field(default="default1")
        field2: str = Field(default="default2")

    settings = Settings()

    assert settings.field1 == "overridden"
    assert settings.field2 == "default2"


# =============================================================================
# Tests for settings_customise_sources
# =============================================================================


def test_toml_settings_customise_sources_called() -> None:
    """Test that settings_customise_sources is properly configured."""
    # Verify the method exists and is callable
    assert hasattr(TomlSettings, "settings_customise_sources")
    assert callable(TomlSettings.settings_customise_sources)


def test_toml_settings_with_toml_file_list(tmp_path: Path) -> None:
    """Test TomlSettings handles toml_file as sequence."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text('[tool.test]\nfield = "from_toml"\n')

    class Settings(TomlSettings):
        model_config = SettingsConfigDict(
            toml_file=[toml_file],  # As a list
            pyproject_toml_table_header=("tool", "test"),
        )
        field: str = Field(default="default")

    settings = Settings()

    assert settings.field == "from_toml"
