.PHONY: test lint verify dev

test:
	uv run pytest -q

lint:
	uv run ruff check backend

verify: lint test

dev:
	uv run uvicorn price_touch.main:app --reload --host 0.0.0.0 --port 8000
