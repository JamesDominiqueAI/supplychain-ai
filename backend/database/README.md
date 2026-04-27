# Database Module

This module owns the active workspace model and persistence logic.

Implemented pieces:

- `schemas.py`: Pydantic models for business settings, products, suppliers, movements, orders, reports, jobs, AI audit logs, agent runs, notifications, and request payloads.
- `dynamodb_store.py`: tenant-scoped workspace store backed by DynamoDB in production and local JSON in development/test.
- `agents.py`: separated operations-agent team, including the operations manager and specialist risk, delay, and cash agents.
- `demo_store.py`: local/demo helper surface.
- `guardrails.py`: chat and unsupported-action boundaries.
- `notifications.py`: email notification adapter and event recording support.
- `services/replenishment.py`: deterministic replenishment calculation service.

The store is keyed by `owner_user_id`, which comes from the authenticated actor. Local mode can be forced with `DYNAMODB_USE_LOCAL=true`.
