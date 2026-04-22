from __future__ import annotations

import types
import unittest
from unittest.mock import patch

from backend.tests.test_support import reset_fake_environment


class ObservabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_fake_environment()
        from src.observability import RequestMetrics, log_request_event, summarize_ai_audit_logs

        self.RequestMetrics = RequestMetrics
        self.log_request_event = log_request_event
        self.summarize_ai_audit_logs = summarize_ai_audit_logs

    def test_request_metrics_tracks_latency_and_error_rate(self) -> None:
        metrics = self.RequestMetrics()
        metrics.record(method="GET", path="/api/products", status_code=200, latency_ms=25.0)
        metrics.record(method="GET", path="/api/reports", status_code=500, latency_ms=75.0)

        snapshot = metrics.snapshot()

        self.assertEqual(snapshot["total_requests"], 2)
        self.assertEqual(snapshot["error_rate"], 0.5)
        self.assertEqual(snapshot["average_latency_ms"], 50.0)
        self.assertEqual(snapshot["status_counts"]["2xx"], 1)
        self.assertEqual(snapshot["status_counts"]["5xx"], 1)
        self.assertEqual(snapshot["server_errors_by_route"]["GET /api/reports"], 1)

    def test_structured_request_log_redacts_and_truncates_error_details(self) -> None:
        long_message = "x" * 300

        with patch("src.observability.logger.info") as logger_info:
            event = self.log_request_event(
                method="get",
                path="/api/products",
                status_code=500,
                latency_ms=12.345,
                request_id="Root=1-test",
                origin="https://example.com",
                error_type="RuntimeError",
                error_message=long_message,
            )

        self.assertEqual(event["event"], "api_request")
        self.assertEqual(event["method"], "GET")
        self.assertEqual(event["path"], "/api/products")
        self.assertEqual(event["status_bucket"], "5xx")
        self.assertEqual(event["latency_ms"], 12.35)
        self.assertEqual(len(event["error_message"]), 240)
        logger_info.assert_called_once()
        self.assertIn('"event": "api_request"', logger_info.call_args.args[0])

    def test_ai_audit_summary_tracks_success_fallback_and_tokens(self) -> None:
        logs = [
            types.SimpleNamespace(feature="chat", status="accepted", input_tokens=20, output_tokens=15, total_tokens=35),
            types.SimpleNamespace(feature="report", status="fallback", input_tokens=None, output_tokens=None, total_tokens=None),
            types.SimpleNamespace(feature="chat", status="refused", input_tokens=5, output_tokens=3, total_tokens=8),
        ]

        summary = self.summarize_ai_audit_logs(logs)

        self.assertEqual(summary["total_ai_events"], 3)
        self.assertEqual(summary["success_rate"], 0.3333)
        self.assertEqual(summary["fallback_rate"], 0.3333)
        self.assertEqual(summary["refusal_rate"], 0.3333)
        self.assertEqual(summary["feature_counts"]["chat"], 2)
        self.assertEqual(summary["token_usage"]["total_tokens"], 43)


if __name__ == "__main__":
    unittest.main()
