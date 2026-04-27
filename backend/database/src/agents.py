from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from schemas import (
    AgentName,
    AgentRunRequest,
    AgentRunResponse,
    AgentStepResult,
    InventoryHealthItem,
    PurchaseOrder,
    ReplenishmentReport,
)


@dataclass(frozen=True)
class AgentExecution:
    run: AgentRunResponse
    audit_status: str
    used_ai: bool
    reason: str


class OperationsAgentTeam:
    """Coordinates specialist agents while keeping persistence inside the store."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def run(self, request: AgentRunRequest, *, recipient_email: str | None = None) -> AgentExecution:
        goal = request.goal.strip()
        agent_name: AgentName = request.agent_name
        guardrail_notes = [
            "Agent team tools are limited to internal workspace data and draft order creation.",
            "External supplier calls, payments, and off-platform purchasing are blocked.",
            "Operations Manager can coordinate Inventory Risk, Supplier Delay, and Cash Replenishment agents.",
        ]

        if not self.store.business.ai_enabled:
            guardrail_notes.append("AI is disabled, so the agent is blocked before planning.")
            return AgentExecution(
                run=AgentRunResponse(
                    business_id=self.store.business.business_id,
                    agent_name=agent_name,
                    goal=goal,
                    status="blocked",
                    summary="Agent run blocked because AI is disabled in Settings.",
                    steps=[],
                    guardrail_notes=guardrail_notes,
                ),
                audit_status="refused",
                used_ai=False,
                reason="AI disabled.",
            )

        if not self.goal_is_allowed(goal):
            guardrail_notes.append("Goal is outside inventory operations or asks for unsupported external action.")
            return AgentExecution(
                run=AgentRunResponse(
                    business_id=self.store.business.business_id,
                    agent_name=agent_name,
                    goal=goal,
                    status="blocked",
                    summary="Agent run blocked by allowed-topic guardrails.",
                    steps=[],
                    guardrail_notes=guardrail_notes,
                ),
                audit_status="refused",
                used_ai=False,
                reason="Unsupported agent goal.",
            )

        health = self.store.inventory_health()
        orders = self.store.list_orders()
        inventory_steps, risky_items = self.run_inventory_risk_agent(health)
        supplier_steps, late_orders = self.run_supplier_delay_agent(orders)
        latest_report, report_detail = self.latest_report_for_agent()

        steps: list[AgentStepResult] = []
        created_orders: list[PurchaseOrder] = []

        if agent_name == "inventory_risk_agent":
            steps.extend(inventory_steps)
        elif agent_name == "supplier_delay_agent":
            steps.extend(supplier_steps)
        elif agent_name == "cash_replenishment_agent":
            cash_steps, created_orders = self.run_cash_replenishment_agent(
                latest_report,
                report_detail,
                allow_order_drafts=request.allow_order_drafts,
                recipient_email=recipient_email,
            )
            steps.extend(cash_steps)
        else:
            steps.append(
                self.step(
                    "operations_manager",
                    "inventory_risk_scan",
                    "completed",
                    "Operations Manager delegated inventory risk scanning to the Inventory Risk Agent.",
                    [inventory_steps[0].summary],
                )
            )
            steps.extend(inventory_steps)
            steps.append(
                self.step(
                    "operations_manager",
                    "late_order_scan",
                    "completed",
                    "Operations Manager delegated late-order monitoring to the Supplier Delay Agent.",
                    [supplier_steps[0].summary],
                )
            )
            steps.extend(supplier_steps)
            cash_steps, created_orders = self.run_cash_replenishment_agent(
                latest_report,
                report_detail,
                allow_order_drafts=request.allow_order_drafts,
                recipient_email=recipient_email,
            )
            steps.append(
                self.step(
                    "operations_manager",
                    "cash_replenishment_check",
                    "completed",
                    "Operations Manager delegated cash and replenishment planning to the Cash Replenishment Agent.",
                    [cash_steps[0].summary],
                )
            )
            steps.extend(cash_steps)

        summary = (
            f"{agent_name.replace('_', ' ').title()} completed {len(steps)} tool step(s): "
            f"{len(risky_items)} risky item(s), {len(late_orders)} late order(s), "
            f"and {len(created_orders)} draft order(s) created."
        )
        return AgentExecution(
            run=AgentRunResponse(
                business_id=self.store.business.business_id,
                agent_name=agent_name,
                goal=goal,
                status="completed",
                summary=summary,
                steps=steps,
                created_orders=created_orders,
                guardrail_notes=guardrail_notes,
            ),
            audit_status="accepted",
            used_ai=True,
            reason="Agent team executed bounded internal tools.",
        )

    @staticmethod
    def step(
        agent_name: AgentName,
        tool_name: str,
        status: str,
        summary: str,
        details: list[str] | None = None,
    ) -> AgentStepResult:
        return AgentStepResult(
            agent_name=agent_name,
            tool_name=tool_name,
            status=status,
            summary=summary,
            details=details or [],
        )

    @staticmethod
    def goal_is_allowed(goal: str) -> bool:
        normalized = goal.strip().lower()
        allowed_terms = {
            "inventory",
            "stock",
            "sku",
            "order",
            "orders",
            "supplier",
            "suppliers",
            "cash",
            "replenishment",
            "purchase",
            "risk",
            "late",
            "delay",
            "forecast",
            "warehouse",
            "business",
            "materials",
        }
        blocked_terms = {
            "call supplier",
            "phone supplier",
            "negotiate",
            "wire money",
            "bank transfer",
            "external purchase",
            "send payment",
        }
        return any(term in normalized for term in allowed_terms) and not any(term in normalized for term in blocked_terms)

    def run_inventory_risk_agent(
        self,
        health: list[InventoryHealthItem],
    ) -> tuple[list[AgentStepResult], list[InventoryHealthItem]]:
        risky_items = [item for item in health if item.risk_level in {"critical", "high", "watch"}]
        return [
            self.step(
                "inventory_risk_agent",
                "inventory_risk_scan",
                "completed",
                f"Inventory Risk Agent found {len(risky_items)} item(s) needing attention.",
                [
                    f"{item.product_name} ({item.sku}): {item.current_stock} on hand, {item.days_of_cover} days cover, risk {item.risk_level}."
                    for item in risky_items[:5]
                ],
            )
        ], risky_items

    def run_supplier_delay_agent(
        self,
        orders: list[PurchaseOrder],
    ) -> tuple[list[AgentStepResult], list[PurchaseOrder]]:
        late_orders = [order for order in orders if order.is_late]
        return [
            self.step(
                "supplier_delay_agent",
                "late_order_scan",
                "completed",
                f"Supplier Delay Agent found {len(late_orders)} late order(s).",
                [
                    f"{order.product_name} ({order.sku}) is late by {order.days_late} day(s), status {order.status.replace('_', ' ')}."
                    for order in late_orders[:5]
                ],
            )
        ], late_orders

    def latest_report_for_agent(self) -> tuple[ReplenishmentReport | None, str]:
        latest_report = self.store.list_reports()[0] if self.store.list_reports() else None
        if latest_report is None:
            job = self.store.run_replenishment_job()
            latest_report = self.store.list_reports()[0] if self.store.list_reports() else None
            return latest_report, f"Generated replenishment report through job {job.job_id}."
        return latest_report, f"Used latest replenishment report {latest_report.report_id}."

    def run_cash_replenishment_agent(
        self,
        latest_report: ReplenishmentReport | None,
        report_detail: str,
        *,
        allow_order_drafts: bool,
        recipient_email: str | None,
    ) -> tuple[list[AgentStepResult], list[PurchaseOrder]]:
        spend = latest_report.total_recommended_spend if latest_report else 0
        steps = [
            self.step(
                "cash_replenishment_agent",
                "cash_replenishment_check",
                "completed",
                (
                    f"Cash Replenishment Agent checked {spend:g} {self.store.business.currency} recommended spend "
                    f"against {self.store.business.available_cash:g} {self.store.business.currency} available cash."
                ),
                [
                    report_detail,
                    "Cash pressure detected; split or defer lower-risk orders."
                    if spend > self.store.business.available_cash
                    else "Recommended spend fits available cash.",
                ],
            )
        ]

        created_orders: list[PurchaseOrder] = []
        if allow_order_drafts and self.store.business.ai_automation_enabled:
            auto_result = self.store.auto_place_orders(recipient_email=recipient_email)
            created_orders = auto_result.created_orders
            steps.append(
                self.step(
                    "cash_replenishment_agent",
                    "draft_replenishment_orders",
                    "completed",
                    auto_result.summary,
                    [f"Drafted {order.quantity} units of {order.product_name} ({order.sku})." for order in created_orders[:5]],
                )
            )
        elif allow_order_drafts:
            steps.append(
                self.step(
                    "cash_replenishment_agent",
                    "draft_replenishment_orders",
                    "blocked",
                    "Draft order creation was requested but AI automation is disabled.",
                    ["Enable AI Automation in Settings before the cash agent can draft orders."],
                )
            )
        else:
            steps.append(
                self.step(
                    "cash_replenishment_agent",
                    "draft_replenishment_orders",
                    "skipped",
                    "Draft order creation was not requested for this run.",
                    ["The cash agent planned only; no orders were created."],
                )
            )
        return steps, created_orders
