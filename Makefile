.PHONY: test test-cov lint typecheck check

test:
	pytest

test-cov:
	pytest --cov=confman --cov-report=term-missing

lint:
	ruff check confman tests

typecheck:
	mypy confman

check: lint typecheck test
