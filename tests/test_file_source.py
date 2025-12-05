from __future__ import annotations

import json
from pathlib import Path

import pytest

from confman import FileSource, ConfigurationError


def test_file_source_loads_json_file(tmp_path: Path):
    config_data = {
        "app": {
            "debug": False,
        },
        "database": {
            "host": "example.local",
            "port": 5432,
        },
    }

    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    source = FileSource(config_file)
    loaded = source.load()

    assert dict(loaded) == config_data


def test_file_source_missing_non_optional_raises(tmp_path: Path):
    missing_file = tmp_path / "does_not_exist.json"
    source = FileSource(missing_file, optional=False)

    with pytest.raises(ConfigurationError):
        _ = source.load()


def test_file_source_missing_optional_returns_empty_or_none(tmp_path: Path):
    """
    FileSource(optional=True) is allowed to either return None or an empty mapping.
    The ConfigManager implementation should handle both gracefully.
    """
    missing_file = tmp_path / "optional_missing.json"
    source = FileSource(missing_file, optional=True)

    loaded = source.load()
    # Accept both behaviors depending on your implementation
    assert loaded is None or loaded == {}


#def test_file_source_loads_yaml_if_pyyaml_installed(tmp_path: Path):
#    yaml = pytest.importorskip("yaml")
#
#    content = """
#    app:
#      debug: true
#    database:
#      host: "db.local"
#      port: 5432
#    """
#    config_file = tmp_path / "config.yaml"
#    config_file.write_text(content, encoding="utf-8")
#
#    source = FileSource(config_file)
#    loaded = source.load()
#
#    assert loaded["app"]["debug"] is True
#    assert loaded["database"]["host"] == "db.local"

def test_file_source_dump_json_roundtrip(tmp_path: Path) -> None:
    """dump() followed by load() should roundtrip JSON configuration data."""
    config_data = {
        "app": {
            "debug": True,
            "log_level": "DEBUG",
        },
        "database": {
            "host": "db.local",
            "port": 5433,
        },
    }

    config_file = tmp_path / "config.json"
    source = FileSource(config_file, optional=True)

    # Write configuration via FileSource
    source.dump(config_data)

    # Ensure file was created
    assert config_file.exists()

    # Read it back via FileSource
    loaded = FileSource(config_file).load()
    assert dict(loaded) == config_data


def test_file_source_dump_ini_roundtrip(tmp_path: Path) -> None:
    """dump() + load() should roundtrip INI configuration data."""
    config_data = {
        "app": {
            "debug": False,
            "workers": 4,
        },
        "database": {
            "host": "db.local",
            "port": 5432,
        },
    }

    config_file = tmp_path / "config.ini"
    source = FileSource(config_file, optional=True)

    # This will currently fail if _dump_ini does not create sections properly.
    source.dump(config_data)

    loaded = FileSource(config_file).load()

    # Values should be parsed back to the appropriate types (bool/int/str)
    assert loaded == {
        "app": {
            "debug": False,
            "workers": 4,
        },
        "database": {
            "host": "db.local",
            "port": 5432,
        },
    }


def test_file_source_dump_yaml_roundtrip_if_pyyaml_installed(tmp_path: Path) -> None:
    """YAML dump/load roundtrip if PyYAML is available."""
    yaml = pytest.importorskip("yaml")

    config_data = {
        "app": {
            "debug": True,
            "log_level": "INFO",
        },
        "database": {
            "host": "db.local",
            "port": 5432,
        },
    }

    # Also implicitly tests that parent directories are created
    config_file = tmp_path / "nested" / "config.yaml"
    source = FileSource(config_file, optional=True)

    source.dump(config_data)
    assert config_file.exists()

    loaded = FileSource(config_file).load()

    # Types should survive the roundtrip (bool/int/str)
    assert loaded == config_data


def test_file_source_dump_toml_roundtrip_if_supported(tmp_path: Path) -> None:
    """
    TOML dump/load roundtrip if TOML support is available.

    Requires:
      - confman.sources.tomllib to be non-None (for reading)
      - tomli-w to be installable (for writing)
    """
    # Skip completely if FileSource has no TOML read support configured
    try:
        import confman.sources as sources  # type: ignore[import]
    except Exception:  # pragma: no cover - extremely unlikely
        pytest.skip("Cannot import confman.sources to check TOML support")

    if getattr(sources, "tomllib", None) is None:
        pytest.skip("TOML read support not available in confman")

    pytest.importorskip("tomli_w")

    config_data = {
        "app": {
            "debug": True,
            "log_level": "DEBUG",
        },
        "database": {
            "host": "db.toml.local",
            "port": 6000,
        },
    }

    config_file = tmp_path / "config.toml"
    source = FileSource(config_file, optional=True)

    source.dump(config_data)
    assert config_file.exists()

    loaded = FileSource(config_file).load()

    # TOML parser should give us the same primitive types back
    assert loaded == config_data

def test_file_source_dump_ini_rejects_nested_structures(tmp_path: Path) -> None:
    """INI dump must fail for nested/non-scalar values (lists, dicts, ...)."""
    config_data = {
        "app": {
            "debug": False,
            "log_level": "INFO",
            "prints": [
                "lila",
                "red",
                "green",
            ],
            "backups": {
                "monday": ["8:00", "9:00"],
            },
        },
    }

    config_file = tmp_path / "config.ini"
    source = FileSource(config_file, optional=True)

    with pytest.raises(ConfigurationError):
        source.dump(config_data)
