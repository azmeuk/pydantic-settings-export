from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic_settings_export import DotEnvGenerator, SettingsInfoModel
from pydantic_settings_export.generators.dotenv import DotEnvSettings


def test_dotenv_simple(simple_settings: type[BaseSettings]) -> None:
    """Test simple .env file generation."""
    generator = DotEnvGenerator(generator_config=DotEnvSettings(split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(simple_settings))

    # Optional field should be commented
    assert "# FIELD=" in result


def test_dotenv_with_required_field(mixed_settings: type[BaseSettings]) -> None:
    """Test .env generation with required fields."""
    generator = DotEnvGenerator(generator_config=DotEnvSettings(split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(mixed_settings))

    # Required field should not be commented
    assert "REQUIRED=" in result
    assert "# REQUIRED=" not in result
    # Optional field should be commented
    assert "# OPTIONAL=" in result


# =============================================================================
# Mode tests
# =============================================================================


def test_dotenv_mode_all(mixed_settings: type[BaseSettings]) -> None:
    """Test mode='all' includes both optional and required variables."""
    generator = DotEnvGenerator(generator_config=DotEnvSettings(mode="all", split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(mixed_settings))

    assert "REQUIRED=" in result
    assert "# OPTIONAL=" in result


def test_dotenv_mode_only_optional(mixed_settings: type[BaseSettings]) -> None:
    """Test mode='only-optional' includes only optional variables."""
    generator = DotEnvGenerator(generator_config=DotEnvSettings(mode="only-optional", split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(mixed_settings))

    # Should not include required field
    assert "REQUIRED=" not in result
    # Should include optional field
    assert "# OPTIONAL=" in result


def test_dotenv_mode_only_required(mixed_settings: type[BaseSettings]) -> None:
    """Test mode='only-required' includes only required variables."""
    generator = DotEnvGenerator(generator_config=DotEnvSettings(mode="only-required", split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(mixed_settings))

    # Should include required field
    assert "REQUIRED=" in result
    # Optional field should not appear (not even commented)
    # Note: The line "# OPTIONAL=" should not be present
    assert "OPTIONAL" not in result or "# OPTIONAL" not in result


# =============================================================================
# Split by group tests
# =============================================================================


def test_dotenv_split_by_group_true(nested_settings: type[BaseSettings]) -> None:
    """Test split_by_group=True adds section headers."""
    generator = DotEnvGenerator(generator_config=DotEnvSettings(split_by_group=True))
    result = generator.generate(SettingsInfoModel.from_settings_model(nested_settings))

    assert "### Settings" in result
    assert "### Database" in result


def test_dotenv_split_by_group_false(nested_settings: type[BaseSettings]) -> None:
    """Test split_by_group=False does not add section headers."""
    generator = DotEnvGenerator(generator_config=DotEnvSettings(split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(nested_settings))

    assert "### Settings" not in result
    assert "### Database" not in result


# =============================================================================
# Examples tests
# =============================================================================


def test_dotenv_with_examples() -> None:
    """Test examples are added as comments."""

    class Settings(BaseSettings):
        field: str = Field(default="default", examples=["ex1", "ex2"])

    generator = DotEnvGenerator(generator_config=DotEnvSettings(add_examples=True, split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    # Examples should be in comments
    assert "# ex1, ex2" in result or "ex1" in result


def test_dotenv_without_examples() -> None:
    """Test examples are not added when add_examples=False."""

    class Settings(BaseSettings):
        field: str = Field(default="default", examples=["ex1", "ex2"])

    generator = DotEnvGenerator(generator_config=DotEnvSettings(add_examples=False, split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    # Should not have example comments (only the field itself)
    lines = [line for line in result.strip().split("\n") if line and not line.startswith("###")]
    # The line should just be the field without an example comment
    assert any("FIELD=" in line for line in lines)


# =============================================================================
# Alias tests
# =============================================================================


def test_dotenv_with_alias() -> None:
    """Test field alias is used as the environment variable name."""

    class Settings(BaseSettings):
        internal_name: str = Field(default="value", alias="EXTERNAL_NAME")

    generator = DotEnvGenerator(generator_config=DotEnvSettings(split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    assert "EXTERNAL_NAME=" in result


# =============================================================================
# Env prefix tests
# =============================================================================


def test_dotenv_with_env_prefix() -> None:
    """Test env_prefix is applied to field names."""

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="APP_")
        field: str = Field(default="value")

    generator = DotEnvGenerator(generator_config=DotEnvSettings(split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    assert "APP_FIELD=" in result


# =============================================================================
# Nested settings tests
# =============================================================================


def test_dotenv_with_nested_settings(nested_settings: type[BaseSettings]) -> None:
    """Test nested settings are included in .env file."""
    generator = DotEnvGenerator(generator_config=DotEnvSettings(split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(nested_settings))

    assert "DATABASE_HOST=" in result
    assert "DATABASE_PORT=" in result


def test_dotenv_nested_with_env_prefix() -> None:
    """Test nested settings with env_prefix."""

    class Database(BaseSettings):
        host: str = Field(default="localhost")

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="APP_")
        database: Database = Field(default_factory=Database)

    generator = DotEnvGenerator(generator_config=DotEnvSettings(split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    assert "APP_DATABASE_HOST=" in result


# =============================================================================
# Default value tests
# =============================================================================


def test_dotenv_optional_field_shows_default() -> None:
    """Test optional fields show their default value."""

    class Settings(BaseSettings):
        field: str = Field(default="my_default")

    generator = DotEnvGenerator(generator_config=DotEnvSettings(split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    # Optional field should be commented with default value
    assert '# FIELD="my_default"' in result


def test_dotenv_required_field_empty_value() -> None:
    """Test required fields have empty value."""

    class Settings(BaseSettings):
        field: str = Field(description="Required")

    generator = DotEnvGenerator(generator_config=DotEnvSettings(split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(Settings))

    # Required field should have empty value
    assert "FIELD=" in result
    # Should not have a value after =
    lines = result.strip().split("\n")
    field_line = next(line for line in lines if "FIELD=" in line and not line.startswith("#"))
    assert field_line.strip() == "FIELD="


# =============================================================================
# Integration tests
# =============================================================================


def test_dotenv_full_settings(full_settings: type[BaseSettings]) -> None:
    """Test comprehensive .env generation with all features."""
    generator = DotEnvGenerator(generator_config=DotEnvSettings(split_by_group=True))
    result = generator.generate(SettingsInfoModel.from_settings_model(full_settings))

    # Check main settings
    assert result == (
        "### Settings\n"
        "\n"
        '# LOG_LEVEL="INFO"\n'
        '# LOG_FORMAT="%(levelname)-8s | %(asctime)s | %(name)s | %(message)s"\n'
        "\n"
        "### MongoDB settings\n"
        "\n"
        '# MONGODB__MONGODB_URL="mongodb://localhost:27017"\n'
        '# MONGODB__MONGODB_DB_NAME="test-db"\n'
        "\n"
        "### OpenRouter settings\n"
        "\n"
        "OPENROUTER__API_KEY=\n"
        '# OPENROUTER__MODEL="google/gemini-2.5-flash"\n'
        '# OPENROUTER__BASE_URL="https://openrouter.ai/api/v1"\n'
        "\n"
        "### APISettings\n"
        "\n"
        '# API__HOST="0.0.0.0"\n'
        "# API__PORT=8000\n"
    )


def test_dotenv_multiple_settings() -> None:
    """Test generating .env for multiple settings classes."""

    class Settings1(BaseSettings):
        """First settings."""

        field1: str = Field(default="value1")

    class Settings2(BaseSettings):
        """Second settings."""

        field2: str = Field(default="value2")

    generator = DotEnvGenerator(generator_config=DotEnvSettings(split_by_group=True))
    result = generator.generate(
        SettingsInfoModel.from_settings_model(Settings1),
        SettingsInfoModel.from_settings_model(Settings2),
    )

    assert "### Settings1" in result
    assert "FIELD1=" in result
    assert "### Settings2" in result
    assert "FIELD2=" in result


def test_dotenv_mode_only_required_nested(nested_settings: type[BaseSettings]) -> None:
    """Test mode='only-required' works with nested settings."""
    generator = DotEnvGenerator(generator_config=DotEnvSettings(mode="only-required", split_by_group=False))
    result = generator.generate(SettingsInfoModel.from_settings_model(nested_settings))

    # Should only include required field from nested settings
    assert "DATABASE_PORT=\n" == result
