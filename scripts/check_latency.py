from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.error
import urllib.request


DEFAULT_PATHS = ["/health", "/api/dashboard/summary", "/api/ai/agents/runs"]


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((pct / 100) * (len(ordered) - 1)))
    return ordered[index]


def measure_once(url: str, token: str | None) -> tuple[float, int, str | None]:
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
            return (time.perf_counter() - started) * 1000, response.status, None
    except urllib.error.HTTPError as exc:
        exc.read()
        return (time.perf_counter() - started) * 1000, exc.code, str(exc)
    except Exception as exc:
        return (time.perf_counter() - started) * 1000, 0, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure SupplyChain AI API latency.")
    parser.add_argument("--api-url", default=os.getenv("API_URL"), help="Base API URL, for example https://abc.execute-api.us-east-1.amazonaws.com")
    parser.add_argument("--token", default=os.getenv("AUTH_TOKEN"), help="Optional Clerk bearer token for protected endpoints")
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--path", action="append", dest="paths", help="Path to measure. Can be passed multiple times.")
    args = parser.parse_args()

    if not args.api_url:
        raise SystemExit("Provide --api-url or API_URL.")

    base_url = args.api_url.rstrip("/")
    results = []
    for path in args.paths or DEFAULT_PATHS:
        samples: list[float] = []
        statuses: list[int] = []
        errors: list[str] = []
        for _ in range(max(1, args.iterations)):
            elapsed_ms, status, error = measure_once(f"{base_url}{path}", args.token)
            samples.append(elapsed_ms)
            statuses.append(status)
            if error:
                errors.append(error)
        results.append(
            {
                "path": path,
                "statuses": statuses,
                "avg_ms": round(statistics.mean(samples), 2),
                "p50_ms": round(statistics.median(samples), 2),
                "p95_ms": round(percentile(samples, 95), 2),
                "max_ms": round(max(samples), 2),
                "errors": errors[:3],
            }
        )

    print(json.dumps({"api_url": base_url, "iterations": args.iterations, "results": results}, indent=2))
    return 0 if all(all(status and status < 500 for status in item["statuses"]) for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
