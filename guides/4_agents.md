# Guide 4: Agents

## Agent Strategy

This project should use multiple narrow agents rather than one general model.

## Implemented Agent Team

The backend now exposes a guarded multi-agent team. The implementation lives in `backend/database/src/agents.py`, while `dynamodb_store.py` stays responsible for persistence, event logging, and workspace state.

- `operations_manager`: coordinates specialist agents and produces the overall run.
- `inventory_risk_agent`: scans critical SKUs, days of cover, and stockout risk.
- `supplier_delay_agent`: monitors late orders and supplier delay exposure.
- `cash_replenishment_agent`: checks cash pressure and can draft replenishment orders when automation is enabled.

API routes:

- `GET /api/ai/agents`
- `GET /api/ai/agents/runs`
- `POST /api/ai/agents/operations`
- `POST /api/ai/agents/inventory-risk`
- `POST /api/ai/agents/supplier-delay`
- `POST /api/ai/agents/cash-replenishment`

The Lambda handler also supports EventBridge scheduled events. Set `ENABLE_SCHEDULED_AGENT=true` and `SCHEDULED_AGENT_OWNER_ID=<workspace owner id>` during deployment to create a scheduled operations-agent run.

## Separation Of Responsibilities

- `OperationsAgentTeam`: orchestrates the run and selects the right specialist path.
- `DynamoDBStore`: owns persistence, agent-run history, event logs, and order creation.
- Specialist agents: return structured `AgentStepResult` records rather than directly mutating state.
- Cash/order drafting: still flows through guarded store methods, so agent code cannot bypass draft-first automation rules.

## Planner Agent

Inputs:
- business context
- inventory health
- supplier state
- requested analysis type

Responsibilities:
- decide which specialist agents to invoke
- gather outputs
- ensure all recommendations are traceable

## Demand Analyst

Inputs:
- product history
- inventory movement history
- recent purchase frequency

Outputs:
- 7-day and 30-day forecast
- confidence level
- demand anomalies

## Replenishment Planner

Inputs:
- current stock
- reorder point
- forecast
- lead time

Outputs:
- recommended order quantity
- reorder urgency
- days until stockout

## Supplier Risk Analyst

Inputs:
- delivery timing
- late deliveries
- single-source concentration
- stock criticality

Outputs:
- supplier risk score
- flagged supplier issues
- mitigation suggestions

## Cash Flow Guard

Inputs:
- available cash
- estimated purchase cost
- urgency by SKU

Outputs:
- what can be bought now
- what should be delayed
- tradeoff summary

## Operations Narrator

Inputs:
- agent outputs
- recent business activity

Outputs:
- owner-friendly summary
- top 3 urgent actions
- explanation of why those actions matter

## Safety Boundaries

- Agents can only use internal workspace tools.
- External supplier calls, negotiations, payments, and off-platform purchases are blocked.
- Draft order creation requires both `ai_enabled` and `ai_automation_enabled`.
- Scheduled runs are disabled by default and require an explicit workspace owner id.
- Every run is stored and summarized in the internal AI event log.
