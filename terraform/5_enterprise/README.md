# Terraform Phase 5: Enterprise

This phase now follows the `alex` project’s monitoring pattern more closely:

- `SNS` topic for operational alerts
- optional email subscription
- `CloudWatch` operations dashboard
- alarms for frontend CDN and backend Lambda when those IDs are provided

Current scope:

- CloudFront request/error visibility
- API Gateway visibility when an API ID is available
- Lambda error monitoring when a function name is available

This gives the project a real AWS observability foundation instead of placeholder files.
