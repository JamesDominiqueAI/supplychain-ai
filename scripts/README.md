# Scripts

Implemented utilities:

- `run_local.py`: local project runner helper.
- `evaluate_project.py`: deterministic product evaluation with external AI/email disabled.
- `check_latency.py`: API latency checker for local or deployed APIs.
- `deploy_aws.sh`: package backend, apply Terraform, build/upload frontend, and apply monitoring.
- `destroy_aws.sh`: remove the AWS deployment in reverse Terraform order.

Run the project evaluation:

```bash
python scripts/evaluate_project.py
```

Measure API latency:

```bash
python scripts/check_latency.py --api-url "https://your-api-url" --iterations 5
```

Protected endpoints require a Clerk token:

```bash
AUTH_TOKEN="..." python scripts/check_latency.py --api-url "https://your-api-url"
```

Deploy to AWS:

```bash
bash scripts/deploy_aws.sh
```

Destroy AWS resources:

```bash
bash scripts/destroy_aws.sh
```

The destroy script asks you to type `destroy supplychain-ai` before deleting resources. Set `SKIP_BUCKET_EMPTY=true` only if you want Terraform to handle frontend bucket deletion itself.
