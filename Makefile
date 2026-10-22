.PHONY: test frontend-test lint typecheck build backtest benchmark verify dev

test:
	uv run pytest -q

frontend-test:
	cd frontend && npm test -- --run

lint:
	uv run ruff check backend scripts

typecheck:
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build

backtest:
	uv run python scripts/run_backtest.py --dataset data/demo/manifest.json --output artifacts/demo-backtest

benchmark:
	uv run python scripts/benchmark_model.py

verify: lint test frontend-test typecheck build backtest benchmark

dev:
	PRICE_TOUCH_STATIC_DIR=frontend/dist uv run uvicorn price_touch.main:app --reload --host 0.0.0.0 --port 8000
