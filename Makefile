.PHONY: lint format test check dev-api dev-ui

lint:
	ruff check --fix .

format:
	ruff format

test:
	pytest

check: format lint test

STATE_DIR ?= ./dev-state
dev-api:
	ENSEMBLINATOR_STATE_DIR=$(STATE_DIR) python -m flask --app ensemblinator.webui.wsgi run --debug --port 5000

dev-ui:
	cd webui-src && ng serve --proxy-config proxy.conf.json