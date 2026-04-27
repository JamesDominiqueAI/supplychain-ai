# Planner Agent

Planning is implemented through the Operations Manager agent route and the workspace store.

Current routes:

- `GET /api/ai/agents`
- `GET /api/ai/agents/runs`
- `POST /api/ai/agents/operations`
- `POST /api/ai/agents/inventory-risk`
- `POST /api/ai/agents/supplier-delay`
- `POST /api/ai/agents/cash-replenishment`

The Operations Manager coordinates:

- inventory risk review
- supplier delay review
- cash-aware replenishment review

Runs are persisted in the workspace and summarized in AI audit logs. Scheduled runs can be enabled in Lambda with `SCHEDULED_AGENT_ENABLED=true` and a configured `SCHEDULED_AGENT_OWNER_ID`.
