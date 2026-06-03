# Infrastructure

Kubernetes + Terraform on AWS EKS targeting **10K+ RPS** (ap-south-1).

---

## Table of Contents

1. [Architecture](#architecture)
2. [Directory Layout](#directory-layout)
3. [Prerequisites](#prerequisites)
4. [First-time Deployment](#first-time-deployment)
5. [Terraform Modules Reference](#terraform-modules-reference)
6. [Kubernetes Manifests Reference](#kubernetes-manifests-reference)
7. [Secrets Management](#secrets-management)
8. [CI/CD Pipeline](#cicd-pipeline)
9. [Day-2 Operations](#day-2-operations)
10. [Scaling](#scaling)
11. [Adding HTTPS](#adding-https)
12. [Teardown / Destroy](#teardown--destroy)
13. [Troubleshooting](#troubleshooting)
14. [Known Errors and Fixes](#known-errors-and-fixes)

---

## Architecture

```
Internet
    │
    ▼
AWS ALB  ← created and managed by the AWS Load Balancer Controller
    │        (annotations in infra/kubernetes/ingress/ingress.yaml)
    │
    ▼  (target-type: ip — routes directly to pod IPs, not node ports)
Nginx pods  ×2
    │
    ├── /api/*  strip prefix ──► backend Service ──► backend pods  ×3–30  (HPA)
    │                                                    │
    │                                          ┌─────────┴──────────┐
    │                                          ▼                    ▼
    │                                   RDS PostgreSQL 16    ElastiCache Redis 7
    │                                   (Multi-AZ)           (cluster, 3 shards)
    │
    └── /*  ────────────────────────► frontend Service ──► frontend pods  ×2–10  (HPA)

celery-worker pods  ×2–15 (HPA)  ──► Redis broker
celery-beat pod     ×1  (Recreate — singleton)

Nodes: c6i.xlarge, 3–15 (Cluster Autoscaler manages ASG)

Secrets path:
AWS Secrets Manager (issue-tracker/production)
    └── External Secrets Operator
            └── K8s Secret: app-secrets (namespace: issue-tracker)
                    └── envFrom in backend, frontend, celery pods
```

### Throughput capacity

| Component | Peak replicas | Workers/pod | Estimate |
|---|---|---|---|
| backend | 30 (HPA max) | 4 uvicorn | 12K–24K RPS |
| nginx | 2 (fixed) | auto (cores) | not a bottleneck |
| RDS | Multi-AZ | — | ~5K QPS with connection pooling |
| Redis | 3 shards × 2 nodes | — | >100K ops/s |

---

## Directory Layout

```
infra/
├── terraform/
│   ├── modules/
│   │   ├── vpc/            VPC, 3 public + 3 private subnets, 3 NAT gateways
│   │   ├── eks/            EKS cluster, node group, OIDC, addons, Helm releases
│   │   ├── rds/            PostgreSQL 16 instance, parameter group, secrets
│   │   ├── elasticache/    Redis 7 cluster mode (3 shards, 1 replica each)
│   │   ├── ecr/            ECR repos + lifecycle policies (keep last 20 images)
│   │   └── iam/            IRSA roles + GitHub Actions OIDC role
│   └── environments/
│       └── production/
│           ├── main.tf         Root module — wires all modules, EKS access entries
│           ├── variables.tf    All configurable inputs with defaults
│           ├── outputs.tf      Exports: endpoints, role ARNs, cluster name
│           ├── versions.tf     Provider versions + S3 backend config
│           └── terraform.tfvars  Your actual values (gitignored)
├── kubernetes/
│   ├── namespace.yaml
│   ├── configmap.yaml                Non-sensitive env vars (APP_ENV, WEB_CONCURRENCY, ...)
│   ├── backend/
│   │   ├── serviceaccount.yaml       IRSA annotation (must be applied BEFORE migration Job)
│   │   ├── deployment.yaml           3 replicas, rolling update
│   │   ├── service.yaml
│   │   ├── hpa.yaml                  min 3, max 30, CPU 60% + memory 75%
│   │   └── pdb.yaml                  minAvailable: 2
│   ├── frontend/
│   │   ├── deployment.yaml           2 replicas
│   │   ├── service.yaml
│   │   ├── hpa.yaml                  min 2, max 10, CPU 70%
│   │   └── pdb.yaml                  minAvailable: 1
│   ├── nginx/
│   │   ├── configmap.yaml            nginx.conf (upstream pools, /nginx-health, proxy rules)
│   │   ├── deployment.yaml           2 replicas, probes on /nginx-health
│   │   └── service.yaml
│   ├── celery/
│   │   ├── worker-deployment.yaml    2 replicas, rolling update
│   │   ├── worker-hpa.yaml           min 2, max 15, CPU 70%
│   │   └── beat-deployment.yaml      1 replica, Recreate strategy (singleton)
│   ├── ingress/
│   │   └── ingress.yaml              AWS ALB, HTTP:80 (see Adding HTTPS below)
│   ├── secrets/
│   │   └── external-secrets.yaml     ClusterSecretStore + ExternalSecret
│   └── jobs/
│       └── migrate-job.yaml          Template — MIGRATE_IMAGE substituted by pipeline
└── scripts/
    ├── bootstrap.sh       One-time: creates S3 state bucket, DynamoDB lock table,
    │                      and Secrets Manager skeleton secret
    └── kubeconfig.sh      Updates local kubectl context for the EKS cluster
```

---

## Prerequisites

Install these tools before running anything:

| Tool | Version | Install |
|---|---|---|
| AWS CLI | v2+ | https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html |
| Terraform | ≥1.6 | https://developer.hashicorp.com/terraform/install |
| kubectl | any recent | https://kubernetes.io/docs/tasks/tools/ |
| git bash / WSL | — | For running shell scripts on Windows |

Configure AWS CLI with admin credentials:

```bash
aws configure
# AWS Access Key ID: ...
# AWS Secret Access Key: ...
# Default region: ap-south-1
# Default output format: json
```

Verify:

```bash
aws sts get-caller-identity
# should print your account ID and IAM user/role ARN
```

---

## First-time Deployment

Run each step in order. **Do not skip steps** — later steps depend on resources created earlier.

### Step 1 — Bootstrap AWS prerequisites

Creates the S3 bucket for Terraform remote state, DynamoDB table for state locking, and a skeleton Secrets Manager secret.

```bash
export AWS_REGION=ap-south-1
bash infra/scripts/bootstrap.sh
```

This is a **one-time operation**. Running it again is safe (it skips already-created resources).

### Step 2 — Fill Terraform variables

```bash
cd infra/terraform/environments/production

# Create your variables file (it is gitignored)
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and set at minimum:

```hcl
github_org        = "YourGitHubOrgOrUsername"
github_repo       = "issue-tracker"
s3_uploads_bucket = "your-globally-unique-bucket-name"
```

All other variables have sensible defaults. See `variables.tf` for the full list.

### Step 3 — Provision all infrastructure

```bash
# From infra/terraform/environments/production/
terraform init
terraform plan          # review — expect ~55 resources on first apply
terraform apply         # takes 15–25 minutes (EKS cluster creation is the slowest)
```

> **Note on timing**: EKS cluster creation takes ~10 minutes. RDS takes ~8 minutes.
> ElastiCache takes ~7 minutes. The Helm releases (LB controller, External Secrets)
> each take 1–2 minutes. Total wall time is typically 20–25 minutes.

After apply succeeds, capture the outputs:

```bash
terraform output github_actions_role_arn   # → paste into GitHub Secrets
terraform output rds_endpoint              # → used to build DATABASE_URL
terraform output redis_endpoint            # → used to build REDIS_URL
terraform output backend_irsa_role_arn     # → already in serviceaccount.yaml
```

### Step 4 — Grant your IAM user EKS access

The EKS cluster auth mode is `API_AND_CONFIG_MAP`. If your IAM user is not the one that created the cluster (e.g. you are running on a different profile), add yourself:

```bash
aws eks create-access-entry \
  --cluster-name issue-tracker-production \
  --principal-arn $(aws sts get-caller-identity --query Arn --output text) \
  --region ap-south-1

aws eks associate-access-policy \
  --cluster-name issue-tracker-production \
  --principal-arn $(aws sts get-caller-identity --query Arn --output text) \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope '{"type":"cluster"}' \
  --region ap-south-1
```

The GitHub Actions role access entry is managed automatically by Terraform.

### Step 5 — Configure kubectl

```bash
aws eks update-kubeconfig \
  --region ap-south-1 \
  --name issue-tracker-production

kubectl get nodes    # should show 3 nodes in Ready state
```

### Step 6 — Populate AWS Secrets Manager

Navigate to **AWS Console → Secrets Manager → `issue-tracker/production`** and update the JSON secret with real values:

```json
{
  "DATABASE_URL": "postgresql+asyncpg://issueadmin:PASSWORD@HOSTNAME:5432/issuetracker",
  "REDIS_URL": "rediss://:AUTH_TOKEN@CLUSTER_CFG_ENDPOINT:6379/0",
  "JWT_SECRET_KEY": "run: openssl rand -hex 32",
  "JWT_REFRESH_SECRET_KEY": "run: openssl rand -hex 32  (different value)",
  "S3_BUCKET_NAME": "your-uploads-bucket-name",
  "SMTP_HOST": "email-smtp.ap-south-1.amazonaws.com",
  "SMTP_USERNAME": "AKIA... (SES SMTP username)",
  "SMTP_PASSWORD": "SES SMTP password (NOT the IAM secret key)",
  "NEXT_PUBLIC_API_URL": "http://YOUR-ALB-DNS-NAME"
}
```

Get the connection string components:

```bash
# RDS endpoint (hostname:port)
terraform output rds_endpoint

# RDS password (stored by Terraform in Secrets Manager)
aws secretsmanager get-secret-value \
  --secret-id issue-tracker/rds-password \
  --query SecretString --output text \
  --region ap-south-1

# Redis cluster config endpoint
terraform output redis_endpoint

# Redis auth token
aws secretsmanager get-secret-value \
  --secret-id issue-tracker/redis-auth-token \
  --query SecretString --output text \
  --region ap-south-1
```

> **DATABASE_URL format**: password may contain special characters — URL-encode them if needed.
> **REDIS_URL**: use `rediss://` (double-s) for TLS. The cluster config endpoint
> (`clustercfg.xxx`) is the correct endpoint for Redis cluster mode.

### Step 7 — Set GitHub Secrets

Go to **GitHub → Your repo → Settings → Secrets and variables → Actions → New repository secret**:

| Secret name | Value |
|---|---|
| `AWS_GITHUB_ACTIONS_ROLE_ARN` | Output from `terraform output github_actions_role_arn` |
| `NEXT_PUBLIC_API_URL` | `http://` + your ALB DNS name (available after first deploy as `kubectl get ingress -n issue-tracker`) |

> Set `NEXT_PUBLIC_API_URL` to a placeholder (`http://placeholder.com`) for the very first deploy.
> After the first deploy, get the real ALB DNS from `kubectl get ingress -n issue-tracker`,
> update the secret, and redeploy the frontend.

### Step 8 — Apply base Kubernetes manifests

These must be applied before the pipeline runs for the first time:

```bash
kubectl apply -f infra/kubernetes/namespace.yaml
kubectl apply -f infra/kubernetes/backend/serviceaccount.yaml
kubectl apply -f infra/kubernetes/configmap.yaml
kubectl apply -f infra/kubernetes/secrets/external-secrets.yaml

# Wait for External Secrets to sync (creates the app-secrets K8s Secret)
kubectl get externalsecret -n issue-tracker
# STATUS should be SecretSynced = True
```

### Step 9 — Push to main

The GitHub Actions pipeline handles everything from here:
tests → build → DB migration Job → rolling deploy.

---

## Terraform Modules Reference

### `modules/vpc`

Creates the network foundation.

| Resource | Details |
|---|---|
| VPC | `10.0.0.0/16` (configurable via `vpc_cidr`) |
| Public subnets | 3 subnets (one per AZ), tagged `kubernetes.io/role/elb=1` for ALB |
| Private subnets | 3 subnets (one per AZ), tagged `kubernetes.io/role/internal-elb=1` |
| NAT Gateways | 3 (one per AZ) — set `single_nat_gateway = true` to use only 1 (saves ~$90/month but loses AZ redundancy) |

### `modules/eks`

Creates the Kubernetes cluster and installs all required controllers.

| Resource | Details |
|---|---|
| EKS Cluster | Kubernetes 1.30, auth mode `API_AND_CONFIG_MAP` |
| Node group | `c6i.xlarge`, 3–15 nodes, auto-scales via Cluster Autoscaler |
| Add-ons | vpc-cni, coredns, kube-proxy, aws-ebs-csi-driver |
| Helm: Metrics Server | Required for HPA CPU/memory scaling |
| Helm: Cluster Autoscaler | Scales nodes in/out based on pending pods |
| Helm: AWS LB Controller | Creates/manages ALB from Ingress resources |
| Helm: External Secrets Operator | Syncs AWS Secrets Manager → K8s Secrets |

**Critical**: the LB Controller Helm release requires `region` and `vpcId` to be set. Without them, the controller pods fail to start and the Helm release times out.

### `modules/rds`

PostgreSQL 16 instance.

| Setting | Value |
|---|---|
| Instance class | `db.r6g.large` (configurable) |
| Multi-AZ | enabled |
| Storage | 100 GB gp3, auto-scales to 1 TB |
| Encryption | enabled (AWS managed key) |
| Deletion protection | disabled (`deletion_protection = false`) |
| Final snapshot | skipped (`skip_final_snapshot = true`) — destroy is clean with no manual steps |
| Backups | 7-day retention |
| Parameter group | `max_connections=500`, `work_mem=4096kB`, `maintenance_work_mem=128MB`, slow query logging ≥500ms |

**Parameter group rule**: do not add `shared_buffers` or `effective_cache_size` using `{DBInstanceClassMemory/x}` formulas unless you account for the parameter's native unit (8kB blocks). Using `{DBInstanceClassMemory/4}` sets shared_buffers to petabytes and puts the instance in `incompatible-parameters` state. See [Known Errors and Fixes](#known-errors-and-fixes).

### `modules/elasticache`

Redis 7 in cluster mode.

| Setting | Value |
|---|---|
| Node type | `cache.r6g.large` (configurable) |
| Shards | 3 (`redis_num_shards`) |
| Replicas per shard | 1 (6 nodes total) |
| TLS | enabled (use `rediss://` in connection string) |
| Auth token | auto-generated, stored in Secrets Manager at `issue-tracker/redis-auth-token` |
| Parameter group | Must include `cluster-enabled = yes` for cluster mode (>1 shard) |

### `modules/ecr`

Two ECR repositories: `issue-tracker-backend` and `issue-tracker-frontend`.
- Image scanning on push enabled
- Lifecycle policy: keep last 20 images, delete older ones

### `modules/iam`

| Role | Used by | Permissions |
|---|---|---|
| `issue-tracker-github-actions` | GitHub Actions OIDC | ECR push, EKS describe |
| `issue-tracker-backend-pod` | Backend K8s ServiceAccount (IRSA) | S3 read/write on uploads bucket, Secrets Manager read |
| `issue-tracker-cluster-autoscaler` | Cluster Autoscaler ServiceAccount (IRSA) | ASG describe/scale |
| `issue-tracker-lb-controller` | LB Controller ServiceAccount (IRSA) | EC2/ELB describe and manage |
| `issue-tracker-external-secrets` | External Secrets ServiceAccount (IRSA) | Secrets Manager read |

---

## Kubernetes Manifests Reference

### Applying manifests

```bash
# Apply a single file
kubectl apply -f infra/kubernetes/backend/deployment.yaml

# Apply a directory
kubectl apply -f infra/kubernetes/backend/

# Apply all manifests (in dependency order — see pipeline for correct order)
kubectl apply -f infra/kubernetes/namespace.yaml
kubectl apply -f infra/kubernetes/configmap.yaml
kubectl apply -f infra/kubernetes/secrets/external-secrets.yaml
kubectl apply -f infra/kubernetes/backend/serviceaccount.yaml
kubectl apply -f infra/kubernetes/nginx/configmap.yaml
kubectl apply -f infra/kubernetes/nginx/deployment.yaml
kubectl apply -f infra/kubernetes/nginx/service.yaml
kubectl apply -f infra/kubernetes/backend/service.yaml
kubectl apply -f infra/kubernetes/backend/hpa.yaml
kubectl apply -f infra/kubernetes/backend/pdb.yaml
kubectl apply -f infra/kubernetes/frontend/service.yaml
kubectl apply -f infra/kubernetes/frontend/hpa.yaml
kubectl apply -f infra/kubernetes/frontend/pdb.yaml
kubectl apply -f infra/kubernetes/celery/worker-hpa.yaml
kubectl apply -f infra/kubernetes/ingress/ingress.yaml
```

### ConfigMap (`configmap.yaml`)

Contains non-sensitive env vars injected into all pods via `envFrom.configMapRef`.

| Key | Value | Notes |
|---|---|---|
| `APP_ENV` | `production` | |
| `WEB_CONCURRENCY` | `4` | gunicorn workers per backend pod |
| `FILE_STORAGE_BACKEND` | `s3` | |
| `AWS_REGION` | `ap-south-1` | |
| `SMTP_PORT` | `587` | |
| `SMTP_USE_TLS` | `true` | |

### ExternalSecret (`secrets/external-secrets.yaml`)

Syncs `issue-tracker/production` from AWS Secrets Manager to the `app-secrets` K8s Secret every hour.

Keys synced:

| Secret Manager key | K8s Secret key |
|---|---|
| `DATABASE_URL` | `DATABASE_URL` |
| `REDIS_URL` | `REDIS_URL` |
| `JWT_SECRET_KEY` | `JWT_SECRET_KEY` |
| `JWT_REFRESH_SECRET_KEY` | `JWT_REFRESH_SECRET_KEY` |
| `S3_BUCKET_NAME` | `S3_BUCKET_NAME` |
| `SMTP_HOST` | `SMTP_HOST` |
| `SMTP_USERNAME` | `SMTP_USERNAME` |
| `SMTP_PASSWORD` | `SMTP_PASSWORD` |
| `NEXT_PUBLIC_API_URL` | `NEXT_PUBLIC_API_URL` |

Force an immediate re-sync:

```bash
kubectl annotate externalsecret app-secrets \
  -n issue-tracker \
  force-sync=$(date +%s) \
  --overwrite
```

### ServiceAccount (`backend/serviceaccount.yaml`)

Contains the IRSA annotation linking the K8s ServiceAccount to the AWS IAM role:

```yaml
annotations:
  eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT:role/issue-tracker-backend-pod
```

**This file must be applied before the migration Job runs.** The Job uses `serviceAccountName: backend`. If the ServiceAccount does not exist, the Job pod fails immediately with `serviceaccount "backend" not found`.

### Nginx ConfigMap (`nginx/configmap.yaml`)

Key routing rules:

```nginx
location /nginx-health {         # Health probe endpoint — returns 200 directly
    return 200 "ok\n";           # Does NOT proxy to any upstream
}

location /api/ {
    proxy_pass http://backend_upstream/;   # Strips /api/ prefix
}

location / {
    proxy_pass http://frontend_upstream;  # Everything else → Next.js
}
```

The liveness and readiness probes in `nginx/deployment.yaml` hit `/nginx-health`. **Never change the probe path to `/`** — that proxies to the frontend upstream, which causes nginx to fail its own health check when frontend pods are not running.

### Migration Job (`jobs/migrate-job.yaml`)

Template file — the `${MIGRATE_IMAGE}` placeholder is substituted at deploy time:

```bash
export MIGRATE_IMAGE="123456.dkr.ecr.ap-south-1.amazonaws.com/issue-tracker-backend:SHA"
envsubst < infra/kubernetes/jobs/migrate-job.yaml | kubectl apply -f -
```

The Job runs `scripts/migrate.sh` (alembic upgrade head + optional seed) and exits. The pipeline waits up to 5 minutes for completion then prints logs and deletes the Job.

---

## Secrets Management

All sensitive values live in **AWS Secrets Manager**, never in code or ConfigMaps.

### Secret structure

One JSON secret at path `issue-tracker/production`:

```json
{
  "DATABASE_URL": "...",
  "REDIS_URL": "...",
  "JWT_SECRET_KEY": "...",
  "JWT_REFRESH_SECRET_KEY": "...",
  "S3_BUCKET_NAME": "...",
  "SMTP_HOST": "...",
  "SMTP_USERNAME": "...",
  "SMTP_PASSWORD": "...",
  "NEXT_PUBLIC_API_URL": "..."
}
```

Two additional secrets are auto-created by Terraform:

| Path | Contents |
|---|---|
| `issue-tracker/rds-password` | RDS master password (plain string) |
| `issue-tracker/redis-auth-token` | ElastiCache auth token (plain string) |

### Update a secret value

```bash
# Update the entire JSON secret
aws secretsmanager put-secret-value \
  --secret-id issue-tracker/production \
  --secret-string '{"DATABASE_URL":"...","REDIS_URL":"...",...}' \
  --region ap-south-1

# Force External Secrets to re-sync immediately
kubectl annotate externalsecret app-secrets \
  -n issue-tracker \
  force-sync=$(date +%s) \
  --overwrite
```

After syncing, roll out pods to pick up the new secret:

```bash
kubectl rollout restart deployment/backend -n issue-tracker
```

---

## CI/CD Pipeline

The single pipeline file is `.github/workflows/deploy.yml`.

### Job graph

```
changes ──┬──► test-backend  ──► build-backend  ──┐
          │                                        ├──► deploy
          └──► test-frontend ──► build-frontend ──┘
```

- `changes`: detects which directories were modified (`backend/` or `frontend/`)
- `test-*`: skipped if the corresponding directory did not change (saves CI minutes)
- `build-*`: skipped if corresponding tests were skipped or failed
- `deploy`: runs if at least one build succeeded or if triggered via `workflow_dispatch`

### Forcing a full run

Use **workflow_dispatch** (manual trigger). Both test conditions include `|| github.event_name == 'workflow_dispatch'` which bypasses the path filter.

GitHub → Actions → "CI / CD — Deploy to Kubernetes" → **Run workflow**

### Required GitHub Secrets

| Secret | Source |
|---|---|
| `AWS_GITHUB_ACTIONS_ROLE_ARN` | `terraform output github_actions_role_arn` |
| `NEXT_PUBLIC_API_URL` | ALB DNS or your domain |

The pipeline uses OIDC (no long-lived AWS credentials stored in GitHub). The GitHub Actions role must have EKS cluster admin access — see Step 4 of First-time Deployment.

---

## Day-2 Operations

### Check cluster health

```bash
kubectl get nodes
kubectl get pods -n issue-tracker
kubectl get hpa -n issue-tracker
kubectl get ingress -n issue-tracker
```

### View logs

```bash
# Stream backend logs (all pods)
kubectl logs -f -l app=backend -n issue-tracker --max-log-requests=10

# Logs for a specific pod
kubectl logs POD_NAME -n issue-tracker

# Previous container logs (after a crash)
kubectl logs POD_NAME -n issue-tracker --previous
```

### Restart a deployment

```bash
kubectl rollout restart deployment/backend -n issue-tracker
kubectl rollout status deployment/backend -n issue-tracker --timeout=10m
```

### Roll back to the previous image

```bash
kubectl rollout undo deployment/backend -n issue-tracker
kubectl rollout status deployment/backend -n issue-tracker --timeout=10m
```

### Force re-deploy without pushing code

```bash
# Via GitHub CLI
gh workflow run deploy.yml

# Or via GitHub UI: Actions → Run workflow
```

### Update a Kubernetes manifest without a pipeline run

```bash
kubectl apply -f infra/kubernetes/nginx/configmap.yaml
kubectl rollout restart deployment/nginx -n issue-tracker
```

Always apply the file **before** the rollout restart — restart uses the current spec in the cluster, which only reflects the manifest after `kubectl apply`.

### Access the EKS cluster from a new machine

```bash
aws eks update-kubeconfig \
  --region ap-south-1 \
  --name issue-tracker-production
```

### Check External Secret sync status

```bash
kubectl get externalsecret -n issue-tracker
kubectl describe externalsecret app-secrets -n issue-tracker
```

### Check migration job logs

```bash
kubectl logs job/db-migrate -n issue-tracker
```

---

## Scaling

### Scale pods (immediately, no Terraform change needed)

Edit the HPA manifest and apply:

```bash
# Edit infra/kubernetes/backend/hpa.yaml — change maxReplicas
kubectl apply -f infra/kubernetes/backend/hpa.yaml
```

### Scale workers per pod

Edit `infra/kubernetes/configmap.yaml`, change `WEB_CONCURRENCY`, apply, restart backend:

```bash
kubectl apply -f infra/kubernetes/configmap.yaml
kubectl rollout restart deployment/backend -n issue-tracker
```

### Scale nodes

Change `node_max_size` in `terraform.tfvars` → `terraform apply`. The Cluster Autoscaler handles actual scaling automatically.

### Change node instance type

Change `node_instance_type` in `terraform.tfvars` → `terraform apply`. This replaces the managed node group with a rolling node drain — existing pods are rescheduled onto new nodes.

---

## Adding HTTPS

When you have a domain and an ACM certificate:

1. Get the certificate ARN from ACM console (must be in `ap-south-1`).
2. Edit `infra/kubernetes/ingress/ingress.yaml` — uncomment and fill:
   ```yaml
   alb.ingress.kubernetes.io/certificate-arn: "arn:aws:acm:ap-south-1:ACCOUNT:certificate/..."
   alb.ingress.kubernetes.io/listen-ports: '[{"HTTP":80},{"HTTPS":443}]'
   alb.ingress.kubernetes.io/ssl-redirect: "443"
   ```
3. `kubectl apply -f infra/kubernetes/ingress/ingress.yaml`
4. Update `NEXT_PUBLIC_API_URL` GitHub Secret to `https://yourdomain.com`.
5. Update `NEXT_PUBLIC_API_URL` in Secrets Manager to `https://yourdomain.com`.
6. Trigger a frontend rebuild (GitHub Actions → Run workflow) so the new URL is baked into the Next.js bundle.

---

## Teardown / Destroy

> **Critical rule**: the S3 state bucket and DynamoDB lock table are the Terraform backend.
> They must be deleted **last** — only after `terraform destroy` finishes successfully.
> Deleting them while Terraform is running corrupts state and forces manual recovery.

### Correct teardown order

#### Step 1 — Delete the Kubernetes Ingress (removes the ALB)

The ALB is created by the AWS Load Balancer Controller from the Ingress resource — it is NOT managed by Terraform. If you run `terraform destroy` before deleting the Ingress, the LB Controller's security groups stay attached to the VPC and `terraform destroy` fails with `DependencyViolation` on the VPC.

```bash
kubectl delete ingress issue-tracker -n issue-tracker

# Wait ~60 seconds then confirm the ALB is gone
aws elbv2 describe-load-balancers --region ap-south-1 \
  --query 'LoadBalancers[*].LoadBalancerName' --output text
# Should return empty
```

#### Step 2 — Empty the S3 uploads bucket

The uploads bucket has `force_destroy = false`. Terraform cannot delete it if it contains objects.

```bash
aws s3 rm s3://issue-tracker-uploads-prod --recursive --region ap-south-1
```

#### Step 3 — Run terraform destroy

```bash
cd infra/terraform/environments/production
terraform destroy
```

Type `yes` when prompted. Expected duration: **15–25 minutes**.

> **Timings to expect**:
> - EKS node group drain: up to 20 minutes (Kubernetes evicts all pods gracefully)
> - ElastiCache deletion: 7–10 minutes
> - RDS deletion: 5–8 minutes (no final snapshot — `skip_final_snapshot = true`)
> - VPC and networking: 2–3 minutes

#### Step 4 — Check for leftover LB Controller security groups

Even after deleting the Ingress, the LB Controller sometimes leaves a security group behind. If `terraform destroy` fails on VPC deletion with `DependencyViolation`:

```bash
VPC_ID=$(aws ec2 describe-vpcs --region ap-south-1 \
  --filters "Name=tag:Name,Values=issue-tracker-vpc" \
  --query 'Vpcs[0].VpcId' --output text)

# List all non-default security groups still in the VPC
aws ec2 describe-security-groups --region ap-south-1 \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'SecurityGroups[?GroupName!=`default`].{Id:GroupId,Name:GroupName}' \
  --output table
```

Delete any `k8s-traffic-*` or `k8s-elb-*` security groups found:

```bash
aws ec2 delete-security-group --group-id sg-XXXXXXXXX --region ap-south-1
```

Then re-run `terraform destroy` — it will pick up where it left off.

#### Step 5 — Delete bootstrap resources (ONLY after destroy succeeds)

These were created by `bootstrap.sh` and are outside Terraform state. Delete them only after `terraform destroy` exits cleanly.

```bash
# The state bucket has versioning enabled — must delete all versions before deleting bucket
python3 -c "
import subprocess, json

bucket = 'issue-tracker-terraform-state'
region = 'ap-south-1'

result = subprocess.run([
    'aws', 's3api', 'list-object-versions',
    '--bucket', bucket, '--region', region
], capture_output=True, text=True)

data = json.loads(result.stdout) if result.stdout.strip() else {}

for kind in ['Versions', 'DeleteMarkers']:
    for obj in data.get(kind, []):
        subprocess.run([
            'aws', 's3api', 'delete-object',
            '--bucket', bucket, '--region', region,
            '--key', obj['Key'],
            '--version-id', obj['VersionId']
        ])
        print('Deleted', obj['Key'], '@', obj['VersionId'])

subprocess.run(['aws', 's3api', 'delete-bucket', '--bucket', bucket, '--region', region])
print('State bucket deleted.')
"

# Delete DynamoDB lock table
aws dynamodb delete-table \
  --table-name issue-tracker-terraform-locks \
  --region ap-south-1
```

#### Step 6 — Force-delete Secrets Manager secrets

Secrets have a 7-day recovery window. Force-delete them immediately to stop any charges:

```bash
for secret in \
  "issue-tracker/production" \
  "issue-tracker/rds-password" \
  "issue-tracker/redis-auth-token"; do
  aws secretsmanager delete-secret \
    --secret-id "$secret" \
    --force-delete-without-recovery \
    --region ap-south-1 2>/dev/null && echo "Deleted $secret"
done
```

#### Step 7 — Verify everything is gone

```bash
echo "=== EC2 instances ===" && \
aws ec2 describe-instances --region ap-south-1 \
  --filters "Name=instance-state-name,Values=running" \
  --query 'Reservations[*].Instances[*].InstanceId' --output text

echo "=== NAT Gateways (cost ~$32/month each) ===" && \
aws ec2 describe-nat-gateways --region ap-south-1 \
  --filter "Name=state,Values=available" \
  --query 'NatGateways[*].NatGatewayId' --output text

echo "=== Load Balancers ===" && \
aws elbv2 describe-load-balancers --region ap-south-1 \
  --query 'LoadBalancers[*].LoadBalancerName' --output text

echo "=== RDS instances ===" && \
aws rds describe-db-instances --region ap-south-1 \
  --query 'DBInstances[*].DBInstanceIdentifier' --output text

echo "=== ElastiCache clusters ===" && \
aws elasticache describe-replication-groups --region ap-south-1 \
  --query 'ReplicationGroups[*].ReplicationGroupId' --output text
```

All should return empty output.

---

### Recovery: terraform destroy failed mid-way and state is lost

This happens when the S3 state bucket is deleted while `terraform destroy` is still running, or when the operation times out. Terraform writes `errored.tfstate` locally in this case.

```bash
cd infra/terraform/environments/production

# 1. Confirm the errored state file exists
ls -la errored.tfstate

# 2. Create a local backend override (so Terraform does not need the S3 bucket)
cat > backend_override.tf << 'EOF'
terraform {
  backend "local" {}
}
EOF

# 3. Use the errored state as the local state
cp errored.tfstate terraform.tfstate

# 4. Re-init with local backend
terraform init -reconfigure

# 5. Destroy what is left
terraform destroy

# 6. Clean up temporary files after destroy succeeds
rm backend_override.tf terraform.tfstate terraform.tfstate.backup errored.tfstate 2>/dev/null
```

Then proceed with Steps 5 and 6 above (delete bootstrap resources and secrets).

---

## Troubleshooting

### Backend pods in CrashLoopBackOff

```bash
kubectl logs POD_NAME -n issue-tracker
kubectl logs POD_NAME -n issue-tracker --previous
kubectl describe pod POD_NAME -n issue-tracker
```

Common causes:

| Symptom in logs | Cause | Fix |
|---|---|---|
| `gunicorn: error: unrecognized arguments` | Invalid gunicorn flag in `start.sh` | Check `--keep-alive` spelling; remove `--proxy-headers` |
| `connection refused` on DB | Wrong DATABASE_URL or RDS not reachable | Check Secrets Manager value; check RDS security group |
| `connection refused` on Redis | Wrong REDIS_URL | Use `rediss://` for TLS; check auth token |
| `secret "app-secrets" not found` | ExternalSecret hasn't synced | Check sync status; verify IAM role has Secrets Manager access |
| `serviceaccount "backend" not found` | ServiceAccount not applied before Job | `kubectl apply -f infra/kubernetes/backend/serviceaccount.yaml` |

### Nginx in CrashLoopBackOff

```bash
kubectl logs -l app=nginx -n issue-tracker
```

Common causes:

| Symptom | Cause | Fix |
|---|---|---|
| `502` on probe path `/` | Probe hits frontend upstream which doesn't exist | Use `/nginx-health` probe path (already in deployment.yaml) — apply the manifest |
| `nginx: [emerg]` config errors | Invalid nginx.conf syntax | Check configmap.yaml |

After fixing the configmap, you must apply it AND then restart:

```bash
kubectl apply -f infra/kubernetes/nginx/configmap.yaml
kubectl apply -f infra/kubernetes/nginx/deployment.yaml   # applies updated probe path
kubectl rollout restart deployment/nginx -n issue-tracker
```

### Migration job timed out

```bash
kubectl describe job db-migrate -n issue-tracker
kubectl logs job/db-migrate -n issue-tracker
```

Common causes: wrong DATABASE_URL, RDS not accepting connections, `app-secrets` not synced.

### Terraform plan/apply errors

| Error | Cause | Fix |
|---|---|---|
| `InvalidParameterCombination: Use a parameter group with cluster-enabled` | ElastiCache cluster mode needs `cluster-enabled = yes` parameter | Add `parameter { name = "cluster-enabled"; value = "yes" }` to the parameter group |
| `cannot use immediate apply method for static parameter` | RDS static params (e.g. `max_connections`) cannot use `apply_method = "immediate"` | Use `apply_method = "pending-reboot"` |
| `name_prefix not supported` (ElastiCache) | `aws_elasticache_parameter_group` only accepts `name`, not `name_prefix` | Use `name = "..."` |
| Helm release context deadline exceeded | Helm timeout too short, or controller pods not ready | Increase `timeout` on the helm_release resource |
| `authentication mode must be API or API_AND_CONFIG_MAP` | Cluster in CONFIG_MAP-only mode; access entries API not available | Run `aws eks update-cluster-config --access-config authenticationMode=API_AND_CONFIG_MAP` |
| Prompts for `acm_certificate_arn` | Variable has no default | Add `default = ""` to the variable |

### Cannot access EKS cluster / kubectl returns 401

Either your IAM identity is not in the cluster auth, or your kubeconfig token is expired.

```bash
# Refresh kubeconfig (gets a new token)
aws eks update-kubeconfig --region ap-south-1 --name issue-tracker-production

# If still 401, check your identity
aws sts get-caller-identity

# Grant access to your identity (EKS 1.30 — API_AND_CONFIG_MAP mode)
aws eks create-access-entry \
  --cluster-name issue-tracker-production \
  --principal-arn $(aws sts get-caller-identity --query Arn --output text) \
  --region ap-south-1

aws eks associate-access-policy \
  --cluster-name issue-tracker-production \
  --principal-arn $(aws sts get-caller-identity --query Arn --output text) \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope '{"type":"cluster"}' \
  --region ap-south-1
```

---

## Known Errors and Fixes

A record of every significant error encountered so future developers can resolve them quickly.

### 1. Gunicorn unrecognized arguments (`start.sh`)

**Error**: `gunicorn: error: unrecognized arguments: --keepalive 5 --proxy-headers`

**Cause**: `--keepalive` (no hyphen) does not exist in gunicorn. `--proxy-headers` is a uvicorn CLI-only flag.

**Fix**: Use `--keep-alive 5` (hyphen). Remove `--proxy-headers` entirely. Gunicorn's equivalent for trusted proxies is `--forwarded-allow-ips "*"`.

---

### 2. RDS `incompatible-parameters` state

**Error**: `waiting for RDS DB Instance create: unexpected state 'incompatible-parameters'`

**Root cause**: The `shared_buffers` and `effective_cache_size` parameters were set using formulas that do not account for the parameter's native unit (8kB blocks). `{DBInstanceClassMemory/4}` evaluates to petabytes, not gigabytes.

**Fix**: Remove these parameters from the custom parameter group entirely and let AWS use its well-tuned defaults (`{DBInstanceClassMemory/32768}` for `shared_buffers` = 25% RAM). Only add parameters with plain numeric units (like `max_connections = 500`).

**Recovery when instance is stuck**:
1. RDS Console → Parameter Groups → `issue-tracker-pg16-xxx` → Edit → reset `shared_buffers` and `effective_cache_size` to default.
2. RDS Console → Databases → `issue-tracker` → Actions → Reboot.
3. Wait for status to become `available`.
4. `terraform apply` will update the parameter group to the fixed version.

---

### 3. ElastiCache cluster mode requires `cluster-enabled = yes`

**Error**: `InvalidParameterCombination: Use a parameter group with cluster-enabled parameter to create more than one node group`

**Fix**: Add to the `aws_elasticache_parameter_group` resource:
```hcl
parameter {
  name  = "cluster-enabled"
  value = "yes"
}
```

---

### 4. RDS static parameters need `apply_method = "pending-reboot"`

**Error**: `cannot use immediate apply method for static parameter`

**Cause**: PostgreSQL static parameters (`max_connections`, `shared_buffers`) require a reboot to take effect. Terraform defaults to `apply_method = "immediate"` which AWS rejects for static parameters.

**Fix**: Add `apply_method = "pending-reboot"` to static parameter blocks.

---

### 5. AWS Load Balancer Controller Helm release times out

**Error**: Helm release `aws_lb_controller` times out (context deadline exceeded)

**Root cause**: The LB Controller requires `region` and `vpcId` values to discover which VPC to manage. Without them, controller pods fail to start.

**Fix**: Add to the `helm_release` resource:
```hcl
set { name = "region"; value = var.aws_region }
set { name = "vpcId";  value = var.vpc_id }
```
Also increase `timeout = 900` (15 minutes) — the LB controller takes time to pull and start on a fresh cluster.

---

### 6. EKS access entries API requires `API_AND_CONFIG_MAP` mode

**Error**: `The cluster's authentication mode must be set to one of [API, API_AND_CONFIG_MAP]`

**Cause**: Cluster was created in legacy `CONFIG_MAP` mode.

**Fix**:
```bash
aws eks update-cluster-config \
  --name issue-tracker-production \
  --access-config authenticationMode=API_AND_CONFIG_MAP \
  --region ap-south-1

aws eks wait cluster-active --name issue-tracker-production --region ap-south-1
```
This is a one-way migration. `CONFIG_MAP` → `API_AND_CONFIG_MAP` is supported. The reverse is not.

---

### 7. Migration Job fails: `serviceaccount "backend" not found`

**Error**: `Error creating: pods "db-migrate-" is forbidden: error looking up service account issue-tracker/backend: serviceaccount "backend" not found`

**Cause**: The backend ServiceAccount was defined inside `backend/deployment.yaml`. The pipeline applied the deployment after running the migration Job, so the ServiceAccount did not exist yet when the Job ran.

**Fix**: The ServiceAccount is now in its own file `backend/serviceaccount.yaml` and applied in the early manifest step before migrations run. This file must always be committed and must be applied before the first Job.

---

### 8. Nginx health probe 502 / CrashLoopBackOff

**Error**: Nginx pods in CrashLoopBackOff. Logs show `connect() failed (111: Connection refused) while connecting to upstream ... request: "GET / HTTP/1.1"` from kube-probe.

**Cause**: The liveness/readiness probe was set to `GET /` which nginx proxies to the frontend upstream. If frontend pods are not running, nginx gets a 502 and fails its own health check, causing Kubernetes to restart it.

**Fix**: Added a `location /nginx-health { return 200; }` block in `nginx/configmap.yaml` and changed both probes in `nginx/deployment.yaml` to use `/nginx-health`. Nginx now reports healthy independently of whether backend or frontend pods are up.

**Important**: When applying configmap changes manually, always apply **both** files and restart in this order:
```bash
kubectl apply -f infra/kubernetes/nginx/configmap.yaml
kubectl apply -f infra/kubernetes/nginx/deployment.yaml
kubectl rollout restart deployment/nginx -n issue-tracker
```
`rollout restart` alone does not update the probe path — only `kubectl apply -f deployment.yaml` does.

---

### 9. Terraform HCL semicolons

**Error**: `An argument or block definition is required here` or similar parse error

**Cause**: HCL does not support semicolons to separate arguments on one line.

**Wrong**:
```hcl
set { name = "clusterName"; value = var.cluster_name }
variable "x" { type = number; default = 3 }
```

**Correct**:
```hcl
set {
  name  = "clusterName"
  value = var.cluster_name
}
variable "x" {
  type    = number
  default = 3
}
```

---

### 10. `aws_elasticache_parameter_group` does not support `name_prefix`

**Error**: `An argument named "name_prefix" is not expected here`

**Fix**: Use `name = "..."` (not `name_prefix`) for `aws_elasticache_parameter_group`.

---

### 11. NEXT_PUBLIC_API_URL must be set before frontend build

If `NEXT_PUBLIC_API_URL` is not set in GitHub Secrets when the pipeline runs the frontend build, the value will be empty or a placeholder in the production JavaScript bundle. All API calls from the browser will fail.

Set the correct ALB DNS (or your domain) in the GitHub Secret **before** triggering a frontend deploy.

---

### 12. `terraform destroy` fails: VPC DependencyViolation

**Error**: `deleting EC2 VPC: DependencyViolation: The vpc has dependencies and cannot be deleted`

**Cause**: The AWS Load Balancer Controller creates security groups in the VPC when it provisions the ALB. These groups are not managed by Terraform. When the EKS cluster is destroyed, the LB Controller pods are gone and can no longer clean up after themselves — the security groups are left orphaned in the VPC.

**Fix**: Before running `terraform destroy`, always delete the Kubernetes Ingress first so the LB Controller can clean up the ALB and its security groups while it is still running:

```bash
kubectl delete ingress issue-tracker -n issue-tracker
# Wait ~60 seconds for the ALB to be deleted by the controller
aws elbv2 describe-load-balancers --region ap-south-1 \
  --query 'LoadBalancers[*].LoadBalancerName' --output text
# Confirm empty, then run terraform destroy
```

If you already ran `terraform destroy` and it failed, find and delete the leftover security groups manually:

```bash
# Find all non-default security groups in the VPC
aws ec2 describe-security-groups --region ap-south-1 \
  --filters "Name=vpc-id,Values=vpc-XXXXXXXXX" \
  --query 'SecurityGroups[?GroupName!=`default`].{Id:GroupId,Name:GroupName}' \
  --output table

# Delete each one (look for names starting with k8s-traffic- or k8s-elb-)
aws ec2 delete-security-group --group-id sg-XXXXXXXXX --region ap-south-1

# Then re-run terraform destroy — it picks up where it left off
terraform destroy
```

---

### 13. `terraform destroy` fails: ECR repositories not empty

**Error**: `RepositoryNotEmptyException: The repository cannot be deleted because it still contains images`

**Cause**: `force_delete = false` (the old default) prevents Terraform from deleting ECR repos that contain images. The fix is now in the codebase (`force_delete = true`), but if you are running an older version:

```bash
# Delete all images in the repo, then destroy
for repo in issue-tracker-backend issue-tracker-frontend; do
  ids=$(aws ecr list-images --repository-name $repo --region ap-south-1 \
        --query 'imageIds[*]' --output json 2>/dev/null)
  [ "$ids" != "[]" ] && [ -n "$ids" ] && \
    aws ecr batch-delete-image --repository-name $repo \
      --image-ids "$ids" --region ap-south-1
  aws ecr delete-repository --repository-name $repo --force --region ap-south-1 2>/dev/null
done
```

---

### 14. `terraform destroy` fails: S3 state bucket already deleted / DNS not found

**Error**: `failed to upload state: dial tcp: lookup issue-tracker-terraform-state.s3.ap-south-1.amazonaws.com: no such host`

**Cause**: The S3 state bucket was manually deleted (following teardown instructions) while `terraform destroy` was still running. Terraform could not save the updated state after some resources were deleted, resulting in an `errored.tfstate` file written locally.

**Fix**: Switch to local backend and continue from the saved state:

```bash
cd infra/terraform/environments/production

cat > backend_override.tf << 'EOF'
terraform {
  backend "local" {}
}
EOF

cp errored.tfstate terraform.tfstate
terraform init -reconfigure
terraform destroy

# Clean up after success
rm backend_override.tf terraform.tfstate terraform.tfstate.backup errored.tfstate 2>/dev/null
```

**Prevention**: Always delete the S3 state bucket and DynamoDB lock table **after** `terraform destroy` completes successfully — never during.

---

### 15. S3 versioned bucket cannot be deleted with `aws s3 rm` or `delete-bucket`

**Error**: `BucketNotEmpty: The bucket you tried to delete is not empty. You must delete all versions in the bucket.`

**Cause**: The Terraform state bucket has versioning enabled. `aws s3 rm --recursive` only deletes current object versions — it leaves all previous versions and delete markers, which still count as "not empty" for bucket deletion.

**Fix**: Use the Python script that deletes all versions and delete markers before deleting the bucket:

```bash
python3 -c "
import subprocess, json

bucket = 'issue-tracker-terraform-state'
region = 'ap-south-1'

result = subprocess.run([
    'aws', 's3api', 'list-object-versions',
    '--bucket', bucket, '--region', region
], capture_output=True, text=True)

data = json.loads(result.stdout) if result.stdout.strip() else {}

for kind in ['Versions', 'DeleteMarkers']:
    for obj in data.get(kind, []):
        subprocess.run([
            'aws', 's3api', 'delete-object',
            '--bucket', bucket, '--region', region,
            '--key', obj['Key'],
            '--version-id', obj['VersionId']
        ])
        print('Deleted', obj['Key'], '@', obj['VersionId'])

subprocess.run(['aws', 's3api', 'delete-bucket', '--bucket', bucket, '--region', region])
print('Done.')
"
```

---

### 16. EKS node group deletion times out (>1 hour)

**Error**: `waiting for EKS Node Group delete: timeout while waiting for resource to be gone (last state: 'DELETING', timeout: 1h0m0s)`

**Cause**: Terraform's EKS node group deletion timeout is 1 hour. If there are many pods with long graceful shutdown periods (e.g. 60s `terminationGracePeriodSeconds`), draining all nodes across 3 AZs can exceed this.

**What to do**: The node group continues draining in the background even after Terraform times out. Check progress:

```bash
aws eks describe-nodegroup \
  --cluster-name issue-tracker-production \
  --nodegroup-name issue-tracker-app \
  --region ap-south-1 \
  --query 'nodegroup.status' --output text
```

When it returns `ResourceNotFoundException` (the group no longer exists), re-run `terraform destroy` — it will skip the already-deleted resources and continue with the remaining ones (VPC, IAM, etc.).
