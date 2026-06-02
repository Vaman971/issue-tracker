# Infrastructure

Kubernetes + Terraform infrastructure targeting **10K+ RPS** on AWS EKS (ap-south-1).

## Architecture

```
Internet
  │
  ▼
AWS ALB  (HTTPS/443 via ACM, HTTP→HTTPS redirect)
  │
  ▼  (Ingress — AWS Load Balancer Controller)
nginx pods  ×2  (reverse proxy, strips /api/ prefix)
  ├── /api/*  ──▶  backend Service  ──▶  backend pods  ×3–30  (HPA)
  └── /*      ──▶  frontend Service ──▶  frontend pods ×2–10  (HPA)

backend pods  (FastAPI + gunicorn, 4 uvicorn workers each)
  ├── RDS PostgreSQL 16  (Multi-AZ, db.r6g.large)
  └── ElastiCache Redis 7  (cluster mode, 3 shards × 2 replicas)

celery-worker pods  ×2–15  (HPA)  ──▶  Redis (broker)
celery-beat pod     ×1     (Recreate strategy)

Cluster Autoscaler  ──▶  ASG  ──▶  c6i.xlarge nodes  ×3–15
```

### Throughput math

| Component | Replicas (peak) | Workers | RPS/worker | Total RPS |
|---|---|---|---|---|
| backend | 30 | 4 each = 120 | ~100–200 | **12K–24K** |
| nginx | 2 | auto (4 cores) | >50K/pod | not a bottleneck |
| RDS | Multi-AZ | — | ~5K QPS w/ pool | ✓ |
| Redis | 3 shards | — | >100K ops/s | ✓ |

## Directory layout

```
infra/
├── terraform/
│   ├── modules/
│   │   ├── vpc/            VPC, subnets, NAT gateways
│   │   ├── eks/            EKS cluster, node group, Helm releases
│   │   ├── rds/            PostgreSQL 16, parameter group, secrets
│   │   ├── elasticache/    Redis 7 cluster mode
│   │   ├── ecr/            ECR repos + lifecycle policies
│   │   └── iam/            IRSA roles (backend, autoscaler, LB controller,
│   │                       external-secrets) + GitHub Actions OIDC role
│   └── environments/
│       └── production/     Root module — wires everything together
├── kubernetes/
│   ├── namespace.yaml
│   ├── configmap.yaml      Non-sensitive env vars
│   ├── nginx/              Deployment, Service, ConfigMap (nginx.conf)
│   ├── backend/            Deployment, Service, HPA (3–30), PDB
│   ├── frontend/           Deployment, Service, HPA (2–10), PDB
│   ├── celery/             Worker Deployment+HPA, Beat Deployment
│   ├── ingress/            AWS ALB Ingress
│   ├── secrets/            ExternalSecret → AWS Secrets Manager
│   └── jobs/               DB migration Job template
└── scripts/
    ├── bootstrap.sh        One-time AWS pre-flight (S3 state, DynamoDB lock,
    │                       Secrets Manager skeleton)
    └── kubeconfig.sh       Update local kubectl context
```

## Prerequisites

- AWS CLI v2, configured with admin credentials
- Terraform >= 1.6
- kubectl
- helm (optional — used by Terraform)
- `envsubst` (for migration job templating in the pipeline)

## First-time deployment

### 1. Bootstrap AWS prerequisites

```bash
export AWS_REGION=ap-south-1
bash infra/scripts/bootstrap.sh
```

### 2. Fill in Terraform variables

```bash
cd infra/terraform/environments/production
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set github_org, acm_certificate_arn, etc.
```

### 3. Provision infrastructure

```bash
terraform init
terraform plan
terraform apply
```

### 4. Configure kubectl

```bash
bash infra/scripts/kubeconfig.sh
```

### 5. Populate AWS Secrets Manager

Navigate to the AWS Secrets Manager console and update the secret
`issue-tracker/production` with real values (DATABASE_URL, REDIS_URL, JWT keys,
SMTP credentials). The DATABASE_URL and REDIS_URL are available as Terraform
outputs:

```bash
terraform output -raw rds_endpoint      # → host:port
terraform output -raw redis_endpoint    # → cluster config endpoint
```

### 6. Apply Kubernetes base manifests

```bash
kubectl apply -f infra/kubernetes/namespace.yaml
kubectl apply -f infra/kubernetes/secrets/external-secrets.yaml
# Wait for ExternalSecret to sync (creates the app-secrets K8s Secret)
kubectl get externalsecret -n issue-tracker
```

Update the two placeholder annotations in the manifests before first apply:

| File | Placeholder | Replace with |
|---|---|---|
| `backend/deployment.yaml` | `BACKEND_IRSA_ROLE_ARN` | `terraform output backend_irsa_role_arn` |
| `ingress/ingress.yaml`    | `ACM_CERTIFICATE_ARN`  | your ACM cert ARN |

### 7. Push to main

The GitHub Actions pipeline handles everything from here:
tests → build → migrations → rolling deploy.

## GitHub Secrets required

Add these in **Settings → Secrets and variables → Actions**:

| Secret | Where to get it |
|---|---|
| `AWS_GITHUB_ACTIONS_ROLE_ARN` | `terraform output github_actions_role_arn` |
| `NEXT_PUBLIC_API_URL` | Your domain, e.g. `https://yourdomain.com` |

## Scaling

- **Vertical**: change `node_instance_type` in terraform.tfvars → `terraform apply`
- **Horizontal nodes**: change `node_max_size` → `terraform apply`
- **Horizontal pods**: edit `maxReplicas` in the HPA manifests → `kubectl apply`
- **Workers per pod**: change `WEB_CONCURRENCY` in `infra/kubernetes/configmap.yaml`

## Day-2 operations

```bash
# Check HPA state
kubectl get hpa -n issue-tracker

# Tail backend logs
kubectl logs -f -l app=backend -n issue-tracker --max-log-requests=5

# Force a re-deploy without a code change
gh workflow run deploy.yml

# Roll back backend to previous image
kubectl rollout undo deployment/backend -n issue-tracker
```
