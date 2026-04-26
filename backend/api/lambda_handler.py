from __future__ import annotations

import json
import os

from mangum import Mangum

from main import app


asgi_handler = Mangum(app)


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _handle_scheduled_agent_event() -> dict:
    if not _env_enabled("SCHEDULED_AGENT_ENABLED"):
        return {
            "statusCode": 200,
            "body": json.dumps({"scheduled_agent": "disabled"}),
        }

    owner_user_id = os.getenv("SCHEDULED_AGENT_OWNER_ID", "").strip()
    if not owner_user_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"scheduled_agent": "missing_owner", "detail": "Set SCHEDULED_AGENT_OWNER_ID."}),
        }

    from dynamodb_store import DynamoDBStore
    from schemas import AgentRunRequest

    store = DynamoDBStore(owner_user_id=owner_user_id)
    run = store.run_operations_agent(
        AgentRunRequest(
            goal=os.getenv(
                "SCHEDULED_AGENT_GOAL",
                "Scheduled operations review: monitor inventory risks, late orders, cash pressure, and safe replenishment actions.",
            ),
            agent_name="operations_manager",
            allow_order_drafts=_env_enabled("SCHEDULED_AGENT_ALLOW_DRAFTS"),
        ),
        recipient_email=os.getenv("SCHEDULED_AGENT_RECIPIENT_EMAIL") or None,
    )
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "scheduled_agent": "completed",
                "run_id": run.run_id,
                "status": run.status,
                "summary": run.summary,
            }
        ),
    }


def handler(event, context):
    if event.get("source") == "aws.events" and event.get("detail-type") == "Scheduled Event":
        return _handle_scheduled_agent_event()
    return asgi_handler(event, context)
