from __future__ import annotations

from pathlib import Path
import stat

import pytest

from confman import RawSource, ConfigurationError


def test_raw_source_text_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "raw.txt"
    src = RawSource(path, optional=True)

    src.dump("hello\nworld")
    assert path.read_text(encoding="utf-8") == "hello\nworld"

    loaded = src.load()
    assert loaded == "hello\nworld"


def test_raw_source_binary_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "raw.bin"
    src = RawSource(path, binary=True, optional=True)

    payload = b"\x00\x01secret-bytes"
    src.dump(payload)
    assert path.read_bytes() == payload

    loaded = src.load()
    assert loaded == payload


def test_raw_source_optional_missing_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "missing.txt"
    src = RawSource(path, optional=True)

    assert src.load() is None


def test_raw_source_missing_non_optional_raises(tmp_path: Path) -> None:
    path = tmp_path / "missing.txt"
    src = RawSource(path, optional=False)

    with pytest.raises(ConfigurationError):
        src.load()


def test_raw_source_applies_file_mode(tmp_path: Path) -> None:
    path = tmp_path / "secret.txt"
    src = RawSource(path, optional=True, file_mode=0o600)

    src.dump("top secret")
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600
