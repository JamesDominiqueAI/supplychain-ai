# Terraform Phase 3: Agents

This phase is reserved for the future async agent layer.

The current product runs replenishment and agents through the FastAPI API and persists jobs, reports, audit logs, and agent runs directly in the workspace store. When workload size requires background processing, this phase should add:

- SQS analysis queue
- dead-letter queue
- planner worker Lambda
- specialist worker Lambdas
- IAM policies for internal agent orchestration
- CloudWatch alarms for queue age and failures
