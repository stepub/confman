from __future__ import annotations

from confman.utils import deep_merge


def test_deep_merge_simple():
    base = {"a": 1, "b": 2}
    override = {"b": 3, "c": 4}

    result = deep_merge(base, override)

    assert result == {"a": 1, "b": 3, "c": 4}
    # Ensure original dicts are not mutated
    assert base == {"a": 1, "b": 2}
    assert override == {"b": 3, "c": 4}


def test_deep_merge_nested():
    base = {
        "a": {"x": 1, "y": 2},
        "b": 1,
    }
    override = {
        "a": {"y": 42, "z": 99},
        "c": 3,
    }

    result = deep_merge(base, override)

    assert result == {
        "a": {"x": 1, "y": 42, "z": 99},
        "b": 1,
        "c": 3,
    }
