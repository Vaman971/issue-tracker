# Module 01 — Full System Architecture Overview

---

## Learning Objectives

After this module you will:
- Understand every component of the system and how they connect
- Know the request lifecycle from browser click to database and back
- Understand why each component exists in the architecture
- Have a mental map to navigate the rest of the course

---

## The Complete System Architecture

<img width="1536" height="1024" alt="image" src="https://github.com/user-attachments/assets/986a215f-0a22-47d2-9f00-706ecee9226d" />

---

## Component Deep Dive

### 1. Next.js Frontend

The frontend is what users see and interact with. It runs in two places:
- **On the server** (Node.js process): Generates HTML for initial page loads (SSR)
- **In the browser**: React takes over after the first load for fast navigation (hydration)

```
User types URL in browser
        │
        ▼
Next.js server (Node.js process)
        │  Fetches data from backend API (server-side)
        │  Renders React components to HTML
        │
        ▼
Browser receives complete HTML (fast first paint)
        │
        ▼
Browser downloads JavaScript bundle
        │
        ▼
React "hydrates" — attaches event listeners to existing HTML
        │
        ▼
Further navigation: React handles in the browser (no full page reload)
```

**Files in this project:**
- `frontend/src/app/` — All pages (Next.js App Router)
- `frontend/src/components/` — Reusable UI components
- `frontend/src/store/` — Redux state + RTK Query API slices

---

### 2. FastAPI Backend

The backend is the brain of the application. It:
- Receives HTTP requests from the frontend
- Validates the data (Pydantic schemas)
- Checks permissions (RBAC)
- Reads/writes the database (SQLAlchemy)
- Returns JSON responses

```
HTTP Request arrives at FastAPI
        │
        ▼
Middleware pipeline:
  1. CORS check (is this origin allowed?)
  2. Request logging (generate request ID)
  3. Rate limit check (too many requests?)
        │
        ▼
Router matches URL to handler function
(e.g. GET /projects → projects.list_projects)
        │
        ▼
Dependency injection:
  - get_db()        → SQLAlchemy async session
  - get_current_user() → Verify JWT, return User object
  - require_roles() → Check user has permission
        │
        ▼
Handler function executes:
  - Query database
  - Apply business logic
  - Return Pydantic response model
        │
        ▼
JSON serialized and sent back to client
```

**Files in this project:**
- `backend/app/main.py` — App factory, middleware, router registration
- `backend/app/api/routes/` — 13 route modules (one per feature)
- `backend/app/models/` — SQLAlchemy ORM models
- `backend/app/schemas/` — Pydantic request/response schemas
- `backend/app/api/deps.py` — Dependency injection functions
- `backend/app/api/rbac.py` — Role-based access control

---

### 3. PostgreSQL Database

PostgreSQL stores all persistent data. It's a **relational database** — data is organized in tables with rows and columns, and tables are connected via foreign keys.

```
users table
┌────┬───────────────────┬──────────┬──────────────┐
│ id │ email             │ role     │ hashed_pass  │
├────┼───────────────────┼──────────┼──────────────┤
│  1 │ alice@example.com │ ADMIN    │ $2b$...      │
│  2 │ bob@example.com   │ DEVELOPER│ $2b$...      │
└────┴───────────────────┴──────────┴──────────────┘

projects table
┌────┬────────────────┬────────────┐
│ id │ name           │ leader_id  │  ◄── foreign key to users.id
├────┼────────────────┼────────────┤
│  1 │ Website Redesign│     1     │
└────┴────────────────┴────────────┘

issues table
┌────┬─────────────────┬────────────┬────────────┬──────────────┐
│ id │ title           │ project_id │ creator_id │ status       │
├────┼─────────────────┼────────────┼────────────┼──────────────┤
│  1 │ Fix login bug   │     1      │     2      │ IN_PROGRESS  │
└────┴─────────────────┴────────────┴────────────┴──────────────┘
```

There are 14 tables total — each module explains them in detail.

---

### 4. Redis

Redis is an **in-memory data store** — like a giant dictionary (key → value) that lives in RAM, making it extremely fast (microseconds to access).

We use it for two separate purposes:

**Purpose 1: Cache**
```
Frontend requests project list
        │
        ▼
FastAPI checks Redis cache
        │
   ┌────┴────┐
   │ Found?  │
   └────┬────┘
        │ YES → return cached data instantly (no DB query)
        │ NO  → query PostgreSQL, store result in Redis (TTL 5 min)
        │       next request hits cache
        ▼
Response returned to frontend
```

**Purpose 2: Celery Task Queue (Broker)**
```
FastAPI endpoint needs to send email
        │
        ▼
Celery task pushed to Redis queue
(non-blocking — endpoint returns immediately)
        │
        ▼
Celery Worker picks up task from Redis
        │
        ▼
Worker sends email via SMTP
        │
        ▼
Task marked complete in Redis result backend
```

---

### 5. Celery

Celery handles work that should happen **asynchronously** — work that's too slow to make the user wait for, or work that should happen on a schedule.

```
SYNCHRONOUS (bad for user experience):
User submits issue
     │
     ▼ FastAPI sends email (takes 2-3 seconds)
     ▼ User waits...
     ▼ Response returned

ASYNCHRONOUS (what we do):
User submits issue
     │
     ▼ FastAPI queues email task in Redis (milliseconds)
     ▼ Response returned immediately ← user sees success
     
     (in background, seconds later)
     Celery Worker picks up task
     Celery Worker sends email
```

**Two types of jobs:**
- **Tasks** triggered by API calls: `notify_issue_assigned`, `send_verification_email`
- **Scheduled tasks** (Celery Beat): `cleanup_expired_tokens` (daily), `cleanup_old_notifications` (weekly)

---

### 6. Nginx (Reverse Proxy)

Nginx sits in front of both the frontend and backend. Users never directly reach either — all requests go through Nginx first.

```
Browser request: POST /api/issues
        │
        ▼
Nginx receives request
        │
        │  URL starts with /api/ ?
        │  YES → strip /api/ prefix, forward to backend:8000
        │  NO  → forward to frontend:3000
        ▼
Backend/Frontend handles request
        │
        ▼
Nginx forwards response back to browser
```

Why do we need Nginx if the browser can talk to the backend directly? Because:
1. **Single entry point** — one URL for the whole app
2. **SSL termination** — handle HTTPS in one place
3. **Load balancing** — distribute across multiple backend pods
4. **Static file serving** — serve cached assets efficiently
5. **Connection limiting** — protect against basic attacks

---

### 7. Docker

Docker packages each service (backend, frontend, nginx, etc.) into an **image** — a self-contained snapshot that includes the code, runtime, and all dependencies.

```
WITHOUT Docker:
Developer A (Mac, Python 3.12): "It works on my machine"
Developer B (Windows, Python 3.10): "It doesn't work on mine"
Production server (Linux, Python 3.11): "It crashes"

WITH Docker:
Developer A builds image ──► runs container ──► "Works"
Developer B runs same image ──► runs container ──► "Works"
Production runs same image ──► runs container ──► "Works"
```

---

### 8. Kubernetes (EKS)

Kubernetes manages **where and how** Docker containers run across a cluster of servers.

Think of it like a highly intelligent operating system for your entire cloud infrastructure:

```
You tell Kubernetes: "I want 3 copies of the backend running at all times"
        │
        ▼
Kubernetes scheduler decides which servers to run them on
        │
        ▼
Kubernetes constantly monitors all pods
        │
        ▼
If a pod crashes → Kubernetes starts a new one automatically
If CPU usage is high → Kubernetes adds more pods (HPA)
If CPU usage drops → Kubernetes removes pods (saves money)
If a server dies → Kubernetes moves pods to healthy servers
```

---

### 9. Terraform

Terraform creates all the AWS infrastructure from code:

```
You run: terraform apply
        │
        ▼
Terraform reads .tf files (infrastructure description)
        │
        ▼
Terraform calls AWS APIs to CREATE:
  - VPC (your private network in AWS)
  - EKS cluster (Kubernetes control plane)
  - RDS instance (PostgreSQL database)
  - ElastiCache cluster (Redis)
  - ECR repositories (container registry)
  - S3 bucket (file storage)
  - ALB (load balancer)
  - IAM roles (permissions)
        │
        ▼
Infrastructure exists and is running
```

Without Terraform, you'd click around in the AWS console to create all this manually — which is error-prone, hard to repeat, and impossible to version control.

---

### 10. GitHub Actions CI/CD

CI/CD means **Continuous Integration / Continuous Deployment**. Every time code is pushed:

```
Developer pushes code to GitHub
        │
        ▼
GitHub Actions pipeline triggers automatically:
        │
        ├─► Run tests (pytest for backend, jest for frontend)
        │         If tests FAIL → pipeline stops, developer notified
        │
        ├─► Build Docker images
        │         Backend image → pushed to AWS ECR
        │         Frontend image → pushed to AWS ECR
        │
        └─► Deploy to Kubernetes
                  kubectl apply (update manifests)
                  kubectl set image (new image tag)
                  kubectl rollout status (wait for healthy)
```

This automation ensures:
- No broken code reaches production
- Deployments are consistent and repeatable
- Every deployment is auditable (GitHub maintains logs)

---

## Request Lifecycle — Complete Walkthrough

Let's trace a single request: "User clicks 'Create Issue' button"

```
1. USER ACTION
   User fills form and clicks "Create Issue"
   Browser: React state → form data object

2. FRONTEND API CALL  
   RTK Query mutation: createIssue(formData)
   fetch("POST /api/issues", {
     headers: { Authorization: "Bearer <JWT>" },
     body: JSON.stringify(formData)
   })

3. NGINX
   Receives POST /api/issues
   Strips /api/ prefix
   Forwards to backend:8000/issues

4. FASTAPI MIDDLEWARE
   Request logging (generates request ID: req-abc123)
   CORS check (origin allowed?)

5. FASTAPI ROUTER
   Matches POST /issues to create_issue handler
   
6. DEPENDENCY INJECTION
   get_db() → creates SQLAlchemy async session
   get_current_user() → verifies JWT → returns User(id=2)
   require_roles([DEVELOPER, ADMIN]) → User.role=DEVELOPER ✓

7. HANDLER FUNCTION
   Validates body against IssueCreate Pydantic schema
   Creates Issue ORM object
   db.add(issue)
   await db.commit()
   
   Queues Celery task:
   notify_issue_assigned.delay(issue_id, assignee_ids)

8. CELERY BROKER (Redis)
   Task serialized as JSON
   Pushed to "notifications" queue in Redis

9. RESPONSE
   FastAPI serializes Issue object → IssueResponse Pydantic model → JSON
   HTTP 201 Created sent back through Nginx to browser

10. FRONTEND UPDATE
    RTK Query receives 201 response
    Cache invalidated for "issues" tag
    React re-renders with new issue in list

11. BACKGROUND (async, user doesn't wait)
    Celery Worker picks up task from Redis queue
    Queries database for assignee user data
    Creates Notification record in PostgreSQL
    Sends email via SMTP (if EMAILS_ENABLED=true)
```

Total time for steps 1-10: **~50ms** (user experience)
Step 11 happens in background: **~2-5 seconds** (user doesn't care)

---

## Data Flow Diagrams

### Authentication Flow
```
User submits login form
        │
        ▼ POST /api/auth/login
FastAPI checks:
  1. User exists in DB?
  2. bcrypt.verify(password, stored_hash) == True?
  3. Email verified?
        │
        ▼ Success
FastAPI generates:
  - Access Token (JWT, expires in 15 min)
  - Refresh Token (JWT, stored hash in DB, expires 7 days)
        │
        ▼
Frontend stores tokens in localStorage
        │
Every subsequent request:
        │
        ▼
RTK Query adds: Authorization: Bearer <access_token>
        │
        ▼
FastAPI extracts token, verifies signature, gets user ID
        │
If access token expired (401 received):
        │
        ▼
RTK Query auto-calls POST /api/auth/refresh
        │
        ▼
FastAPI verifies refresh token (in DB + not expired)
        │
        ▼
New access token issued
        │
        ▼
Original request retried with new token
```

### File Upload Flow
```
User selects file attachment
        │
        ▼
Frontend POST /api/attachments (multipart form data)
        │
        ▼
FastAPI receives file
        │
        ▼
In Production:
  storage.upload(file) → boto3 → AWS S3
  Returns: s3://bucket/path/filename
  
In Development:
  storage.upload(file) → local filesystem
  Returns: /uploads/filename
        │
        ▼
Attachment record saved to PostgreSQL
(stores: issue_id, filename, storage_path, size, content_type)
        │
        ▼
Frontend shows attachment link
        │
When user clicks download:
        ▼
FastAPI generates presigned URL (valid 1 hour)
Frontend redirects to presigned URL
S3 serves file directly to browser (no FastAPI involved)
```

---

## Environment Overview

| Environment | How to run | Purpose |
|-------------|-----------|---------|
| **Development** | `docker compose -f docker-compose.dev.yml up` | Local coding with hot reload |
| **Testing** | `pytest` / `npm test` | Automated test suite |
| **Production** | GitHub Actions → EKS | Live user-facing deployment |

---

## Further Reading & Videos

- **YouTube**: Search "System Design Basics" on YouTube — channels like "Gaurav Sen" and "Tech Dummies Narendra L" give excellent overviews
- **YouTube**: Search "Microservices vs Monolith" — helps understand why we separate frontend, backend, workers
- **Official Docs**: [AWS Architecture Center](https://aws.amazon.com/architecture/) — real-world architecture patterns

---

*Next: [Module 02-01 — Next.js Fundamentals](../02-frontend/01-nextjs-fundamentals.md)*
