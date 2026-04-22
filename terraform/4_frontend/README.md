# Terraform Phase 4: Frontend

This phase now follows the `alex` project pattern more closely:

- private `S3` bucket for frontend artifacts
- `CloudFront` distribution in front of the bucket
- origin access control instead of public bucket hosting
- optional `Lambda + API Gateway` backend resources in the same phase
- outputs for CDN URL, distribution ID, and deploy workflow

Current scope:

- frontend asset bucket
- CloudFront CDN
- SPA-style fallback for `index.html`
- optional backend API deployment resources

Important note:

The frontend now has a dedicated static export build path for `S3 + CloudFront`, and the backend now has a matching optional `Lambda + API Gateway` path. The remaining AWS work is packaging, secrets handling, and eventually replacing SQLite with a cloud-native database.
