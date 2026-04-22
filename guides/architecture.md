# Architecture

## High-Level Flow

```text
User -> Frontend -> API -> Aurora
                    |
                    -> SQS job queue -> Planner Agent
                                        |-> Demand Analyst
                                        |-> Replenishment Planner
                                        |-> Supplier Risk Analyst
                                        |-> Cash Flow Guard
                                        -> Operations Narrator
```

## Major Components

### Frontend

- dashboard for inventory health
- purchase recommendations
- supplier view
- weekly operations summary
- alerts and job progress

### Backend API

- tenant-aware CRUD APIs
- inventory balance calculations
- forecast request endpoints
- job triggering and status endpoints
- report retrieval

### Database

Core tables:
- businesses
- users
- locations
- products
- suppliers
- purchase_orders
- purchase_order_lines
- inventory_movements
- stock_snapshots
- forecasts
- analysis_jobs
- reports

### Agents

- Planner:
  - decides which specialist agents to invoke
  - gathers current business state
  - coordinates outputs
- Demand Analyst:
  - predicts short-term demand from historical movements
- Replenishment Planner:
  - proposes purchase quantities and reorder timing
- Supplier Risk Analyst:
  - evaluates vendor delay, concentration, and fill-rate risk
- Cash Flow Guard:
  - constrains recommendations to budget and working capital realities
- Operations Narrator:
  - produces plain-language summaries and action items

## Data Sources

Initial MVP:
- manual data entry
- CSV uploads

Later:
- POS integration
- WhatsApp / chat intake
- invoice parsing
- supplier message ingestion

## AI Usage Philosophy

Use AI where it adds leverage:
- summarization
- explanation
- scenario comparison
- judgment over multiple signals

Do not use AI where deterministic logic is better:
- stock balance arithmetic
- permission checks
- data validation
- threshold alerts

## Success Metrics

- fewer stockouts
- lower dead inventory
- more accurate purchase timing
- faster owner decision-making
- report usefulness and action completion rate
