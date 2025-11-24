from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two mappings.

    Values from `override` take precedence.
    Nested mappings are merged, all other values are replaced.
    """
    result: Dict[str, Any] = dict(base)
    #TODO: recursion protect
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], Mapping)
            and isinstance(value, Mapping)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
