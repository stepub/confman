## Development setup

### Prerequisites

* Python 3.10 or newer
* `pip`
* (Recommended) A virtual environment, e.g.:

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows PowerShell
```

### Install in editable mode (with dev tools)

Install the package together with all development dependencies (tests, linting, type checking):

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

This will install:

* `pytest` and `pytest-cov` for tests and coverage
* `mypy` for static type checking
* `ruff` for linting / style checks
* Optional runtime dependencies like `jsonschema`, `PyYAML`, `tomli` (depending on Python version)

### Running tests

You can run the test suite directly with `pytest`:

```bash
pytest
```

If `pyproject.toml` configures `pytest` with coverage options (via `tool.pytest.ini_options`), this will also measure test coverage for the `confman` package and show missing lines.

Alternatively, you can call pytest explicitly with coverage options:

```bash
pytest --cov=confman --cov-report=term-missing
```

mypy and ruff
```bash
mypy
# or
python -m mypy
ruff check confman tests
```

freez the installation
```bash
(python -m) pip freeze > requirements.lock.txt
```

### Makefile commands

With the `Makefile` you can simply use:

* `make test`
  
  Run the test suite.

* `make test-cov`
  
  Run tests with coverage report for the `confman` package.

* `make lint`

  Run `ruff` against `confman` and `tests` to catch style and simple logic issues.

* `make typecheck`

  Run `mypy` static type checking on the `confman` package.

* `make check`

  Run linting, type checking, and tests in one go.

---

## Roadmap / Future ideas

`confman` is intentionally small and focused. The current feature set is enough
for many CLI tools and services. Still, there are several directions it could evolve in:

### Profiles / environments

Support for named profiles/environments, for example:

* `dev`, `test`, `prod`, `staging`
* configuration sections or separate files per profile
* profile selection via environment variable (e.g. `MYAPP_ENV=prod`) or explicit
  parameter on `ConfigManager`

Example ideas:

* `config.dev.yaml`, `config.prod.yaml`
* a `profile` key in the configuration to conditionally select subtrees

### Better debugging / tracing tools

Make it easier to understand **where** a value came from:

* an optional `debug_dump()` or `explain(key)` API:

  * shows which source(s) contributed a value
  * shows the merge order and overrides
* optional integration with logging so that misconfigurations can be reported
  without users needing to catch and print exceptions manually

### Additional built-in sources

New `ConfigSource` implementations for common backends, for example:

* `EnvFileSource` – `.env` files (dotenv-style)
* `SecretsSource` – pluggable interface for secret stores (HashiCorp Vault, AWS SSM, etc.)
* `HTTPSource` – load configuration from a remote endpoint (with caching)

All of these can already be implemented out-of-tree today by subclassing
`ConfigSource`, but having some batteries included may be convenient.

### CLI helper

A small, optional `confman` CLI could provide commands like:

* `confman validate path/to/config.yaml --schema schema.json`
* `confman show --source /etc/myapp/config.toml --source config.local.yaml`
* `confman explain app.debug`

This would make it easier to inspect configuration without writing a custom script.

### Schema helpers / documentation generation

Tools to generate documentation or example configuration files from a JSON Schema:

* generate a commented example `config.example.yaml` from a schema
* generate Markdown tables describing expected keys, types, and defaults

This would help keep configuration and its documentation in sync.

### Hot reload / watching

For long-running services, optional support for:

* reloading configuration on demand, e.g. after receiving a signal
* watching files for changes and reloading configuration safely

This would remain strictly opt-in to avoid surprising behavior in simple CLI tools.
