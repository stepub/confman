from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Dict, Iterator

from .exceptions import ConfigurationError
from .sources import ConfigSource
from .utils import deep_merge
from .validation import validate_config


class Config(Mapping[str, Any]):
    """
    Read-only configuration object.

    Provides both mapping access (cfg["section"]["key"]) and
    attribute-style access (cfg.section.key).
    """

    def __init__(self, data: Mapping[str, Any]):
        self._data: Dict[str, Any] = dict(data)

    def __getitem__(self, key: str) -> Any:
        return _wrap_nested(self._data[key])

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __getattr__(self, name: str) -> Any:
        try:
            value = self._data[name]
        except KeyError as exc:
            raise AttributeError(name) from exc
        return _wrap_nested(value)

    def to_dict(self) -> Dict[str, Any]:
        """Return a deep copy of the underlying data."""
        from copy import deepcopy

        return deepcopy(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        """Return value for key if present, else default."""
        if key in self._data:
            return _wrap_nested(self._data[key])
        return default

    def __repr__(self) -> str:
        # Avoid dumping potentially huge or sensitive configs verbosely
        keys_preview = ", ".join(list(self._data.keys())[:5])
        more = "..." if len(self._data) > 5 else ""
        return f"<Config keys=[{keys_preview}{more}]>"


def _wrap_nested(value: Any) -> Any:
    """
    Wrap nested mappings in Config so attribute access works recursively.
    """
    if isinstance(value, Mapping) and not isinstance(value, Config):
        return Config(value)
    return value


class ConfigManager:
    """
    Central orchestrator for loading, merging and validating configuration.

    Typical usage:

        from confman import ConfigManager, DictSource, FileSource, EnvSource

        manager = ConfigManager(
            sources=[
                DictSource(defaults),
                FileSource("/etc/myapp/config.yaml", optional=True),
                FileSource("config.local.yaml", optional=True),
                EnvSource("MYAPP_"),
            ],
            schema=my_json_schema,
        )

        cfg = manager.load()
        db_host = cfg.database.host
    """

    def __init__(
        self,
        sources: Iterable[ConfigSource],
        *,
        schema: Mapping[str, Any] | None = None,
    ):
        self._sources = list(sources)
        if not self._sources:
            raise ValueError("At least one configuration source must be provided.")
        self._schema = schema

    def load(self) -> Config:
        """
        Load, merge and validate configuration from all configured sources.

        The sources are applied in the given order; later sources override earlier ones.
        """
        merged: Dict[str, Any] = {}

        for source in self._sources:
            data = source.load()
            if data is None:
                continue
            if not isinstance(data, Mapping):
                raise ConfigurationError(
                    f"Configuration source {source!r} returned a non-mapping value."
                )
            merged = deep_merge(merged, data)

        # Validate, if a schema is provided
        validate_config(merged, self._schema)

        return Config(merged)
