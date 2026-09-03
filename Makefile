.PHONY: lint format test check

lint:
	ruff check --fix .

format:
	ruff format

test:
	pytest

check: format lint test