# Replenishment Planner

Replenishment is implemented through deterministic logic in `backend/database/src/services/replenishment.py` and exposed by `POST /api/analysis/replenishment`.

The planner computes:

- urgency
- days of cover
- predicted 7-day and 30-day demand
- EOQ-style order quantity
- recommended order quantity
- estimated cost
- buy/wait/split recommendation type
- cash affordability at report level
- rationale for each SKU

Optional AI can improve the owner-facing wording, but numeric recommendation fields remain deterministic.
