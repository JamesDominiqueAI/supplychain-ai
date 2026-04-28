from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_SRC = ROOT / "backend" / "database" / "src"
if str(DB_SRC) not in sys.path:
    sys.path.insert(0, str(DB_SRC))


def configure_demo_store(owner_id: str, state_path: Path) -> None:
    os.environ["APP_ENV"] = "development"
    os.environ["DYNAMODB_USE_LOCAL"] = "true"
    os.environ["DYNAMODB_USE_REMOTE"] = "false"
    os.environ["DYNAMODB_FALLBACK_TO_FILE"] = "true"
    os.environ["LOCAL_STATE_PATH"] = str(state_path)
    os.environ.setdefault("AI_AUTO_ORDER_DRAFT_FIRST", "true")
    os.environ.setdefault("AI_AUTO_ORDER_MAX_SPEND", "250000")
    os.environ.setdefault("ALLOW_DEV_AUTH_FALLBACK", "true")
    os.environ["DEMO_OWNER_ID"] = owner_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a deterministic local demo workspace.")
    parser.add_argument("--owner-id", default="demo-owner", help="Workspace owner id used for the local JSON store.")
    parser.add_argument(
        "--state-path",
        default=str(ROOT / "data" / "workspaces" / "demo.json"),
        help="Base local state file or directory. The store appends the owner id when a file path is provided.",
    )
    parser.add_argument("--reset", action="store_true", help="Delete the existing demo workspace before seeding.")
    args = parser.parse_args()

    state_path = Path(args.state_path)
    configure_demo_store(args.owner_id, state_path)

    from dynamodb_store import DynamoDBStore
    from schemas import AgentRunRequest, UpdateBusinessSettingsRequest

    store = DynamoDBStore(owner_user_id=args.owner_id)

    if args.reset and store._local_state_path.exists():
        store._local_state_path.unlink()
        store = DynamoDBStore(owner_user_id=args.owner_id)

    store.update_business_settings(
        UpdateBusinessSettingsRequest(
            ai_enabled=True,
            ai_automation_enabled=True,
            notification_email="owner@example.com",
            critical_alerts_enabled=True,
        )
    )

    report_job = store.run_replenishment_job()
    refusal = store.chat_answer("Write a poem about the weather")
    agent_run = store.run_operations_agent(
        AgentRunRequest(
            goal="Demo review: monitor stockout risk, supplier delays, cash pressure, and safe draft orders.",
            allow_order_drafts=False,
        ),
        recipient_email="owner@example.com",
    )

    payload = {
        "owner_id": args.owner_id,
        "state_file": str(store._local_state_path),
        "products": len(store.list_products()),
        "suppliers": len(store.list_suppliers()),
        "orders": len(store.list_orders()),
        "reports": len(store.list_reports()),
        "latest_job_status": report_job.status,
        "agent_run_status": agent_run.status,
        "audit_events": len(store.list_ai_audit_logs(limit=50)),
        "refusal_demo": {
            "refused": refusal.refused,
            "used_ai": refusal.used_ai,
            "reason": refusal.refusal_reason,
        },
        "next_steps": [
            "Run backend with the same LOCAL_STATE_PATH and owner id.",
            "Open /audit after signing in to show the refusal and agent audit events.",
            "Use /reports to show the seeded replenishment report.",
        ],
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
