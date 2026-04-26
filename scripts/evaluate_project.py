from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
DB_SRC = ROOT / "backend" / "database" / "src"
if str(DB_SRC) not in sys.path:
    sys.path.insert(0, str(DB_SRC))


def configure_local_eval_store() -> Path:
    state_path = Path(tempfile.gettempdir()) / f"supplychain-ai-eval-{uuid4().hex}.json"
    os.environ["APP_ENV"] = "test"
    os.environ["DYNAMODB_USE_LOCAL"] = "true"
    os.environ["DYNAMODB_USE_REMOTE"] = "false"
    os.environ["DYNAMODB_FALLBACK_TO_FILE"] = "true"
    os.environ["LOCAL_STATE_PATH"] = str(state_path)
    os.environ["OPENAI_API_KEY"] = ""
    os.environ["RESEND_API_KEY"] = ""
    os.environ["SMTP_HOST"] = ""
    os.environ["AI_AUTO_ORDER_DRAFT_FIRST"] = "true"
    return state_path


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    expected: str
    actual: str


def scenario(name: str, expected: str, actual: str, passed: bool) -> ScenarioResult:
    return ScenarioResult(name=name, expected=expected, actual=actual, passed=passed)


def main() -> int:
    state_path = configure_local_eval_store()

    from dynamodb_store import DynamoDBStore
    from schemas import (
        AgentRunRequest,
        CreateInventoryMovementRequest,
        CreateProductRequest,
        CreateSupplierRequest,
        UpdateBusinessSettingsRequest,
    )

    store = DynamoDBStore(owner_user_id=f"eval-{uuid4().hex}")
    store.email_alerts.send_order_placed_alert = lambda *args, **kwargs: (True, "eval email sent")
    store.email_alerts.send_critical_stock_alert = lambda *args, **kwargs: (True, "eval critical sent")

    results: list[ScenarioResult] = []

    products = store.list_products()
    suppliers = store.list_suppliers()
    reports = store.list_reports()
    results.append(
        scenario(
            "seed-data",
            "At least 5 products, 5 suppliers, and 1 replenishment report exist.",
            f"{len(products)} products, {len(suppliers)} suppliers, {len(reports)} reports.",
            len(products) >= 5 and len(suppliers) >= 5 and len(reports) >= 1,
        )
    )

    supplier = store.create_supplier(
        CreateSupplierRequest(name="Evaluation Supplier", lead_time_days=3, reliability_score=0.93)
    )
    product = store.create_product(
        CreateProductRequest(
            sku="EVAL-CRIT",
            name="Evaluation Critical Item",
            category="Evaluation",
            current_stock=6,
            reorder_point=10,
            lead_time_days=4,
            avg_daily_demand=3,
            unit_cost=50,
            preferred_supplier_id=supplier.supplier_id,
        )
    )
    store.add_inventory_movement(
        CreateInventoryMovementRequest(
            product_id=product.product_id,
            movement_type="sale",
            quantity=4,
            note="Evaluation sale to force critical risk",
        )
    )
    critical_item = next(item for item in store.inventory_health() if item.product_id == product.product_id)
    results.append(
        scenario(
            "sale-critical-risk",
            "A sale reduces stock and the SKU becomes critical.",
            f"{critical_item.sku} stock={critical_item.current_stock}, risk={critical_item.risk_level}.",
            critical_item.current_stock == 2 and critical_item.risk_level == "critical",
        )
    )

    job = store.run_replenishment_job()
    latest_report = store.list_reports()[0]
    results.append(
        scenario(
            "replenishment-report",
            "Running replenishment completes a job and produces recommendations.",
            f"job={job.status}, recommendations={len(latest_report.recommendations)}.",
            job.status == "completed" and len(latest_report.recommendations) > 0,
        )
    )

    store.update_business_settings(UpdateBusinessSettingsRequest(ai_enabled=True, ai_automation_enabled=True))
    auto_orders = store.auto_place_orders(recipient_email="owner@example.com")
    results.append(
        scenario(
            "draft-first-auto-orders",
            "AI automation creates only draft orders by default.",
            f"created={len(auto_orders.created_orders)}, statuses={[order.status for order in auto_orders.created_orders]}.",
            len(auto_orders.created_orders) > 0 and all(order.status == "draft" for order in auto_orders.created_orders),
        )
    )

    refused = store.chat_answer("Write a poem about the weather")
    results.append(
        scenario(
            "chat-topic-guardrail",
            "Off-topic chat is refused and does not use AI.",
            f"refused={refused.refused}, used_ai={refused.used_ai}, reason={refused.refusal_reason}.",
            refused.refused and not refused.used_ai,
        )
    )

    audit_logs = store.list_ai_audit_logs(limit=200)
    results.append(
        scenario(
            "ai-audit-log",
            "AI/fallback/refusal decisions are stored in the audit log.",
            f"{len(audit_logs)} audit event(s), latest_status={audit_logs[0].status if audit_logs else 'none'}.",
            len(audit_logs) > 0,
        )
    )

    agent_run = store.run_operations_agent(
        AgentRunRequest(goal="Monitor inventory risks, supplier delays, and cash pressure.", allow_order_drafts=False),
        recipient_email="owner@example.com",
    )
    agent_names = {step.agent_name for step in agent_run.steps}
    results.append(
        scenario(
            "multi-agent-run",
            "The operations manager delegates work to specialist agents and stores the run.",
            f"status={agent_run.status}, agents={sorted(agent_names)}, stored={len(store.list_agent_runs())}.",
            agent_run.status == "completed"
            and {"inventory_risk_agent", "supplier_delay_agent", "cash_replenishment_agent"}.issubset(agent_names)
            and len(store.list_agent_runs()) >= 1,
        )
    )

    other_store = DynamoDBStore(owner_user_id=f"eval-other-{uuid4().hex}")
    results.append(
        scenario(
            "tenant-isolation",
            "A different owner workspace cannot see this run or custom evaluation SKU.",
            f"other_products={len(other_store.list_products())}, other_agent_runs={len(other_store.list_agent_runs())}.",
            not any(item.sku == "EVAL-CRIT" for item in other_store.list_products())
            and len(other_store.list_agent_runs()) == 0,
        )
    )

    payload = {
        "passed": sum(1 for item in results if item.passed),
        "failed": sum(1 for item in results if not item.passed),
        "state_file": str(state_path),
        "scenarios": [item.__dict__ for item in results],
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
