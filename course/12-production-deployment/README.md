# Module 12 — Full Production Deployment Walkthrough

---

## Overview

This module walks through deploying the issue-tracker from zero to a live, HTTPS-secured application on AWS. By the end, you will have:

```
https://yourdomain.com         → Issue Tracker (HTTPS, ACM cert)
  ↓
AWS ALB (ap-south-1)
  ↓
EKS cluster (3 EC2 nodes, c6i.xlarge)
  ├── backend pods (FastAPI, 3+ replicas)
  ├── frontend pods (Next.js, 3+ replicas)
  ├── nginx pods (reverse proxy, 3+ replicas)
  └── celery pods (worker + beat)
  ↓
  ├── RDS PostgreSQL (Multi-AZ, db.r6g.large)
  ├── ElastiCache Redis (3 shards, cache.r6g.large)
  └── S3 (file attachments)
```

**Estimated time**: 2-3 hours (most of it waiting for AWS to provision resources)
**Estimated cost**: ~$1,400/month at full scale (see cost section for how to minimize this)

---

## Prerequisites

### Tools to Install

```bash
# 1. AWS CLI v2
# Download: https://aws.amazon.com/cli/
aws --version
# aws-cli/2.15.0 Python/3.11.6

# 2. Terraform
# Download: https://developer.hashicorp.com/terraform/install
terraform --version
# Terraform v1.6.0

# 3. kubectl
# Download: https://kubernetes.io/docs/tasks/tools/
kubectl version --client
# Client Version: v1.30.0

# 4. Helm
# Download: https://helm.sh/docs/intro/install/
helm version
# version.BuildInfo{Version:"v3.14.0"}

# 5. Docker
# Download: https://www.docker.com/products/docker-desktop/
docker --version
# Docker version 25.0.3

# 6. git
git --version
```

### AWS Account Setup

```bash
# 1. Create an AWS account at https://aws.amazon.com/
#    (requires credit card — you WILL be charged for resources created here)

# 2. Create an IAM user with programmatic access:
#    AWS Console → IAM → Users → Create User
#    Attach policy: AdministratorAccess (for simplicity; tighten in real use)
#    Create access key → download credentials

# 3. Configure AWS CLI:
aws configure
# AWS Access Key ID: AKIA...
# AWS Secret Access Key: ...
# Default region name: ap-south-1
# Default output format: json

# Verify:
aws sts get-caller-identity
# {
#   "Account": "123456789012",
#   "Arn": "arn:aws:iam::123456789012:user/yourname"
# }
```

### Domain Name

You need a domain name for HTTPS. Options:
- Buy from AWS Route53 (~$12/year for .com)
- Buy from Namecheap, GoDaddy, etc. and point nameservers to Route53

```bash
# If buying in Route53:
# AWS Console → Route53 → Register Domain → follow steps

# Note your hosted zone ID (needed later):
aws route53 list-hosted-zones
# {
#   "HostedZones": [{
#     "Name": "yourdomain.com.",
#     "Id": "/hostedzone/Z1234567890"
#   }]
# }
```

---

## Phase 0: Bootstrap State Storage (One Time Only)

Before Terraform can run, you must create the S3 bucket and DynamoDB table that will store Terraform's state. These are created manually because Terraform cannot manage its own state backend.

```bash
export AWS_REGION=ap-south-1

# 1. Create S3 bucket for Terraform state
aws s3 mb s3://issue-tracker-terraform-state --region $AWS_REGION

# 2. Enable versioning (protects against accidental state corruption)
aws s3api put-bucket-versioning \
  --bucket issue-tracker-terraform-state \
  --versioning-configuration Status=Enabled

# 3. Enable encryption
aws s3api put-bucket-encryption \
  --bucket issue-tracker-terraform-state \
  --server-side-encryption-configuration \
    '{"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}'

# 4. Block all public access
aws s3api put-public-access-block \
  --bucket issue-tracker-terraform-state \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# 5. Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name issue-tracker-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION

echo "Bootstrap complete"
```

> **Why manually?** Terraform stores its state in this S3 bucket. If Terraform managed the bucket, you'd have a chicken-and-egg problem — Terraform can't run without state, but state doesn't exist yet.

---

## Phase 1: Configure Terraform Variables

### Edit the variables file

```bash
cd infra/terraform/environments/production

# Open terraform.tfvars and review/update these values:
```

```hcl
# infra/terraform/environments/production/terraform.tfvars

aws_region         = "ap-south-1"        # AWS region to deploy into
environment        = "production"
vpc_cidr           = "10.0.0.0/16"
kubernetes_version = "1.30"

# EC2 instance type for EKS worker nodes
# c6i.xlarge = 4 vCPU, 8 GB RAM — fits ~10 pods per node
node_instance_type = "c6i.xlarge"
node_min_size      = 3               # minimum 3 for HA across 3 AZs
node_max_size      = 15
node_desired_size  = 3               # start with 3, HPA scales pods up

# RDS PostgreSQL
db_instance_class = "db.r6g.large"  # 2 vCPU, 16 GB RAM
db_name           = "issuetracker"
db_username       = "issueadmin"

# ElastiCache Redis
redis_node_type  = "cache.r6g.large"  # 2 vCPU, 13 GB RAM
redis_num_shards = 3

# Your GitHub organization and repo name
github_org  = "YOUR_GITHUB_USERNAME"   # ← Update this
github_repo = "issue-tracker"

# S3 bucket name for file attachments (must be globally unique)
s3_uploads_bucket = "issue-tracker-uploads-prod-YOUR_ACCOUNT_ID"  # ← Make unique
```

### Set sensitive variables as environment variables

Never put passwords in `.tfvars` files — they'd end up in git history.

```bash
# Generate random secrets
export TF_VAR_db_password="$(openssl rand -base64 32 | tr -d '=+/')"
export TF_VAR_redis_auth_token="$(openssl rand -base64 32 | tr -d '=+/')"

# Save these somewhere safe — you'll need them in Phase 4!
echo "DB Password: $TF_VAR_db_password"
echo "Redis Token: $TF_VAR_redis_auth_token"
```

---

## Phase 2: Initialize Terraform

```bash
cd infra/terraform/environments/production

# Download providers and modules
terraform init

# Expected output:
# Initializing modules...
# - vpc in ../../modules/vpc
# - eks in ../../modules/eks
# - rds in ../../modules/rds
# - elasticache in ../../modules/elasticache
# - ecr in ../../modules/ecr
# - iam in ../../modules/iam
#
# Initializing the backend...
# Successfully configured the backend "s3"!
#
# Terraform has been successfully initialized!
```

### Preview what Terraform will create

```bash
terraform plan -var-file="terraform.tfvars" -out=tfplan

# Review the output carefully. You should see:
# Plan: 50+ to add, 0 to change, 0 to destroy.
#
# Key resources:
# + aws_vpc.main
# + aws_subnet.public[0,1,2]
# + aws_subnet.private[0,1,2]
# + aws_eks_cluster.main
# + aws_eks_node_group.main
# + aws_db_instance.main
# + aws_elasticache_replication_group.main
# + aws_ecr_repository.backend
# + aws_ecr_repository.frontend
# + aws_iam_role.github_actions
# ... 40+ more resources
```

---

## Phase 3: Apply Infrastructure (~15-20 minutes)

```bash
# Apply the plan (type "yes" when prompted)
terraform apply tfplan

# This takes 15-20 minutes because:
# - EKS cluster creation: ~12-15 minutes
# - RDS Multi-AZ: ~5-10 minutes
# - ElastiCache: ~5-10 minutes
# - Everything else: ~2-3 minutes

# Watch progress in AWS Console:
# EC2 → EKS clusters → your cluster → status: CREATING → ACTIVE
```

After completion:

```bash
# View all outputs
terraform output

# Key outputs you'll need:
terraform output eks_cluster_name
# issue-tracker-prod

terraform output ecr_backend_url
# 123456789012.dkr.ecr.ap-south-1.amazonaws.com/issue-tracker-backend

terraform output ecr_frontend_url
# 123456789012.dkr.ecr.ap-south-1.amazonaws.com/issue-tracker-frontend

terraform output github_actions_role_arn
# arn:aws:iam::123456789012:role/issue-tracker-github-actions

# Sensitive outputs (use -raw flag):
terraform output -raw rds_endpoint
# issue-tracker-db.xyz.ap-south-1.rds.amazonaws.com

terraform output -raw redis_endpoint
# clustercfg.issue-tracker-redis.xyz.cache.amazonaws.com:6379
```

---

## Phase 4: Configure kubectl

```bash
# Update kubeconfig to connect to your new EKS cluster
aws eks update-kubeconfig \
  --name $(terraform output -raw eks_cluster_name) \
  --region ap-south-1

# Verify connection
kubectl get nodes

# Expected output (after nodes are Ready — may take 2-3 minutes):
# NAME                                         STATUS   ROLES    AGE   VERSION
# ip-10-0-11-100.ap-south-1.compute.internal  Ready    <none>   3m    v1.30.0-eks-036c24b
# ip-10-0-12-200.ap-south-1.compute.internal  Ready    <none>   3m    v1.30.0-eks-036c24b
# ip-10-0-13-150.ap-south-1.compute.internal  Ready    <none>   3m    v1.30.0-eks-036c24b
```

---

## Phase 5: Set Up AWS Secrets Manager

Store all sensitive application configuration centrally:

```bash
# Collect the values you need
RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
REDIS_ENDPOINT=$(terraform output -raw redis_endpoint)

# Generate additional secrets
JWT_SECRET=$(openssl rand -base64 64 | tr -d '\n')
JWT_REFRESH_SECRET=$(openssl rand -base64 64 | tr -d '\n')

# Create the secret (all app config in one JSON object)
aws secretsmanager create-secret \
  --name "issue-tracker/production/app-secrets" \
  --description "Issue Tracker production application secrets" \
  --secret-string "{
    \"JWT_SECRET_KEY\": \"$JWT_SECRET\",
    \"JWT_REFRESH_SECRET_KEY\": \"$JWT_REFRESH_SECRET\",
    \"DATABASE_URL\": \"postgresql+asyncpg://issueadmin:${TF_VAR_db_password}@${RDS_ENDPOINT}:5432/issuetracker\",
    \"CELERY_BROKER_URL\": \"redis://:${TF_VAR_redis_auth_token}@${REDIS_ENDPOINT}/1\",
    \"CELERY_RESULT_BACKEND\": \"redis://:${TF_VAR_redis_auth_token}@${REDIS_ENDPOINT}/2\",
    \"REDIS_URL\": \"redis://:${TF_VAR_redis_auth_token}@${REDIS_ENDPOINT}/0\",
    \"SEED_ADMIN_EMAIL\": \"admin@yourdomain.com\",
    \"SEED_ADMIN_PASSWORD\": \"$(openssl rand -base64 16)\",
    \"SMTP_HOST\": \"smtp.yourmailprovider.com\",
    \"SMTP_USERNAME\": \"your-smtp-username\",
    \"SMTP_PASSWORD\": \"your-smtp-password\"
  }" \
  --region ap-south-1

echo "Secret created successfully"

# Verify it was stored:
aws secretsmanager get-secret-value \
  --secret-id "issue-tracker/production/app-secrets" \
  --query SecretString \
  --output text \
  --region ap-south-1 | python -m json.tool
```

---

## Phase 6: Request SSL Certificate (ACM)

```bash
# Request a certificate for your domain
# This is free — AWS Certificate Manager costs nothing for the certificate

aws acm request-certificate \
  --domain-name yourdomain.com \
  --subject-alternative-names "*.yourdomain.com" \
  --validation-method DNS \
  --region ap-south-1

# Get the certificate ARN (save this for later)
CERT_ARN=$(aws acm list-certificates \
  --region ap-south-1 \
  --query "CertificateSummaryList[?DomainName=='yourdomain.com'].CertificateArn" \
  --output text)

echo "Certificate ARN: $CERT_ARN"
```

### Validate the certificate via DNS

```bash
# Get the DNS validation records you need to add
aws acm describe-certificate \
  --certificate-arn $CERT_ARN \
  --region ap-south-1 \
  --query "Certificate.DomainValidationOptions"

# Output shows you CNAME records to add:
# {
#   "DomainName": "yourdomain.com",
#   "ValidationStatus": "PENDING_VALIDATION",
#   "ResourceRecord": {
#     "Name": "_abc123.yourdomain.com.",
#     "Type": "CNAME",
#     "Value": "_xyz789.acm-validations.aws."
#   }
# }
```

Add these CNAME records in your DNS provider (Route53 or your registrar). AWS then validates within 5-30 minutes:

```bash
# If using Route53:
HOSTED_ZONE_ID="Z1234567890"  # Your hosted zone ID

aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "_abc123.yourdomain.com.",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [{"Value": "_xyz789.acm-validations.aws."}]
      }
    }]
  }'

# Wait for validation (5-30 minutes):
aws acm wait certificate-validated \
  --certificate-arn $CERT_ARN \
  --region ap-south-1

echo "Certificate validated!"
```

### Update the Ingress with your certificate ARN

```bash
# Open infra/kubernetes/ingress/ingress.yaml
# Find the line with: alb.ingress.kubernetes.io/certificate-arn
# Replace with your actual ARN:
# alb.ingress.kubernetes.io/certificate-arn: "arn:aws:acm:ap-south-1:123456789012:certificate/..."
```

---

## Phase 7: Configure GitHub Actions Secrets

Add these secrets to your GitHub repository:

```
GitHub Repo → Settings → Secrets and variables → Actions → New repository secret
```

| Secret Name | Value | How to get |
|------------|-------|------------|
| `AWS_GITHUB_ACTIONS_ROLE_ARN` | `arn:aws:iam::...` | `terraform output github_actions_role_arn` |
| `ECR_REGISTRY` | `123456789012.dkr.ecr.ap-south-1.amazonaws.com` | From `terraform output ecr_backend_url` (account + region part) |
| `EKS_CLUSTER_NAME` | `issue-tracker-prod` | `terraform output eks_cluster_name` |

```bash
# Quick way to get ECR_REGISTRY:
terraform output ecr_backend_url | cut -d/ -f1
# 123456789012.dkr.ecr.ap-south-1.amazonaws.com
```

---

## Phase 8: Push Initial Docker Images

Before Kubernetes can deploy your application, the Docker images must exist in ECR. The first push is done manually; subsequent pushes happen automatically via GitHub Actions.

```bash
# Get ECR URLs
ECR_BACKEND=$(terraform output -raw ecr_backend_url)
ECR_FRONTEND=$(terraform output -raw ecr_frontend_url)
ECR_REGISTRY=$(echo $ECR_BACKEND | cut -d/ -f1)

# Authenticate Docker to ECR
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin $ECR_REGISTRY

# Build and push backend
cd backend
docker build -t $ECR_BACKEND:latest -t $ECR_BACKEND:initial .
docker push $ECR_BACKEND:latest
docker push $ECR_BACKEND:initial
cd ..

# Build and push frontend
cd frontend
docker build \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://yourdomain.com \
  -t $ECR_FRONTEND:latest \
  -t $ECR_FRONTEND:initial .
docker push $ECR_FRONTEND:latest
docker push $ECR_FRONTEND:initial
cd ..

echo "Images pushed to ECR"
```

---

## Phase 9: Apply Kubernetes Manifests

Apply manifests in the correct order — dependencies first:

```bash
# 1. Create the namespace (everything lives inside this)
kubectl apply -f infra/kubernetes/namespace.yaml

# Verify:
kubectl get namespaces
# issue-tracker   Active   10s

# 2. Create ConfigMap (non-sensitive configuration)
kubectl apply -f infra/kubernetes/configmap.yaml

# Verify:
kubectl get configmap -n issue-tracker
# app-config   1     5s

# 3. Deploy External Secrets Operator resources
#    (connects K8s to AWS Secrets Manager)
kubectl apply -f infra/kubernetes/secrets/external-secrets.yaml

# Wait for the secret to sync (ESO fetches from Secrets Manager):
kubectl wait --for=condition=ready \
  externalsecret/app-secrets \
  -n issue-tracker \
  --timeout=120s

# Verify the K8s Secret was created from Secrets Manager:
kubectl get secret -n issue-tracker
# app-secrets   Opaque   12    30s

# 4. Deploy backend service account (needed for IRSA — S3 access)
kubectl apply -f infra/kubernetes/backend/serviceaccount.yaml

# Annotate with IRSA role ARN:
BACKEND_ROLE_ARN=$(terraform output -raw backend_irsa_role_arn)
kubectl annotate serviceaccount backend \
  -n issue-tracker \
  eks.amazonaws.com/role-arn=$BACKEND_ROLE_ARN

# 5. Run database migration (one-time job)
kubectl apply -f infra/kubernetes/jobs/migrate-job.yaml

# Wait for migration to complete:
kubectl wait --for=condition=complete \
  job/db-migration \
  -n issue-tracker \
  --timeout=120s

# Check migration logs:
kubectl logs -n issue-tracker -l job-name=db-migration
# INFO  [alembic.runtime.migration] Running upgrade -> abc123, initial schema
# INFO  [alembic.runtime.migration] Running upgrade abc123 -> def456, add indexes

# 6. Deploy application services
kubectl apply -f infra/kubernetes/backend/
kubectl apply -f infra/kubernetes/frontend/
kubectl apply -f infra/kubernetes/nginx/
kubectl apply -f infra/kubernetes/celery/

# 7. Deploy the Ingress (this creates the AWS ALB)
kubectl apply -f infra/kubernetes/ingress/ingress.yaml

# 8. Wait for rollouts to complete
kubectl rollout status deployment/backend -n issue-tracker
kubectl rollout status deployment/frontend -n issue-tracker
kubectl rollout status deployment/nginx -n issue-tracker
kubectl rollout status deployment/celery-worker -n issue-tracker

# All expected output:
# deployment "backend" successfully rolled out
# deployment "frontend" successfully rolled out
# deployment "nginx" successfully rolled out
# deployment "celery-worker" successfully rolled out
```

---

## Phase 10: Configure DNS

Get your ALB's DNS name and point your domain to it.

```bash
# Get the ALB DNS name (may take 3-5 minutes after Ingress is applied)
kubectl get ingress -n issue-tracker

# Expected output:
# NAME            CLASS   HOSTS   ADDRESS                                           PORTS
# issue-tracker   alb     *       k8s-abc-def-123456.ap-south-1.elb.amazonaws.com   80, 443

ALB_DNS="k8s-abc-def-123456.ap-south-1.elb.amazonaws.com"
```

### Point your domain to the ALB

```bash
# Option A: Using Route53 (recommended — supports ALIAS records)
HOSTED_ZONE_ID="Z1234567890"

aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch "{
    \"Changes\": [{
      \"Action\": \"CREATE\",
      \"ResourceRecordSet\": {
        \"Name\": \"yourdomain.com\",
        \"Type\": \"A\",
        \"AliasTarget\": {
          \"HostedZoneId\": \"ZP97RAFLXTNZK\",
          \"DNSName\": \"$ALB_DNS\",
          \"EvaluateTargetHealth\": true
        }
      }
    }, {
      \"Action\": \"CREATE\",
      \"ResourceRecordSet\": {
        \"Name\": \"www.yourdomain.com\",
        \"Type\": \"A\",
        \"AliasTarget\": {
          \"HostedZoneId\": \"ZP97RAFLXTNZK\",
          \"DNSName\": \"$ALB_DNS\",
          \"EvaluateTargetHealth\": true
        }
      }
    }]
  }"
```

> **ALB Hosted Zone ID by region**: The `ZP97RAFLXTNZK` above is the hosted zone ID for ALBs in `ap-south-1`. Each region has a different hosted zone ID for ALBs — look it up in the [AWS docs](https://docs.aws.amazon.com/general/latest/gr/elb.html).

```bash
# Option B: Using a non-Route53 registrar
# Add a CNAME record:
#   Host: @ (or yourdomain.com)
#   Value: k8s-abc-def-123456.ap-south-1.elb.amazonaws.com
#   TTL: 300

# Note: CNAME on root domain (@) isn't universally supported.
# Use ALIAS if available, or use www.yourdomain.com as the canonical name.
```

### Verify DNS propagation

```bash
# Check DNS resolution (may take 5-60 minutes to propagate):
dig yourdomain.com
# Should resolve to ALB IPs

# Test HTTPS:
curl -I https://yourdomain.com
# HTTP/2 200
# server: nginx

# Test API:
curl https://yourdomain.com/api/v1/health
# {"status":"healthy","database":"connected","redis":"connected"}
```

---

## Phase 11: Verify the Deployment

### All pods should be Running

```bash
kubectl get pods -n issue-tracker

# Expected output:
# NAME                             READY   STATUS    RESTARTS   AGE
# backend-7d9f8c-abc12             1/1     Running   0          5m
# backend-7d9f8c-def34             1/1     Running   0          5m
# backend-7d9f8c-ghi56             1/1     Running   0          5m
# frontend-5b6d7e-jkl78            1/1     Running   0          5m
# frontend-5b6d7e-mno90            1/1     Running   0          5m
# frontend-5b6d7e-pqr12            1/1     Running   0          5m
# nginx-4c5d6f-stu34               1/1     Running   0          5m
# nginx-4c5d6f-vwx56               1/1     Running   0          5m
# celery-worker-8e9f0a-yza78       1/1     Running   0          5m
# celery-beat-1b2c3d-bcd90         1/1     Running   0          5m
```

### Check logs for errors

```bash
# Backend logs:
kubectl logs -n issue-tracker -l app=backend --tail=50

# Frontend logs:
kubectl logs -n issue-tracker -l app=frontend --tail=50

# Celery logs:
kubectl logs -n issue-tracker -l app=celery-worker --tail=50
```

### Run a smoke test

```bash
API="https://yourdomain.com"

# 1. Health check
curl $API/api/v1/health

# 2. Login with the admin user you seeded
TOKEN=$(curl -s -X POST $API/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@yourdomain.com","password":"YOUR_SEED_ADMIN_PASSWORD"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token obtained: ${TOKEN:0:20}..."

# 3. Create a project
curl -s -X POST $API/api/v1/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Project","description":"Smoke test"}' \
  | python -m json.tool
```

---

## Phase 12: Configure GitHub Actions for Ongoing Deployments

With all secrets set in Phase 7, every push to `main` now automatically:
1. Runs tests
2. Builds new Docker images
3. Pushes to ECR
4. Updates the Kubernetes deployment (rolling update)

### Trigger your first CI/CD run

```bash
# Make a small change to trigger the pipeline:
echo "# Deploy trigger" >> README.md
git add README.md
git commit -m "chore: trigger initial CI/CD deployment"
git push origin main

# Watch the pipeline in GitHub:
# Your Repo → Actions → the running workflow
```

### Monitor the deployment

```bash
# Watch pods rolling update in real-time:
kubectl rollout status deployment/backend -n issue-tracker -w

# See events:
kubectl describe deployment backend -n issue-tracker | tail -20
```

---

## Post-Deployment Checklist

```
Infrastructure:
  ✓ All pods in Running state
  ✓ No pods in CrashLoopBackOff or Error state
  ✓ HPA created and showing metrics:
      kubectl get hpa -n issue-tracker

Application:
  ✓ https://yourdomain.com loads the login page
  ✓ Login works with admin credentials
  ✓ Can create a project
  ✓ Can create an issue
  ✓ File upload works (attaches file to issue)
  ✓ Celery tasks visible in ... actually, Flower isn't exposed publicly

DNS and SSL:
  ✓ HTTPS works (padlock in browser)
  ✓ HTTP redirects to HTTPS (try http://yourdomain.com)
  ✓ www.yourdomain.com works (if configured)

Monitoring:
  ✓ CloudWatch metrics visible in AWS Console
  ✓ ALB access logs going to S3 (if configured in Ingress annotations)
```

---

## Ongoing Operations

### Updating the Application

```bash
# Push code to main → GitHub Actions handles the rest automatically

# To deploy a specific image tag manually:
kubectl set image deployment/backend \
  backend=123456789012.dkr.ecr.ap-south-1.amazonaws.com/issue-tracker-backend:abc1234 \
  -n issue-tracker

# Monitor rollout:
kubectl rollout status deployment/backend -n issue-tracker
```

### Running Database Migrations

Migrations run automatically during CI/CD (the deploy job runs the migrate Job before the new application version starts). For manual migrations:

```bash
# Re-apply the migration job (change the job name to make it unique):
kubectl apply -f infra/kubernetes/jobs/migrate-job.yaml
kubectl wait --for=condition=complete job/db-migration -n issue-tracker --timeout=120s
kubectl logs -n issue-tracker -l job-name=db-migration
```

### Scaling

```bash
# View current HPA status:
kubectl get hpa -n issue-tracker

# NAME             REFERENCE               TARGETS          MINPODS  MAXPODS  REPLICAS
# backend-hpa      Deployment/backend      32%/60%, 40%/75%   3       30       3
# frontend-hpa     Deployment/frontend     15%/60%, 20%/75%   3       20       3
# celery-hpa       Deployment/celery-worker 5%/70%, 10%/80%   2       20       2

# Manually scale (bypasses HPA temporarily):
kubectl scale deployment backend --replicas=6 -n issue-tracker

# Scale back to HPA control:
kubectl scale deployment backend --replicas=3 -n issue-tracker
```

### Rotating Secrets

```bash
# Update a secret in Secrets Manager:
aws secretsmanager update-secret \
  --secret-id "issue-tracker/production/app-secrets" \
  --secret-string '{"JWT_SECRET_KEY": "new-rotated-secret", ...}' \
  --region ap-south-1

# External Secrets Operator syncs automatically (check refresh interval in external-secrets.yaml)
# Default refresh: every 1 hour

# Force immediate sync:
kubectl annotate externalsecret app-secrets \
  -n issue-tracker \
  force-sync=$(date +%s) --overwrite

# Restart pods to pick up new secret:
kubectl rollout restart deployment/backend -n issue-tracker
```

### Viewing Logs in Production

```bash
# Real-time logs from all backend pods:
kubectl logs -n issue-tracker -l app=backend -f

# Logs from a specific pod:
kubectl logs -n issue-tracker backend-7d9f8c-abc12 -f

# Previous container logs (if pod restarted):
kubectl logs -n issue-tracker backend-7d9f8c-abc12 --previous
```

---

## Cost Management

### Full Production Cost Breakdown

```
Per month at minimum scale (3 nodes, steady state):

EKS Control Plane:        $73/month   (fixed)
EC2 nodes (3× c6i.xlarge): $373/month  (on-demand, 3× $124)
RDS db.r6g.large Multi-AZ: $276/month
ElastiCache (6 nodes):    $728/month
NAT Gateways (3):         $99/month
ALB:                      $16/month
S3 (storage + requests):  ~$5/month
Secrets Manager:          $1.20/month (3 secrets × $0.40)
ECR:                      ~$2/month
Data transfer:            ~$10/month
TOTAL:                    ~$1,583/month
```

### Reducing Costs for Learning/Staging

```bash
# Option 1: Use smaller instance types
# In terraform.tfvars, change:
node_instance_type = "t3.medium"    # 2 vCPU, 4 GB — 80% cheaper
db_instance_class  = "db.t3.medium" # cheapest RDS — 90% cheaper
redis_node_type    = "cache.t3.micro" # cheapest ElastiCache — 95% cheaper

# Option 2: Disable Multi-AZ for RDS (dev/staging only)
# In infra/terraform/modules/rds/main.tf:
# multi_az = false

# Option 3: Use fewer NAT gateways (1 instead of 3)
# Saves ~$66/month but reduces HA for private subnets

# Option 4: Use Spot instances for nodes
# Add to node group configuration:
# capacity_type = "SPOT"
# Up to 70% savings — pods may be evicted, but EKS reschedules them

# Rough cost at minimum scale for learning:
# t3.medium nodes × 2:   $60/month
# db.t3.medium (no HA):  $27/month
# cache.t3.micro:         $27/month
# Other:                 $100/month
# TOTAL:                 ~$214/month
```

---

## Teardown (Deleting All Resources)

When you're done and want to stop paying:

```bash
# IMPORTANT: Do this in order — Kubernetes resources first, then Terraform

# Step 1: Delete Kubernetes resources (prevents ALB from lingering)
kubectl delete namespace issue-tracker
# This deletes all pods, services, and importantly the Ingress (which deletes the ALB)

# Wait for ALB to be deleted (check AWS Console → EC2 → Load Balancers)
# Takes ~2 minutes

# Step 2: Terraform destroy
cd infra/terraform/environments/production

export TF_VAR_db_password="the-password-you-used"
export TF_VAR_redis_auth_token="the-token-you-used"

terraform destroy -var-file="terraform.tfvars"
# Type "yes" when prompted
# Takes ~10 minutes

# Step 3: Delete ECR images (so the repositories can be destroyed)
# If terraform destroy fails on ECR, manually delete images first:
aws ecr batch-delete-image \
  --repository-name issue-tracker-backend \
  --image-ids "$(aws ecr list-images --repository-name issue-tracker-backend --query 'imageIds[*]' --output json)" \
  --region ap-south-1

# Step 4: Delete the Terraform state bucket (Terraform can't delete itself)
aws s3 rb s3://issue-tracker-terraform-state --force

# Step 5: Delete the DynamoDB table
aws dynamodb delete-table \
  --table-name issue-tracker-terraform-locks \
  --region ap-south-1

# Step 6: Delete Secrets Manager secret
aws secretsmanager delete-secret \
  --secret-id "issue-tracker/production/app-secrets" \
  --force-delete-without-recovery \
  --region ap-south-1

echo "All resources deleted. No more charges."
```

> **Verify in AWS Console**: After teardown, check EC2, RDS, ElastiCache, and Load Balancers to confirm everything is gone. Lingering resources continue to accrue charges.

---

## Troubleshooting Production Issues

### Pods in CrashLoopBackOff

```bash
# Get pod name:
kubectl get pods -n issue-tracker

# Describe the pod for events:
kubectl describe pod backend-7d9f8c-abc12 -n issue-tracker

# Check logs:
kubectl logs backend-7d9f8c-abc12 -n issue-tracker

# Common causes:
# 1. Secret not synced — ExternalSecret pending
kubectl get externalsecret -n issue-tracker

# 2. Database connection failed — check DATABASE_URL
kubectl exec -n issue-tracker backend-7d9f8c-abc12 -- env | grep DATABASE

# 3. Out of memory — increase resources in deployment.yaml
```

### ALB Not Created (Ingress Stuck)

```bash
# Check ALB Ingress Controller logs:
kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller

# Common causes:
# 1. IAM permissions not set up correctly
# 2. Subnets not tagged with correct EKS cluster tags
#    Required tags: kubernetes.io/cluster/CLUSTER_NAME = shared
#    kubernetes.io/role/elb = 1 (for public subnets)
#    kubernetes.io/role/internal-elb = 1 (for private subnets)
```

### Database Connection Issues

```bash
# Test connectivity from inside a pod:
kubectl exec -it -n issue-tracker \
  $(kubectl get pod -n issue-tracker -l app=backend -o name | head -1) \
  -- python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
import os
engine = create_async_engine(os.environ['DATABASE_URL'])
async def test():
    async with engine.connect() as conn:
        print('Connection successful')
asyncio.run(test())
"
```

### External Secrets Not Syncing

```bash
# Check ExternalSecret status:
kubectl describe externalsecret app-secrets -n issue-tracker

# Check ClusterSecretStore:
kubectl describe clustersecretstore aws-secrets-manager

# Check ESO controller logs:
kubectl logs -n external-secrets -l app.kubernetes.io/name=external-secrets

# Verify IAM permissions:
# The backend pod service account must have secretsmanager:GetSecretValue permission
```

---

## What You've Built

Congratulations! You now have:

```
Production Infrastructure:
  ✓ High-availability VPC (3 AZs, public + private subnets)
  ✓ EKS cluster with 3-15 EC2 nodes
  ✓ RDS PostgreSQL Multi-AZ (automatic failover)
  ✓ ElastiCache Redis cluster (3 shards, HA)
  ✓ S3 for file attachments
  ✓ ECR for private Docker images
  ✓ ALB for HTTPS traffic routing
  ✓ AWS Secrets Manager for secrets
  ✓ IAM roles with least privilege

Application Stack:
  ✓ FastAPI backend (3+ replicas, HPA auto-scaling)
  ✓ Next.js frontend (3+ replicas, HPA auto-scaling)
  ✓ Celery workers for async tasks
  ✓ Nginx reverse proxy
  ✓ External Secrets Operator for secret management
  ✓ Migration Job for database schema updates

CI/CD Pipeline:
  ✓ GitHub Actions: test → build → push → deploy
  ✓ OIDC keyless authentication (no stored AWS keys)
  ✓ Rolling deployments with zero downtime
  ✓ Automatic image tagging with git SHA

Security:
  ✓ HTTPS with free ACM certificate (auto-renewed)
  ✓ Private subnets for database and cache
  ✓ Security groups restricting traffic
  ✓ IRSA for pod-level AWS IAM permissions
  ✓ Secrets never in git or environment variables
```

This is the same architecture that powers real SaaS applications serving millions of users. You now understand how every piece works — from the React component in the browser to the PostgreSQL WAL log on disk.

---

## Further Reading & Videos

- **YouTube**: Search "AWS EKS deployment tutorial" — end-to-end EKS walkthrough
- **YouTube**: Search "Terraform AWS EKS production" — production-grade IaC
- **YouTube**: Search "GitHub Actions AWS OIDC" — keyless auth setup
- **YouTube**: Search "Kubernetes rolling update zero downtime" — deployment strategies
- **Official Docs**: [EKS getting started](https://docs.aws.amazon.com/eks/latest/userguide/getting-started.html)
- **Official Docs**: [Terraform AWS provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- **Official Docs**: [GitHub Actions OIDC with AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- **Official Docs**: [Kubernetes best practices](https://kubernetes.io/docs/concepts/cluster-administration/manage-deployment/)

---

*You have completed the course. Go build something great.*
