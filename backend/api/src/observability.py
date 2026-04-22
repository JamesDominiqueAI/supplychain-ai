from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from statistics import mean
from threading import Lock
from typing import Any

logger = logging.getLogger("supplychain_ai.api")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class RequestMetrics:
    """Small in-process metrics collector for local demos and warm Lambda workers."""

    def __init__(self, max_samples: int = 500) -> None:
        self._max_samples = max_samples
        self._lock = Lock()
        self._latencies_ms: deque[float] = deque(maxlen=max_samples)
        self._requests_by_route: dict[str, int] = defaultdict(int)
        self._errors_by_route: dict[str, int] = defaultdict(int)
        self._status_counts: dict[str, int] = defaultdict(int)
        self._total_requests = 0

    def record(self, *, method: str, path: str, status_code: int, latency_ms: float) -> None:
        route_key = f"{method.upper()} {path}"
        status_bucket = f"{status_code // 100}xx"
        with self._lock:
            self._total_requests += 1
            self._latencies_ms.append(latency_ms)
            self._requests_by_route[route_key] += 1
            self._status_counts[status_bucket] += 1
            if status_code >= 500:
                self._errors_by_route[route_key] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            latencies = list(self._latencies_ms)
            total_errors = sum(self._errors_by_route.values())
            p95_latency_ms = 0.0
            if latencies:
                sorted_latencies = sorted(latencies)
                p95_index = min(int(len(sorted_latencies) * 0.95), len(sorted_latencies) - 1)
                p95_latency_ms = sorted_latencies[p95_index]
            return {
                "total_requests": self._total_requests,
                "error_rate": round(total_errors / self._total_requests, 4) if self._total_requests else 0.0,
                "average_latency_ms": round(mean(latencies), 2) if latencies else 0.0,
                "p95_latency_ms": round(p95_latency_ms, 2),
                "sample_size": len(latencies),
                "status_counts": dict(sorted(self._status_counts.items())),
                "requests_by_route": dict(sorted(self._requests_by_route.items())),
                "server_errors_by_route": dict(sorted(self._errors_by_route.items())),
            }


def log_request_event(
    *,
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    request_id: str | None = None,
    origin: str | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    """Emit one structured request log line without secrets, tokens, or bodies."""

    event: dict[str, Any] = {
        "event": "api_request",
        "method": method.upper(),
        "path": path,
        "status_code": status_code,
        "status_bucket": f"{status_code // 100}xx",
        "latency_ms": round(latency_ms, 2),
    }
    if request_id:
        event["request_id"] = request_id
    if origin:
        event["origin"] = origin
    if error_type:
        event["error_type"] = error_type
    if error_message:
        event["error_message"] = error_message[:240]

    logger.info(json.dumps(event, sort_keys=True))
    return event


def summarize_ai_audit_logs(audit_logs: list[Any]) -> dict[str, Any]:
    total = len(audit_logs)
    status_counts: dict[str, int] = defaultdict(int)
    feature_counts: dict[str, int] = defaultdict(int)
    token_totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }

    for log in audit_logs:
        status_counts[getattr(log, "status", "unknown")] += 1
        feature_counts[getattr(log, "feature", "unknown")] += 1
        token_totals["input_tokens"] += int(getattr(log, "input_tokens", 0) or 0)
        token_totals["output_tokens"] += int(getattr(log, "output_tokens", 0) or 0)
        token_totals["total_tokens"] += int(getattr(log, "total_tokens", 0) or 0)

    accepted = status_counts.get("accepted", 0)
    fallback = status_counts.get("fallback", 0)
    refused = status_counts.get("refused", 0)
    return {
        "total_ai_events": total,
        "success_rate": round(accepted / total, 4) if total else 0.0,
        "fallback_rate": round(fallback / total, 4) if total else 0.0,
        "refusal_rate": round(refused / total, 4) if total else 0.0,
        "status_counts": dict(sorted(status_counts.items())),
        "feature_counts": dict(sorted(feature_counts.items())),
        "token_usage": token_totals,
    }


request_metrics = RequestMetrics()
