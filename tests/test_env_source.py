from __future__ import annotations

import os

from confman import EnvSource


def test_env_source_reads_prefixed_variables(monkeypatch):
    # Clean up environment in case tests share process
    for key in list(os.environ.keys()):
        if key.startswith("MYAPP_"):
            monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("MYAPP_DB__HOST", "localhost")
    monkeypatch.setenv("MYAPP_DB__PORT", "5432")
    monkeypatch.setenv("MYAPP_APP__DEBUG", "true")
    monkeypatch.setenv("OTHER_PREFIX_SHOULD_BE_IGNORED", "1")

    source = EnvSource("MYAPP_")
    data = source.load() or {}

    assert data["db"]["host"] == "localhost"
    # port should be parsed to int
    assert data["db"]["port"] == 5432
    # debug should be parsed to bool
    assert data["app"]["debug"] is True

    # ensure unrelated env vars are ignored
    assert "other_prefix_should_be_ignored".lower() not in str(data).lower()
