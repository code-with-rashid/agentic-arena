.PHONY: install lint fmt test smoke clean

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff check --fix .
	ruff format .

test:
	pytest -q

# Mock smoke: prove the dependency-free path wires together.
smoke:
	python -m arena run --arena tool_use --framework vanilla --mode mock

# Mock smoke including the real frameworks (install their requirements first).
smoke-all:
	python -m arena run --arena tool_use --framework all --mode mock

clean:
	rm -rf runs .pytest_cache .ruff_cache **/__pycache__
