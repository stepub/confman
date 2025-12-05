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
- Optional support for raw files (templates, SSH configs, secrets, …) via `RawSource`.

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

### Persisting configuration back to files

`confman` keeps the `Config` object itself read-only. To write configuration changes back to disk, you work with a mutable copy and a `FileSource`:

```python
from confman import ConfigManager, DictSource, FileSource

default_config = {
    "app": {
        "debug": False,
        "log_level": "INFO",
    },
}

user_config = FileSource("config.yaml", optional=True)

manager = ConfigManager(
    sources=[
        DictSource(default_config),
        user_config,
    ],
)

# Load merged configuration (defaults + existing user config)
cfg = manager.load()

# Get a mutable deep copy
data = cfg.to_dict()

# Apply changes in your application / CLI
data["app"]["debug"] = True

# (Optional) validate again with your JSON Schema before writing

# Persist back to the same file
user_config.dump(data)
```

Notes on write-back behaviour:

* The output format is inferred from the file extension, just like for reading:

  * `.json` – JSON
  * `.toml` – TOML (requires `tomli-w`)
  * `.ini`, `.cfg`, `.conf` – INI via `configparser`
  * `.yaml`, `.yml` – YAML (requires `PyYAML`)
* Write operations are designed to be *atomic*:

  * Data is written to a temporary file first
  * The temporary file then replaces the target file

This keeps the configuration model simple:

* All sources participate in reading/merging
* You choose explicitly *which* file to write back to (usually a user-level config file), via the corresponding `FileSource`.

## Raw file support (RawSource)

`confman` also ships with a small helper for “opaque” files: `RawSource`.

Unlike the other sources (`DictSource`, `FileSource`, `EnvSource`), `RawSource` **does not participate in `ConfigManager` merging**. It is intended for files that should be treated as a single blob (for example templates, OpenSSH configs, TLS keys, or other secrets).

You can still use it alongside a `ConfigManager` instance, but you manage raw files explicitly instead of merging them into a configuration mapping.

### When to use `RawSource`

Use `RawSource` when:

- You want to manage a single file next to your structured configuration.
- The file format is not a simple key/value mapping (e.g. custom config formats, templates, generated files).
- You care about:
  - **atomic writes** (temp file + `os.replace()`),
  - **predictable file permissions** (e.g. `0o600` for secrets),
  - and a simple API (`load()` / `dump()`).

`RawSource` never appears in `ConfigManager.sources` and is never merged into a `Config` object.

### API overview

```python
from confman import RawSource

RawSource(
    path: str | pathlib.Path,
    *,
    binary: bool = False,
    encoding: str = "utf-8",
    errors: str = "strict",
    optional: bool = False,
    file_mode: int | None = None,
)
````

* **`path`**
  Path to the file. `~` is expanded via `Path(path).expanduser()`.

* **`binary`**

  * `False` (default): text mode, `load()` returns `str`, `dump()` expects `str`.
  * `True`: binary mode, `load()` returns `bytes`, `dump()` expects bytes-like data.

* **`encoding` / `errors`**
  Used in text mode only (`binary=False`), passed to `open(..., encoding=..., errors=...)`.

* **`optional`**

  * `True`: if the file does not exist, `load()` returns `None`.
  * `False` (default): missing file raises `ConfigurationError`.

* **`file_mode`**
  Optional POSIX file mode (e.g. `0o600`).
  If provided, `RawSource` calls `os.chmod()` on the temporary file and on the final file after an atomic `replace()`. Only permission bits (`0o777`) are applied; higher bits are masked out.

Methods:

* `load() -> str | bytes | None`
* `dump(data: str | bytes) -> None`

Both methods raise `ConfigurationError` on I/O errors; `dump()` additionally raises `TypeError` if the data type does not match the selected mode.

### Example: text file next to your config

```python
from confman import ConfigManager, FileSource, RawSource

manager = ConfigManager(
    sources=[
        FileSource("config.toml", optional=True),
    ]
)

config = manager.load()

# Manage an additional banner file as plain text
banner_source = RawSource("banner.txt", optional=True)

banner = banner_source.load()  # type: str | None
if banner is None:
    banner = "Welcome to my app!\n"
    banner_source.dump(banner)

print(banner)
```

### Example: secret key with strict permissions

```python
from pathlib import Path
from secrets import token_bytes

from confman import RawSource

secret_path = Path("secret.key")

secret_source = RawSource(
    secret_path,
    binary=True,
    optional=True,
    file_mode=0o600,  # owner read/write only
)

key = secret_source.load()  # bytes | None

if key is None:
    # Generate a new 32-byte key
    key = token_bytes(32)
    secret_source.dump(key)

# Use `key` (bytes) for encryption, signing, etc.
```

### Security considerations

* Prefer **binary mode** (`binary=True`) for keys, tokens and other secrets to avoid accidental encoding/decoding issues.
* Use a restrictive `file_mode` (for example `0o600`) for any sensitive file so that only the owner can read/write it.
* Writes are **atomic**:

  * data is written to a temporary file next to the target,
  * permissions are applied,
  * then `os.replace()` is used to move it into place.
* On load, `RawSource` will raise `ConfigurationError` if the file exists but cannot be read (I/O error, permission problems, …), so callers can handle this explicitly.
