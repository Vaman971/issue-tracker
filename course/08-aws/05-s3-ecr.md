# Module 08-05 — S3 & ECR: Object Storage & Container Registry

---

## AWS ECR — Elastic Container Registry

ECR is AWS's private Docker container registry. Like Docker Hub but private and integrated with IAM:

```
Docker Hub (public):
  docker pull nginx:latest           → Free, public
  docker push yourusername/myapp     → Requires Docker Hub account

AWS ECR (private):
  docker pull 123456.dkr.ecr.ap-south-1.amazonaws.com/myapp:latest
  docker push 123456.dkr.ecr.ap-south-1.amazonaws.com/myapp:v1.0
  → Authenticated via IAM (no separate registry credentials!)
  → Images stored in YOUR AWS account, private
```

### ECR Architecture

```
GitHub Actions CI/CD:
  1. Build Docker image
  2. aws ecr get-login-password --region ap-south-1 | docker login ...
  3. docker push 123456.dkr.ecr.ap-south-1.amazonaws.com/backend:abc123
  
                        ECR
                  ┌──────────────┐
                  │ Repositories │
                  │              │
                  │ backend/     │
                  │   :abc123    │ ← git commit SHA
                  │   :latest    │ ← mutable tag
                  │              │
                  │ frontend/    │
                  │   :abc123    │
                  │   :latest    │
                  └──────────────┘
                         │
                    EKS pulls images:
                    kubelet → ECR
                    (authenticated via node IAM role)
```

### ECR Terraform Configuration

```hcl
# infra/terraform/modules/ecr/main.tf

resource "aws_ecr_repository" "backend" {
  name                 = "issue-tracker-backend"
  image_tag_mutability = "MUTABLE"  # "latest" tag can be overwritten
  
  image_scanning_configuration {
    scan_on_push = true  # Scan for CVEs on every push
  }
  
  encryption_configuration {
    encryption_type = "AES256"  # Encrypt images at rest
  }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "issue-tracker-frontend"
  image_tag_mutability = "MUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
}

# Lifecycle policy: automatically clean up old images
resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      }
    ]
  })
}
```

### Why ECR Instead of Docker Hub?

```
Security:
  ✓ Private (no public exposure)
  ✓ IAM-controlled (no registry username/password to manage)
  ✓ Images in YOUR AWS account
  ✓ Image scanning for CVEs

Performance:
  ✓ Within AWS network (EKS pulls from ECR in same region = fast)
  ✓ No bandwidth charges within same region

Integration:
  ✓ Native IAM authentication
  ✓ GitHub Actions OIDC works with ECR
  ✓ EKS nodes can pull via node IAM role (no credentials in pod)

Cost:
  - $0.10/GB/month storage
  - Free data transfer within the same AWS region
```

---

## S3 — Object Storage

We covered S3 in detail in [Module 05-02](../05-caching-storage/02-s3-file-storage.md). Here's the infrastructure perspective:

### S3 Versioning

With versioning enabled:

```
Upload "document.pdf":
  Version 1: 2024-01-01 → actual file

Upload updated "document.pdf":
  Version 1: 2024-01-01 → still there (older version)
  Version 2: 2024-01-15 → new file

"Delete" document.pdf:
  S3 adds a "delete marker" (doesn't actually delete)
  Version 1: still there
  Version 2: still there
  Delete marker: most recent version

Restore by deleting the delete marker → original file back!
```

This protects against:
- Accidental deletion by application bugs
- Ransomware attacks (can't encrypt all versions)
- Compliance requirements (audit trails)

### S3 Storage Classes (Cost Optimization)

```
For old attachment files you rarely access:

Standard (default): $0.023/GB/month   ← attachments in last 30 days
Standard-IA:        $0.0125/GB/month  ← attachments 30-90 days old
Glacier:            $0.004/GB/month   ← attachments >90 days old

S3 Intelligent-Tiering: automatically moves objects between tiers
based on access patterns — great for unknown usage patterns
```

For this project, a simple lifecycle rule:

```hcl
resource "aws_s3_bucket_lifecycle_configuration" "attachments" {
  bucket = aws_s3_bucket.attachments.id
  
  rule {
    id     = "transition-to-ia"
    status = "Enabled"
    
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
}
```

---

## Pushing Images in CI/CD

```yaml
# .github/workflows/deploy.yml (build-backend job)

- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    # Use OIDC — no stored AWS keys in GitHub!
    role-to-assume: ${{ secrets.AWS_GITHUB_ACTIONS_ROLE_ARN }}
    aws-region: ap-south-1

- name: Login to ECR
  uses: aws-actions/amazon-ecr-login@v2

- name: Build and push backend image
  uses: docker/build-push-action@v5
  with:
    context: ./backend
    push: true
    tags: |
      ${{ secrets.ECR_REGISTRY }}/issue-tracker-backend:${{ github.sha }}
      ${{ secrets.ECR_REGISTRY }}/issue-tracker-backend:latest
    cache-from: type=registry,ref=${{ secrets.ECR_REGISTRY }}/issue-tracker-backend:latest
    cache-to: type=inline
    # ↑ Docker layer caching from ECR — speeds up builds
    # Layers unchanged since last push are not rebuilt
```

### Image Tags Strategy

```
:abc1234  (git commit SHA)
  → Pinned to exact code
  → Reproducible: "deploy abc1234" = exact same code always
  → Used in deployment: kubectl set image deployment/backend backend=ecr/backend:abc1234

:latest
  → Moves to newest build
  → Convenient for development/testing
  → Never use for production deployments (non-reproducible)
```

---

## Further Reading & Videos

- **YouTube**: Search "AWS ECR Tutorial" — getting started with ECR
- **YouTube**: Search "Docker push ECR GitHub Actions" — CI/CD integration
- **Official Docs**: [ECR documentation](https://docs.aws.amazon.com/ecr/)
- **Official Docs**: [S3 storage classes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html)

---

*Next: [Module 08-06 — ALB & Secrets Manager](./06-alb-secrets.md)*
