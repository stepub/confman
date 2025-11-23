from __future__ import annotations


class ConfigurationError(Exception):
    """Raised when there is a problem loading or validating configuration."""

class ConfigSourceError(ConfigurationError):
    """..."""

class ValidationError(ConfigurationError):
    """Raised when there is a problem validating configuration."""
