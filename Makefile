PYTHON ?= python
.PHONY: install lint format typecheck test check up down
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
