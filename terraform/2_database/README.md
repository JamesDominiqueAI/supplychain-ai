# Terraform Phase 2: Database

This phase now provisions the active application database:

- `DynamoDB` single-table workspace storage
- server-side encryption
- point-in-time recovery support

The backend now reads and writes workspace state from DynamoDB instead of SQLite.
