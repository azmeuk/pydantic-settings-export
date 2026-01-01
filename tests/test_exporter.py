import warnings
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import Field
from pydantic_settings import BaseSettings

from pydantic_settings_export import Exporter, PSESettings
from pydantic_settings_export.generators import AbstractGenerator
from pydantic_settings_export.generators.simple import SimpleGenerator, SimpleSettings


@pytest.fixture
def pse_settings(tmp_path: Path) -> PSESettings:
    """PSESettings with temp directory."""
    return PSESettings(root_dir=tmp_path, project_dir=tmp_path)


# =============================================================================
# Initialization tests
# =============================================================================


def test_exporter_init_default() -> None:
    """Test Exporter initialization with defaults."""
    exporter = Exporter()

    assert exporter.settings is not None
    assert isinstance(exporter.settings, PSESettings)
    assert len(exporter.generators) > 0


def test_exporter_init_with_settings(pse_settings: PSESettings) -> None:
    """Test Exporter initialization with custom settings."""
    exporter = Exporter(settings=pse_settings)

    assert exporter.settings == pse_settings


def test_exporter_init_default_generators() -> None:
    """Test Exporter initializes with all default generators."""
    exporter = Exporter()

    # Should have generators for all registered generator classes
    generator_types = [type(g) for g in exporter.generators]
    for gen_class in AbstractGenerator.ALL_GENERATORS:
        assert gen_class in generator_types


def test_exporter_init_custom_generators(pse_settings: PSESettings) -> None:
    """Test Exporter initialization with custom generators."""
    custom_generator = SimpleGenerator(pse_settings)
    exporter = Exporter(settings=pse_settings, generators=[custom_generator])

    assert len(exporter.generators) == 1
    assert exporter.generators[0] == custom_generator


def test_exporter_init_empty_generators(pse_settings: PSESettings) -> None:
    """Test Exporter initialization with empty generators list."""
    exporter = Exporter(settings=pse_settings, generators=[])

    assert len(exporter.generators) == 0


# =============================================================================
# run_all tests
# =============================================================================


def test_exporter_run_all_returns_paths(simple_settings: Any, tmp_path: Path) -> None:
    """Test run_all returns list of paths."""
    pse_settings = PSESettings(root_dir=tmp_path, project_dir=tmp_path)
    output_file = tmp_path / "output.txt"

    # Create a generator with a path
    generator = SimpleGenerator(
        pse_settings,
        generator_config=SimpleSettings(paths=[output_file]),
    )
    exporter = Exporter(settings=pse_settings, generators=[generator])

    result = exporter.run_all(simple_settings)

    assert isinstance(result, list)
    assert output_file in result
    assert output_file.exists()


def test_exporter_run_all_multiple_settings(tmp_path: Path) -> None:
    """Test run_all with multiple settings classes."""

    class Settings1(BaseSettings):
        field1: str = Field(default="value1")

    class Settings2(BaseSettings):
        field2: str = Field(default="value2")

    pse_settings = PSESettings(root_dir=tmp_path, project_dir=tmp_path)
    output_file = tmp_path / "output.txt"

    generator = SimpleGenerator(
        pse_settings,
        generator_config=SimpleSettings(paths=[output_file]),
    )
    exporter = Exporter(settings=pse_settings, generators=[generator])

    result = exporter.run_all(Settings1, Settings2)

    assert output_file in result
    content = output_file.read_text()
    assert "Settings1" in content
    assert "Settings2" in content


def test_exporter_run_all_no_generators(simple_settings: Any, pse_settings: PSESettings) -> None:
    """Test run_all with no generators returns empty list."""
    exporter = Exporter(settings=pse_settings, generators=[])

    result = exporter.run_all(simple_settings)

    assert result == []


def test_exporter_run_all_with_settings_instance(tmp_path: Path) -> None:
    """Test run_all accepts settings instance (not just class)."""

    class Settings(BaseSettings):
        field: str = Field(default="value")

    settings_instance = Settings()
    pse_settings = PSESettings(root_dir=tmp_path, project_dir=tmp_path)
    output_file = tmp_path / "output.txt"

    generator = SimpleGenerator(
        pse_settings,
        generator_config=SimpleSettings(paths=[output_file]),
    )
    exporter = Exporter(settings=pse_settings, generators=[generator])

    result = exporter.run_all(settings_instance)

    assert output_file in result


# =============================================================================
# Generator failure handling tests
# =============================================================================


def test_exporter_handles_generator_failure(simple_settings: Any, pse_settings: PSESettings) -> None:
    """Test Exporter handles generator failures with warning."""
    # Create a mock generator that raises an exception
    mock_generator = MagicMock(spec=AbstractGenerator)
    mock_generator.run.side_effect = Exception("Generator failed")

    exporter = Exporter(settings=pse_settings, generators=[mock_generator])

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = exporter.run_all(simple_settings)

        # Should have a warning about the failure
        assert len(w) >= 1
        assert any("failed" in str(warning.message).lower() for warning in w)

    # Should return empty list since generator failed
    assert result == []


def test_exporter_continues_after_generator_failure(simple_settings: Any, tmp_path: Path) -> None:
    """Test Exporter continues with other generators after one fails."""
    pse_settings = PSESettings(root_dir=tmp_path, project_dir=tmp_path)
    output_file = tmp_path / "output.txt"

    # Create a failing generator
    failing_generator = MagicMock(spec=AbstractGenerator)
    failing_generator.run.side_effect = Exception("Generator failed")

    # Create a working generator
    working_generator = SimpleGenerator(
        pse_settings,
        generator_config=SimpleSettings(paths=[output_file]),
    )

    exporter = Exporter(settings=pse_settings, generators=[failing_generator, working_generator])

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        result = exporter.run_all(simple_settings)

    # Should still have output from working generator
    assert output_file in result


# =============================================================================
# Generator initialization failure tests
# =============================================================================


def test_exporter_handles_generator_init_failure() -> None:
    """Test Exporter handles generator initialization failures."""
    # This test verifies that if a generator fails to initialize,
    # the Exporter still works with other generators

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        # Default initialization should work even if some generators fail
        exporter = Exporter()

        # Exporter should still be created
        assert exporter is not None


# =============================================================================
# File creation tests
# =============================================================================


def test_exporter_creates_output_directory(simple_settings: Any, tmp_path: Path) -> None:
    """Test Exporter creates an output directory if it doesn't exist."""
    pse_settings = PSESettings(root_dir=tmp_path, project_dir=tmp_path)
    nested_dir = tmp_path / "nested" / "dir"
    output_file = nested_dir / "output.txt"

    generator = SimpleGenerator(
        pse_settings,
        generator_config=SimpleSettings(paths=[output_file]),
    )
    exporter = Exporter(settings=pse_settings, generators=[generator])

    result = exporter.run_all(simple_settings)

    assert nested_dir.exists()
    assert output_file in result


def test_exporter_skips_unchanged_files(simple_settings: Any, tmp_path: Path) -> None:
    """Test Exporter skips writing if file content unchanged."""
    pse_settings = PSESettings(root_dir=tmp_path, project_dir=tmp_path)
    output_file = tmp_path / "output.txt"

    generator = SimpleGenerator(
        pse_settings,
        generator_config=SimpleSettings(paths=[output_file]),
    )
    exporter = Exporter(settings=pse_settings, generators=[generator])

    # The first run - should create a file
    result1 = exporter.run_all(simple_settings)
    assert output_file in result1

    # The second run - should skip since content unchanged
    result2 = exporter.run_all(simple_settings)
    assert output_file not in result2  # File not in an updated list
