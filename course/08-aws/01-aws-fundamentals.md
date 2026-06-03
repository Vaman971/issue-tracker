# Module 08-01 — AWS Fundamentals: Regions, IAM, VPC & Core Services

---

## Learning Objectives

After this module you will:
- Understand the AWS global infrastructure
- Know IAM (Identity and Access Management) — the key to AWS security
- Have a map of every AWS service used in this project
- Understand the principle of least privilege

---

## AWS Global Infrastructure

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        AWS GLOBAL INFRASTRUCTURE                         │
│                                                                          │
│  Region: ap-south-1 (Mumbai)    Region: us-east-1 (N. Virginia)         │
│  ┌──────────────────────────┐   ┌──────────────────────────────────┐    │
│  │                          │   │                                  │    │
│  │  AZ: ap-south-1a         │   │  AZ: us-east-1a                  │    │
│  │  ┌────────────────────┐  │   │  (Data center 1)                 │    │
│  │  │  Data center 1     │  │   │                                  │    │
│  │  └────────────────────┘  │   │  AZ: us-east-1b                  │    │
│  │                          │   │  (Data center 2)                 │    │
│  │  AZ: ap-south-1b         │   │                                  │    │
│  │  ┌────────────────────┐  │   │  AZ: us-east-1c                  │    │
│  │  │  Data center 2     │  │   │  (Data center 3)                 │    │
│  │  └────────────────────┘  │   └──────────────────────────────────┘    │
│  │                          │                                           │
│  │  AZ: ap-south-1c         │                                           │
│  └──────────────────────────┘                                           │
│                                                                          │
│  ~33 Regions worldwide, 2-6 AZs per Region, 100+ Edge Locations         │
└──────────────────────────────────────────────────────────────────────────┘
```

**Region**: A geographic area with multiple data centers. This project uses `ap-south-1` (Mumbai). Choose the region closest to your users.

**Availability Zone (AZ)**: One or more physically separate data centers within a Region. They have:
- Independent power, cooling, and networking
- Low-latency connections between AZs in a Region
- Distributed across them → survive a single data center failure

**Why multi-AZ?**:
- RDS Multi-AZ: Primary in ap-south-1a, standby in ap-south-1b
- EKS nodes across 3 AZs
- If ap-south-1a's data center floods → app still runs on 1b and 1c

---

## IAM — Identity and Access Management

IAM controls WHO can do WHAT in your AWS account:

```
IAM Entities:
  
  User: "alice"
    → Has credentials (access key + secret)
    → Can log in to AWS Console
    → Used by humans
  
  Group: "developers"
    → Collection of users
    → Permissions applied to all members
  
  Role: "backend-pod-role"
    → Like a User but for AWS services (EC2, Lambda, EKS pods)
    → No permanent credentials (temporary tokens)
    → Used by machines
  
  Policy: "S3UploadPolicy"
    → JSON document defining permissions
    → Attached to users, groups, or roles
```

### IAM Policy Structure

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::issue-tracker-attachments-prod/*"
      //                                                      ↑
      //                              Only this bucket, not ALL S3 buckets!
    }
  ]
}
```

### Principle of Least Privilege

```
WRONG (over-permissioned):
  "Give the backend full S3 access"
  → If backend is compromised, attacker can read ALL S3 buckets

CORRECT (least privilege):
  "Give the backend only s3:GetObject + s3:PutObject on ONLY the attachments bucket"
  → If compromised, attacker can only access attachments bucket

This project's IAM roles:
  backend-role: S3 access to attachments bucket only
  external-secrets-role: Read specific Secrets Manager secrets only
  github-actions-role: ECR push, EKS update deployments only
```

### IAM in This Project

```hcl
# infra/terraform/modules/iam/main.tf

# EKS Cluster Role (what the Kubernetes control plane can do)
resource "aws_iam_role" "eks_cluster" {
  name = "${var.cluster_name}-cluster-role"
  assume_role_policy = jsonencode({
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}
resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  role = aws_iam_role.eks_cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

# Node Role (what EC2 worker nodes can do)
resource "aws_iam_role" "eks_node" {
  name = "${var.cluster_name}-node-role"
  # Permissions: EKS worker node, ECR read (pull images), VPC CNI, SSM (remote access)
}

# GitHub Actions OIDC Role (CI/CD)
# Allows GitHub Actions to push to ECR and deploy to EKS
# WITHOUT storing AWS credentials in GitHub!
resource "aws_iam_role" "github_actions" {
  name = "github-actions-role"
  assume_role_policy = jsonencode({
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
        }
      }
    }]
  })
}
```

---

## AWS Services Used in This Project

```
┌────────────────────────────────────────────────────────────────────────┐
│                     AWS SERVICES MAP                                   │
│                                                                        │
│  ┌─────────────┐                                                       │
│  │   Route 53  │  ← DNS (yourdomain.com → ALB)                       │
│  └──────┬──────┘                                                       │
│         ▼                                                               │
│  ┌─────────────┐                                                       │
│  │     ALB     │  ← Application Load Balancer (HTTPS termination)     │
│  └──────┬──────┘                                                       │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                           VPC                                    │  │
│  │                                                                  │  │
│  │  ┌──────────────────────────────────────────────────────────┐   │  │
│  │  │                      EKS Cluster                         │   │  │
│  │  │  [nginx pods] → [backend pods] + [frontend pods]         │   │  │
│  │  │  [celery worker pods] + [celery beat pod]                │   │  │
│  │  └──────────────────────────────────────────────────────────┘   │  │
│  │                          │           │                            │  │
│  │                          ▼           ▼                            │  │
│  │  ┌────────────────┐  ┌──────────────────────┐                   │  │
│  │  │  RDS PostgreSQL│  │  ElastiCache Redis   │                   │  │
│  │  │  Multi-AZ      │  │  Cluster mode        │                   │  │
│  │  └────────────────┘  └──────────────────────┘                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  External to VPC (but accessed securely):                              │
│  ┌─────┐  ┌─────────────────┐  ┌──────────────────┐                  │
│  │ ECR │  │ Secrets Manager │  │       S3          │                  │
│  │     │  │                 │  │                   │                  │
│  │ Container│ JWT secrets,  │  │  File attachments │                  │
│  │ images │  DB passwords   │  │                   │                  │
│  └─────┘  └─────────────────┘  └──────────────────┘                  │
│                                                                        │
│  Monitoring/Observability:                                             │
│  ┌──────────────────────┐                                             │
│  │  CloudWatch           │  ← Logs, metrics, alarms                  │
│  └──────────────────────┘                                             │
└────────────────────────────────────────────────────────────────────────┘
```

| Service | Purpose | Module |
|---------|---------|--------|
| EKS | Managed Kubernetes | 08-03 |
| VPC | Private network | 08-02 |
| RDS | PostgreSQL database | 08-04 |
| ElastiCache | Redis cluster | 08-04 |
| S3 | File storage | 05-02 |
| ECR | Container registry | 08-05 |
| ALB | Load balancer | 08-06 |
| Secrets Manager | Secret storage | 08-06 |
| IAM | Identity/permissions | this module |
| Route53 | DNS | this module |
| CloudWatch | Monitoring/logs | production module |

---

## ARN — Amazon Resource Name

Every AWS resource has a unique identifier (ARN):

```
arn:aws:s3:::my-bucket
arn:partition:service:region:account-id:resource

arn:aws:iam::123456789012:role/backend-role
                           ↑
                     account ID (12 digits)

arn:aws:rds:ap-south-1:123456789012:db:issue-tracker-db

arn:aws:secretsmanager:ap-south-1:123456789012:secret:issue-tracker/production/app-secrets
```

ARNs are used in IAM policies to specify which resources a permission applies to.

---

## AWS Pricing Model

AWS charges for what you use:

```
EKS:
  Cluster: $0.10/hour (~$73/month)
  EC2 nodes: depends on instance type
  c6i.xlarge: ~$0.17/hour each
  3 nodes: ~$376/month

RDS:
  db.r6g.large: ~$0.19/hour (~$138/month)
  Storage: ~$0.115/GB/month

ElastiCache:
  cache.r6g.large: ~$0.166/hour per node
  3 nodes: ~$360/month

ALB:
  ~$0.008/hour + $0.008/LCU (processed connections)
  Typical: ~$20-50/month

S3:
  Storage: ~$0.023/GB/month
  Requests: negligible

Total estimate for this project: ~$1000-1500/month
```

---

## AWS CLI — Useful Commands

```bash
# Configure credentials
aws configure
# Enter: Access Key ID, Secret Access Key, Region (ap-south-1), Format (json)

# Test authentication
aws sts get-caller-identity

# List EKS clusters
aws eks list-clusters --region ap-south-1

# Update kubeconfig for kubectl access
aws eks update-kubeconfig --name issue-tracker-prod --region ap-south-1

# List ECR repositories
aws ecr describe-repositories --region ap-south-1

# Get ECR login (to push images)
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin \
  123456789.dkr.ecr.ap-south-1.amazonaws.com

# List RDS instances
aws rds describe-db-instances --region ap-south-1

# List Secrets Manager secrets
aws secretsmanager list-secrets --region ap-south-1
```

---

## Further Reading & Videos

- **YouTube**: Search "AWS Tutorial for Beginners" — TechWorld with Nana has a full AWS Fundamentals course
- **YouTube**: Search "AWS IAM Tutorial" — understand IAM deeply before using AWS in production
- **YouTube**: Search "AWS IAM Best Practices" — security-focused AWS tutorial
- **Official Docs**: [AWS Documentation](https://docs.aws.amazon.com) — start with the service you're using
- **Free Training**: [AWS Skill Builder](https://skillbuilder.aws) — official free courses

---

*Next: [Module 08-02 — VPC: Subnets, NAT & Security Groups](./02-networking-vpc.md)*
