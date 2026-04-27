# Demand Analyst

Demand analysis is implemented in the shared store/service layer rather than as a separate worker process today.

Current behavior:

- uses configured average daily demand as a baseline
- incorporates recent inventory movement history
- produces 7-day and 30-day demand estimates
- labels trend direction and confidence
- feeds replenishment recommendations, dashboard forecasts, and anomaly detection

Future expansion can move this module into an async specialist worker when `terraform/3_agents` becomes active.
