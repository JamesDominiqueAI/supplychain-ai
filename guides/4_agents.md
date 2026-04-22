# Guide 4: Agents

## Agent Strategy

This project should use multiple narrow agents rather than one general model.

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
