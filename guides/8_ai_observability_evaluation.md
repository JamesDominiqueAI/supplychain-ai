# AI, Guardrails, Observability, and Evaluation

This project uses deterministic inventory logic as the system of record, then uses an LLM as a guarded decision-support layer. The LLM improves explanations, scenarios, chat answers, and report summaries, but it does not silently change stock counts, costs, supplier state, or purchase-order status.

## LLM Use Cases

- Replenishment report narration: the deterministic engine computes EOQ-style quantities, urgency, spend, and recommendation type; the LLM can rewrite the summary, actions, and product rationales without changing the numeric recommendation fields.
- Workspace chat: the assistant answers inventory, stock, supplier, order, cash, report, forecast, sales, movement, anomaly, and delay questions from the current workspace snapshot.
- Morning brief: the assistant summarizes today's operational focus from critical items, late orders, anomalies, forecasts, and the latest report.
- Cash scenarios: the assistant explains what to buy or defer under a cash cap.
- Report comparison: the assistant compares the latest report against the previous one and explains operational changes.
- Multi-agent operations: the Operations Manager coordinates specialist agents for inventory risk, supplier delay, and cash-aware replenishment. Specialist runs can also be called directly.

## Structured Outputs

Every LLM feature asks for JSON with a strict shape:

- `report`: `summary`, `actions`, `recommendation_rationales`.
- `chat`: `answer`, `confidence`, `refused`, `refusal_reason`.
- `brief`: `summary`, `priorities`, `confidence`.
- `scenario`: `summary`, `recommended_skus`, `deferred_skus`, `confidence`.
- `comparison`: `summary`, `changes`, `confidence`.

The backend records each event in the AI audit log with feature name, AI usage, accepted/fallback/refused status, confidence, reason, preview fields, and token usage when the provider returns usage data.

## Guardrails

- Input boundary: chat only accepts operations topics related to inventory, suppliers, orders, cash, reports, forecasts, sales, movements, anomalies, and delays.
- Unsupported actions: the assistant refuses prompts asking it to claim external actions such as calling suppliers, negotiating, logging into accounts, or moving money.
- Output boundary: AI chat output is rejected if it is too short, too long, or claims unsupported external actions.
- Fallback behavior: if AI is disabled, unavailable, low confidence, or rejected by guardrails, the backend returns deterministic rule-based answers.
- Automation boundary: AI auto-ordering is draft-first by default and constrained by available cash plus `AI_AUTO_ORDER_MAX_SPEND`.
- Agent boundary: agents are restricted to internal tools. Scheduled agents are disabled by default and require explicit owner/workspace configuration.
- Auditability: prompts and responses are not fully stored, but short previews, reasons, confidence, status, and token counts are logged for traceability.

Prompt-injection hardening is the next guardrail layer. The current tests cover topic and unsupported-action refusal; future tests should include attempts to override system instructions, request hidden prompts, bypass the operations-only topic boundary, or force the assistant to claim an external supplier/payment action.

## Observability

The API exposes `GET /api/observability/metrics` for signed-in workspaces. It returns:

- Request metrics: total requests, average latency, p95 latency, status buckets, server error rate, requests by route, and server errors by route.
- AI metrics: accepted/fallback/refused counts, success rate, fallback rate, refusal rate, feature counts, and total input/output/combined tokens.

Trade-off: request metrics are in-process and reset when the backend worker restarts. AI metrics are summarized from persistent workspace audit logs, so they survive restarts.

The frontend exposes the same governance story in `/audit`. That page lists recent AI audit events with status, feature, reason/refusal text, input and output previews, confidence, token usage, and aggregate success/fallback/refusal rates. A strong demo path is to ask an off-topic chat question, show the refusal in the UI, then point to the persisted audit event.

## Evaluation

Run the deterministic evaluation script:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --package supplychain-api python scripts/evaluate_project.py
```

The script creates an isolated local workspace in `/tmp`, disables external AI/email calls, and checks these scenarios:

- Seed data exists for products, suppliers, and reports.
- Product creation and sale movement can force a critical stock state.
- Replenishment creates a completed job and recommendations.
- AI automation creates draft orders by default.
- Off-topic chat is refused.
- AI audit events are persisted.
- Multi-agent runs delegate to specialist agents and persist run history.
- Tenant isolation checks verify another owner cannot see the evaluation SKU or agent run.

Measure API latency with:

```bash
python scripts/check_latency.py --api-url "https://your-api-url" --iterations 5
```

Protected endpoints require a Clerk session token:

```bash
AUTH_TOKEN="..." python scripts/check_latency.py --api-url "https://your-api-url"
```

Run browser E2E tests after starting the frontend and backend:

```bash
cd frontend
E2E_CLERK_EMAIL="your-test-user@example.com" E2E_CLERK_PASSWORD="..." npm run test:e2e
```

The browser test covers Clerk login, product creation, sale recording, replenishment report generation, manual order placement, and order-page visibility.

## Current Limitations

- The LLM does not perform external supplier calls, negotiations, bank activity, or real purchasing outside the app.
- Forecasting is still lightweight compared with enterprise ML systems, but it combines configured demand, historical movement averages, recent sales, and trend direction.
- Request metrics should eventually be shipped to CloudWatch, Datadog, Grafana, or another production monitoring system.
- E2E login requires Clerk test credentials, so CI must provide `E2E_CLERK_EMAIL` and `E2E_CLERK_PASSWORD`.
- Token costs depend on provider response metadata; fallback and disabled-AI paths record zero or null token usage.
- Resend test mode can only deliver to the verified account email. Sending to arbitrary recipients requires a verified sending domain.
