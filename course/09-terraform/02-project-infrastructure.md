# Module 09-02 — This Project's Infrastructure: Complete Terraform Walkthrough

---

## The Infrastructure We're Building

```
Total AWS resources created by Terraform: ~50+

Networking (vpc module):
  - 1 VPC
  - 3 public subnets (one per AZ)
  - 3 private subnets (one per AZ)
  - 1 Internet Gateway
  - 3 NAT Gateways (one per AZ — HA)
  - 6 Route tables
  - 5 Security groups (ALB, EKS nodes, RDS, ElastiCache, general)

Compute (eks module):
  - 1 EKS cluster
  - 1 Node group (3-10 EC2 c6i.xlarge instances)
  - 1 OIDC provider

Database (rds module):
  - 1 RDS PostgreSQL instance (Multi-AZ)
  - 1 DB subnet group
  - 1 DB parameter group

Cache (elasticache module):
  - 1 ElastiCache replication group (3 shards, 6 nodes)
  - 1 ElastiCache subnet group

Containers (ecr module):
  - 2 ECR repositories (backend, frontend)
  - 2 ECR lifecycle policies

Identity (iam module):
  - 4 IAM roles (EKS cluster, EKS nodes, GitHub Actions, backend pod)
  - 6 IAM policies
  - 1 IAM OIDC provider for GitHub Actions

Storage:
  - 1 S3 bucket (file attachments)
  - 1 S3 bucket (terraform state)
  - 1 DynamoDB table (terraform locks)
```

---

## Step-by-Step: First-Time Infrastructure Setup

### Phase 0: Bootstrap (One Time Only)

Before Terraform can store its state in S3, you must create the S3 bucket manually:

```bash
# Create the state bucket manually (one-time only)
aws s3 mb s3://issue-tracker-terraform-state --region ap-south-1

# Enable versioning (to recover from state corruption)
aws s3api put-bucket-versioning \
  --bucket issue-tracker-terraform-state \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket issue-tracker-terraform-state \
  --server-side-encryption-configuration \
    '{"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}'

# Block public access
aws s3api put-public-access-block \
  --bucket issue-tracker-terraform-state \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name issue-tracker-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-south-1
```

### Phase 1: Initialize and Plan

```bash
cd infra/terraform/environments/production

# Set sensitive variables as environment variables (never in files!)
export TF_VAR_db_password="$(openssl rand -base64 32)"
export TF_VAR_redis_auth_token="$(openssl rand -base64 32)"
export TF_VAR_jwt_secret="$(openssl rand -base64 64)"

# Initialize: download providers and modules
terraform init

# Plan: see what will be created (~50+ resources)
terraform plan -var-file="production.tfvars" -out=tfplan

# Review the plan carefully before applying!
```

### Phase 2: Apply (Create Infrastructure)

```bash
# Apply: create all the AWS resources
# This takes ~15-20 minutes (EKS alone takes 12-15 minutes)
terraform apply tfplan

# After completion, view outputs
terraform output
```

### Phase 3: Configure kubectl

```bash
# Get credentials to connect kubectl to EKS
aws eks update-kubeconfig \
  --name $(terraform output -raw eks_cluster_name) \
  --region ap-south-1

# Verify
kubectl get nodes
```

### Phase 4: Create Secrets in Secrets Manager

```bash
# Store application secrets (DB password, JWT key, etc.)
aws secretsmanager create-secret \
  --name "issue-tracker/production/app-secrets" \
  --secret-string '{
    "JWT_SECRET_KEY": "'$TF_VAR_jwt_secret'",
    "JWT_REFRESH_SECRET_KEY": "'$(openssl rand -base64 64)'",
    "DATABASE_URL": "postgresql+asyncpg://postgres:'$TF_VAR_db_password'@'$(terraform output -raw rds_endpoint)':5432/issuetracker",
    "CELERY_BROKER_URL": "redis://:'$TF_VAR_redis_auth_token'@'$(terraform output -raw elasticache_endpoint)':6379/1",
    "CELERY_RESULT_BACKEND": "redis://:'$TF_VAR_redis_auth_token'@'$(terraform output -raw elasticache_endpoint)':6379/2",
    "SEED_ADMIN_EMAIL": "admin@yourdomain.com",
    "SEED_ADMIN_PASSWORD": "initial-admin-password-change-me"
  }' \
  --region ap-south-1
```

### Phase 5: Apply Kubernetes Manifests

```bash
# Create namespace
kubectl apply -f infra/kubernetes/namespace.yaml

# Create ConfigMap
kubectl apply -f infra/kubernetes/configmap.yaml

# Deploy External Secrets Operator resources
kubectl apply -f infra/kubernetes/secrets/external-secrets.yaml
# ESO syncs secrets from Secrets Manager to K8s Secret

# Wait for K8s Secret to be created
kubectl wait --for=condition=ready \
  externalsecret/app-secrets \
  -n issue-tracker \
  --timeout=60s

# Deploy all components
kubectl apply -f infra/kubernetes/backend/
kubectl apply -f infra/kubernetes/frontend/
kubectl apply -f infra/kubernetes/nginx/
kubectl apply -f infra/kubernetes/celery/
kubectl apply -f infra/kubernetes/ingress/

# Wait for rollout
kubectl rollout status deployment/backend -n issue-tracker
kubectl rollout status deployment/frontend -n issue-tracker
kubectl rollout status deployment/nginx -n issue-tracker
```

---

## Understanding Each Module

### VPC Module

```hcl
# infra/terraform/modules/vpc/main.tf

# Key outputs used by other modules:
output "vpc_id" { value = aws_vpc.main.id }
output "public_subnet_ids" { value = aws_subnet.public[*].id }
output "private_subnet_ids" { value = aws_subnet.private[*].id }
output "rds_security_group_id" { value = aws_security_group.rds.id }
output "elasticache_security_group_id" { value = aws_security_group.elasticache.id }
output "eks_nodes_security_group_id" { value = aws_security_group.eks_nodes.id }
```

### EKS Module

```hcl
# infra/terraform/modules/eks/main.tf

# Install AWS Load Balancer Controller via Helm
resource "helm_release" "aws_load_balancer_controller" {
  depends_on = [aws_eks_node_group.main]
  # Must install after nodes are ready
  
  name       = "aws-load-balancer-controller"
  namespace  = "kube-system"
  chart      = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  version    = "1.6.2"
  
  values = [
    yamlencode({
      clusterName = var.cluster_name
      serviceAccount = {
        annotations = {
          "eks.amazonaws.com/role-arn" = aws_iam_role.aws_load_balancer_controller.arn
        }
      }
    })
  ]
}

# Install External Secrets Operator via Helm
resource "helm_release" "external_secrets" {
  depends_on = [aws_eks_node_group.main]
  
  name             = "external-secrets"
  namespace        = "external-secrets"
  chart            = "external-secrets"
  repository       = "https://charts.external-secrets.io"
  version          = "0.9.11"
  create_namespace = true
}
```

---

## The Complete variables.tf

```hcl
# infra/terraform/environments/production/variables.tf

variable "app_name" {
  description = "Application name (used for naming all resources)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of AZs to use"
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b", "ap-south-1c"]
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.30"
}

variable "node_instance_type" {
  description = "EC2 instance type for EKS nodes"
  type        = string
  default     = "c6i.xlarge"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.r6g.large"
}

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.r6g.large"
}

variable "github_repo" {
  description = "GitHub repo in format owner/repo"
  type        = string
}

# Sensitive (set via TF_VAR_* env vars, never in .tfvars file)
variable "db_password" {
  description = "RDS PostgreSQL password"
  type        = string
  sensitive   = true
}

variable "redis_auth_token" {
  description = "ElastiCache Redis auth token"
  type        = string
  sensitive   = true
}
```

---

## Cost Estimation

```bash
# Before applying, estimate costs with infracost
# (optional open-source tool)
infracost breakdown --path .

# Example output:
# Name                     Monthly Qty  Unit       Monthly Cost
# aws_eks_cluster.main              1  months              $73
# aws_instance (x3 nodes)     3 × 730  hours             $372
# aws_db_instance.main              1  months             $138
# aws_elasticache_replication 6 × 730  hours             $728
# aws_nat_gateway (x3)        3 × 730  hours             $100
# aws_data_transfer                  -  GB                 $10
# TOTAL                                                 $1,421/month
```

---

## Terraform Destroy — Tearing Down

```bash
# CAREFUL: This deletes ALL infrastructure

# Drain Kubernetes workloads first
kubectl delete --all deployments -n issue-tracker

# Apply terraform destroy
terraform destroy -var-file="production.tfvars"

# Type "yes" when prompted
# Takes ~10 minutes

# Delete the state bucket manually (terraform can't delete itself)
aws s3 rb s3://issue-tracker-terraform-state --force
```

See the [Teardown Guide](../../README.md) for the complete step-by-step.

---

## Further Reading & Videos

- **YouTube**: Search "Terraform AWS Tutorial Step by Step" — full project from scratch
- **YouTube**: Search "Terraform Modules Best Practices" — structuring large Terraform codebases
- **Official Registry**: [Terraform AWS modules](https://registry.terraform.io/namespaces/terraform-aws-modules) — community modules for common patterns
- **Official Docs**: [Terraform best practices](https://developer.hashicorp.com/terraform/language/modules/develop/structure)

---

*Next: [Module 10-01 — GitHub Actions CI/CD Pipeline](../10-cicd/01-github-actions.md)*
