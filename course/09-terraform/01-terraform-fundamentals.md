# Module 09-01 — Terraform: State, Providers, Modules & Plan/Apply

---

## Learning Objectives

After this module you will:
- Understand what Terraform is and why Infrastructure as Code matters
- Know the plan/apply cycle
- Understand Terraform state and why it's critical
- Know how modules enable code reuse

---

## Infrastructure as Code (IaC)

The traditional way to create AWS infrastructure was to click around in the AWS Console. This has serious problems:

```
MANUAL (clicking in AWS Console):
  ✗ Not reproducible (can you remember every click?)
  ✗ Not auditable (no history of what changed, when, who)
  ✗ Error-prone (easy to miss a setting)
  ✗ Hard to replicate for staging/testing
  ✗ Drift: console changes aren't tracked
  ✗ Disaster recovery: recreating from scratch is slow and error-prone

INFRASTRUCTURE AS CODE (Terraform):
  ✓ Reproducible: run `terraform apply` → identical infrastructure
  ✓ Version controlled: git history shows every change
  ✓ Code-reviewed: team reviews infrastructure changes like code
  ✓ Automated: CI/CD can run `terraform apply` on merge
  ✓ Documented: code IS the documentation
  ✓ Disaster recovery: re-run apply → infrastructure recreated exactly
```

---

## How Terraform Works

```
1. You write .tf files describing desired infrastructure

2. terraform plan → compares desired vs actual → shows diff
   "Plan: 12 to add, 0 to change, 0 to destroy"

3. terraform apply → calls AWS APIs to create resources
   "Apply complete! Resources: 12 added, 0 changed, 0 destroyed."

4. Terraform saves the current state to terraform.tfstate

5. Next run: Terraform reads state + describes current AWS resources
             Computes diff → only changes what needs changing
```

---

## Terraform State

State is the most important (and most dangerous) concept in Terraform:

```
terraform.tfstate (JSON file):
{
  "resources": [
    {
      "type": "aws_vpc",
      "name": "main",
      "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
      "instances": [
        {
          "attributes": {
            "id": "vpc-0abc123",      ← The actual AWS VPC ID
            "cidr_block": "10.0.0.0/16",
            "arn": "arn:aws:ec2:...",
            ...all AWS resource attributes...
          }
        }
      ]
    },
    // ... every other resource ...
  ]
}
```

The state file is Terraform's "memory" — it knows that your `aws_vpc.main` resource is the real AWS VPC with ID `vpc-0abc123`.

**CRITICAL**: The state file contains sensitive data (passwords, secret ARNs). It must be:
- **Never committed to git** (add to .gitignore)
- **Stored in S3 with encryption** (remote state backend)
- **State locked** when someone is running terraform apply (S3 + DynamoDB)

### Remote State Backend

```hcl
# terraform/environments/production/versions.tf

terraform {
  backend "s3" {
    bucket         = "issue-tracker-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "ap-south-1"
    encrypt        = true      # Encrypt state at rest
    
    # State locking: prevents two people from running apply simultaneously
    dynamodb_table = "issue-tracker-terraform-locks"
  }
}
```

```
Team member A runs: terraform apply
  → Acquires lock in DynamoDB
  → Makes changes
  → Releases lock

Team member B simultaneously runs: terraform apply
  → Tries to acquire lock
  → Lock is held by A → BLOCKED
  → "Error: Error locking state..."
  → B must wait for A to finish

Without locking: both A and B apply simultaneously → state corruption!
```

---

## Terraform Configuration Language (HCL)

```hcl
# HCL (HashiCorp Configuration Language)

# Provider: which cloud/service to use
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"  # Use 5.x but not 6.x
    }
  }
  required_version = ">= 1.6"
}

provider "aws" {
  region = var.aws_region  # "ap-south-1"
}

# Variables: parameterize your configuration
variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "issue-tracker-prod"
}

variable "instance_type" {
  type    = string
  default = "c6i.xlarge"
}

# Resources: what to create
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  
  tags = {
    Name = "${var.cluster_name}-vpc"
    Environment = "production"
  }
}

# Data sources: read existing AWS resources (not created by Terraform)
data "aws_caller_identity" "current" {}
# Now use: data.aws_caller_identity.current.account_id

# Locals: computed values (avoid repetition)
locals {
  common_tags = {
    Project     = "issue-tracker"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

# Outputs: values to expose after apply
output "vpc_id" {
  description = "The VPC ID"
  value       = aws_vpc.main.id
}

output "eks_cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = aws_eks_cluster.main.endpoint
  sensitive   = true  # Won't show in normal output
}
```

---

## Resource References — How Resources Connect

Terraform knows the dependency order from references:

```hcl
# VPC must exist before subnets
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "public" {
  vpc_id = aws_vpc.main.id   # ← Reference creates implicit dependency
  # Terraform knows: create VPC first, then subnet
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id   # ← Another dependency on VPC
}

# RDS depends on subnet group, which depends on subnets
resource "aws_db_subnet_group" "main" {
  subnet_ids = aws_subnet.private[*].id  # ← Depends on all private subnets
}

resource "aws_db_instance" "main" {
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  # Terraform creates these in the right order
}
```

Terraform builds a **dependency graph** and creates resources in the correct order (parallel where possible).

---

## Modules — Code Reuse

Modules are reusable Terraform configurations. This project has 6 modules:

```
infra/terraform/
├── environments/production/
│   ├── main.tf      ← Uses all modules
│   ├── variables.tf
│   └── outputs.tf
│
└── modules/
    ├── vpc/         ← Create VPC, subnets, NAT
    ├── eks/         ← Create EKS cluster + nodes
    ├── rds/         ← Create PostgreSQL
    ├── elasticache/ ← Create Redis
    ├── ecr/         ← Create container registries
    └── iam/         ← Create IAM roles
```

```hcl
# infra/terraform/environments/production/main.tf

# Use the VPC module
module "vpc" {
  source = "../../modules/vpc"
  
  # Pass inputs to the module
  name               = var.app_name
  vpc_cidr           = var.vpc_cidr           # "10.0.0.0/16"
  availability_zones = var.availability_zones  # ["ap-south-1a", "ap-south-1b", "ap-south-1c"]
  cluster_name       = var.cluster_name
}

# Use the EKS module, pass outputs from VPC module
module "eks" {
  source = "../../modules/eks"
  
  cluster_name         = var.cluster_name
  kubernetes_version   = var.kubernetes_version  # "1.30"
  node_instance_type   = var.node_instance_type  # "c6i.xlarge"
  
  # Use outputs from the VPC module
  vpc_id              = module.vpc.vpc_id
  private_subnet_ids  = module.vpc.private_subnet_ids
}

# Use the RDS module
module "rds" {
  source = "../../modules/rds"
  
  identifier       = "${var.app_name}-db"
  instance_class   = var.db_instance_class   # "db.r6g.large"
  db_password      = var.db_password
  
  private_subnet_ids      = module.vpc.private_subnet_ids
  rds_security_group_id   = module.vpc.rds_security_group_id
}

# Use the ElastiCache module
module "elasticache" {
  source = "../../modules/elasticache"
  
  name              = "${var.app_name}-redis"
  node_type         = var.redis_node_type  # "cache.r6g.large"
  num_shards        = 3
  
  private_subnet_ids            = module.vpc.private_subnet_ids
  elasticache_security_group_id = module.vpc.elasticache_security_group_id
}
```

---

## The Terraform Workflow

```bash
# 1. Initialize (download providers + modules)
cd infra/terraform/environments/production
terraform init

# 2. Plan (dry run — shows what would change)
terraform plan -var-file="production.tfvars"

# Output:
# Plan: 47 to add, 0 to change, 0 to destroy.
# 
# + aws_vpc.main {
#     + cidr_block = "10.0.0.0/16"
#     + id = (known after apply)
#   }
# ... etc

# 3. Apply (make the changes)
terraform apply -var-file="production.tfvars"
# Review the plan, type "yes" to proceed

# 4. View outputs
terraform output
# eks_cluster_endpoint = "https://..."
# rds_endpoint = "issue-tracker-db.xyz.ap-south-1.rds.amazonaws.com"

# 5. Destroy (when you want to tear down everything)
terraform destroy -var-file="production.tfvars"
```

---

## Terraform Workspaces and Environments

Different environments (dev/staging/prod) use separate state:

```
Using directories (this project's approach):
  terraform/environments/production/   ← separate state per directory
  terraform/environments/staging/      ← would be added for staging
  
Each environment directory:
  - Has its own backend configuration
  - Has its own state file in S3
  - Has its own variables (.tfvars file)
  
Security: separate AWS accounts for each environment is even safer
  - Production account: prod-issuetracker
  - Development account: dev-issuetracker
  - CI/CD role can only deploy to its target account
```

---

## Variables File

```hcl
# infra/terraform/environments/production/production.tfvars

app_name          = "issue-tracker"
aws_region        = "ap-south-1"
vpc_cidr          = "10.0.0.0/16"
availability_zones = ["ap-south-1a", "ap-south-1b", "ap-south-1c"]
cluster_name       = "issue-tracker-prod"
kubernetes_version = "1.30"
node_instance_type = "c6i.xlarge"
db_instance_class  = "db.r6g.large"
redis_node_type    = "cache.r6g.large"
github_repo        = "username/issue-tracker"

# Sensitive values — set via environment variables or secrets manager
# db_password = set via TF_VAR_db_password environment variable
# redis_auth_token = set via TF_VAR_redis_auth_token
```

---

## Terraform Outputs (Used by CI/CD)

```hcl
# infra/terraform/environments/production/outputs.tf

output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "ecr_backend_repository_url" {
  value = module.ecr.backend_repository_url
  # "123456789.dkr.ecr.ap-south-1.amazonaws.com/issue-tracker-backend"
}

output "ecr_frontend_repository_url" {
  value = module.ecr.frontend_repository_url
}

output "rds_endpoint" {
  value     = module.rds.db_endpoint
  sensitive = true
}

output "elasticache_endpoint" {
  value     = module.elasticache.cluster_endpoint
  sensitive = true
}
```

GitHub Actions reads these outputs to know where to push images and deploy:
```bash
ECR_BACKEND=$(terraform output -raw ecr_backend_repository_url)
EKS_CLUSTER=$(terraform output -raw eks_cluster_name)
```

---

## Further Reading & Videos

- **YouTube**: Search "Terraform Tutorial for Beginners" — TechWorld with Nana covers Terraform comprehensively
- **YouTube**: Search "Terraform State Backend S3" — how to set up remote state
- **YouTube**: Search "Terraform Modules" — code reuse patterns
- **Official Docs**: [Terraform documentation](https://developer.hashicorp.com/terraform/docs)
- **Official Docs**: [Terraform AWS provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

---

*Next: [Module 09-02 — This Project's Infrastructure Walkthrough](./02-project-infrastructure.md)*
