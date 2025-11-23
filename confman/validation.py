from __future__ import annotations

from typing import Any, Mapping

from .exceptions import ConfigurationError


def validate_config(data: Mapping[str, Any], schema: Mapping[str, Any] | None) -> None:
    """
    Validate configuration data against a JSON Schema.

    :param data: Configuration mapping to validate.
    :param schema: JSON Schema mapping. If None, validation is skipped.
    :raises ConfigurationError: if validation fails or jsonschema is missing.
    """
    if schema is None:
        return

    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ConfigurationError(
            "JSON Schema validation requested but 'jsonschema' package is not installed."
        ) from exc

    try:
        jsonschema.validate(instance=data, schema=schema)
    except Exception as exc:
        # Try to provide a helpful error message if jsonschema exposes path/message
        path = getattr(exc, "path", ())
        path_str = ".".join(str(p) for p in path) if path else "<root>"
        message = getattr(exc, "message", str(exc))
        raise ConfigurationError(
            f"Configuration validation error at '{path_str}': {message}"
        ) from exc
