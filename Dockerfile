FROM node:24-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY pyproject.toml ./
COPY backend ./backend
RUN pip install --no-cache-dir .
COPY data/demo ./data/demo
COPY scripts/run_backtest.py ./scripts/run_backtest.py
COPY --from=frontend /build/frontend/dist ./frontend/dist
RUN python scripts/run_backtest.py --dataset data/demo/manifest.json --output artifacts/demo-backtest \
    && useradd --create-home --uid 10001 app \
    && mkdir -p runtime \
    && chown -R app:app /app/runtime /app/artifacts
USER app
ENV PRICE_TOUCH_DATA_MODE=REPLAY \
    PRICE_TOUCH_STATIC_DIR=/app/frontend/dist \
    PRICE_TOUCH_BACKTEST_DIR=/app/artifacts \
    PRICE_TOUCH_SNAPSHOT_PATH=/app/runtime/latest.json
EXPOSE 8000
CMD ["uvicorn", "price_touch.main:app", "--host", "0.0.0.0", "--port", "8000"]
