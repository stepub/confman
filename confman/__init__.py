from __future__ import annotations

"""
confman - Small, extensible configuration management library.

This package provides:
- ConfigManager: orchestrates loading, merging and validating configuration.
- Config: read-only configuration object with attribute-style access.
- Built-in sources: dict, file, environment variables.
"""

from .exceptions import ConfigurationError
from .manager import ConfigManager, Config
from .sources import DictSource, FileSource, EnvSource

__all__ = [
    "ConfigurationError",
    "ConfigManager",
    "Config",
    "DictSource",
    "FileSource",
    "EnvSource",
]
