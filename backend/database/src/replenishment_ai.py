from __future__ import annotations

import json
import logging
import os
from typing import Any

from guardrails import validate_chat_output, validate_report_inputs
from schemas import Business, PurchaseRecommendation, ReplenishmentReport

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional until dependencies are installed
    OpenAI = None


logger = logging.getLogger(__name__)


class OpenAIReplenishmentNarrator:
    """Optional narrative layer for replenishment reports and operational AI summaries."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
        self.reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT")
        self.timeout_seconds = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "8"))
        self.last_audit_event: dict[str, Any] | None = None

    @property
    def is_enabled(self) -> bool:
        return bool(self.api_key and OpenAI is not None)

    def _build_request(
        self,
        *,
        model_input: str,
        instructions: str,
        schema_name: str,
        schema: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "instructions": instructions,
            "input": model_input,
            "max_output_tokens": max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        if self.reasoning_effort:
            request_kwargs["reasoning"] = {"effort": self.reasoning_effort}
        return request_kwargs

    def _token_usage_from_response(self, response: Any) -> dict[str, int | None]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {"input_tokens": None, "output_tokens": None, "total_tokens": None}

        def usage_value(*names: str) -> int | None:
            for name in names:
                if isinstance(usage, dict):
                    value = usage.get(name)
                else:
                    value = getattr(usage, name, None)
                if value is not None:
                    return int(value)
            return None

        input_tokens = usage_value("input_tokens", "prompt_tokens")
        output_tokens = usage_value("output_tokens", "completion_tokens")
        total_tokens = usage_value("total_tokens")
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

    def _run_structured_response(
        self,
        *,
        request_kwargs: dict[str, Any],
        feature: str,
        input_preview: str,
        default_reason: str,
    ) -> dict[str, Any] | None:
        self.last_audit_event = None
        if not self.is_enabled:
            self.last_audit_event = {
                "feature": feature,
                "used_ai": False,
                "status": "fallback",
                "input_preview": input_preview[:240],
                "output_preview": None,
                "confidence": "low",
                "reason": "AI disabled.",
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
            }
            return None

        client = OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)
        try:
            response = client.responses.create(**request_kwargs)
            token_usage = self._token_usage_from_response(response)
            if not getattr(response, "output_text", None):
                self.last_audit_event = {
                    "feature": feature,
                    "used_ai": False,
                    "status": "fallback",
                    "input_preview": input_preview[:240],
                    "output_preview": None,
                    "confidence": "low",
                    "reason": default_reason,
                    **token_usage,
                }
                return None
            parsed = json.loads(response.output_text)
            output_preview = (
                parsed.get("summary")
                or parsed.get("answer")
                or json.dumps(parsed, ensure_ascii=True)[:240]
            )
            self.last_audit_event = {
                "feature": feature,
                "used_ai": True,
                "status": "accepted",
                "input_preview": input_preview[:240],
                "output_preview": output_preview[:240],
                "confidence": parsed.get("confidence", "medium"),
                "reason": None,
                **token_usage,
            }
            return parsed
        except Exception as exc:  # pragma: no cover - network/API failures vary by environment
            logger.warning("OpenAI %s generation failed: %s", feature, exc)
            self.last_audit_event = {
                "feature": feature,
                "used_ai": False,
                "status": "fallback",
                "input_preview": input_preview[:240],
                "output_preview": None,
                "confidence": "low",
                "reason": str(exc)[:240],
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
            }
            return None

    def enhance_report(
        self,
        *,
        business: Business,
        recommendations: list[PurchaseRecommendation],
        total_spend: float,
        affordable_now: bool,
        default_summary: str,
        default_actions: list[str],
    ) -> dict[str, Any] | None:
        self.last_audit_event = None
        if not self.is_enabled or not recommendations:
            self.last_audit_event = {
                "feature": "report",
                "used_ai": False,
                "status": "fallback",
                "input_preview": default_summary[:240],
                "output_preview": None,
                "confidence": "low",
                "reason": "AI disabled or no recommendations.",
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
            }
            return None
        validation = validate_report_inputs(recommendations)
        if not validation.allowed:
            self.last_audit_event = {
                "feature": "report",
                "used_ai": False,
                "status": "refused",
                "input_preview": default_summary[:240],
                "output_preview": None,
                "confidence": "low",
                "reason": validation.reason,
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
            }
            return None

        request_kwargs = self._build_request(
            model_input=self._build_prompt(
                business=business,
                recommendations=recommendations,
                total_spend=total_spend,
                affordable_now=affordable_now,
                default_summary=default_summary,
                default_actions=default_actions,
            ),
            instructions=(
                "You are a supply chain copilot for a small business in Haiti. "
                "Improve the narrative quality of a replenishment report without changing the "
                "underlying quantities, urgency labels, or cost figures. Be concise, practical, "
                "and grounded in the provided numbers."
            ),
            schema_name="replenishment_report_enhancement",
            max_output_tokens=900,
            schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "summary": {"type": "string"},
                    "actions": {"type": "array", "items": {"type": "string"}},
                    "recommendation_rationales": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "sku": {"type": "string"},
                                "rationale": {"type": "string"},
                            },
                            "required": ["sku", "rationale"],
                        },
                    },
                },
                "required": ["summary", "actions", "recommendation_rationales"],
            },
        )
        return self._run_structured_response(
            request_kwargs=request_kwargs,
            feature="report",
            input_preview=default_summary,
            default_reason="OpenAI returned no output_text.",
        )

    def _build_prompt(
        self,
        *,
        business: Business,
        recommendations: list[PurchaseRecommendation],
        total_spend: float,
        affordable_now: bool,
        default_summary: str,
        default_actions: list[str],
    ) -> str:
        payload = {
            "business": {
                "name": business.name,
                "country": business.country,
                "currency": business.currency,
                "available_cash": business.available_cash,
            },
            "report_context": {
                "total_recommended_spend": total_spend,
                "affordable_now": affordable_now,
                "default_summary": default_summary,
                "default_actions": default_actions,
            },
            "recommendations": [
                {
                    "sku": item.sku,
                    "product_name": item.product_name,
                    "current_stock": item.current_stock,
                    "reorder_point": item.reorder_point,
                    "predicted_7d_demand": item.predicted_7d_demand,
                    "predicted_30d_demand": item.predicted_30d_demand,
                    "days_of_cover": item.days_of_cover,
                    "eoq_order_qty": item.eoq_order_qty,
                    "recommended_order_qty": item.recommended_order_qty,
                    "estimated_cost": item.estimated_cost,
                    "urgency": item.urgency,
                    "recommendation_type": item.recommendation_type,
                    "confidence": item.confidence,
                    "rationale": item.rationale,
                }
                for item in recommendations
            ],
            "requirements": {
                "summary": "2 to 3 sentences. Mention cash coverage and the most urgent stock risks.",
                "actions": "Return exactly 3 operational next steps.",
                "recommendation_rationales": (
                    "Return one rationale per recommendation SKU. Each rationale should be one short paragraph "
                    "grounded in stock, demand, lead time, EOQ baseline, recommendation type, and urgency."
                ),
            },
        }
        return json.dumps(payload, ensure_ascii=True)

    def answer_workspace_question(
        self,
        *,
        workspace_snapshot: dict[str, Any],
        question: str,
    ) -> dict[str, Any] | None:
        request_kwargs = self._build_request(
            model_input=json.dumps(
                {
                    "question": question,
                    "workspace_snapshot": workspace_snapshot,
                },
                ensure_ascii=True,
            ),
            instructions=(
                "You are a practical supply chain assistant for a small business in Haiti. "
                "Answer using only the provided workspace data. Be concise, specific, and operational. "
                "If a supplier negotiation strategy is asked for, give supplier-comparison advice rather than pretending to contact vendors."
                " Return JSON with keys answer, confidence, refused, refusal_reason."
            ),
            schema_name="guarded_workspace_chat",
            max_output_tokens=700,
            schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "answer": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "refused": {"type": "boolean"},
                    "refusal_reason": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                },
                "required": ["answer", "confidence", "refused", "refusal_reason"],
            },
        )
        parsed = self._run_structured_response(
            request_kwargs=request_kwargs,
            feature="chat",
            input_preview=question,
            default_reason="OpenAI returned no output_text.",
        )
        if not parsed:
            return None
        output_validation = validate_chat_output(parsed.get("answer", ""))
        status = "refused" if parsed.get("refused") else (
            "accepted" if output_validation.allowed and parsed.get("confidence") != "low" else "fallback"
        )
        token_usage = {
            "input_tokens": self.last_audit_event.get("input_tokens") if self.last_audit_event else None,
            "output_tokens": self.last_audit_event.get("output_tokens") if self.last_audit_event else None,
            "total_tokens": self.last_audit_event.get("total_tokens") if self.last_audit_event else None,
        }
        self.last_audit_event = {
            "feature": "chat",
            "used_ai": status == "accepted",
            "status": status,
            "input_preview": question[:240],
            "output_preview": parsed.get("answer", "")[:240],
            "confidence": parsed.get("confidence", "low"),
            "reason": parsed.get("refusal_reason") or output_validation.reason,
            **token_usage,
        }
        if not output_validation.allowed:
            return None
        return parsed

    def create_morning_brief(self, *, workspace_snapshot: dict[str, Any]) -> dict[str, Any] | None:
        request_kwargs = self._build_request(
            model_input=json.dumps(workspace_snapshot, ensure_ascii=True),
            instructions=(
                "You are preparing a morning operations brief for a supply-chain workspace. "
                "Summarize the most important risks and next actions for today only. Keep it practical and concise."
            ),
            schema_name="morning_brief",
            max_output_tokens=500,
            schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "summary": {"type": "string"},
                    "priorities": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["summary", "priorities", "confidence"],
            },
        )
        return self._run_structured_response(
            request_kwargs=request_kwargs,
            feature="brief",
            input_preview="morning brief",
            default_reason="OpenAI returned no output_text.",
        )

    def analyze_cash_scenario(
        self,
        *,
        business: Business,
        report: ReplenishmentReport | None,
        scenario_cash: float,
    ) -> dict[str, Any] | None:
        if not report:
            self.last_audit_event = {
                "feature": "scenario",
                "used_ai": False,
                "status": "fallback",
                "input_preview": f"{scenario_cash}",
                "output_preview": None,
                "confidence": "low",
                "reason": "No report available.",
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
            }
            return None
        request_kwargs = self._build_request(
            model_input=json.dumps(
                {
                    "business": business.model_dump(mode="json"),
                    "scenario_cash": scenario_cash,
                    "report": report.model_dump(mode="json"),
                },
                ensure_ascii=True,
            ),
            instructions=(
                "You are analyzing a cash-constrained purchasing scenario for a small business. "
                "Recommend what should be bought first within the given cash cap and what should be deferred."
            ),
            schema_name="cash_scenario",
            max_output_tokens=650,
            schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "summary": {"type": "string"},
                    "recommended_skus": {"type": "array", "items": {"type": "string"}},
                    "deferred_skus": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["summary", "recommended_skus", "deferred_skus", "confidence"],
            },
        )
        return self._run_structured_response(
            request_kwargs=request_kwargs,
            feature="scenario",
            input_preview=f"cash {scenario_cash}",
            default_reason="OpenAI returned no output_text.",
        )

    def compare_reports(
        self,
        *,
        latest_report: ReplenishmentReport,
        previous_report: ReplenishmentReport,
    ) -> dict[str, Any] | None:
        request_kwargs = self._build_request(
            model_input=json.dumps(
                {
                    "latest_report": latest_report.model_dump(mode="json"),
                    "previous_report": previous_report.model_dump(mode="json"),
                },
                ensure_ascii=True,
            ),
            instructions=(
                "Compare two replenishment reports and summarize what changed operationally. "
                "Focus on stock risk, spend, and recommendation shifts."
            ),
            schema_name="report_comparison",
            max_output_tokens=550,
            schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "summary": {"type": "string"},
                    "changes": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["summary", "changes", "confidence"],
            },
        )
        return self._run_structured_response(
            request_kwargs=request_kwargs,
            feature="comparison",
            input_preview=f"{latest_report.report_id}->{previous_report.report_id}",
            default_reason="OpenAI returned no output_text.",
        )
