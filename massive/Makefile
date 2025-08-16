

.PHONY: help venv install lint test clean

# Default target
help:
	@echo "Common Make targets:"
	@echo "  make venv     - Create virtual environment"
	@echo "  make install  - Install project dependencies"
	@echo "  make lint     - Run linters (flake8 + mypy)"
	@echo "  make test     - Run pytest"
	@echo "  make clean    - Remove caches and build artifacts"

venv:
	python3 -m venv .venv

install: venv
	. .venv/bin/activate && pip install -U pip && pip install -e .[dev]

lint:
	. .venv/bin/activate && flake8 src tests && mypy src

test:
	. .venv/bin/activate && pytest -q

clean:
	rm -rf .venv
	rm -rf __pycache__ */__pycache__
	rm -rf .pytest_cache
	rm -rf *.egg-info