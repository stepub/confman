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
    import yaml as _yaml
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

    def dump(self, data: Mapping[str, Any]) -> None:
        """
        Persist configuration data to this file.

        The format is chosen based on the file extension, using the same
        rules as for `load()`. The write is performed atomically by writing
        to a temporary file and then replacing the target file.
        """
        from pathlib import Path

        # Ensure parent directory exists
        self._path.parent.mkdir(parents=True, exist_ok=True)

        suffix = self._path.suffix.lower()
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")

        if suffix == ".json":
            self._dump_json(tmp_path, data)
        elif suffix == ".toml":
            self._dump_toml(tmp_path, data)
        elif suffix in {".ini", ".cfg", ".conf"}:
            self._dump_ini(tmp_path, data)
        elif suffix in {".yaml", ".yml"}:
            self._dump_yaml(tmp_path, data)
        else:
            raise ConfigurationError(
                f"Unsupported configuration file format for writing: {self._path} "
                f"(extension '{suffix}')"
            )

        # Atomic replace (os.replace), overwrites existing file
        try:
            tmp_path.replace(self._path)
        except OSError as exc:
            raise ConfigurationError(
                f"Could not move temporary config file {tmp_path!r} to {self._path!r}: {exc}"
            ) from exc

    def _load_json(self) -> Mapping[str, Any]:
        try:
            with self._path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Invalid JSON in {self._path}: {exc}") from exc

    def _dump_json(self, path: Path, data: Mapping[str, Any]) -> None:
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
                f.write("\n")
        except OSError as exc:
            raise ConfigurationError(f"Could not write JSON config {path!r}: {exc}") from exc

    def _load_toml(self) -> Mapping[str, Any]:
        if tomllib is None:
            raise ConfigurationError(
                "TOML configuration requested but neither 'tomllib' (Python 3.11+) "
                "nor 'tomli' is available. Install 'tomli' to enable TOML support."
            )
        try:
            with self._path.open("rb") as f:
                return tomllib.load(f)
        #TODO: tomllib.TOMLDecodeError
        except Exception as exc:
            raise ConfigurationError(f"Invalid TOML in {self._path}: {exc}") from exc

    def _dump_toml(self, path: Path, data: Mapping[str, Any]) -> None:
        try:
            import tomli_w  # optional dependency
        except ImportError as exc:
            raise ConfigurationError(
                "Writing TOML configuration requires the optional 'tomli-w' package."
            ) from exc

        try:
            toml_text = tomli_w.dumps(data)
            # tomli_w.dumps may return bytes or str depending on version
            if not isinstance(toml_text, str):
                toml_text = toml_text.decode("utf-8")

            with path.open("w", encoding="utf-8") as f:
                f.write(toml_text)
        except Exception as exc:
            raise ConfigurationError(f"Could not write TOML config {path!r}: {exc}") from exc

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

    def _dump_ini(self, path: Path, data: Mapping[str, Any]) -> None:
        parser = configparser.ConfigParser(interpolation=None)

        def _ensure_scalar(value: Any, path_str: str) -> str:
            if isinstance(value, (str, int, float, bool)):
                return str(value)

            raise ConfigurationError(
                "Cannot dump non-scalar value at "
                f"{path_str!r} to INI; INI is limited to flat key/value "
                "pairs. Use JSON, TOML or YAML for nested structures."
            )

        for section_name, section_value in data.items():
            if not isinstance(section_value, Mapping):
                raise ConfigurationError(
                    "INI root must be a mapping of section names to mappings. "
                    f"Found non-mapping value at top-level key {section_name!r}."
                )

            section_name_str = str(section_name)
            if not parser.has_section(section_name_str):
                parser.add_section(section_name_str)

            section = parser[section_name_str]

            for option, option_value in section_value.items():
                key_path = f"{section_name_str}.{option}"
                section[str(option)] = _ensure_scalar(option_value, key_path)

        try:
            with path.open("w", encoding="utf-8") as f:
                parser.write(f)
        except OSError as exc:
            raise ConfigurationError(
                f"Could not write INI config {path!r}: {exc}"
            ) from exc

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

    def _dump_yaml(self, path: Path, data: Mapping[str, Any]) -> None:
        if yaml is None:
            raise ConfigurationError(
                "Writing YAML configuration requires the optional 'PyYAML' package."
            )

        try:
            with path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(
                    dict(data),
                    f,
                    sort_keys=False,
                    default_flow_style=False,
                )
        except OSError as exc:
            raise ConfigurationError(f"Could not write YAML config {path!r}: {exc}") from exc


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


def _apply_file_mode(path: Path, mode: int | None) -> None:
    """
    Apply a restrictive file mode to the given path, if requested.

    Only permission bits (0o777) are used. Any higher bits are masked out.
    """
    if mode is None:
        return

    safe_mode = mode & 0o777
    try:
        os.chmod(path, safe_mode)
    except OSError as exc:
        raise ConfigurationError(
            f"Could not set permissions on {path!r}: {exc}"
        ) from exc


class RawSource:
    """
    Read and write raw configuration data from a single file.

    Unlike DictSource, FileSource and EnvSource, RawSource does NOT participate
    in ConfigManager merging. It is intended for use cases where the content is
    treated as an opaque blob (for example templates, SSH configs, or secrets).

    You can operate in either text mode (str) or binary mode (bytes):

    - binary=False (default): load() / dump() work with str and an encoding
    - binary=True: load() / dump() work with bytes

    Optionally, you can enforce a specific file_mode (e.g. 0o600 for secrets).
    """

    def __init__(
        self,
        path: str | Path,
        *,
        binary: bool = False,
        encoding: str = "utf-8",
        errors: str = "strict",
        optional: bool = False,
        file_mode: int | None = None,
    ) -> None:
        """
        :param path: Path to the file.
        :param binary: If True, read/write bytes. If False, read/write text.
        :param encoding: Encoding used in text mode.
        :param errors: Error handling strategy in text mode ('strict' by default).
        :param optional: If True, missing file on load() returns None instead of raising.
        :param file_mode: Optional POSIX file mode (e.g. 0o600). If provided,
                          chmod() is called on the temp file and final file.
        """
        self._path = Path(path).expanduser()
        self._binary = bool(binary)
        self._encoding = encoding
        self._errors = errors
        self._optional = optional
        self._file_mode = file_mode

    @property
    def path(self) -> Path:
        """Return the resolved file path."""
        return self._path

    def load(self) -> str | bytes | None:
        """
        Load raw content from the file.

        :returns: str or bytes depending on mode, or None if optional and missing.
        :raises ConfigurationError: on I/O errors or missing non-optional files.
        """
        if not self._path.exists():
            if self._optional:
                return None
            raise ConfigurationError(f"Raw configuration file not found: {self._path}")

        if self._binary:
            try:
                with self._path.open("rb") as f:
                    return f.read()
            except OSError as exc:
                raise ConfigurationError(
                    f"Could not read raw binary file {self._path!r}: {exc}"
                ) from exc

        # text mode
        try:
            with self._path.open(
                "r", encoding=self._encoding, errors=self._errors
            ) as f:
                return f.read()
        except OSError as exc:
            raise ConfigurationError(
                f"Could not read raw text file {self._path!r}: {exc}"
            ) from exc

    def dump(self, data: str | bytes) -> None:
        """
        Write raw content to the file atomically.

        - Writes to a temporary file next to the target.
        - Optionally applies a restrictive file_mode (e.g. 0o600).
        - Uses os.replace() to atomically move the temp file into place.

        :param data: str (for binary=False) or bytes (for binary=True).
        :raises TypeError: if data type does not match the selected mode.
        :raises ConfigurationError: on I/O errors or chmod failures.
        """
        if self._binary:
            if not isinstance(data, (bytes, bytearray, memoryview)):
                raise TypeError(
                    "RawSource(binary=True).dump() expects bytes-like data."
                )
            payload: bytes
            if isinstance(data, bytes):
                payload = data
            else:
                payload = bytes(data)
        else:
            if not isinstance(data, str):
                raise TypeError(
                    "RawSource(binary=False).dump() expects 'str' data."
                )
            payload = data

        # Ensure parent directory exists
        self._path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")

        try:
            if self._binary:
                with tmp_path.open("wb") as f:
                    f.write(payload)
            else:
                with tmp_path.open(
                    "w", encoding=self._encoding, errors=self._errors
                ) as f:
                    f.write(payload)

            # Apply requested file mode to the temp file and final file
            _apply_file_mode(tmp_path, self._file_mode)

            tmp_path.replace(self._path)

            # Re-apply mode on the final file in case the filesystem adjusts it
            _apply_file_mode(self._path, self._file_mode)

        except OSError as exc:
            raise ConfigurationError(
                f"Could not write raw configuration file {self._path!r}: {exc}"
            ) from exc