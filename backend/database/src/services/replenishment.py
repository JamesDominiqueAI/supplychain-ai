from __future__ import annotations

from datetime import datetime, timezone
from math import ceil

from replenishment_ai import OpenAIReplenishmentNarrator
from schemas import AnalysisJob, Business, InventoryMovement, Product, PurchaseRecommendation, ReplenishmentReport


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReplenishmentService:
    """Builds replenishment jobs and reports from product and cash state."""

    def __init__(self, narrator: OpenAIReplenishmentNarrator | None = None) -> None:
        self.narrator = narrator or OpenAIReplenishmentNarrator()

    def run(
        self,
        *,
        business: Business,
        products: list[Product],
        movements: list[InventoryMovement] | None = None,
    ) -> tuple[AnalysisJob, ReplenishmentReport]:
        job = AnalysisJob(business_id=business.business_id, job_type="replenishment", status="running")

        recommendations: list[PurchaseRecommendation] = []
        total_spend = 0.0

        for product in products:
            recommendation = self._build_recommendation(product, movements or [])
            if recommendation is None:
                continue
            recommendations.append(recommendation)
            total_spend += recommendation.estimated_cost

        recommendations.sort(key=self._priority_sort_key)

        cash_budget = business.available_cash
        for recommendation in recommendations:
            if recommendation.estimated_cost <= cash_budget:
                recommendation.recommendation_type = "buy_now"
                cash_budget -= recommendation.estimated_cost
            elif recommendation.urgency in {"critical", "high"}:
                recommendation.recommendation_type = "split_order"
            else:
                recommendation.recommendation_type = "wait"
        recommendations.sort(key=self._priority_sort_key)

        total_spend = round(total_spend, 2)
        affordable_now = total_spend <= business.available_cash
        actions = [
            "Prioritize critical and high urgency products first.",
            "Use EOQ as a baseline, then trim or split orders when cash cannot cover the full plan.",
            "Review supplier lead times before committing low-priority purchases.",
        ]
        summary = (
            f"Generated {len(recommendations)} purchase recommendations. "
            f"Estimated spend is {total_spend} {business.currency}. "
            f"{'Current cash can cover the plan.' if affordable_now else 'Current cash cannot fully cover the plan.'}"
        )

        enhancement = None
        if business.ai_enabled:
            enhancement = self.narrator.enhance_report(
                business=business,
                recommendations=recommendations,
                total_spend=total_spend,
                affordable_now=affordable_now,
                default_summary=summary,
                default_actions=actions,
            )
        else:
            self.narrator.last_audit_event = {
                "feature": "report",
                "used_ai": False,
                "status": "fallback",
                "input_preview": summary[:240],
                "output_preview": None,
                "confidence": "low",
                "reason": "AI is disabled in workspace settings.",
            }
        if enhancement:
            summary = enhancement.get("summary", summary)
            actions = enhancement.get("actions", actions)
            rationale_by_sku = {
                item.get("sku"): item.get("rationale")
                for item in enhancement.get("recommendation_rationales", [])
                if item.get("sku") and item.get("rationale")
            }
            for recommendation in recommendations:
                if recommendation.sku in rationale_by_sku:
                    recommendation.rationale = rationale_by_sku[recommendation.sku]

        report = ReplenishmentReport(
            business_id=business.business_id,
            summary=summary,
            total_recommended_spend=total_spend,
            affordable_now=affordable_now,
            actions=actions,
            recommendations=recommendations,
        )

        job.status = "completed"
        job.result_report_id = report.report_id
        job.completed_at = utc_now()

        return job, report

    def _priority_sort_key(self, item: PurchaseRecommendation) -> tuple[int, float, float]:
        urgency_rank = ["critical", "high", "medium", "low"].index(item.urgency)
        recommendation_rank = ["buy_now", "split_order", "wait"].index(item.recommendation_type)
        return (urgency_rank, recommendation_rank, -item.estimated_cost)

    def _forecast_daily_demand(self, product: Product, movements: list[InventoryMovement]) -> tuple[float, str, str, float]:
        sales = [
            movement.quantity
            for movement in movements
            if movement.product_id == product.product_id and movement.movement_type == "sale"
        ]
        if not sales:
            return product.avg_daily_demand, "steady", "medium", product.avg_daily_demand

        recent_sales = sales[:3]
        recent_average = sum(recent_sales) / len(recent_sales)
        historical_average = sum(sales) / len(sales)
        weighted_daily = round((product.avg_daily_demand * 0.45) + (historical_average * 0.2) + (recent_average * 0.35), 2)

        if recent_average >= historical_average * 1.15:
            trend_direction = "up"
        elif recent_average <= historical_average * 0.85:
            trend_direction = "down"
        else:
            trend_direction = "steady"

        confidence = "high" if len(sales) >= 4 else "medium"
        return max(weighted_daily, 0.1), trend_direction, confidence, round(recent_average, 2)

    def _build_recommendation(
        self,
        product: Product,
        movements: list[InventoryMovement],
    ) -> PurchaseRecommendation | None:
        forecast_daily, trend_direction, confidence, recent_average = self._forecast_daily_demand(product, movements)
        predicted_7d = round(forecast_daily * 7, 1)
        predicted_30d = round(forecast_daily * 30, 1)
        target_stock = ceil(forecast_daily * product.target_days_of_cover)
        deficit = max(0, target_stock - product.current_stock)
        if deficit == 0:
            return None

        days_of_cover = product.current_stock / forecast_daily if forecast_daily > 0 else 999.0
        annual_demand = max(forecast_daily * 365, 1)
        ordering_cost = 1500.0
        annual_holding_cost = max(product.unit_cost * 0.18, 1.0)
        eoq_order_qty = max(ceil(((2 * annual_demand * ordering_cost) / annual_holding_cost) ** 0.5), 1)
        recommended_order_qty = min(max(deficit, 1), max(eoq_order_qty, deficit))
        estimated_cost = round(recommended_order_qty * product.unit_cost, 2)

        if days_of_cover <= 3:
            urgency = "critical"
        elif days_of_cover <= product.lead_time_days:
            urgency = "high"
        elif days_of_cover <= product.target_days_of_cover / 2:
            urgency = "medium"
        else:
            urgency = "low"

        return PurchaseRecommendation(
            product_id=product.product_id,
            sku=product.sku,
            product_name=product.name,
            current_stock=product.current_stock,
            reorder_point=product.reorder_point,
            predicted_7d_demand=predicted_7d,
            predicted_30d_demand=predicted_30d,
            days_of_cover=round(days_of_cover, 1),
            eoq_order_qty=eoq_order_qty,
            recommended_order_qty=recommended_order_qty,
            estimated_cost=estimated_cost,
            urgency=urgency,
            recommendation_type="buy_now",
            confidence=confidence,
            rationale=(
                f"{product.name} has {product.current_stock} units on hand, about {round(days_of_cover, 1)} "
                f"days of cover, with supplier lead time around {product.lead_time_days} days. "
                f"Forecast demand is {forecast_daily}/day with a {trend_direction} trend, recent sales averaging {recent_average}. "
                f"EOQ baseline is {eoq_order_qty} units and the suggested action is cash-aware."
            ),
        )
