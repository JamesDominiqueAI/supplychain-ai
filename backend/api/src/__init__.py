from pathlib import Path
import sys

project_database_src = Path(__file__).resolve().parents[2] / "database" / "src"
lambda_database_src = Path(__file__).resolve().parents[1] / "database_src"

for candidate in (project_database_src, lambda_database_src):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from .auth import actor_id_from_request, auth_debug_info
from schemas import (
    AIAuditLog,
    AnomalyInsight,
    AutoOrderResult,
    ChatRequest,
    ChatResponse,
    CreateInventoryMovementRequest,
    CreateProductRequest,
    CreatePurchaseOrderRequest,
    ForecastInsight,
    MorningBriefResponse,
    OrderNotificationEvent,
    ReceivePurchaseOrderRequest,
    ReportComparisonResponse,
    ScenarioAnalysisResponse,
    ScenarioRequest,
    CreateSupplierRequest,
    SupplierScorecard,
    TestNotificationResponse,
    UpdateBusinessSettingsRequest,
    UpdatePurchaseOrderStatusRequest,
)
from dynamodb_store import DynamoDBStore

__all__ = [
    "actor_id_from_request",
    "auth_debug_info",
    "AIAuditLog",
    "AnomalyInsight",
    "AutoOrderResult",
    "ChatRequest",
    "ChatResponse",
    "CreateInventoryMovementRequest",
    "CreateProductRequest",
    "CreatePurchaseOrderRequest",
    "ForecastInsight",
    "MorningBriefResponse",
    "OrderNotificationEvent",
    "ReceivePurchaseOrderRequest",
    "ReportComparisonResponse",
    "ScenarioAnalysisResponse",
    "ScenarioRequest",
    "SupplierScorecard",
    "TestNotificationResponse",
    "CreateSupplierRequest",
    "DynamoDBStore",
    "UpdateBusinessSettingsRequest",
    "UpdatePurchaseOrderStatusRequest",
]
