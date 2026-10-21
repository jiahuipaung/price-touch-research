# Data sources

Verified on 2026-10-21. Public network adapters are optional; deterministic replay remains the offline acceptance path.

## BTC — Binance Spot public trade stream

- Endpoint: `wss://data-stream.binance.vision/ws/btcusdt@trade`
- Authentication: none for market-data-only streams.
- Semantics: raw BTCUSDT trades; `t` is trade ID, `p` is price, `T` is trade time in Unix milliseconds.
- Declared cadence: real time. Connections are finite-lived and require ping/pong/reconnect handling.
- Provider contract: <https://developers.binance.com/en/docs/products/spot/testnet/web-socket-streams>
- Application state: `LIVE` while fresh. This stream is not silently replaced by replay on failure.

## Gold — XAUS keyless spot API

- Endpoint: `https://xaus.com/api/v1/spot?compact=1`
- Authentication: none; the provider asks reasonable-use clients to cache for at least 30 seconds.
- Semantics: indicative XAU/USD mid-market price per troy ounce, not an exchange trade or executable quote.
- Timestamp/freshness: `data_state.as_of`, `status`, and `age_seconds`; edge cache is documented as 30 seconds.
- Provider contract: <https://xaus.com/api/>
- Application state: always `DELAYED`; `stale` is also preserved. It may center an indicative matrix but cannot create `TICK_EXACT` truth labels.

## Oil — AmericasOilWatch keyless WTI API

- Endpoint: `https://americasoilwatch.com/api/v1/wti`
- Authentication: none; response cache headers document five-minute freshness behavior.
- Semantics: session-dated WTI price based on Yahoo Finance `CL=F`, with EIA/FRED fallback described by the provider. It is not a raw trade stream.
- Timestamp/freshness: `observedAt`, `quoteStatus`, `quoteType`, `basis`, and `sessionDate`.
- Provider contract: <https://americasoilwatch.com/api>
- Application state: always `DELAYED`; it cannot create `TICK_EXACT` truth labels.

## Rejected candidate

Stooq's formerly common `q/l` CSV paths returned HTTP 404 during the 2026-10-21 probe, so the project does not depend on that undocumented endpoint.

## Limitations

Free commodity endpoints do not provide the tick-by-tick trade truth required for exact five-second calibration. They are therefore displayed as delayed indicative sources only. Full-cycle, high-resolution backtests use separately downloaded manifest-backed history, and the UI keeps `TICK_EXACT` and `BAR_APPROX` results separate.
