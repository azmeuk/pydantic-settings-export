"""TOML generator for Pydantic settings export."""

import re
import textwrap
from pathlib import Path
from typing import Any, Literal

from pydantic import ConfigDict, Field

from pydantic_settings_export.models import FieldInfoModel, SettingsInfoModel, format_types, value_repr

from .abstract import AbstractGenerator, BaseGeneratorSettings

try:
    import tomlkit
    from tomlkit import comment, document, inline_table, key, nl, table

    TOMLKIT_AVAILABLE = True
except ImportError:
    TOMLKIT_AVAILABLE = False

__all__ = ("TomlGenerator", "TomlSettings")


TomlMode = Literal["all", "only-optional", "only-required"]

TOML_MODE_MAP: dict[TomlMode, tuple[bool, bool]] = {
    "all": (True, True),
    "only-optional": (True, False),
    "only-required": (False, True),
}
TOML_MODE_MAP_DEFAULT = TOML_MODE_MAP["all"]

TOML_MAX_LINE_WIDTH = 80


def _remove_none_values(value: Any) -> Any:
    """Recursively remove None values from nested structures."""
    if value is None:
        return None

    if isinstance(value, dict):
        cleaned = {}
        for k, v in value.items():
            cleaned_value = _remove_none_values(v)
            if cleaned_value is not None:
                cleaned[k] = cleaned_value
        return cleaned

    elif isinstance(value, (list, tuple)):
        cleaned_items = []
        for item in value:
            cleaned_item = _remove_none_values(item)
            if cleaned_item is not None:
                cleaned_items.append(cleaned_item)
        return cleaned_items if cleaned_items else value.__class__()

    return value


def _to_inline_tables(value: Any) -> Any:
    """Recursively convert dicts to inline_table for TOML serialization."""
    if isinstance(value, dict):
        it = inline_table()
        for k, v in value.items():
            it[k] = _to_inline_tables(v)
        return it
    elif isinstance(value, list):
        return [item if isinstance(item, dict) else _to_inline_tables(item) for item in value]
    return value


def _format_list_value(value: Any, field_key: str, full_key: str) -> Any:
    """Convert a list to a tomlkit array, using multiline if the inline form exceeds 80 chars.

    Caller is responsible for converting nested dicts to inline tables beforehand.
    """
    if not TOMLKIT_AVAILABLE or not isinstance(value, list) or any(isinstance(item, dict) for item in value):
        return value
    arr = tomlkit.array()
    for item in value:
        arr.append(item)
    # Check if inline form fits in 80 chars
    inline_str = tomlkit.dumps({field_key: arr}).strip()
    if field_key != full_key:
        inline_str = inline_str.replace(f"{field_key} =", f"{full_key} =", 1)
    if len(inline_str) <= TOML_MAX_LINE_WIDTH:
        return arr
    arr_ml = tomlkit.array()
    arr_ml.multiline(True)
    for item in arr:
        arr_ml.append(item)
    return arr_ml


class TomlSettings(BaseGeneratorSettings):
    """Settings for the TOML file generator."""

    model_config = ConfigDict(title="Generator: TOML Configuration File Settings")

    paths: list[Path] = Field(
        default_factory=list,
        description="The paths to the resulting TOML files.",
        examples=[
            Path("config.toml"),
            Path("config.example.toml"),
            Path("settings.toml"),
        ],
    )

    show_header: bool = Field(
        True,
        description="Show a header comment with the settings class name and docstring.",
    )

    show_types: bool = Field(
        True,
        description="Show a type annotation comment for each field.",
    )

    show_description: bool = Field(
        True,
        description="Show a description comment for each field.",
    )

    show_default: bool = Field(
        True,
        description="Show a default-value comment for each field.",
    )

    show_examples: bool = Field(
        True,
        description="Show an examples comment for each field.",
    )

    comment_defaults: bool = Field(
        True,
        description="Comment out fields that have their default value (prefix with #).",
    )

    mode: TomlMode = Field(
        "all",
        description="The mode to export for the configuration variables.",
    )

    section_depth: int | None = Field(
        None,
        description=(
            "Maximum depth for using TOML sections for nested settings. "
            "If None, all nested settings use sections. "
            "If 0, all settings use dotted keys. "
            "If 1, only first-level child settings use sections. "
            "If 2, child settings and their children use sections, etc."
        ),
    )

    prefix: str | None = Field(
        None,
        description=(
            "Prefix for all TOML sections. "
            "All fields and sections will be nested under this prefix. "
            "The prefix does not count towards section_depth."
        ),
        examples=["tool.myapp", "app.config"],
    )


class TomlGenerator(AbstractGenerator[TomlSettings]):
    """The TOML configuration file generator."""

    name = "toml"
    config = TomlSettings

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if not TOMLKIT_AVAILABLE:  # pragma: no cover
            raise ImportError(
                "tomlkit is required for TOML generation. Install it with: pip install pydantic-settings-export[toml]"
            )

    # Utility methods (naming)

    def _make_toml_key(self, field: FieldInfoModel) -> str:
        """Get the TOML key name for a field."""
        if field.aliases:
            return field.aliases[0]
        return field.name

    def _should_include_field(self, field: FieldInfoModel) -> bool:
        """Determine if a field should be included based on the mode."""
        is_optional, is_required = TOML_MODE_MAP.get(self.generator_config.mode, TOML_MODE_MAP_DEFAULT)

        if field.is_required and not is_required:
            return False

        if not field.is_required and not is_optional:
            return False

        return True

    def _should_comment_field(self, field: FieldInfoModel) -> bool:
        """Determine if a field should be commented out.

        A field is commented out if:
        - It has a None default (always commented regardless of comment_defaults)
        - It is required (always commented to force user to provide a value)
        - comment_defaults is True and the field has a default value
        - BUT NOT if we have an actual value from an instance
        """
        if field.has_value:
            return False

        if field.is_required:
            return True

        if field.default is None:
            return True

        return self.generator_config.comment_defaults

    def _format_header_comment(self, name: str, docstring: str) -> str:
        """Format the header comment lines for a settings class or section.

        Override this method in a subclass to customise header formatting.

        :param name: The settings class or section name.
        :param docstring: The docstring associated with the class or section.
        :return: Multi-line string to emit as successive TOML comments.
        """
        lines = []
        if name:
            lines.append(name)
        if docstring:
            wrapped = textwrap.fill(docstring, width=80, break_long_words=False, break_on_hyphens=False)
            lines.append(wrapped)
        return "\n".join(lines)

    def _format_type_comment(self, key_name: str, types: list[Any], required: bool, deprecated: bool) -> str:
        """Format the type-annotation comment line for a field.

        Override this method in a subclass to customise type formatting.

        :param key_name: The display name (TOML key) for the field.
        :param types: The raw types list from :class:`~pydantic_settings_export.models.FieldInfoModel`.
        :param required: Whether the field is required.
        :param deprecated: Whether the field is deprecated.
        :return: Single comment line string.
        """
        type_str = " | ".join(format_types(types))
        required_marker = " (REQUIRED)" if required else ""
        deprecated_marker = " (DEPRECATED)" if deprecated else ""
        return f"{key_name}: {type_str}{required_marker}{deprecated_marker}"

    def _format_description_comment(self, description: str) -> str:
        """Format the description comment for a field.

        Override this method in a subclass to customise description formatting.

        :param description: The raw description string.
        :return: Formatted (possibly multi-line) string.
        """
        return textwrap.fill(description, width=80, break_long_words=False, break_on_hyphens=False)

    def _format_default_comment(self, default: Any) -> str:
        """Format the default-value comment line for a field.

        Override this method in a subclass to customise default formatting.

        :param default: The raw Python default value.
        :return: Single comment line string.
        """
        return f"Default: {value_repr(default)}"

    def _format_examples_comment(self, examples: list[Any]) -> str:
        """Format the examples comment line for a field.

        Override this method in a subclass to customise examples formatting.

        :param examples: The list of raw Python example values.
        :return: Single comment line string.
        """
        return f"Examples: {', '.join(value_repr(e) for e in examples)}"

    def _add_header_comments(self, container: Any, name: str, docstring: str) -> None:
        """Add header comments to a container."""
        if not self.generator_config.show_header:
            return

        formatted = self._format_header_comment(name, docstring)
        if formatted:
            for line in formatted.split("\n"):
                container.add(comment(line))
            container.add(nl())

    def _add_description_comments(self, container: Any, description: str) -> None:
        """Add description comments to a container."""
        if not self.generator_config.show_description or not description:
            return

        formatted = self._format_description_comment(description)
        if formatted:
            for line in formatted.split("\n"):
                container.add(comment(line))
            container.add(nl())

    def _format_field_comment(self, field: FieldInfoModel, key_name: str | None = None) -> list[str]:
        """Generate comment lines for a field."""
        lines: list[str] = []

        if self.generator_config.show_types:
            display_name = key_name if key_name else field.name
            type_line = self._format_type_comment(display_name, field.types, field.is_required, field.deprecated)
            lines.append(type_line)

        if self.generator_config.show_description and field.description:
            formatted_desc = self._format_description_comment(field.description)
            lines.extend(formatted_desc.split("\n"))

        if self.generator_config.show_default and not field.is_required:
            default_line = self._format_default_comment(field.default)
            lines.append(default_line)

        if self.generator_config.show_examples and field.has_examples():
            examples_line = self._format_examples_comment(field.examples)
            lines.append(examples_line)

        return lines

    def _write_value_to_container(self, container: Any, value: Any, full_key: str, prefix: str) -> None:
        """Write a value to the container, handling dotted-key prefix."""
        if prefix:
            key_parts = full_key.split(".")
            toml_key = key(key_parts)
            container.append(toml_key, value)
        else:
            container[full_key] = value

    def _add_default_hint_when_has_value(
        self,
        container: Any,
        field: FieldInfoModel,
        field_key: str,
        full_key: str,
        prefix: str,
        is_dict_entry: bool = False,
    ) -> None:
        """When an instance value is present, add the class default as a commented hint."""
        if not self.generator_config.show_default:
            return
        if field.is_required or field.default is None:
            if not is_dict_entry:
                container.add(comment(f"{full_key} ="))
        else:
            value = field.default
            value = _remove_none_values(value)
            if value is not None:
                value = _to_inline_tables(value)
                value = _format_list_value(value, field_key, full_key)
                value_str = tomlkit.dumps({field_key: value}).strip()
                if prefix:
                    value_str = value_str.replace(f"{field_key} =", f"{full_key} =", 1)
                for line in value_str.split("\n"):
                    container.add(comment(line))

    def _add_commented_default(
        self,
        container: Any,
        field: FieldInfoModel,
        field_key: str,
        full_key: str,
        prefix: str,
        section_path: str,
    ) -> None:
        """Add the field's default value as commented-out TOML."""
        value = field.default
        value = _remove_none_values(value)
        if value is None:
            return
        value = _to_inline_tables(value)
        value = _format_list_value(value, field_key, full_key)
        value_str = tomlkit.dumps({field_key: value}).strip()
        if prefix:
            value_str = value_str.replace(f"{field_key} =", f"{full_key} =", 1)
        if section_path and f"[[{field_key}]]" in value_str:
            full_path = f"{section_path}.{field_key}"
            value_str = value_str.replace(f"[[{field_key}]]", f"[[{full_path}]]")
        for line in value_str.split("\n"):
            container.add(comment(line))

    def _add_field_to_container(
        self,
        container: Any,
        field: FieldInfoModel,
        prefix: str = "",
        section_path: str = "",
        is_dict_entry: bool = False,
    ) -> None:
        """Add a field to a TOML document or section container."""
        field_key = self._make_toml_key(field)
        full_key = f"{prefix}{field_key}" if prefix else field_key

        comment_lines = self._format_field_comment(field, key_name=full_key if prefix else None)
        for line in comment_lines:
            container.add(comment(line))

        if field.has_value:
            value = field.value
            value = _remove_none_values(value)
            value = _to_inline_tables(value)
            value = _format_list_value(value, field_key, full_key)
            self._write_value_to_container(container, value, full_key, prefix)

        elif not self._should_comment_field(field):
            value = field.default
            value = _remove_none_values(value)
            value = _to_inline_tables(value)
            value = _format_list_value(value, field_key, full_key)
            self._write_value_to_container(container, value, full_key, prefix)

        elif field.is_required or field.default is None:
            if not is_dict_entry:
                container.add(comment(f"{full_key} ="))

        else:
            self._add_commented_default(container, field, field_key, full_key, prefix, section_path)

        container.add(nl())

    def _add_child_as_dotted_keys(self, container: Any, child: SettingsInfoModel, dotted_prefix: str) -> None:
        """Add a child settings using dotted key syntax."""
        if child.field_description:
            self._add_description_comments(container, child.field_description)

        self._add_header_comments(container, child.name, child.docs)

        for field in child.fields:
            if field.is_env_only:
                continue  # synthetic JSON fields are for env generators only
            if self._should_include_field(field):
                self._add_field_to_container(container, field, prefix=dotted_prefix, is_dict_entry=child.is_dict_entry)

    def _add_settings_to_container(
        self,
        container: Any,
        settings: SettingsInfoModel,
        current_depth: int = 0,
        section_path: str = "",
    ) -> None:
        """Add settings (fields + child settings) to a container (doc or section)."""
        for field in settings.fields:
            if field.is_env_only:
                continue  # synthetic JSON fields are for env generators only
            if self._should_include_field(field):
                self._add_field_to_container(
                    container, field, section_path=section_path, is_dict_entry=settings.is_dict_entry
                )

        for child in settings.child_settings:
            next_depth = current_depth + 1
            child_section_path = f"{section_path}.{child.field_name}" if section_path else child.field_name

            use_section = (
                self.generator_config.section_depth is None or next_depth <= self.generator_config.section_depth
            )

            if use_section:
                self._add_child_as_section(container, child, child.field_name, next_depth, child_section_path)
            else:
                dotted_prefix = f"{child.field_name}."
                self._add_child_as_dotted_keys(container, child, dotted_prefix)

    def _add_child_as_section(
        self,
        container: Any,
        child: SettingsInfoModel,
        section_name: str,
        current_depth: int = 1,
        section_path: str | None = None,
    ) -> None:
        """Add a child settings as a TOML section, including nested child settings recursively."""
        if child.field_description:
            self._add_description_comments(container, child.field_description)

        self._add_header_comments(container, child.name, child.docs)

        section = table()
        container[section_name] = section
        if not child.is_dict_entry:
            container.add(nl())

        self._add_settings_to_container(section, child, current_depth, section_path or section_name)

    def _create_prefix_section(self, doc: Any, prefix: str) -> Any:
        """Create nested sections for a dotted prefix (e.g., 'tool.myapp')."""
        parts = prefix.split(".")
        current_section = doc

        for part in parts:
            new_section = table()
            current_section[part] = new_section
            current_section = new_section

        doc.add(nl())
        return current_section

    def generate_single(self, settings_info: SettingsInfoModel, level: int = 1) -> str:
        """Generate TOML configuration for a pydantic settings class."""
        doc = document()

        self._add_header_comments(doc, settings_info.name or "", settings_info.docs)

        if self.generator_config.prefix:
            container = self._create_prefix_section(doc, self.generator_config.prefix)
            self._add_settings_to_container(
                container, settings_info, current_depth=0, section_path=self.generator_config.prefix
            )
        else:
            self._add_settings_to_container(doc, settings_info, current_depth=0)

        result = tomlkit.dumps(doc)

        result = re.sub(r"#\s+$", "#", result, flags=re.MULTILINE)
        return result
