# Guide 7: Enterprise

This project now includes the beginnings of enterprise posture: tenant isolation, auth, guarded AI, event logs, notification records, deterministic evaluation, and deployable AWS monitoring.

## Security

- Clerk JWT validation protects workspace endpoints.
- The backend derives `owner_user_id` from the signed-in actor.
- Local development fallback auth is configurable and should be disabled in production.
- DynamoDB access is scoped to the workspace table.
- API Lambda uses environment-provided secrets rather than hard-coded credentials.
- CORS is configured for local origins and the deployed frontend.

## Tenant Isolation

The store loads and saves workspace state by owner id. The deterministic evaluation script verifies that a second owner cannot see a custom evaluation SKU or agent run from the first owner.

## Reliability

- Local JSON fallback keeps development usable without AWS.
- DynamoDB point-in-time recovery can be enabled by Terraform.
- Replenishment reports and agent runs are persisted, so outputs remain inspectable after the request finishes.
- Order notifications are stored as events and can be retried.
- Lambda aliases and optional provisioned concurrency support a more stable API deployment.

## AI Governance

- AI is optional per workspace.
- Automation is controlled separately from AI summaries.
- Unsupported external actions are refused.
- Chat topics are restricted to operations, inventory, suppliers, orders, cash, reports, forecasts, sales, movements, anomalies, and delays.
- AI output is structured and validated.
- Fallbacks are deterministic and traceable.
- AI event logs record status, feature, confidence, reason, previews, and token usage.

## Observability

Application endpoint:

- `GET /api/observability/metrics`

It returns request counts, latency, p95 latency, status buckets, error rate, per-route metrics, AI success/fallback/refusal rates, feature counts, and token totals.

AWS monitoring:

- CloudFront requests and error rates
- API Gateway request, error, and latency widgets
- Lambda invocations, errors, duration, and throttles
- SNS-backed alarm notifications

## Evaluation

`scripts/evaluate_project.py` runs a deterministic project evaluation with external AI/email disabled. It checks seed data, stock-risk behavior, replenishment reporting, draft-first auto-orders, chat guardrails, AI event logging, multi-agent persistence, and tenant isolation.

## Remaining Enterprise Gaps

- Role-based permissions are not implemented yet.
- Request metrics are in-memory and should be shipped to a durable metrics backend.
- Async queue workers are planned but not active.
- Advanced data retention, export, and deletion policies are not yet formalized.
- Full CI/CD files should be reviewed alongside the actual GitHub repository configuration.
