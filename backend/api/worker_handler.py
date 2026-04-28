"""
SQS-style worker entrypoint for future async analysis jobs.

The production API still runs replenishment and agent jobs inline by default.
This module documents and exercises the queue handoff shape so the eventual SQS
worker can reuse the same store methods without changing the domain logic.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


project_database_src = Path(__file__).resolve().parents[1] / "database" / "src"
lambda_database_src = Path(__file__).resolve().parent / "database_src"

for candidate in (project_database_src, lambda_database_src):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def _decode_record_body(record: dict[str, Any]) -> dict[str, Any]:
    body = record.get("body", "{}")
    if isinstance(body, str):
        return json.loads(body)
    if isinstance(body, dict):
        return body
    raise ValueError("Unsupported SQS record body")


def process_job_message(payload: dict[str, Any]) -> dict[str, Any]:
    owner_user_id = str(payload.get("owner_user_id") or "").strip()
    job_type = str(payload.get("job_type") or "replenishment").strip()
    if not owner_user_id:
        raise ValueError("owner_user_id is required")

    from dynamodb_store import DynamoDBStore
    from schemas import AgentRunRequest

    store = DynamoDBStore(owner_user_id=owner_user_id)

    if job_type == "replenishment":
        job = store.run_replenishment_job()
        return {
            "owner_user_id": owner_user_id,
            "job_type": job_type,
            "status": job.status,
            "job_id": job.job_id,
            "result_report_id": job.result_report_id,
        }

    if job_type == "operations_agent":
        run = store.run_operations_agent(
            AgentRunRequest(
                goal=payload.get(
                    "goal",
                    "Queued operations review: monitor inventory risks, late orders, cash pressure, and safe replenishment actions.",
                ),
                allow_order_drafts=bool(payload.get("allow_order_drafts", False)),
            ),
            recipient_email=payload.get("recipient_email"),
        )
        return {
            "owner_user_id": owner_user_id,
            "job_type": job_type,
            "status": run.status,
            "run_id": run.run_id,
            "created_orders": len(run.created_orders),
        }

    raise ValueError(f"Unsupported job_type: {job_type}")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for record in event.get("Records", []):
        message_id = str(record.get("messageId") or record.get("message_id") or "unknown")
        try:
            results.append(process_job_message(_decode_record_body(record)))
        except Exception as exc:  # pragma: no cover - Lambda batch failure surface
            failures.append({"itemIdentifier": message_id, "error": str(exc)})

    return {
        "batchItemFailures": [{"itemIdentifier": item["itemIdentifier"]} for item in failures],
        "results": results,
        "failures": failures,
        "async_jobs_enabled": os.getenv("ASYNC_JOBS_ENABLED", "false").lower() == "true",
    }
