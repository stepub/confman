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
