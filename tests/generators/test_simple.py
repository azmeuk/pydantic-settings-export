from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic_settings_export import SettingsInfoModel, SimpleGenerator

# =============================================================================
# Basic generation tests
# =============================================================================


def test_simple_basic_output(simple_settings: Any) -> None:
    """Test basic simple text output."""
    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(simple_settings))

    # Check header
    assert "Settings" in result
    assert "========" in result  # Header underline
    # Check docstring
    assert "Test settings." in result
    # Check field
    assert "`field`" in result
    assert "string" in result
    assert "Field description" in result


def test_simple_with_env_prefix() -> None:
    """Test simple output shows env_prefix."""

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="APP_")
        field: str = Field(default="value", description="A field")

    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    assert "Environment Prefix: APP_" in result


def test_simple_without_env_prefix(simple_settings: Any) -> None:
    """Test simple output without env_prefix."""
    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(simple_settings))

    assert "Environment Prefix:" not in result


# =============================================================================
# Field display tests
# =============================================================================


def test_simple_with_default(simple_settings: Any) -> None:
    """Test default value is displayed."""
    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(simple_settings))

    assert 'Default: "value"' in result


def test_simple_without_default() -> None:
    """Test required field without default."""

    class Settings(BaseSettings):
        field: str = Field(description="Required field")

    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    # Should not have Default line for required field
    assert "Default:" not in result


def test_simple_with_deprecated() -> None:
    """Test deprecated field is marked."""

    class Settings(BaseSettings):
        field: str = Field(default="value", deprecated=True)

    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    assert "(⚠️ Deprecated)" in result


def test_simple_with_examples() -> None:
    """Test examples are displayed."""

    class Settings(BaseSettings):
        field: str = Field(default="default", examples=["ex1", "ex2"])

    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    assert "Examples:" in result
    assert "ex1" in result
    assert "ex2" in result


def test_simple_without_examples() -> None:
    """Test no examples line when examples equal default."""

    class Settings(BaseSettings):
        field: str = Field(default="value")

    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    # Should not have Examples line when examples equal default
    assert "Examples:" not in result


def test_simple_with_description(simple_settings: Any) -> None:
    """Test description is displayed."""
    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(simple_settings))

    assert "Field description" in result


def test_simple_without_description() -> None:
    """Test field without description."""

    class Settings(BaseSettings):
        field: str = Field(default="value")

    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    # Field should still be present
    assert "`field`" in result


# =============================================================================
# Type display tests
# =============================================================================


def test_simple_with_various_types() -> None:
    """Test various Python types are displayed."""

    class Settings(BaseSettings):
        str_field: str = Field(default="value")
        int_field: int = Field(default=42)
        bool_field: bool = Field(default=True)
        list_field: list[str] = Field(default_factory=list)

    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    assert "string" in result
    assert "integer" in result
    assert "boolean" in result
    assert "array" in result


# =============================================================================
# Alias tests
# =============================================================================


def test_simple_with_alias() -> None:
    """Test field alias is used as full_name."""

    class Settings(BaseSettings):
        internal_name: str = Field(default="value", alias="external_name")

    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    assert "`external_name`" in result


# =============================================================================
# Documentation tests
# =============================================================================


def test_simple_with_docstring(simple_settings: Any) -> None:
    """Test settings docstring is displayed."""
    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(simple_settings))

    assert "Test settings." in result


def test_simple_without_docstring() -> None:
    """Test settings without docstring."""

    class Settings(BaseSettings):
        field: str = Field(default="value")

    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    # Should still have header
    assert "Settings" in result
    assert "========" in result


# =============================================================================
# Integration tests
# =============================================================================


def test_simple_full_settings(full_settings: Any) -> None:
    """Test comprehensive simple output with all features."""
    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(full_settings))

    # Check main settings
    assert result == (
        "Settings\n"
        "========\n"
        "\n"
        "`log_level`: ['\"DEBUG\"', '\"INFO\"', '\"WARNING\"', '\"ERROR\"', "
        "'\"CRITICAL\"']\n"
        "------------------------------------------------------------------------\n"
        "\n"
        "The log level to use\n"
        "\n"
        'Default: "INFO"\n'
        "\n"
        "`log_format`: ['string']\n"
        "------------------------\n"
        "\n"
        "The log format to use\n"
        "\n"
        'Default: "%(levelname)-8s | %(asctime)s | %(name)s | %(message)s"\n'
    )


def test_simple_multiple_settings() -> None:
    """Test generating simple output for multiple settings classes."""

    class Settings1(BaseSettings):
        """First settings."""

        field1: str = Field(default="value1")

    class Settings2(BaseSettings):
        """Second settings."""

        field2: str = Field(default="value2")

    generator = SimpleGenerator()
    result = generator.generate(
        SettingsInfoModel.from_settings_model(Settings1),
        SettingsInfoModel.from_settings_model(Settings2),
    )

    assert "Settings1" in result
    assert "First settings." in result
    assert "`field1`" in result
    assert "Settings2" in result
    assert "Second settings." in result
    assert "`field2`" in result


def test_simple_multiple_fields() -> None:
    """Test settings with multiple fields."""

    class Settings(BaseSettings):
        field1: str = Field(default="value1", description="First field")
        field2: int = Field(default=42, description="Second field")
        field3: bool = Field(default=True, description="Third field")

    generator = SimpleGenerator()
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    assert "`field1`" in result
    assert "`field2`" in result
    assert "`field3`" in result
    assert "First field" in result
    assert "Second field" in result
    assert "Third field" in result
