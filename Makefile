PYTHON ?= python
.PHONY: install lint format typecheck test check up down simulate reproduce site-fixtures
install:
	$(PYTHON) -m pip install -e ".[dev]"
lint:
	ruff check src tests
format:
	ruff format src tests
typecheck:
	mypy src
test:
	pytest
check: lint typecheck test
up:
	docker compose up --build
down:
	docker compose down
simulate:
	uv run python -m syncmesh.simulation.run --seed $(or $(SEED),1) --schedules 1
reproduce:
	uv run python -m syncmesh.simulation.run --reproduce
site-fixtures:
	uv run python site/scripts/export_fixtures.py
