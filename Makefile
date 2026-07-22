.PHONY: sync lint format typecheck test cov build smoke check

sync:
	uv sync --locked --all-groups

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

typecheck:
	uv run mypy src

test:
	uv run pytest

cov:
	uv run pytest --cov=smart_parking --cov-report=term-missing --cov-fail-under=85

build:
	uv build

smoke:
	uv run smart-parking --help

check: format-check lint typecheck cov smoke
