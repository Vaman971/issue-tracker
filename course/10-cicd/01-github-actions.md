# Module 10-01 — GitHub Actions: CI/CD Pipelines, OIDC & EKS Deployment

---

## Learning Objectives

After this module you will:
- Understand what CI/CD is and why it matters
- Know the entire pipeline from code push to production
- Understand GitHub Actions OIDC (keyless AWS auth)
- Be able to trace any deployment failure

---

## What Is CI/CD?

**CI** = Continuous Integration: Automatically test every code change

**CD** = Continuous Deployment: Automatically deploy tested code

```
WITHOUT CI/CD (manual process):
  Developer writes code
  Developer runs tests locally (maybe)
  Developer manually builds Docker image
  Developer manually uploads to ECR
  Developer manually runs kubectl commands
  
  Problems:
  - Tests might not be run
  - Deployment steps might be skipped
  - Human error in command typos
  - No audit trail of deployments
  - Deployments are scary and infrequent

WITH CI/CD:
  Developer pushes code to GitHub
  Pipeline automatically:
    - Runs all tests
    - Builds Docker images
    - Pushes to ECR
    - Updates Kubernetes deployments
  
  Benefits:
  - Tests ALWAYS run (no bypassing)
  - Deployments are routine, not scary
  - Audit trail of every deployment (git history)
  - Catch bugs before they reach production
  - Deploy multiple times per day safely
```

---

## The Complete Pipeline

```
.github/workflows/deploy.yml

TRIGGER: Push to main branch OR manual dispatch

JOB 1: detect-changes
  ├── Check which directories changed (backend/ or frontend/)
  └── Output: backend=true/false, frontend=true/false

JOB 2: test-backend (if backend changed)
  ├── Start: PostgreSQL 16 service container
  ├── Start: Redis 7 service container
  ├── Install: Python 3.12 + requirements
  ├── Run: alembic upgrade head (migrations)
  ├── Run: pytest with coverage
  └── Upload: coverage report artifact

JOB 3: test-frontend (if frontend changed)
  ├── Install: Node 22 + npm ci
  ├── Run: eslint (code quality)
  └── Run: jest (unit tests with coverage)

JOB 4: build-backend (if test-backend passed)
  ├── Authenticate: GitHub OIDC → AWS IAM role
  ├── Login: to ECR
  ├── Build: Docker image (backend)
  ├── Tag: :${github.sha} and :latest
  └── Push: to ECR

JOB 5: build-frontend (if test-frontend passed)
  ├── Authenticate: GitHub OIDC → AWS IAM role
  ├── Build: Docker image (frontend)
  │         With NEXT_PUBLIC_API_URL build arg
  └── Push: to ECR

JOB 6: deploy (if builds passed)
  ├── Authenticate: GitHub OIDC → AWS IAM role
  ├── Update: kubeconfig for EKS
  ├── Apply: all Kubernetes manifests
  ├── Run: migration job (if backend built)
  ├── Set: new image tags
  ├── Wait: rollout status
  └── Verify: all pods healthy
```

---

## The deploy.yml File — Complete Walkthrough

```yaml
# .github/workflows/deploy.yml

name: Deploy to Production

on:
  push:
    branches: [main]        # Trigger on every push to main
  workflow_dispatch:         # Allow manual trigger from GitHub UI
    inputs:
      force_deploy:
        description: 'Force deploy even if no changes'
        type: boolean
        default: false

# Only allow one deployment at a time
# If two pushes happen quickly, the second waits for the first
concurrency:
  group: production-deploy
  cancel-in-progress: false  # Don't cancel ongoing deployments

jobs:
  # ── JOB 1: Detect what changed ──────────────────────────────────
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      backend: ${{ steps.filter.outputs.backend }}
      frontend: ${{ steps.filter.outputs.frontend }}
    steps:
      - uses: actions/checkout@v4
      
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            backend:
              - 'backend/**'
            frontend:
              - 'frontend/**'

  # ── JOB 2: Test Backend ─────────────────────────────────────────
  test-backend:
    needs: detect-changes
    # Only run if backend changed OR it's a manual dispatch
    if: needs.detect-changes.outputs.backend == 'true' || github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    
    # Service containers: start alongside the job
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: issuetracker_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
        # Wait until postgres is healthy before starting steps
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
    
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'          # Cache pip downloads
          cache-dependency-path: backend/requirements.txt
      
      - name: Install dependencies
        working-directory: backend
        run: pip install -r requirements.txt
      
      - name: Run migrations
        working-directory: backend
        env:
          # Must set APP_ENV for pydantic settings to not require all vars
          APP_ENV: testing
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/issuetracker_test
          REDIS_URL: redis://localhost:6379/0
          JWT_SECRET_KEY: test-secret-key
          JWT_REFRESH_SECRET_KEY: test-refresh-secret
        run: alembic upgrade head
      
      - name: Run tests
        working-directory: backend
        env:
          APP_ENV: testing
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/issuetracker_test
          REDIS_URL: redis://localhost:6379/0
          JWT_SECRET_KEY: test-secret-key
          JWT_REFRESH_SECRET_KEY: test-refresh-secret
        run: |
          pytest tests/ -v \
            --cov=app \
            --cov-report=term-missing \
            --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: backend/coverage.xml

  # ── JOB 3: Test Frontend ─────────────────────────────────────────
  test-frontend:
    needs: detect-changes
    if: needs.detect-changes.outputs.frontend == 'true' || github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      
      - name: Install dependencies
        working-directory: frontend
        run: npm ci  # Clean install (uses package-lock.json exactly)
      
      - name: Lint
        working-directory: frontend
        run: npm run lint
      
      - name: Test
        working-directory: frontend
        run: npm test -- --ci --coverage --passWithNoTests
        # --ci: fail on test suite errors
        # --passWithNoTests: don't fail if no tests exist yet

  # ── JOB 4: Build Backend ─────────────────────────────────────────
  build-backend:
    needs: [test-backend]
    # Build if test passed, or if only frontend changed (backend unchanged)
    if: |
      always() && 
      (needs.test-backend.result == 'success' || 
       needs.test-backend.result == 'skipped')
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      # OIDC: Get temporary AWS credentials without storing secrets
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_GITHUB_ACTIONS_ROLE_ARN }}
          aws-region: ap-south-1
      
      - name: Login to ECR
        uses: aws-actions/amazon-ecr-login@v2
      
      # Docker Buildx: multi-platform builds + layer caching
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Build and push backend image
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: |
            ${{ secrets.ECR_REGISTRY }}/issue-tracker-backend:${{ github.sha }}
            ${{ secrets.ECR_REGISTRY }}/issue-tracker-backend:latest
          # Use ECR for layer caching — speeds up builds
          cache-from: type=registry,ref=${{ secrets.ECR_REGISTRY }}/issue-tracker-backend:latest
          cache-to: type=inline

  # ── JOB 5: Build Frontend ────────────────────────────────────────
  build-frontend:
    needs: [test-frontend]
    if: |
      always() && 
      (needs.test-frontend.result == 'success' || 
       needs.test-frontend.result == 'skipped')
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_GITHUB_ACTIONS_ROLE_ARN }}
          aws-region: ap-south-1
      
      - name: Login to ECR
        uses: aws-actions/amazon-ecr-login@v2
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Build and push frontend image
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: true
          tags: |
            ${{ secrets.ECR_REGISTRY }}/issue-tracker-frontend:${{ github.sha }}
            ${{ secrets.ECR_REGISTRY }}/issue-tracker-frontend:latest
          # Build arg: the Next.js public URL (baked into JS bundle at build time)
          build-args: |
            NEXT_PUBLIC_API_BASE_URL=${{ secrets.NEXT_PUBLIC_API_URL }}
          cache-from: type=registry,ref=${{ secrets.ECR_REGISTRY }}/issue-tracker-frontend:latest
          cache-to: type=inline

  # ── JOB 6: Deploy ─────────────────────────────────────────────────
  deploy:
    needs: [build-backend, build-frontend]
    if: always() && !contains(needs.*.result, 'failure')
    runs-on: ubuntu-latest
    
    # Require manual approval for production deployments (optional)
    environment:
      name: production
      url: https://yourdomain.com
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_GITHUB_ACTIONS_ROLE_ARN }}
          aws-region: ap-south-1
      
      - name: Update kubeconfig
        run: |
          aws eks update-kubeconfig \
            --name ${{ secrets.EKS_CLUSTER_NAME }} \
            --region ap-south-1
      
      - name: Apply Kubernetes manifests
        run: |
          kubectl apply -f infra/kubernetes/namespace.yaml
          kubectl apply -f infra/kubernetes/configmap.yaml
          kubectl apply -f infra/kubernetes/secrets/
          kubectl apply -f infra/kubernetes/backend/
          kubectl apply -f infra/kubernetes/frontend/
          kubectl apply -f infra/kubernetes/nginx/
          kubectl apply -f infra/kubernetes/celery/
          kubectl apply -f infra/kubernetes/ingress/
      
      - name: Run database migrations
        if: needs.build-backend.result == 'success'
        run: |
          # Unique job name prevents duplicate runs
          JOB_NAME="db-migrate-${{ github.sha }}"
          
          # Substitute image tag in Job manifest
          sed "s|IMAGE_TAG|${{ github.sha }}|g" \
            infra/kubernetes/jobs/migrate-job.yaml | \
            kubectl apply -f -
          
          # Wait for job to complete (timeout 5 minutes)
          kubectl wait --for=condition=complete \
            job/$JOB_NAME \
            -n issue-tracker \
            --timeout=300s
          
          # Show migration logs
          kubectl logs job/$JOB_NAME -n issue-tracker
      
      - name: Update deployment images
        run: |
          if [ "${{ needs.build-backend.result }}" == "success" ]; then
            kubectl set image deployment/backend \
              backend=${{ secrets.ECR_REGISTRY }}/issue-tracker-backend:${{ github.sha }} \
              -n issue-tracker
            
            kubectl set image deployment/celery-worker \
              celery-worker=${{ secrets.ECR_REGISTRY }}/issue-tracker-backend:${{ github.sha }} \
              -n issue-tracker
            
            kubectl set image deployment/celery-beat \
              celery-beat=${{ secrets.ECR_REGISTRY }}/issue-tracker-backend:${{ github.sha }} \
              -n issue-tracker
          fi
          
          if [ "${{ needs.build-frontend.result }}" == "success" ]; then
            kubectl set image deployment/frontend \
              frontend=${{ secrets.ECR_REGISTRY }}/issue-tracker-frontend:${{ github.sha }} \
              -n issue-tracker
          fi
      
      - name: Wait for rollouts
        run: |
          kubectl rollout status deployment/backend \
            -n issue-tracker --timeout=600s
          kubectl rollout status deployment/frontend \
            -n issue-tracker --timeout=600s
          kubectl rollout status deployment/nginx \
            -n issue-tracker --timeout=300s
```

---

## GitHub Actions OIDC — Keyless AWS Authentication

This is critical for security. Traditional approach stored AWS secrets in GitHub:

```
WRONG (credentials as secrets):
  GitHub Secret: AWS_ACCESS_KEY_ID=AKIA...
  GitHub Secret: AWS_SECRET_ACCESS_KEY=wJalr...
  
  Risk: If GitHub is compromised, attacker gets permanent AWS access
  These credentials never expire!
```

```
RIGHT (OIDC - temporary credentials):
  GitHub generates a JWT token proving: "This is a job from vaman971/issue-tracker"
  
  AWS IAM verifies the JWT using GitHub's public keys
  → Issues temporary credentials (15-minute expiry)
  
  No permanent credentials stored anywhere!
```

```
Flow:
  GitHub Actions job starts
        │
        ▼ Request JWT from GitHub's OIDC provider
  GitHub issues JWT:
    {
      "iss": "https://token.actions.githubusercontent.com",
      "sub": "repo:vaman971/issue-tracker:ref:refs/heads/main",
      "aud": "sts.amazonaws.com"
    }
        │
        ▼ Call AWS STS AssumeRoleWithWebIdentity
  AWS IAM verifies:
    1. JWT signature (using GitHub's OIDC public keys)
    2. "sub" matches the allowed repo/branch pattern
    3. "aud" is sts.amazonaws.com
        │
        ▼ Issues temporary credentials:
    AWS_ACCESS_KEY_ID (expires in 15 minutes)
    AWS_SECRET_ACCESS_KEY
    AWS_SESSION_TOKEN
        │
        ▼ GitHub Actions uses these for the job duration
```

The IAM role is configured in Terraform:
```hcl
# infra/terraform/modules/iam/main.tf

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
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          # Only allow from YOUR repository
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
        }
      }
    }]
  })
}

# Permissions: what GitHub Actions can do
resource "aws_iam_role_policy" "github_actions" {
  role = aws_iam_role.github_actions.name
  
  policy = jsonencode({
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:ListClusters"
        ]
        Resource = "*"
      }
    ]
  })
}
```

---

## Required GitHub Secrets

```
In your GitHub repository → Settings → Secrets and variables → Actions:

AWS_GITHUB_ACTIONS_ROLE_ARN
  Value: arn:aws:iam::123456789012:role/github-actions-role
  Purpose: The IAM role to assume via OIDC

ECR_REGISTRY
  Value: 123456789012.dkr.ecr.ap-south-1.amazonaws.com
  Purpose: ECR registry URL for image tags

EKS_CLUSTER_NAME
  Value: issue-tracker-prod
  Purpose: Which EKS cluster to deploy to

NEXT_PUBLIC_API_URL
  Value: https://yourdomain.com
  Purpose: Baked into Next.js bundle at build time
```

---

## Understanding Pipeline Failures

```
Failure in test-backend:
  → build-backend job is skipped
  → deploy job is skipped (nothing broken reaches production)
  → Fix the failing test, push again

Failure in build-backend:
  → deploy job runs but skips image update for backend
  → Old backend version remains in production
  → Frontend can still be deployed (independent)

Failure in migration job:
  → kubectl wait --timeout returns non-zero exit code
  → deploy job fails
  → New pods are NOT started (image set already ran)
  → You need to: fix the migration, push fix, redeploy

Failure in rollout wait:
  → New pods crashed or readiness probe failed
  → kubectl rollout status returns failure
  → Previous pods might still be running (RollingUpdate)
  → kubectl rollout undo deployment/backend to rollback
```

---

## Path Filtering — Efficient Pipelines

```yaml
# Only test/build backend when backend/ changed
# Only test/build frontend when frontend/ changed

detect-changes:
  steps:
    - uses: dorny/paths-filter@v3
      with:
        filters: |
          backend:
            - 'backend/**'    # Any change in backend/ directory
          frontend:
            - 'frontend/**'   # Any change in frontend/ directory
```

This saves significant CI time:
- Documentation change → no tests run → no build
- Frontend-only change → no backend tests/build (saves ~5 minutes)
- Backend-only change → no frontend tests/build

---

## Further Reading & Videos

- **YouTube**: Search "GitHub Actions Tutorial for Beginners" — TechWorld with Nana
- **YouTube**: Search "GitHub Actions OIDC AWS" — keyless authentication walkthrough
- **YouTube**: Search "CI/CD Pipeline GitHub Actions Docker Kubernetes" — end-to-end
- **Official Docs**: [GitHub Actions documentation](https://docs.github.com/en/actions)
- **Official Docs**: [AWS OIDC with GitHub](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)

---

*Next: [Module 11 — Local Development Setup](../11-local-setup/README.md)*
