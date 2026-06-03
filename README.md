# Issue Tracker

A full-stack project and issue tracking application — FastAPI backend, Next.js frontend, deployed on AWS EKS with Kubernetes.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Tech Stack](#tech-stack)
3. [Project Structure](#project-structure)
4. [Local Development](#local-development)
5. [Backend](#backend)
6. [Frontend](#frontend)
7. [Environment Variables](#environment-variables)
8. [Running Tests](#running-tests)
9. [Database Migrations](#database-migrations)
10. [Background Jobs (Celery)](#background-jobs-celery)
11. [Docker Compose Reference](#docker-compose-reference)
12. [Deployment](#deployment)
13. [Known Gotchas](#known-gotchas)

---

## Architecture Overview

```
Internet
    │
    ▼
AWS ALB  (HTTP:80 — add ACM cert annotation in ingress.yaml for HTTPS)
    │
    ▼
Nginx pods  (reverse proxy, 2 replicas)
    │
    ├── /api/*  ──► Backend pods  (FastAPI + Gunicorn, 3–30 replicas via HPA)
    │                   │
    │                   ├── PostgreSQL 16  (RDS Multi-AZ, db.r6g.large)
    │                   └── Redis 7        (ElastiCache cluster mode, 3 shards)
    │
    └── /*  ────► Frontend pods  (Next.js, 2–10 replicas via HPA)

Background workers:
    Celery Worker pods  (2–15 replicas, HPA on CPU)  ──► Redis broker
    Celery Beat pod     (1 replica, Recreate strategy — singleton scheduler)

Secrets:
    AWS Secrets Manager ──► External Secrets Operator ──► K8s Secret (app-secrets)
```

**Request flow for `/api/...`:**
Client → ALB → Nginx (`/api/` prefix stripped) → FastAPI on port 8000

**Request flow for `/*`:**
Client → ALB → Nginx → Next.js on port 3000

---

## Tech Stack

| Layer | Technology |
|---|---|
| **API** | FastAPI 0.104+, Uvicorn (ASGI), Gunicorn (4 workers/pod) |
| **Database** | PostgreSQL 16 (SQLAlchemy async ORM, Alembic migrations) |
| **Cache / Queue** | Redis 7 (cache + Celery broker) |
| **Background Jobs** | Celery + Celery Beat |
| **File Storage** | AWS S3 (production) / local filesystem (development) |
| **Frontend** | Next.js 16, React 19, Redux Toolkit, RTK Query |
| **Styling** | CSS Modules |
| **Forms / Validation** | React Hook Form + Zod |
| **Auth** | JWT (access + refresh token flow), RBAC authorisation |
| **Testing** | pytest + pytest-cov (backend), Jest + React Testing Library (frontend) |
| **Containerisation** | Docker, Docker Compose |
| **Orchestration** | Kubernetes 1.30 on AWS EKS |
| **Load Balancer** | AWS ALB via AWS Load Balancer Controller |
| **Ingress Proxy** | Nginx 1.27-alpine |
| **Secret Management** | AWS Secrets Manager + External Secrets Operator |
| **Infrastructure** | Terraform 1.6+ (AWS provider ~5.0) |
| **Container Registry** | AWS ECR |
| **Autoscaling** | Kubernetes HPA + Cluster Autoscaler |
| **CI/CD** | GitHub Actions (single pipeline: test → build → deploy) |

---

## Project Structure

```
issueTraker/
├── backend/
│   ├── app/
│   │   ├── api/routes/         # 13 API route modules (auth, projects, issues, ...)
│   │   ├── core/               # Config (Pydantic Settings), logging, Redis, rate limiting
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # Business logic (cache, rate_limit, ...)
│   │   └── main.py             # FastAPI app factory and lifespan
│   ├── alembic/                # Migration scripts
│   ├── tests/                  # pytest suite (api/routes/, conftest.py)
│   ├── scripts/
│   │   ├── start.sh            # Production server (gunicorn + uvicorn workers)
│   │   └── migrate.sh          # alembic upgrade head + optional seed
│   ├── Dockerfile              # Multi-stage production image (python:3.12-slim)
│   ├── Dockerfile.dev          # Dev image (hot-reload via uvicorn --reload)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js App Router pages and layouts
│   │   ├── components/         # Shared React components
│   │   ├── store/              # Redux store + RTK Query API slices
│   │   └── __tests__/          # Jest test files co-located with components
│   ├── jest.config.js          # Uses babel-jest + next/babel (NOT SWC) for CI compatibility
│   ├── jest.setup.js           # Testing Library setup
│   ├── Dockerfile              # Multi-stage production image (node:22-alpine)
│   ├── Dockerfile.dev          # Dev image (hot-reload)
│   └── package.json
├── infra/                      # All infrastructure — see infra/README.md
│   ├── terraform/
│   ├── kubernetes/
│   └── scripts/
├── docker-compose.yml          # Production-like local stack (nginx on :80)
├── docker-compose.dev.yml      # Development stack + pgadmin, flower, redis-commander
└── .github/workflows/
    └── deploy.yml              # Single CI/CD pipeline (test → build → deploy)
```

---

## Local Development

### Prerequisites

- Docker Desktop with Compose v2
- Git

### Start everything

```bash
git clone https://github.com/Vaman971/issue-tracker.git
cd issue-tracker

# Copy backend environment file (dev values are pre-filled with safe defaults)
cp backend/.env.example backend/.env

# Start the full dev stack
docker compose -f docker-compose.dev.yml up --build
```

Services after startup:

| Service | URL | Credentials |
|---|---|---|
| Frontend | http://localhost:3000 | — |
| Backend API | http://localhost:8000 | — |
| API Docs (Swagger) | http://localhost:8000/docs | — |
| PgAdmin | http://localhost:5050 | admin@issue.com / admin |
| Redis Commander | http://localhost:8081 | — |
| Flower (Celery) | http://localhost:5555 | — |

**Seed admin account** (created automatically on first startup):
- Email: `admin@example.com`
- Password: `admin12345`

### Stop

```bash
docker compose -f docker-compose.dev.yml down          # preserve volumes
docker compose -f docker-compose.dev.yml down -v       # wipe database + uploads too
```

### Rebuild a single service

```bash
docker compose -f docker-compose.dev.yml up --build backend
```

---

## Backend

### API Routes

| Module | Prefix | What it handles |
|---|---|---|
| auth | `/api/auth/` | Login, logout, refresh, email verify, password reset |
| users | `/api/users/` | Profile management |
| admin | `/api/admin/` | Admin-only operations |
| projects | `/api/projects/` | Project CRUD |
| project_member | `/api/projects/{id}/members/` | Team membership |
| issues | `/api/issues/` | Issue CRUD, assignment, status transitions |
| comments | `/api/comments/` | Issue comments |
| attachments | `/api/attachments/` | File upload / download |
| labels | `/api/labels/` | Issue labels |
| notifications | `/api/notifications/` | User notification inbox |
| activity | `/api/activity/` | Per-project activity feed |
| search | `/api/search/` | Full-text search across issues |
| stats | `/api/stats/` | Dashboard statistics |

### Health endpoints

```
GET /health/live    # Liveness — is the process running?
GET /health/ready   # Readiness — is DB + Redis reachable?
```

Always use these paths for liveness/readiness probes — NOT `/api/health/live`. Nginx strips the `/api/` prefix, so probes hit `backend:8000/health/live` directly.

### Running without Docker

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # edit with real values
alembic upgrade head             # apply migrations
uvicorn app.main:app --reload --port 8000
```

### Production server startup

The production container runs `scripts/start.sh`:

```bash
exec gunicorn app.main:app \
  --workers "${WEB_CONCURRENCY:-1}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --worker-tmp-dir /dev/shm \
  --timeout 120 \
  --keep-alive 5 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  --forwarded-allow-ips "*"
```

> **Gotcha — gunicorn flags**: `--keepalive` (no hyphen) is **not a valid gunicorn flag** — it silently
> crashes the container. The correct flag is `--keep-alive` (with hyphen).
> Similarly, `--proxy-headers` is a **uvicorn CLI flag**, not a gunicorn flag. Do not add it here.
> If either flag is wrong, the container starts, prints the error, and immediately exits
> (visible in `kubectl logs` as: `gunicorn: error: unrecognized arguments: ...`).

---

## Frontend

### Running without Docker

```bash
cd frontend
npm install

# Create local env file
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

npm run dev       # starts on port 3000
```

### Build for production

```bash
npm run build
npm run start
```

### Key scripts

```bash
npm run dev            # Dev server with hot reload
npm run build          # Production build (requires NEXT_PUBLIC_API_URL to be set)
npm run start          # Serve the production build
npm run lint           # ESLint check
npm test               # Jest (watch mode)
npm test -- --ci --coverage --passWithNoTests   # CI single-run with coverage
```

> **Important — `NEXT_PUBLIC_API_URL` is a build-time variable.**
> It is baked into the Next.js JavaScript bundle during `next build`.
> Changing it requires rebuilding the image. In the CI pipeline it is injected as a
> Docker build argument from the `NEXT_PUBLIC_API_URL` GitHub Secret.

---

## Environment Variables

### Backend — complete reference

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `development` | `development`, `production`, or `testing` |
| `DATABASE_URL` | — | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | — | Dev: `redis://localhost:6379/0`. Prod: `rediss://:TOKEN@HOST:6379/0` (TLS + auth) |
| `JWT_SECRET_KEY` | — | ≥32-char random string. `openssl rand -hex 32` |
| `JWT_REFRESH_SECRET_KEY` | — | Different random string from above |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRES_MINUTES` | `15` | |
| `REFRESH_TOKEN_EXPIRES_DAYS` | `7` | |
| `BACKEND_CORS_ORIGINS` | `http://localhost:3000,...` | Comma-separated |
| `FRONTEND_URL` | `http://localhost:3000` | Used in email verification / password-reset links |
| `SMTP_HOST` | — | e.g. `email-smtp.ap-south-1.amazonaws.com` or `smtp.sendgrid.net` |
| `SMTP_PORT` | `587` | |
| `SMTP_USERNAME` | — | For SES: the SMTP username from the IAM SMTP credentials (starts with `AKIA...`) |
| `SMTP_PASSWORD` | — | For SES: the **SMTP password** from the SES console — NOT the IAM secret key |
| `SMTP_FROM_EMAIL` | — | Sender address |
| `SMTP_USE_TLS` | `true` | |
| `EMAILS_ENABLED` | `true` | Set `false` to skip email sends in dev |
| `STORAGE_BACKEND` | `local` | `local` or `s3` |
| `S3_BUCKET_NAME` | — | Required when `STORAGE_BACKEND=s3` |
| `AWS_REGION` | `ap-south-1` | |
| `CELERY_BROKER_URL` | = `REDIS_URL` | |
| `CELERY_RESULT_BACKEND` | = `REDIS_URL` | |
| `MAX_UPLOAD_SIZE_MB` | `10` | |
| `AUTH_RATE_LIMIT_LOGIN_MAX_ATTEMPTS` | `5` | Per 60-second window |
| `AUTH_RATE_LIMIT_REGISTER_MAX_ATTEMPTS` | `3` | Per 60-second window |
| `SEED_ADMIN_EMAIL` | `admin@example.com` | Used by migrate.sh seed |
| `SEED_ADMIN_PASSWORD` | `admin12345` | Change in production! |

### Frontend

| Variable | Notes |
|---|---|
| `NEXT_PUBLIC_API_URL` | Full URL of the backend. Set at **build time**. Dev: `http://localhost:8000`. Prod: ALB DNS or your domain. |
| `NODE_ENV` | Set automatically by Next.js (`development` / `production`) |

---

## Running Tests

### Backend

```bash
# With the dev compose stack running:
docker compose -f docker-compose.dev.yml exec backend pytest tests/ -v

# Standalone (needs Postgres + Redis):
cd backend
DATABASE_URL=postgresql+asyncpg://test_user:test_password@localhost:5432/test_db \
REDIS_URL=redis://localhost:6379/0 \
JWT_SECRET_KEY=ci-test-key \
JWT_REFRESH_SECRET_KEY=ci-test-refresh-key \
APP_ENV=testing \
pytest tests/ -v --cov=app --cov-report=term-missing
```

> `APP_ENV=testing` is required — the settings validator runs at import time
> (in `alembic/env.py`), so even the migration step needs all JWT env vars set.

### Frontend

```bash
cd frontend
npm test                                           # watch mode
npm test -- --ci --coverage --passWithNoTests      # CI single-run
```

> **Jest uses `babel-jest` + `next/babel`** (configured in `jest.config.js`), not the default
> SWC transform. This is intentional — SWC requires platform-specific binaries that are not
> available on Linux CI runners. Do not remove `jest.config.js` or `jest.setup.js`;
> they were accidentally excluded from git by a stray `.gitignore` entry in an earlier version —
> both files must be committed.

---

## Database Migrations

Alembic manages all schema changes.

```bash
# Apply all pending migrations (run this after pulling new code)
alembic upgrade head

# Roll back one step
alembic downgrade -1

# Create a new auto-detected migration
alembic revision --autogenerate -m "describe the change"

# Show current migration version
alembic current

# Show full history
alembic history --verbose
```

In production, migrations run automatically as a Kubernetes Job (`infra/kubernetes/jobs/migrate-job.yaml`) before every deployment. The pipeline deletes the previous Job, creates a new one with the current image, waits for completion (5-minute timeout), prints logs, then proceeds to roll out pods.

---

## Background Jobs (Celery)

Celery handles async tasks: email delivery, notification fan-out, and scheduled maintenance.

**Queues:**

| Queue | Purpose |
|---|---|
| `default` | General background tasks |
| `email` | Email delivery (isolated so SMTP slowness does not stall other work) |
| `notifications` | Notification fan-out |

**Celery Beat** is a singleton scheduler. The Kubernetes deployment uses `strategy: Recreate` (not `RollingUpdate`) to ensure exactly one Beat pod runs at a time. Never scale Beat replicas above 1.

```bash
# Inspect running tasks (dev compose)
docker compose -f docker-compose.dev.yml exec celery-worker \
  celery -A app.worker.celery_app inspect active

# Monitor via Flower UI
open http://localhost:5555
```

---

## Docker Compose Reference

### Development (`docker-compose.dev.yml`)

Runs all services with hot-reload and includes developer tools.

```bash
# Start (rebuild images on first run or after Dockerfile changes)
docker compose -f docker-compose.dev.yml up --build

# Rebuild only one service
docker compose -f docker-compose.dev.yml up --build backend

# Follow logs for a service
docker compose -f docker-compose.dev.yml logs -f backend

# Open a shell inside a running container
docker compose -f docker-compose.dev.yml exec backend bash
docker compose -f docker-compose.dev.yml exec frontend sh

# Stop and preserve volumes
docker compose -f docker-compose.dev.yml down

# Stop and wipe everything (database, uploads)
docker compose -f docker-compose.dev.yml down -v
```

### Production-like (`docker-compose.yml`)

Mirrors the production layout (nginx on port 80, no dev tools).

```bash
docker compose up --build -d
docker compose logs -f
docker compose down
```

---

## Deployment

All production infrastructure docs are in [`infra/README.md`](infra/README.md).

**Pipeline summary** (`.github/workflows/deploy.yml`):

1. **Detect changes** — `dorny/paths-filter` checks which of `backend/` or `frontend/` changed.
2. **Test** — Backend (pytest) and frontend (ESLint + Jest) run in parallel. Tests are skipped if the corresponding directory was not modified.
3. **Build** — Docker images are built and pushed to ECR. Frontend build injects `NEXT_PUBLIC_API_URL` from GitHub Secrets.
4. **Deploy** — `kubectl apply` on all manifests → DB migration Job → `kubectl set image` + `kubectl rollout status`.

**To trigger a full deploy without pushing code:**
GitHub → Actions → "CI / CD — Deploy to Kubernetes" → **Run workflow**

**GitHub Secrets required:**

| Secret | Value |
|---|---|
| `AWS_GITHUB_ACTIONS_ROLE_ARN` | `terraform output github_actions_role_arn` |
| `NEXT_PUBLIC_API_URL` | ALB DNS or your domain (e.g. `http://k8s-xxx.ap-south-1.elb.amazonaws.com`) |

---

## Known Gotchas

These are real issues encountered during development and deployment. Read before debugging.

### Gunicorn flag names

`--keepalive` and `--proxy-headers` **do not exist** in gunicorn.
- `--keepalive` must be `--keep-alive` (hyphen between words)
- `--proxy-headers` is a uvicorn CLI-only flag; remove it from gunicorn invocations
- Wrong flags cause the container to exit immediately with `gunicorn: error: unrecognized arguments`

### NEXT_PUBLIC_API_URL is baked in at build time

Changing this env var in Secrets Manager or ConfigMap has no effect on a running frontend pod. You must rebuild the frontend image with the new value and redeploy.

### AWS SES SMTP credentials

When creating SES SMTP credentials, AWS generates a **derived SMTP password** that is NOT the same as your IAM secret access key. Always use the password from the SMTP credentials download page, never the IAM secret key directly.

### RDS parameter group formulas use parameter-native units

PostgreSQL parameters like `shared_buffers` and `effective_cache_size` are measured in **8kB blocks**, not bytes. The formula `{DBInstanceClassMemory/4}` does **not** mean "25% of RAM" — it means `RAM_in_bytes / 4` blocks, which is petabytes. Valid formulas divide by a much larger number: `{DBInstanceClassMemory/32768}` = 25% RAM in 8kB blocks.

Parameters with invalid formulas put the RDS instance into `incompatible-parameters` state. Recovery: edit the parameter group in the RDS Console → reset the offending parameters to default → reboot the instance.

### Nginx health probe must not depend on upstream services

Probing `GET /` routes to the frontend upstream. If frontend pods do not exist, the probe gets a 502, nginx is marked not-ready, and Kubernetes restarts it endlessly. The nginx deployment uses a dedicated `location /nginx-health { return 200; }` endpoint for both liveness and readiness probes so nginx stays healthy independent of whether backend and frontend pods are up.

### EKS access entries require API or API_AND_CONFIG_MAP auth mode

EKS clusters created without an explicit `access_config` block default to `CONFIG_MAP` mode. The newer `aws eks create-access-entry` API requires `API` or `API_AND_CONFIG_MAP`. Upgrade the auth mode first:

```bash
aws eks update-cluster-config \
  --name issue-tracker-production \
  --access-config authenticationMode=API_AND_CONFIG_MAP \
  --region ap-south-1

aws eks wait cluster-active --name issue-tracker-production --region ap-south-1
```

### ServiceAccount must exist before the migration Job

The migration Job references `serviceAccountName: backend`. If `backend/deployment.yaml` is the first place the ServiceAccount is created, and it has not been applied before the Job runs, the Job pod fails with `serviceaccount "backend" not found`. The ServiceAccount is kept in its own file (`infra/kubernetes/backend/serviceaccount.yaml`) and applied in the early manifest step of the pipeline — before migrations run.

### ElastiCache cluster mode requires `cluster-enabled = yes` parameter

When `num_node_groups > 1` (cluster mode), the parameter group **must** contain `cluster-enabled = yes`. Without it, AWS returns `InvalidParameterCombination: Use a parameter group with cluster-enabled parameter to create more than one node group`.

### Terraform HCL semicolons

HCL does not use semicolons to separate block arguments — use newlines. `set { name = "a"; value = "b" }` is a syntax error. Each attribute must be on its own line.

### GitHub Actions role needs explicit EKS access

The IAM role assumed by GitHub Actions is not automatically added to the EKS cluster auth. Grant access once after `terraform apply`:

```bash
aws eks create-access-entry \
  --cluster-name issue-tracker-production \
  --principal-arn arn:aws:iam::ACCOUNT_ID:role/issue-tracker-github-actions \
  --region ap-south-1

aws eks associate-access-policy \
  --cluster-name issue-tracker-production \
  --principal-arn arn:aws:iam::ACCOUNT_ID:role/issue-tracker-github-actions \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope '{"type":"cluster"}' \
  --region ap-south-1
```

This is now also managed by Terraform (`aws_eks_access_entry` + `aws_eks_access_policy_association` in `environments/production/main.tf`).

### Teardown: always delete the Kubernetes Ingress before running `terraform destroy`

The ALB is created by the AWS Load Balancer Controller, not Terraform. If you destroy EKS without deleting the Ingress first, the LB Controller has no chance to clean up the ALB's security groups. Those security groups remain in the VPC and `terraform destroy` fails on VPC deletion with `DependencyViolation`. Always run:

```bash
kubectl delete ingress issue-tracker -n issue-tracker
# wait ~60 seconds
terraform destroy
```

### Teardown: never delete the S3 state bucket while `terraform destroy` is running

The state bucket is the Terraform backend. Deleting it mid-destroy causes Terraform to fail saving state, leaving an `errored.tfstate` file locally and requiring manual recovery. Full teardown order is documented in [`infra/README.md`](infra/README.md#teardown--destroy).

### Teardown: versioned S3 buckets require all versions deleted before `delete-bucket`

`aws s3 rm --recursive` only removes current object versions. A versioned bucket still has version history and delete markers, which block bucket deletion with `BucketNotEmpty`. Use the Python script in `infra/README.md` which iterates all versions and delete markers before deleting the bucket.
