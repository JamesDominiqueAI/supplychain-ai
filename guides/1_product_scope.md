# Guide 1: Product Scope

## Problem

Many small businesses operate inventory through memory, notebooks, messaging threads, and spreadsheets. They know stock and cash are under pressure, but they cannot easily answer:

- what is selling fastest
- what is at risk of stockout
- what should be reordered now
- whether there is enough cash to buy inventory
- which supplier is becoming unreliable
- what changed since the last operations review

## Product Goal

Deliver a workspace that helps one business track inventory, manage suppliers and orders, generate replenishment recommendations, and receive plain-language operational guidance without adopting a full ERP system.

## Primary User Story

As a small business owner, I want the system to tell me what to reorder this week, how much to buy, what it will cost, and why, without needing to interpret raw spreadsheets.

## Implemented Product Surface

- Clerk-protected workspace
- product catalog
- supplier catalog and scorecards
- inventory movement tracking
- inventory health dashboard
- forecast and anomaly signals
- purchase-order creation and receiving
- late-order and notification event visibility
- replenishment report generation
- CSV report export
- cash scenario analysis
- report comparison
- workspace AI chat with guardrails
- morning brief
- multi-agent operations review
- AI event and observability metrics
- settings for cash, AI, automation, notification email, and critical alerts

## Non-Goals

- accounting system replacement
- route optimization for delivery fleets
- real supplier negotiation or payments
- external marketplace/POS integrations at launch
- offline mobile app
- advanced ML forecasting research
- multi-country tax logic

## Product Principles

- plain language first
- deterministic operations logic before AI wording
- every recommendation should explain why
- AI must refuse unsupported external actions
- draft risky actions before execution
- make low-data environments workable
- prioritize owner decisions over vanity dashboards

## Demo Narrative

1. Add or review products and suppliers.
2. Record a sale that pushes a SKU into critical risk.
3. Open the dashboard and inspect the risk, forecast, anomaly, and morning brief.
4. Generate a replenishment report.
5. Review recommended quantities, estimated spend, and actions.
6. Draft or place a purchase order.
7. Receive the order and watch inventory recover.
8. Ask the workspace AI a grounded operations question.
9. Open observability metrics to show governance.
