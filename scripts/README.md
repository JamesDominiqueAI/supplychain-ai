# Scripts

Implemented utilities:

- `run_local.py`: local project runner helper.
- `seed_demo.py`: reset and seed a deterministic local demo workspace.
- `evaluate_project.py`: deterministic product evaluation with external AI/email disabled.
- `check_latency.py`: API latency checker for local or deployed APIs.
- `deploy_aws.sh`: package backend, apply Terraform, build/upload frontend, and apply monitoring.
- `destroy_aws.sh`: remove the AWS deployment in reverse Terraform order.

Run the project evaluation:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --package supplychain-api python scripts/evaluate_project.py
```

Seed a local demo workspace:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --package supplychain-api python scripts/seed_demo.py --reset
```

The script prints the local workspace state file, counts for products/suppliers/reports/orders, and a refusal demo that appears on the `/audit` page.

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
