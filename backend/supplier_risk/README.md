# Supplier Risk Analyst

Supplier risk is currently surfaced through supplier scorecards, anomalies, dashboard signals, and the `supplier_delay_agent`.

Implemented signals include:

- configured reliability score
- configured lead time
- total/open/arrived/delayed order counts
- late open orders
- on-time rate
- fill rate
- average delay days
- open order value

The supplier delay agent uses the same workspace state to summarize follow-up priorities.
