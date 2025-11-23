from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Dict

import configparser
import json
import os

from .exceptions import ConfigurationError
from .utils import deep_merge

# Optional TOML support:
# - Python >= 3.11: stdlib `tomllib`
# - Older: `tomli` fallback
# - `toml` needed ?
tomllib: Any | None
try:
    import tomllib as _tomllib
    tomllib = _tomllib
except ImportError:  # pragma: no cover
    try:
        import tomli as _tomli
        tomllib = _tomli
    except ImportError:  # pragma: no cover
        tomllib = None

# Optional YAML support (PyYAML)
yaml: Any | None
try:
    import yaml as _yaml  # type: ignore[import]
    yaml = _yaml
except ImportError:  # pragma: no cover
    yaml = None


class ConfigSource(ABC):
    """Abstract base class for configuration sources."""

    @abstractmethod
    def load(self) -> Mapping[str, Any] | None:
        """Return a mapping with configuration values or None if nothing was loaded."""
        raise NotImplementedError


class DictSource(ConfigSource):
    """Configuration source backed by an in-memory dictionary."""

    def __init__(self, data: Mapping[str, Any]):
        self._data = dict(data)

    def load(self) -> Mapping[str, Any] | None:
        return dict(self._data)


class FileSource(ConfigSource):
    """
    Load configuration from a single file.

    Supported formats (by extension):
      - .json
      - .toml  (requires Python 3.11+ or tomli)
      - .ini, .cfg, .conf (ConfigParser)
      - .yaml, .yml (requires PyYAML)

    Values are returned as a nested mapping.
    """

    def __init__(self, path: str | Path, *, optional: bool = False):
        self._path = Path(path).expanduser()
        self._optional = optional

    def load(self) -> Mapping[str, Any] | None:
        if not self._path.exists():
            if self._optional:
                return None
            raise ConfigurationError(f"Configuration file not found: {self._path}")

        suffix = self._path.suffix.lower()

        if suffix == ".json":
            return self._load_json()
        if suffix == ".toml":
            return self._load_toml()
        if suffix in {".ini", ".cfg", ".conf"}:
            return self._load_ini()
        if suffix in {".yaml", ".yml"}:
            return self._load_yaml()

        raise ConfigurationError(
            f"Unsupported configuration file format: {self._path} "
            f"(extension '{suffix}')"
        )

    def _load_json(self) -> Mapping[str, Any]:
        try:
            with self._path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            raise ConfigurationError(f"Invalid JSON in {self._path}: {exc}") from exc

    def _load_toml(self) -> Mapping[str, Any]:
        if tomllib is None:
            raise ConfigurationError(
                "TOML configuration requested but neither 'tomllib' (Python 3.11+) "
                "nor 'tomli' is available. Install 'tomli' to enable TOML support."
            )
        try:
            with self._path.open("rb") as f:
                return tomllib.load(f)
        except Exception as exc:
            raise ConfigurationError(f"Invalid TOML in {self._path}: {exc}") from exc

    def _load_ini(self) -> Mapping[str, Any]:
        # Disable interpolation for predictable behavior
        parser = configparser.ConfigParser(interpolation=None)
        try:
            with self._path.open("r", encoding="utf-8") as f:
                parser.read_file(f)
        except Exception as exc:
            raise ConfigurationError(
                f"Error reading INI file {self._path}: {exc}"
            ) from exc

        data: Dict[str, Dict[str, Any]] = {}
        for section in parser.sections():
            section_dict: Dict[str, Any] = {}
            for key, value in parser.items(section):
                section_dict[key] = _parse_env_like_value(value)
            data[section] = section_dict
        return data

    def _load_yaml(self) -> Mapping[str, Any]:
        if yaml is None:
            raise ConfigurationError(
                "YAML configuration requested but 'PyYAML' is not installed."
            )
        try:
            with self._path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as exc:
            raise ConfigurationError(f"Invalid YAML in {self._path}: {exc}") from exc

        if data is None:
            return {}
        if not isinstance(data, Mapping):
            raise ConfigurationError(
                f"Top-level YAML structure in {self._path} must be a mapping."
            )
        return data


class EnvSource(ConfigSource):
    """
    Load configuration from environment variables.

    Keys are derived from variable names with a fixed prefix. For example:

      prefix = "MYAPP_"
      MYAPP_DB__HOST=localhost
      MYAPP_DB__PORT=5432

    will be translated to:

      {
        "db": {
          "host": "localhost",
          "port": 5432
        }
      }

    The separator for nested keys is a double underscore "__".
    """

    def __init__(self, prefix: str):
        if not prefix:
            raise ValueError("Environment prefix must not be empty.")
        self._prefix = prefix

    def load(self) -> Mapping[str, Any] | None:
        result: Dict[str, Any] = {}
        prefix_len = len(self._prefix)

        for key, value in os.environ.items():
            if not key.startswith(self._prefix):
                continue

            raw_key = key[prefix_len:]
            if not raw_key:
                continue

            parts = [p.lower() for p in raw_key.split("__") if p]
            if not parts:
                continue

            # Build a nested dict structure based on "__"-separated path
            nested: Dict[str, Any] = {}
            current: Dict[str, Any] = nested
            for part in parts[:-1]:
                child = current.get(part)
                if not isinstance(child, dict):
                    child = {}
                    current[part] = child
                current = child

            current[parts[-1]] = _parse_env_like_value(value)
            result = deep_merge(result, nested)

        return result or None


def _parse_env_like_value(raw: str) -> Any:
    """
    Best-effort parsing for environment-like string values.

    Converts:
      - "true"/"false" (case-insensitive) to bool
      - integer strings to int
      - float strings to float
    Leaves everything else as str.
    """
    lowered = raw.strip().lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False

    # Try int
    try:
        return int(raw)
    except ValueError:
        pass

    # Try float
    try:
        return float(raw)
    except ValueError:
        pass

    return raw
