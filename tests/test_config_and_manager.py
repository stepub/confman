from __future__ import annotations

from typing import Any, Mapping

import pytest

from confman import (
    Config,
    ConfigManager,
    DictSource,
    EnvSource,
    ConfigurationError,
)


def test_config_allows_dict_and_attribute_access():
    data = {
        "app": {
            "debug": True,
            "log_level": "INFO",
        },
        "database": {
            "host": "localhost",
            "port": 5432,
        },
    }

    cfg = Config(data)

    # dict-style
    assert cfg["app"]["debug"] is True
    assert cfg["database"]["port"] == 5432

    # attribute-style
    assert cfg.app.debug is True
    assert cfg.database.host == "localhost"

    # __contains__ / iteration
    assert "app" in cfg
    keys = set(iter(cfg))
    assert keys == {"app", "database"}


def test_config_to_dict_returns_deep_copy():
    data = {"a": {"b": 1}}
    cfg = Config(data)

    d = cfg.to_dict()
    assert d == {"a": {"b": 1}}

    # Mutate copy and ensure original config is not affected
    d["a"]["b"] = 2
    assert cfg.a.b == 1


def test_config_get_with_default():
    cfg = Config({"a": 1})

    assert cfg.get("a") == 1
    assert cfg.get("missing", "fallback") == "fallback"


def test_config_manager_merges_sources_in_order():
    defaults = {"app": {"debug": False, "log_level": "INFO"}}
    override = {"app": {"log_level": "DEBUG"}}

    manager = ConfigManager(
        sources=[
            DictSource(defaults),
            DictSource(override),
        ]
    )

    cfg = manager.load()

    assert cfg.app.debug is False
    # Later source overrides earlier one
    assert cfg.app.log_level == "DEBUG"


def test_config_manager_raises_on_non_mapping_source():
    class BadSource:
        def load(self) -> object:  # type: ignore[override]
            return 42  # not a mapping

    manager = ConfigManager(sources=[BadSource()])  # type: ignore[arg-type]

    with pytest.raises(ConfigurationError):
        manager.load()


def test_config_manager_with_schema_validation_success(monkeypatch):
    jsonschema = pytest.importorskip("jsonschema")

    # Simple schema: 'app' object with 'debug' bool is required
    schema: Mapping[str, Any] = {
        "type": "object",
        "properties": {
            "app": {
                "type": "object",
                "properties": {
                    "debug": {"type": "boolean"},
                },
                "required": ["debug"],
            }
        },
        "required": ["app"],
    }

    data = {"app": {"debug": True}}

    manager = ConfigManager(
        sources=[DictSource(data)],
        schema=schema,
    )

    cfg = manager.load()
    assert cfg.app.debug is True


def test_config_manager_with_schema_validation_failure():
    pytest.importorskip("jsonschema")

    schema: Mapping[str, Any] = {
        "type": "object",
        "properties": {
            "app": {
                "type": "object",
                "properties": {
                    "debug": {"type": "boolean"},
                },
                "required": ["debug"],
            }
        },
        "required": ["app"],
    }

    invalid_data = {"app": {"debug": "not-a-bool"}}

    manager = ConfigManager(
        sources=[DictSource(invalid_data)],
        schema=schema,
    )

    with pytest.raises(ConfigurationError) as excinfo:
        manager.load()

    msg = str(excinfo.value)
    assert "app.debug" in msg or "app" in msg  # path hint in error message is okay
    assert "boolean" in msg
