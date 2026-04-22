# Terraform

This repository now follows the same phased Terraform idea used in the `alex`
project: keep each major deployment concern in its own independent directory so
we can deploy incrementally without forcing the whole platform to be perfect on
day one.

Current phases:

- `1_foundation/` - shared AWS/IAM/auth setup
- `2_database/` - persistent data layer
- `3_agents/` - queues, background workers, AI orchestration
- `4_frontend/` - frontend delivery layer, modeled after the `alex` frontend deployment style
- `5_enterprise/` - CloudWatch dashboards, alarms, and SNS notifications

Notes:

- `4_frontend/` now contains real `S3 + CloudFront` infrastructure instead of only placeholders.
- `5_enterprise/` now contains real monitoring primitives instead of only placeholders.
- The current frontend app still needs a deployment-specific build strategy before it can be published cleanly as a static site through this layer.
