# Infrastructure

Two self-contained Terraform root modules, each with its own provider and state backend:

| Directory | Provider        | Backend                                                 | Deploy target | Workflows                                                                                  |
| --------- | --------------- | ------------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------ |
| `civo/`   | `civo/civo`     | Civo Object Store (S3-compatible) bucket `infrastates`  | Civo instance | `civo-terraform-plan/apply/destroy`, `civo-server-setup`, `civo-app-deploy`                |
| `aws/`    | `hashicorp/aws` | S3 bucket `thumbgen-tfstate-017731864396-ap-south-1-an` | EC2 t3.micro  | `aws-terraform-plan/apply/destroy`, `aws-server-setup`, `aws-app-deploy`, `build-push-ecr` |

Each root module requires a distinct working directory. A single root `main.tf` is not
possible because Terraform supports only one backend and provider state per root module.

Run inside a module directory:

```
terraform init
terraform plan
terraform apply
```

GitHub Actions credentials:

- Civo workflows authenticate with the `CIVO_TOKEN` secret and an S3-compatible
  `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` pair for state.
- AWS workflows authenticate with the `thumbgen-bootstrap` IAM user keys
  (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`) for plan/apply/destroy, and with the
  OIDC role `gh-actions-deploy` (secret `AWS_ROLE_ARN`) for image builds.

For the end-to-end deployment runbooks see:

- [`docs/deploy-civo.md`](../docs/deploy-civo.md) : Civo environment
- [`docs/deploy-aws.md`](../docs/deploy-aws.md) : AWS environment
