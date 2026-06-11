# Makefile — atalhos da esteira PIM-PF.
# No Windows sem `make`, veja os comandos equivalentes no README.

.PHONY: report test lint format install

install:
	pip install -e ".[dev]"

report:
	python -m pim_report --periodo last

test:
	pytest

lint:
	ruff check .
	black --check .

format:
	ruff check --fix .
	black .
