# Module 00 — Introduction, Prerequisites & Mental Models

---

## Learning Objectives

After this module you will:
- Understand what we are building and why
- Have the right mental model for the rest of the course
- Know how the modules connect to each other
- Have all tools installed and ready

---

## What Is an Issue Tracker?

An issue tracker is a system for recording, assigning, and tracking work items (bugs, features, tasks) across a software project. Think of it as a structured to-do list for teams — similar to **Jira**, **Linear**, or **GitHub Issues**.

Our issue tracker supports:
- Multiple **projects** with role-based teams
- **Issues** with status, priority, assignees, comments, attachments
- **Notifications** for assignment and comment events
- **Background email** delivery
- **Admin** management

---

## The Big Picture — What You Are Learning

This course teaches you to build and deploy a **three-tier web application**:

```
┌─────────────────────────────────────────────────────────────┐
│                    TIER 1: PRESENTATION                      │
│                                                             │
│   Browser ──► Next.js (React)                               │
│              - Renders HTML pages                           │
│              - Makes API calls                              │
│              - Manages client-side state (Redux)            │
└─────────────────────────────────────────────────────────────┘
                           │ HTTP/JSON
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    TIER 2: APPLICATION                       │
│                                                             │
│   FastAPI (Python)                                          │
│   - Receives HTTP requests                                  │
│   - Validates input (Pydantic)                              │
│   - Applies business rules (RBAC)                           │
│   - Reads/writes database                                   │
│   - Queues background jobs (Celery → Redis)                 │
└─────────────────────────────────────────────────────────────┘
                           │ SQL / Redis
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    TIER 3: DATA                              │
│                                                             │
│   PostgreSQL     ── Stores all persistent data              │
│   Redis          ── Cache + job queue                       │
│   AWS S3         ── File attachments                        │
└─────────────────────────────────────────────────────────────┘
```

This three-tier architecture is the foundation of virtually every web application you will encounter professionally.

---

## The Journey — From Code to Running in the Cloud

```
You write code on your laptop
        │
        ▼
Docker builds an IMAGE (a snapshot of your code + OS)
        │
        ▼
Docker Compose runs multiple containers locally for testing
        │
        ▼
GitHub Actions CI/CD pipeline:
   1. Runs tests
   2. Builds Docker images
   3. Pushes images to AWS ECR (registry)
   4. Deploys to Kubernetes (AWS EKS)
        │
        ▼
Kubernetes runs your containers on AWS servers
        │
        ▼
AWS Load Balancer receives traffic from the internet
        │
        ▼
Users worldwide access your application
```

Each step in this journey is a module in this course.

---

## How Modern Software Teams Work

Understanding **why** we use these tools is as important as knowing **how**.

| Problem | Solution we use |
|---------|----------------|
| Multiple developers need to run the same code | Docker containers |
| Code needs to run on many servers for reliability | Kubernetes |
| Infrastructure must be reproducible and auditable | Terraform |
| Changes must be tested before going live | GitHub Actions CI/CD |
| Secrets (passwords) must not be in code | AWS Secrets Manager |
| App must stay up even if one server dies | Kubernetes HPA + multi-replica deployments |
| App must handle traffic spikes | Kubernetes HPA autoscaling |
| Database must survive an entire data center failure | AWS RDS Multi-AZ |

---

## Key Mental Models

### Mental Model 1: Everything Is a Process

At the lowest level, your application is just **processes running on CPUs**. Docker, Kubernetes, and AWS are all just different ways to manage where and how those processes run.

```
Physical CPU core
    └─ Operating System (Linux kernel)
           └─ Process (Python interpreter running gunicorn)
                   └─ Threads (handling HTTP requests)
```

### Mental Model 2: All Data Lives Somewhere

Every piece of data has a location:
- **In memory (RAM)**: Temporary, fast, lost on restart (Redis cache, process variables)
- **On disk**: Persistent, slower (PostgreSQL files, uploaded files)
- **In a message queue**: Waiting to be processed (Celery tasks in Redis)
- **In the cloud**: Durable, replicated (AWS RDS, S3)

### Mental Model 3: Network Calls Are Slow

Everything that crosses a network boundary takes ~1ms minimum. Inside a function: nanoseconds. Across the internet: hundreds of milliseconds. This is why:
- We **cache** database results in Redis (avoid repeated queries)
- We use **async/await** (don't block while waiting for slow I/O)
- We use **CDNs** for static assets (serve from nearby servers)
- We **batch** operations where possible

### Mental Model 4: Failure Is Normal

In production, things fail all the time. Good systems are designed to survive failure:
- **Multiple replicas**: If one pod dies, others continue
- **Health checks**: Kubernetes restarts unhealthy pods
- **Retry logic**: Failed tasks are retried
- **Circuit breakers**: Stop calling a broken service
- **Backups**: RDS automated backups for data recovery

---

## Technology Selection Rationale

Every technology choice in this project was deliberate:

| Choice | Why |
|--------|-----|
| **Python + FastAPI** | Python is the most popular language for APIs; FastAPI is modern, async, and auto-documents |
| **Next.js** | React for UI, with server-side rendering for SEO, file-based routing |
| **PostgreSQL** | Battle-tested, ACID-compliant relational database; perfect for structured data |
| **Redis** | In-memory speed for caching; also doubles as Celery broker |
| **Kubernetes** | Industry standard for container orchestration; handles scaling and reliability |
| **Terraform** | Infrastructure as code — version control your cloud resources |
| **AWS** | Most widely used cloud provider; skills transfer to almost any job |

---

## Prerequisites Checklist

### Install These Tools

#### 1. Git
```bash
# Check if installed
git --version

# Install: https://git-scm.com/downloads
```

#### 2. Docker Desktop
```bash
# Check if installed
docker --version
docker compose version

# Install: https://www.docker.com/products/docker-desktop
```

#### 3. Node.js 22+
```bash
# Check if installed
node --version   # should be v22.x.x
npm --version

# Install: https://nodejs.org (download LTS)
```

#### 4. Python 3.12+
```bash
# Check if installed
python --version    # or python3 --version

# Install: https://python.org/downloads
```

#### 5. VS Code
```
Install from: https://code.visualstudio.com

Recommended extensions:
- Python (ms-python.python)
- ESLint (dbaeumer.vscode-eslint)
- Docker (ms-azuretools.vscode-docker)
- Kubernetes (ms-kubernetes-tools.vscode-kubernetes-tools)
- Terraform (hashicorp.terraform)
- GitLens (eamodio.gitlens)
```

#### 6. AWS CLI
```bash
# Check
aws --version

# Install: https://aws.amazon.com/cli
# Configure with your AWS credentials:
aws configure
```

#### 7. kubectl
```bash
# Check
kubectl version --client

# Install: https://kubernetes.io/docs/tasks/tools
```

#### 8. Terraform
```bash
# Check
terraform --version

# Install: https://developer.hashicorp.com/terraform/install
```

---

## Clone and Explore the Project

```bash
# If you haven't already, clone the project
# (or you already have it since you're reading this inside it)

# Start the local development stack
cd E:\Myweb\issueTraker
docker compose -f docker-compose.dev.yml up

# In a new terminal, verify everything is running
docker compose -f docker-compose.dev.yml ps
```

You should see these services running:
- `db` — PostgreSQL on port 5431
- `redis` — Redis on port 6379
- `backend` — FastAPI on port 8000
- `frontend` — Next.js on port 3000
- `nginx` — Reverse proxy on port 80
- `celery_worker` — Background job worker
- `celery_beat` — Scheduled task runner
- `flower` — Celery monitoring UI on port 5555
- `pgadmin` — Database GUI on port 5050
- `redis_commander` — Redis GUI on port 8081

Open `http://localhost` in your browser — you should see the issue tracker UI.

---

## How to Read This Course

### Code Reference Format
When a module says:
> See `backend/app/main.py:45`

Open VS Code, press `Ctrl+P`, type the filename, then `Ctrl+G` and the line number.

### Diagram Format
All architecture diagrams are ASCII — they render in any Markdown viewer, any terminal, or even a plain text file.

### YouTube Links
Each module includes video links. Watch them when you want a different explanation of the same concept — it often takes multiple angles for something to click.

---

## Further Reading

- **YouTube**: "How the internet works" — search for this on YouTube, TechWorld with Nana's channel has excellent content
- **Official Docs**: [MDN Web Docs](https://developer.mozilla.org) — the bible for web fundamentals
- **Book**: "Designing Data-Intensive Applications" by Martin Kleppmann — covers databases, distributed systems at depth

---

*Next: [Module 01 — Full System Architecture Overview](../01-architecture-overview/README.md)*
