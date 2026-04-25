"""
SupplyChain AI starter API.

This API exposes the workspace operations contract. In development it can use a
local JSON fallback store; in production it should run against DynamoDB.
"""

from __future__ import annotations

import os
import time
from io import StringIO
import csv
from pathlib import Path
import sys

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

project_database_src = Path(__file__).resolve().parents[1] / "database" / "src"
lambda_database_src = Path(__file__).resolve().parent / "database_src"
api_src = Path(__file__).resolve().parent / "src"

for candidate in (project_database_src, lambda_database_src, api_src):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional in deployed Lambda bundle
    load_dotenv = None

from schemas import (
    ChatRequest,
    CreateInventoryMovementRequest,
    CreateProductRequest,
    CreatePurchaseOrderRequest,
    CreateSupplierRequest,
    MorningBriefResponse,
    OrderNotificationEvent,
    ReceivePurchaseOrderRequest,
    ReportComparisonResponse,
    ScenarioAnalysisResponse,
    ScenarioRequest,
    TestNotificationResponse,
    UpdateBusinessSettingsRequest,
    UpdatePurchaseOrderStatusRequest,
)
from auth import actor_id_from_request, auth_debug_info
from observability import log_request_event, request_metrics, summarize_ai_audit_logs

if load_dotenv and not os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    load_dotenv(override=True)

app = FastAPI(
    title="SupplyChain AI API",
    description="Starter API for inventory intelligence and replenishment planning",
    version="0.1.0",
)


def get_store(actor_id: str = Depends(actor_id_from_request)) -> DynamoDBStore:
    from dynamodb_store import DynamoDBStore

    return DynamoDBStore(owner_user_id=actor_id)


def _cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def collect_request_metrics(request: Request, call_next):
    start = time.perf_counter()
    status_code = 500
    error_type = None
    error_message = None
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as exc:
        error_type = type(exc).__name__
        error_message = str(exc)
        raise
    finally:
        latency_ms = (time.perf_counter() - start) * 1000
        path = request.url.path
        request_metrics.record(
            method=request.method,
            path=path,
            status_code=status_code,
            latency_ms=latency_ms,
        )
        log_request_event(
            method=request.method,
            path=path,
            status_code=status_code,
            latency_ms=latency_ms,
            request_id=request.headers.get("x-amzn-trace-id") or request.headers.get("x-request-id"),
            origin=request.headers.get("origin"),
            error_type=error_type,
            error_message=error_message,
        )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "supplychain-ai-api"}


@app.get("/api/auth/debug")
async def debug_auth(authorization: str | None = Header(default=None)):
    return auth_debug_info(authorization)


@app.get("/api/observability/metrics")
async def get_observability_metrics(store: DynamoDBStore = Depends(get_store)):
    ai_logs = store.list_ai_audit_logs(limit=200)
    return {
        "requests": request_metrics.snapshot(),
        "ai": summarize_ai_audit_logs(ai_logs),
        "notes": [
            "Request metrics are in-process and reset when the API worker restarts.",
            "AI metrics are summarized from workspace audit logs and persist with the workspace store.",
        ],
    }


@app.get("/api/business")
async def get_business(store: DynamoDBStore = Depends(get_store)):
    return store.get_business()


@app.get("/api/dashboard/summary")
async def get_dashboard_summary(store: "DynamoDBStore" = Depends(get_store)):
    reports = store.list_reports()
    return {
        "business": store.get_business(),
        "inventory_health": store.inventory_health(),
        "orders": store.list_orders(),
        "latest_report": reports[0] if reports else None,
        "forecasts": store.list_forecast_insights(),
        "anomalies": store.list_anomaly_insights(),
        "morning_brief": store.get_morning_brief(),
    }


@app.patch("/api/business/settings")
async def update_business_settings(
    payload: UpdateBusinessSettingsRequest,
    store: DynamoDBStore = Depends(get_store),
):
    return store.update_business_settings(payload)


@app.get("/api/products")
async def list_products(store: DynamoDBStore = Depends(get_store)):
    return store.list_products()


@app.post("/api/products")
async def create_product(payload: CreateProductRequest, store: DynamoDBStore = Depends(get_store)):
    return store.create_product(payload)


@app.get("/api/suppliers")
async def list_suppliers(store: DynamoDBStore = Depends(get_store)):
    return store.list_suppliers()


@app.get("/api/suppliers/scorecards")
async def list_supplier_scorecards(store: DynamoDBStore = Depends(get_store)):
    return store.list_supplier_scorecards()


@app.post("/api/suppliers")
async def create_supplier(payload: CreateSupplierRequest, store: DynamoDBStore = Depends(get_store)):
    return store.create_supplier(payload)


@app.post("/api/inventory/movements")
async def create_inventory_movement(
    payload: CreateInventoryMovementRequest,
    store: DynamoDBStore = Depends(get_store),
):
    try:
        return store.add_inventory_movement(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Product not found") from exc


@app.get("/api/inventory/movements")
async def list_inventory_movements(store: DynamoDBStore = Depends(get_store)):
    return store.list_inventory_movements()


@app.get("/api/inventory/health")
async def get_inventory_health(store: DynamoDBStore = Depends(get_store)):
    return store.inventory_health()


@app.get("/api/ai/forecast")
async def get_forecast_insights(store: DynamoDBStore = Depends(get_store)):
    return store.list_forecast_insights()


@app.get("/api/ai/anomalies")
async def get_anomaly_insights(store: DynamoDBStore = Depends(get_store)):
    return store.list_anomaly_insights()


@app.get("/api/ai/audit")
async def list_ai_audit(store: DynamoDBStore = Depends(get_store)):
    return store.list_ai_audit_logs()


@app.get("/api/ai/brief")
async def get_morning_brief(store: DynamoDBStore = Depends(get_store)) -> MorningBriefResponse:
    return store.get_morning_brief()


@app.post("/api/ai/scenario")
async def analyze_scenario(
    payload: ScenarioRequest,
    store: DynamoDBStore = Depends(get_store),
) -> ScenarioAnalysisResponse:
    return store.analyze_scenario(payload)


@app.get("/api/ai/report-comparison")
async def compare_latest_reports(store: DynamoDBStore = Depends(get_store)) -> ReportComparisonResponse:
    return store.compare_latest_reports()


@app.get("/api/notifications/orders")
async def list_order_notifications(store: DynamoDBStore = Depends(get_store)) -> list[OrderNotificationEvent]:
    return store.list_order_notification_events()


@app.post("/api/notifications/orders/retry")
async def retry_order_notifications(
    store: DynamoDBStore = Depends(get_store),
    actor_email: str | None = Header(default=None, alias="X-Actor-Email"),
) -> list[OrderNotificationEvent]:
    return store.retry_failed_order_notifications(recipient_email=actor_email)


@app.post("/api/notifications/test-order-email")
async def send_test_order_email(
    store: DynamoDBStore = Depends(get_store),
    actor_email: str | None = Header(default=None, alias="X-Actor-Email"),
) -> TestNotificationResponse:
    return store.send_test_order_notification(recipient_email=actor_email)


@app.post("/api/ai/auto-orders")
async def create_auto_orders(
    store: DynamoDBStore = Depends(get_store),
    actor_email: str | None = Header(default=None, alias="X-Actor-Email"),
):
    return store.auto_place_orders(recipient_email=actor_email)


@app.post("/api/ai/chat")
async def ask_workspace_ai(payload: ChatRequest, store: DynamoDBStore = Depends(get_store)):
    return store.chat_answer(payload.message)


@app.post("/api/analysis/replenishment")
async def trigger_replenishment(store: DynamoDBStore = Depends(get_store)):
    return store.run_replenishment_job()


@app.get("/api/jobs")
async def list_jobs(store: DynamoDBStore = Depends(get_store)):
    return store.list_jobs()


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, store: DynamoDBStore = Depends(get_store)):
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/reports")
async def list_reports(store: DynamoDBStore = Depends(get_store)):
    return store.list_reports()


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str, store: DynamoDBStore = Depends(get_store)):
    report = store.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.get("/api/reports/{report_id}/export.csv")
async def export_report_csv(report_id: str, store: DynamoDBStore = Depends(get_store)):
    report = store.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "sku",
            "product_name",
            "urgency",
            "recommendation_type",
            "confidence",
            "current_stock",
            "reorder_point",
            "days_of_cover",
            "predicted_7d_demand",
            "predicted_30d_demand",
            "eoq_order_qty",
            "recommended_order_qty",
            "estimated_cost",
            "rationale",
        ]
    )
    for item in report.recommendations:
        writer.writerow(
            [
                item.sku,
                item.product_name,
                item.urgency,
                item.recommendation_type,
                item.confidence,
                item.current_stock,
                item.reorder_point,
                item.days_of_cover,
                item.predicted_7d_demand,
                item.predicted_30d_demand,
                item.eoq_order_qty,
                item.recommended_order_qty,
                item.estimated_cost,
                item.rationale,
            ]
        )

    filename = f"replenishment-report-{report_id}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/orders")
async def list_orders(store: DynamoDBStore = Depends(get_store)):
    return store.list_orders()


@app.post("/api/orders")
async def create_order(
    payload: CreatePurchaseOrderRequest,
    store: DynamoDBStore = Depends(get_store),
    actor_email: str | None = Header(default=None, alias="X-Actor-Email"),
):
    try:
        return store.create_purchase_order(
            payload,
            placed_by_type="user",
            placed_by_label=f"Signed-in user ({store.owner_user_id})",
            recipient_email=actor_email,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Product or supplier not found") from exc


@app.post("/api/orders/{order_id}/status")
async def update_order_status(
    order_id: str,
    payload: UpdatePurchaseOrderStatusRequest,
    store: DynamoDBStore = Depends(get_store),
):
    try:
        return store.update_purchase_order_status(order_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Order not found") from exc


@app.post("/api/orders/{order_id}/receive")
async def receive_order(
    order_id: str,
    payload: ReceivePurchaseOrderRequest,
    store: DynamoDBStore = Depends(get_store),
):
    try:
        return store.receive_purchase_order(order_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Order not found") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("BACKEND_HOST", "127.0.0.1"),
        port=int(os.getenv("BACKEND_PORT", "8010")),
        reload=False,
    )
