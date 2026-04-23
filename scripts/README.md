# Scripts

Suggested utilities:
- local dev runner
- seed demo business
- import CSV data
- deploy frontend
- destroy infrastructure

## AWS Teardown

Use `scripts/destroy_aws.sh` to remove the AWS deployment created by the Terraform layers.
The script destroys layers in reverse order, empties the frontend S3 bucket first, and requires
typing `destroy supplychain-ai` before it deletes anything.

```bash
scripts/destroy_aws.sh
```

Set `SKIP_BUCKET_EMPTY=true` only if you want Terraform to handle the bucket deletion itself.
