from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request


def fetch(base_url: str, path: str) -> tuple[int, str, str]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=2) as response:
        return response.status, response.headers.get_content_type(), response.read().decode()


def fail(message: str) -> None:
    raise RuntimeError(f"FAIL: {message}")


def verify(base_url: str, timeout_seconds: float) -> dict:
    deadline = time.monotonic() + timeout_seconds
    snapshots: dict[str, dict] = {}
    fault_seen = False
    recovered_after_fault = False
    last_error = "service not contacted"

    while time.monotonic() < deadline:
        try:
            status, _, health_body = fetch(base_url, "/api/v1/health")
            if status != 200:
                fail(f"health returned {status}")
            health = json.loads(health_body)
            if health.get("live") is not True:
                fail("process is not live")
            _, _, snapshots_body = fetch(base_url, "/api/v1/snapshots?limit=20")
            for snapshot in json.loads(snapshots_body):
                snapshots[snapshot["forecast_id"]] = snapshot
            ordered = sorted(snapshots.values(), key=lambda item: item["origin_time"])
            for snapshot in ordered:
                message = snapshot["source"].get("message")
                if message == "SOURCE_ERROR":
                    fault_seen = True
                elif fault_seen and message == "HEALTHY":
                    recovered_after_fault = True
            if len(ordered) >= 3 and health.get("ready") and fault_seen and recovered_after_fault:
                break
        except (OSError, urllib.error.URLError, json.JSONDecodeError, RuntimeError) as error:
            last_error = str(error)
        time.sleep(0.5)
    else:
        fail(
            f"timed out: snapshots={len(snapshots)}, fault={fault_seen}, "
            f"recovered={recovered_after_fault}, last_error={last_error}"
        )

    ordered = sorted(snapshots.values(), key=lambda item: item["origin_time"])
    latest = ordered[-1]
    calibrated = latest["matrices"]["calibrated"]
    if len(calibrated) != 21 or any(len(row) != 36 for row in calibrated):
        fail("latest matrix is not 21x36")
    values = [value for row in calibrated for value in row]
    valid_values = all(
        isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 1
        for value in values
    )
    if not valid_values:
        fail("latest matrix has non-finite or out-of-range probability")

    _, content_type, export = fetch(base_url, f"/api/v1/exports/{latest['forecast_id']}?format=csv")
    if content_type != "text/csv" or "interval_lower_ticks" not in export:
        fail("CSV export does not preserve frozen bounds")
    _, content_type, page = fetch(base_url, "/")
    if content_type != "text/html" or "TouchLab" not in page or 'id="root"' not in page:
        fail("UI entry point is not served")

    return {
        "status": "PASS",
        "snapshot_count": len(ordered),
        "first_forecast_id": ordered[0]["forecast_id"],
        "last_forecast_id": latest["forecast_id"],
        "shape": [len(calibrated), len(calibrated[0])],
        "fault_seen": fault_seen,
        "recovered_after_fault": recovered_after_fault,
        "export_bytes": len(export.encode()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the packaged offline acceptance runtime")
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--timeout-seconds", type=float, default=25)
    args = parser.parse_args()
    try:
        evidence = verify(args.base_url, args.timeout_seconds)
    except Exception as error:
        print(error)
        raise SystemExit(1) from error
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
