# Full-Stack Issue Tracker — Complete Engineering Course

> **From Zero to Production-Deployed Engineer**
> Built around a real, production-grade codebase.

---

## What You Will Build

By the end of this course you will understand **every line** of this issue-tracker application — a production-grade project management tool similar to Jira or Linear — and be able to deploy your own full-stack application on AWS without referring to the internet.

The application you study includes:
- A **Next.js 16** frontend with Redux Toolkit and RTK Query
- A **FastAPI** (Python) async REST API backend
- **PostgreSQL 16** with SQLAlchemy ORM and Alembic migrations
- **Redis** for caching and background job brokering
- **Celery** for async background tasks (email, notifications)
- **Docker** containers for every service
- **Kubernetes** on AWS EKS for orchestration
- **Terraform** for infrastructure-as-code
- **GitHub Actions** for CI/CD
- **AWS** services: RDS, ElastiCache, S3, ECR, ALB, Secrets Manager, IAM

---

## Who This Course Is For

| Level | What you get |
|-------|-------------|
| **Beginner** | Start from Module 0 and go sequentially — every concept is introduced from scratch |
| **Intermediate developer** | Skip to any module — each is self-contained with links back to prerequisites |
| **Senior developer** | Jump to the deployment and infrastructure modules for production patterns |

---

## How to Use This Course

Each module follows this structure:

```
1. What is it? (plain English definition)
2. How does it work internally? (engineering deep-dive with diagrams)
3. How does our project use it? (real code references)
4. Hands-on practice (guided exercises)
5. Further reading (YouTube + official docs)
```

Every diagram uses plain-text ASCII so it renders in any Markdown viewer without external dependencies.

Code references use the format `path/to/file.py:line_number` — open the file in VS Code and press `Ctrl+G` then type the line number to jump directly there.

---

## Course Modules

### Part 1 — Foundations

| Module | Title | Time Estimate |
|--------|-------|---------------|
| [00](./00-introduction/README.md) | Introduction, Prerequisites & Local Setup | 30 min |
| [01](./01-architecture-overview/README.md) | Full System Architecture Overview | 45 min |

### Part 2 — Frontend

| Module | Title | Time Estimate |
|--------|-------|---------------|
| [02-01](./02-frontend/01-nextjs-fundamentals.md) | Next.js — App Router, SSR, SSG, and Hydration | 2 hrs |
| [02-02](./02-frontend/02-react-components.md) | React 19 — Components, Hooks, and Patterns | 1.5 hrs |
| [02-03](./02-frontend/03-state-management.md) | Redux Toolkit & RTK Query — State and Data Fetching | 2 hrs |
| [02-04](./02-frontend/04-forms-validation.md) | React Hook Form & Zod — Forms and Validation | 1 hr |
| [02-05](./02-frontend/05-auth-protected-routes.md) | Authentication, JWT Flow & Protected Routes | 1.5 hrs |

### Part 3 — Backend

| Module | Title | Time Estimate |
|--------|-------|---------------|
| [03-01](./03-backend/01-fastapi-fundamentals.md) | FastAPI — Async Python, Pydantic, Dependency Injection | 2.5 hrs |
| [03-02](./03-backend/02-api-design.md) | REST API Design, Routes, RBAC & Middleware | 2 hrs |
| [03-03](./03-backend/03-auth-security.md) | Authentication, JWT, bcrypt & Rate Limiting | 1.5 hrs |
| [03-04](./03-backend/04-background-jobs.md) | Celery, Redis Broker & Scheduled Tasks | 1.5 hrs |

### Part 4 — Data Layer

| Module | Title | Time Estimate |
|--------|-------|---------------|
| [04-01](./04-database/01-postgresql-fundamentals.md) | PostgreSQL — Internals, Schema Design & ACID | 2 hrs |
| [04-02](./04-database/02-sqlalchemy-orm.md) | SQLAlchemy Async ORM — Models, Queries & Relationships | 2 hrs |
| [04-03](./04-database/03-alembic-migrations.md) | Alembic — Database Migrations & Version Control | 1 hr |
| [05-01](./05-caching-storage/01-redis-caching.md) | Redis — Internals, Caching Strategies & Pub/Sub | 1.5 hrs |
| [05-02](./05-caching-storage/02-s3-file-storage.md) | AWS S3 — Object Storage, Presigned URLs & Security | 1 hr |

### Part 5 — Containerization

| Module | Title | Time Estimate |
|--------|-------|---------------|
| [06-01](./06-docker/01-docker-fundamentals.md) | Docker — Internals, Images, Containers & Multi-stage Builds | 2 hrs |
| [06-02](./06-docker/02-docker-compose.md) | Docker Compose — Local Dev & Production Stacks | 1 hr |

### Part 6 — Kubernetes

| Module | Title | Time Estimate |
|--------|-------|---------------|
| [07-01](./07-kubernetes/01-kubernetes-architecture.md) | Kubernetes — Control Plane, etcd, Scheduler & Kubelet | 2.5 hrs |
| [07-02](./07-kubernetes/02-workloads.md) | Pods, Deployments, ReplicaSets & Rolling Updates | 2 hrs |
| [07-03](./07-kubernetes/03-networking.md) | Services, Ingress, DNS & Load Balancing | 1.5 hrs |
| [07-04](./07-kubernetes/04-configuration.md) | ConfigMaps, Secrets & External Secrets Operator | 1 hr |
| [07-05](./07-kubernetes/05-autoscaling.md) | HPA, PDB, Topology Spread & Resource Management | 1 hr |

### Part 7 — AWS & Cloud Infrastructure

| Module | Title | Time Estimate |
|--------|-------|---------------|
| [08-01](./08-aws/01-aws-fundamentals.md) | AWS Fundamentals — Regions, IAM & Core Services | 1.5 hrs |
| [08-02](./08-aws/02-networking-vpc.md) | VPC — Subnets, NAT Gateway, Security Groups & Routing | 2 hrs |
| [08-03](./08-aws/03-eks.md) | EKS — Managed Kubernetes, Node Groups & OIDC | 2 hrs |
| [08-04](./08-aws/04-rds-elasticache.md) | RDS & ElastiCache — Managed Postgres & Redis | 1.5 hrs |
| [08-05](./08-aws/05-s3-ecr.md) | S3 & ECR — Object Storage & Container Registry | 1 hr |
| [08-06](./08-aws/06-alb-secrets.md) | ALB & Secrets Manager — Load Balancing & Secret Storage | 1 hr |

### Part 8 — Infrastructure as Code

| Module | Title | Time Estimate |
|--------|-------|---------------|
| [09-01](./09-terraform/01-terraform-fundamentals.md) | Terraform — State, Providers, Modules & Plan/Apply | 2 hrs |
| [09-02](./09-terraform/02-project-infrastructure.md) | This Project's Infrastructure — Full Terraform Walkthrough | 2 hrs |

### Part 9 — CI/CD & Deployment

| Module | Title | Time Estimate |
|--------|-------|---------------|
| [10-01](./10-cicd/01-github-actions.md) | GitHub Actions — Pipelines, OIDC & Deployment Automation | 2 hrs |
| [11](./11-local-setup/README.md) | Complete Local Development Setup Guide | 45 min |
| [12](./12-production-deployment/README.md) | Full Production Deployment Walkthrough | 2 hrs |

---

## Prerequisites

You do **not** need prior experience with any specific technology listed above. However you should be comfortable with:
- Basic programming concepts (variables, functions, loops)
- Using a terminal/command line
- Understanding what a web browser does (HTTP requests/responses)

### Tools to Install Before Starting

```
- Git                  https://git-scm.com
- Docker Desktop       https://www.docker.com/products/docker-desktop
- Node.js 22+          https://nodejs.org
- Python 3.12+         https://python.org
- VS Code              https://code.visualstudio.com
- AWS CLI v2           https://aws.amazon.com/cli
- kubectl              https://kubernetes.io/docs/tasks/tools
- Terraform 1.6+       https://developer.hashicorp.com/terraform/install
```

---

## Total Estimated Time

| Section | Time |
|---------|------|
| Part 1 (Foundations) | 1.25 hrs |
| Part 2 (Frontend) | 8 hrs |
| Part 3 (Backend) | 7.5 hrs |
| Part 4 (Data Layer) | 7.5 hrs |
| Part 5 (Docker) | 3 hrs |
| Part 6 (Kubernetes) | 8 hrs |
| Part 7 (AWS) | 9 hrs |
| Part 8 (Terraform) | 4 hrs |
| Part 9 (CI/CD + Deployment) | 4.75 hrs |
| **Total** | **~53 hrs** |

---

*Start with [Module 00 — Introduction](./00-introduction/README.md)*
