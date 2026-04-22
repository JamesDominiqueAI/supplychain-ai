# Guide 2: Data Model

## Multi-Tenant Model

Every record belongs to a business.

Key relationships:
- business -> users
- business -> locations
- business -> products
- business -> suppliers
- product -> inventory movements
- product -> purchase order lines
- business -> analysis jobs
- business -> reports

## Core Entities

### products

- product_id
- business_id
- sku
- name
- category
- unit
- reorder_point
- target_days_of_cover
- active

### suppliers

- supplier_id
- business_id
- name
- contact_phone
- lead_time_days
- reliability_score
- notes

### inventory_movements

- movement_id
- business_id
- location_id
- product_id
- movement_type
- quantity
- unit_cost
- occurred_at
- source_reference

### purchase_orders

- po_id
- business_id
- supplier_id
- status
- expected_delivery_date
- total_amount

### stock_snapshots

- snapshot_id
- business_id
- location_id
- product_id
- on_hand
- reserved
- available
- snapshot_at

### forecasts

- forecast_id
- business_id
- product_id
- horizon_days
- predicted_units
- confidence
- generated_at

### analysis_jobs

- job_id
- business_id
- requested_by
- job_type
- status
- request_payload
- result_payload
- created_at
- completed_at

## Validation Rules

- SKU unique within a business
- no negative received quantity
- stock balance derived from movements or validated snapshots
- purchase recommendations must cite source assumptions
- all reports must include business_id and generated_at
