# confman

A small, focused configuration management library for Python applications.

`confman` lets you:

- Combine multiple configuration sources (defaults, files, environment variables)
- Deep-merge nested configuration structures
- Optionally validate configuration with JSON Schema
- Access configuration via both dict-style and attribute-style APIs

It is designed to be lightweight, dependency-aware, and easy to embed into CLI tools and services.

## Features

- **Multiple sources**:
  - In-memory defaults (`DictSource`)
  - Files (`FileSource`) – JSON, INI, TOML, YAML
  - Environment variables (`EnvSource`) with nested keys
- **Deterministic precedence**:
  - Sources are applied in order; later sources override earlier ones
- **Deep merge**:
  - Nested mappings are merged recursively; non-mapping values are replaced
- **Optional JSON Schema validation**:
  - Uses `jsonschema` if available
- **Read-only configuration object**:
  - Dict access: `cfg["app"]["debug"]`
  - Attribute access: `cfg.app.debug`
- **Typed, tested, and tool-friendly**:
  - `pytest`, `mypy`, `ruff` integration for development

---

## Installation

### Requirements

- Python 3.10 or newer
- `pip` for installation

### Install

```bash
pip install .
````

---

## Basic usage

### Defining defaults and loading configuration

```python
from confman import ConfigManager, DictSource, FileSource, EnvSource

default_config = {
    "app": {
        "debug": False,
        "log_level": "INFO",
    },
    "database": {
        "host": "localhost",
        "port": 5432,
    },
}

manager = ConfigManager(
    sources=[
        DictSource(default_config),
        FileSource("/etc/myapp/config.yaml", optional=True),
        FileSource("config.local.toml", optional=True),
        EnvSource("MYAPP_"),
    ],
)

cfg = manager.load()

print(cfg.app.debug)          # attribute-style access
print(cfg["database"]["host"])  # dict-style access
print(cfg.get("timeout", 30)) # safe access with default
```

Files are merged in the order given and then overridden by environment variables.

---

## Advanced usage

### Combining multiple sources with clear precedence

`ConfigManager` applies sources in the given order.
Later sources override earlier ones on a deep-merge basis.

A common pattern is:

1. Built-in defaults (`DictSource`)
2. System-wide config file (optional)
3. User-specific config file (optional)
4. Environment variables (`EnvSource`)

```python
from confman import ConfigManager, DictSource, FileSource, EnvSource

default_config = {
    "app": {
        "debug": False,
        "log_level": "INFO",
    },
    "database": {
        "host": "localhost",
        "port": 5432,
    },
}

manager = ConfigManager(
    sources=[
        DictSource(default_config),
        FileSource("/etc/myapp/config.toml", optional=True),
        FileSource("config.local.yaml", optional=True),
        EnvSource("MYAPP_"),
    ],
)

cfg = manager.load()

# Environment variables like MYAPP_APP__DEBUG=true will override defaults:
print(cfg.app.debug)
print(cfg.database.host)
```

Deep merging means nested mappings are merged recursively; non-mapping values are replaced by later sources.

### Environment variables with nested keys

`EnvSource` lets you map environment variables into nested configuration keys using
a prefix and a `__` (double underscore) separator.

For example:

```bash
export MYAPP_APP__DEBUG=true
export MYAPP_APP__LOG_LEVEL=DEBUG
export MYAPP_DB__HOST=db.internal
export MYAPP_DB__PORT=5433
```

and:

```python
from confman import EnvSource, ConfigManager

manager = ConfigManager(
    sources=[
        EnvSource("MYAPP_"),
    ],
)

cfg = manager.load()

assert cfg.app.debug is True
assert cfg.app.log_level == "DEBUG"
assert cfg.db.host == "db.internal"
assert cfg.db.port == 5433
```

Parsing rules are:

* `"true"`, `"yes"`, `"on"` → `True`
* `"false"`, `"no"`, `"off"` → `False`
* integer-like strings → `int`
* float-like strings → `float`
* everything else stays a `str`

### Using JSON Schema validation

If `jsonschema` is installed, you can provide a JSON Schema to validate your
configuration after all sources have been merged:

```python
from typing import Any, Mapping
from confman import ConfigManager, DictSource, ConfigurationError

schema: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "app": {
            "type": "object",
            "properties": {
                "debug": {"type": "boolean"},
                "log_level": {"type": "string"},
            },
            "required": ["debug", "log_level"],
            "additionalProperties": False,
        },
        "database": {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
            "required": ["host", "port"],
        },
    },
    "required": ["app", "database"],
}

default_config = {
    "app": {"debug": True, "log_level": "INFO"},
}

manager = ConfigManager(
    sources=[DictSource(default_config)],
    schema=schema,
)

try:
    cfg = manager.load()
except ConfigurationError as exc:
    print(f"Invalid configuration: {exc}")
else:
    print("Configuration is valid!")
```

If validation fails, `ConfigurationError` contains a helpful message including:

* the path where the error occurred (e.g. `app.log_level`), and
* the underlying validation message (e.g. `is not of type 'boolean'`).

If `jsonschema` is **not** installed but a schema is provided, `ConfigManager.load()`
will raise `ConfigurationError` explaining that JSON Schema validation is not available.

### Attribute vs. dict-style access

The `Config` object is a read-only mapping with both dict and attribute-style access:

```python
cfg["app"]["debug"]
cfg.app.debug
cfg.get("timeout", 30)
```

Because `Config` is also a Python object, some keys may conflict with methods or
attributes (`get`, `to_dict`, etc.). In such cases:

* prefer `cfg["key"]` for your configuration data
* reserve attribute access for keys that do not clash with method names

To get a deep copy of the underlying data:

```python
data = cfg.to_dict()
```

This is safe to mutate without affecting the original configuration object.
