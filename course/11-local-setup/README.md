# Module 11 — Complete Local Development Setup Guide

---

## What You Will Achieve

By the end of this module you will have the entire issue-tracker running on your laptop:

```
http://localhost        → Full application (nginx routing to frontend + backend)
http://localhost:3000   → Frontend (Next.js with hot-reload)
http://localhost:8000   → Backend API (FastAPI with hot-reload)
http://localhost:5050   → pgAdmin (PostgreSQL GUI)
http://localhost:5555   → Flower (Celery task monitor)
http://localhost:8081   → Redis Commander (Redis GUI)
```

All 10 services run via a single `docker compose` command. No manual installation of PostgreSQL, Redis, or Python required — Docker handles everything.

---

## Prerequisites

### Required Tools

Install these before starting:

```bash
# 1. Git
# Windows: https://git-scm.com/download/win
# Mac:
brew install git
# Linux (Ubuntu/Debian):
sudo apt install git

# Verify:
git --version
# git version 2.43.0

# 2. Docker Desktop
# Download from: https://www.docker.com/products/docker-desktop/
# After install, ensure Docker Desktop is running

# Verify:
docker --version
# Docker version 25.0.3, build 4debf41

docker compose version
# Docker Compose version v2.24.5

# 3. Node.js (for running tests and type-checking locally)
# Download LTS from: https://nodejs.org/
# Or use nvm:
nvm install --lts
nvm use --lts

# Verify:
node --version   # v20.x or newer
npm --version    # 10.x or newer

# 4. Python (for running backend tests locally)
# Download from: https://www.python.org/downloads/
# Or use pyenv:
pyenv install 3.12
pyenv global 3.12

# Verify:
python --version  # Python 3.12.x
```

### System Requirements

```
Minimum:
  RAM: 8 GB (Docker needs ~4 GB for all services)
  Disk: 10 GB free (images + volumes)
  CPU: 4 cores (2 cores minimum, slower)

Recommended:
  RAM: 16 GB
  Disk: 20 GB free
  CPU: 8 cores
```

---

## Step 1: Clone the Repository

```bash
# Clone (replace with your repository URL if you forked it)
git clone https://github.com/YOUR_USERNAME/issue-tracker.git

# Enter the project directory
cd issue-tracker

# Verify the structure
ls
# backend/   frontend/   infra/   nginx/   course/   docker-compose.yml   docker-compose.dev.yml
```

---

## Step 2: Create Environment Files

The application needs environment variables for configuration. Start from the provided examples:

### Backend Environment

```bash
# Copy the example file
cp backend/.env.example backend/.env
```

Open `backend/.env` and review the defaults. For local development, everything works out of the box. The important variables:

```bash
# backend/.env — what each variable does

APP_NAME=Team Issue Tracker API
APP_ENV=development       # Controls debug mode, logging level

# Database — Docker Compose creates this automatically
DATABASE_URL=postgresql+asyncpg://issue_user:issue_password@localhost:5432/issue_tracker
# NOTE: When running inside Docker Compose, use the service name:
# DATABASE_URL=postgresql+asyncpg://issue_user:issue_password@postgres:5432/issue_tracker
# docker-compose.dev.yml sets this automatically for the backend service

REDIS_URL=redis://localhost:6379/0

# JWT secrets — change these in production, fine as-is for local dev
JWT_SECRET_KEY=replace-with-access-token-secret
JWT_REFRESH_SECRET_KEY=replace-with-refresh-token-secret

# The admin account seeded on first run
SEED_ADMIN_EMAIL=admin@example.com
SEED_ADMIN_PASSWORD=change-this-password

# Email — disabled for local dev (emails log to console instead)
EMAILS_ENABLED=false

# File storage — "local" saves files in backend/uploads/
STORAGE_BACKEND=local
```

> **Note**: The Docker Compose file already sets all required variables internally. The `backend/.env` file is used when running the backend directly (outside Docker). You only NEED to create it if you plan to run the backend outside Docker.

### Frontend Environment

```bash
# Copy the example file
cp frontend/.env.example frontend/.env.local
```

```bash
# frontend/.env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost    # The nginx proxy running at port 80
BACKEND_INTERNAL_URL=http://127.0.0.1:8000  # Direct backend access (for SSR)
```

> **Why two URLs?** Browser requests go through nginx at port 80 (`NEXT_PUBLIC_API_BASE_URL`). Server-side rendering in Next.js calls the backend directly (`BACKEND_INTERNAL_URL`) to avoid the extra network hop.

---

## Step 3: Start All Services

This single command starts all 10 services:

```bash
# From the project root:
docker compose -f docker-compose.dev.yml up -d --build

# What each flag does:
#   -f docker-compose.dev.yml  → use the development compose file
#   -d                         → run in background (detached)
#   --build                    → build images before starting (important on first run)
```

### What Happens During Startup

Watch Docker pull images and build your application:

```
[+] Building (first time — ~5-10 minutes)
 => [postgres] pulling image
 => [redis] pulling image
 => [backend] building from ./backend/Dockerfile
    → installing Python dependencies (takes longest on first run)
 => [frontend] building from ./frontend/Dockerfile
    → npm install + next build
 => [nginx] building from ./nginx/Dockerfile

[+] Running (subsequent starts — ~30 seconds)
 ✔ Container issue_tracker_postgres_dev  Healthy
 ✔ Container issue_tracker_redis_dev     Started
 ✔ Container issue_tracker_migrate_dev   Exited (0)   ← migration ran successfully
 ✔ Container issue_tracker_seed_dev      Exited (0)   ← seed data loaded
 ✔ Container issue_tracker_backend_dev   Started
 ✔ Container issue_tracker_frontend_dev  Started
 ✔ Container issue_tracker_nginx_dev     Started
 ✔ Container issue_tracker_celery_dev    Started
 ✔ Container issue_tracker_flower_dev    Started
 ✔ Container issue_tracker_redis_cmd_dev Started
```

### Understanding the Startup Order

Services don't all start simultaneously — they have dependencies:

```
Phase 1: Infrastructure
  postgres (healthcheck: pg_isready)
  redis

Phase 2: One-time jobs (after postgres is healthy)
  migrate  → runs: alembic upgrade head
             creates all 14 database tables
  seed     → runs: python seed.py
             creates admin user + sample data

Phase 3: Application services (after migrate exits successfully)
  backend  → FastAPI (hot-reload via uvicorn --reload)
  celery   → Celery worker

Phase 4: Frontend and proxy
  frontend → Next.js dev server (hot-reload)
  nginx    → reverse proxy (routes / → frontend, /api → backend)
  flower   → Celery monitoring UI
  redis_commander → Redis GUI
```

---

## Step 4: Verify All Services Are Running

```bash
# Check container status
docker compose -f docker-compose.dev.yml ps

# Expected output:
NAME                           STATUS          PORTS
issue_tracker_backend_dev      Up              0.0.0.0:8000->8000/tcp
issue_tracker_celery_dev       Up
issue_tracker_flower_dev       Up              0.0.0.0:5555->5555/tcp
issue_tracker_frontend_dev     Up              0.0.0.0:3000->3000/tcp
issue_tracker_migrate_dev      Exited (0)      ← good, means migration succeeded
issue_tracker_nginx_dev        Up              0.0.0.0:80->80/tcp
issue_tracker_postgres_dev     Up (healthy)    0.0.0.0:5431->5432/tcp
issue_tracker_redis_cmd_dev    Up              0.0.0.0:8081->8081/tcp
issue_tracker_redis_dev        Up              0.0.0.0:6379->6379/tcp
issue_tracker_seed_dev         Exited (0)      ← good, means seed succeeded
```

> **If migrate or seed shows `Exited (1)`**, something went wrong. Check logs immediately:
> ```bash
> docker compose -f docker-compose.dev.yml logs migrate
> docker compose -f docker-compose.dev.yml logs seed
> ```

---

## Step 5: Access the Application

### Main Application

Open your browser and go to:

```
http://localhost
```

You should see the login page. Log in with the seeded admin account:
- **Email**: `admin@example.com`
- **Password**: `change-this-password`

(These are set by `SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD` in the backend environment.)

### Backend API Documentation

FastAPI auto-generates interactive API documentation:

```
http://localhost:8000/docs      → Swagger UI (interactive)
http://localhost:8000/redoc     → ReDoc (readable)
http://localhost:8000/health    → Health check endpoint
```

The Swagger UI lets you try every API endpoint directly from the browser — useful for understanding the API structure.

### Database Admin (pgAdmin)

```
http://localhost:5050

Login:
  Email:    admin@issue.com
  Password: admin
```

pgAdmin is pre-configured to connect to the PostgreSQL container. You can browse tables, run SQL queries, and inspect data:

```
After login:
  Servers → issue_tracker_dev → Databases → issue_tracker → Schemas → public → Tables
```

Try this SQL query to see your tables:
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

### Celery Task Monitor (Flower)

```
http://localhost:5555
```

Flower shows:
- Active workers and their status
- Task history (succeeded / failed / pending)
- Task details (arguments, result, execution time)
- Queue lengths

When you perform actions that trigger background tasks (like user registration when `EMAILS_ENABLED=true`), you'll see tasks appear here in real-time.

### Redis Commander

```
http://localhost:8081
```

Browse Redis keys in your browser. After using the app:
- `cache:*` keys — application cache
- `celery` list — pending tasks in the queue
- `rate_limit:*` keys — rate limiter counters

---

## Step 6: Understanding Hot-Reload

Both frontend and backend support hot-reload — saving a file instantly reflects the change without restarting containers.

### Backend Hot-Reload

```bash
# The backend starts with:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app

# When you save a Python file, uvicorn detects the change:
INFO:     Detected change in '/app/app/api/routes/issues.py', reloading...
INFO:     Application startup complete.
```

Test it: open `backend/app/api/routes/health.py`, add a field to the health response, save the file, then hit `http://localhost:8000/health` — the change appears instantly.

### Frontend Hot-Reload

```bash
# Next.js dev server with Fast Refresh:
# Saving a React component updates only that component in the browser
# without losing application state (Redux store, form values, etc.)

# You'll see in the browser console:
[Fast Refresh] done in 234ms
```

### Database Changes Require Migration

Hot-reload does NOT automatically apply database schema changes. If you modify a SQLAlchemy model:

```bash
# 1. Generate a migration
docker compose -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "describe_your_change"

# 2. Apply it
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

---

## Step 7: Running Tests Locally

### Backend Tests

```bash
# Run all backend tests inside the Docker container
docker compose -f docker-compose.dev.yml exec backend pytest

# Run specific test file
docker compose -f docker-compose.dev.yml exec backend pytest tests/test_auth.py -v

# Run with coverage report
docker compose -f docker-compose.dev.yml exec backend pytest --cov=app --cov-report=term-missing

# Run outside Docker (requires Python + dependencies installed locally):
cd backend
pip install -r requirements.txt
pytest
```

### Frontend Tests

```bash
# Run tests in the frontend container
docker compose -f docker-compose.dev.yml exec frontend npm test

# Or run locally (requires Node.js):
cd frontend
npm install
npm test

# Type checking (no tests, just TypeScript/JSX type errors):
npm run type-check

# Linting:
npm run lint
```

### Testing the API Manually

```bash
# Using curl (replace token with actual JWT from login response):

# Login and get token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"change-this-password"}'

# Response:
# {"access_token":"eyJ...", "refresh_token":"eyJ...", "token_type":"bearer"}

# Use the token to get projects
ACCESS_TOKEN="eyJ..."
curl http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Step 8: Common Development Workflows

### Adding a New API Endpoint

```bash
# 1. Create/edit the route file
# backend/app/api/routes/your_feature.py

# 2. Register it in the router
# backend/app/api/__init__.py (or wherever routes are registered)

# 3. Hot-reload picks it up automatically

# 4. Test in Swagger UI: http://localhost:8000/docs
```

### Adding a New Frontend Page

```bash
# 1. Create the page file following Next.js App Router conventions:
# frontend/app/(protected)/your-feature/page.jsx

# 2. Add navigation link in the sidebar component

# 3. Next.js hot-reload picks it up automatically

# 4. Visit: http://localhost:3000/your-feature
```

### Creating a Database Migration

```bash
# 1. Modify your SQLAlchemy model in backend/app/models/

# 2. Generate migration
docker compose -f docker-compose.dev.yml exec backend \
  alembic revision --autogenerate -m "add_your_column"

# 3. Review the generated file in backend/alembic/versions/

# 4. Apply
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head

# 5. Verify in pgAdmin or directly:
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U issue_user -d issue_tracker -c "\d your_table"
```

### Resetting the Database

```bash
# Nuclear option — wipe all data and start fresh:

# Stop all services
docker compose -f docker-compose.dev.yml down

# Remove the postgres volume
docker volume rm issue-tracker_postgres_dev_data

# Restart (migrate + seed run automatically)
docker compose -f docker-compose.dev.yml up -d
```

---

## Troubleshooting

### Problem: Port Already in Use

```
Error: bind: address already in use
```

Something on your machine is already using port 80, 3000, or 8000.

```bash
# Find what's using the port:
# Linux/Mac:
lsof -i :80
# Windows:
netstat -ano | findstr :80

# Options:
# 1. Stop the conflicting process
# 2. Change the port in docker-compose.dev.yml
```

### Problem: Frontend Shows "Cannot connect to backend"

```bash
# 1. Check if backend is actually running:
curl http://localhost:8000/health
# Expected: {"status":"healthy","database":"connected","redis":"connected"}

# 2. Check nginx is routing correctly:
curl http://localhost/api/v1/health
# Same expected output (via nginx proxy)

# 3. Check nginx logs:
docker compose -f docker-compose.dev.yml logs nginx

# 4. Restart nginx if needed:
docker compose -f docker-compose.dev.yml restart nginx
```

### Problem: Migration Failed

```bash
# Check migration logs:
docker compose -f docker-compose.dev.yml logs migrate

# Common causes:
# - Database not ready yet (postgres healthcheck failed)
# - Migration file has a syntax error
# - Database already at that version (usually harmless — exit 0)

# Manually run migration to see detailed error:
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

### Problem: Backend Keeps Restarting

```bash
# Check backend logs:
docker compose -f docker-compose.dev.yml logs backend --tail=50

# Common causes:
# - Syntax error in Python code (hot-reload fails to reload)
# - Environment variable missing
# - Database connection failed

# Verify database connection:
docker compose -f docker-compose.dev.yml exec backend \
  python -c "import asyncio; from app.db.session import AsyncSessionLocal; print('DB OK')"
```

### Problem: "No module named 'app'" in Backend

```bash
# The Python path is set in the Dockerfile's WORKDIR.
# If running pytest locally outside Docker:
cd backend
PYTHONPATH=. pytest

# Or install the package in editable mode:
pip install -e .
```

### Problem: Docker Runs Out of Memory

```bash
# Check Docker resource usage:
docker stats

# Increase Docker Desktop memory limit:
# Docker Desktop → Settings → Resources → Memory → increase to 6GB

# Or stop services you're not using:
docker compose -f docker-compose.dev.yml stop flower redis_commander pgadmin
```

### Problem: Frontend Build Fails

```bash
# Check frontend logs:
docker compose -f docker-compose.dev.yml logs frontend

# Common cause: .env.local missing
ls frontend/.env.local

# If missing:
cp frontend/.env.example frontend/.env.local

# Rebuild frontend:
docker compose -f docker-compose.dev.yml build frontend
docker compose -f docker-compose.dev.yml up -d frontend
```

### Problem: Celery Tasks Not Processing

```bash
# Check Celery worker logs:
docker compose -f docker-compose.dev.yml logs celery

# Verify Redis is running:
docker compose -f docker-compose.dev.yml exec redis redis-cli ping
# Expected: PONG

# Restart Celery:
docker compose -f docker-compose.dev.yml restart celery
```

---

## Useful Commands Reference

```bash
# Start everything
docker compose -f docker-compose.dev.yml up -d --build

# Stop everything (keeps data)
docker compose -f docker-compose.dev.yml down

# Stop everything and delete all data (fresh start)
docker compose -f docker-compose.dev.yml down -v

# View logs for all services (live)
docker compose -f docker-compose.dev.yml logs -f

# View logs for one service
docker compose -f docker-compose.dev.yml logs -f backend

# Restart one service
docker compose -f docker-compose.dev.yml restart backend

# Run a command inside a running container
docker compose -f docker-compose.dev.yml exec backend bash
docker compose -f docker-compose.dev.yml exec postgres psql -U issue_user -d issue_tracker

# Rebuild one service image (after Dockerfile change)
docker compose -f docker-compose.dev.yml build backend
docker compose -f docker-compose.dev.yml up -d backend

# Check container resource usage
docker stats

# List all volumes
docker volume ls | grep issue-tracker
```

---

## Development vs Production Configuration Comparison

| Aspect | Local Dev (`docker-compose.dev.yml`) | Production (EKS) |
|--------|--------------------------------------|-----------------|
| Backend start command | `uvicorn ... --reload` | `gunicorn ... -k uvicorn.workers.UvicornWorker` |
| Frontend | Dev server (slow, live reload) | Static build served by nginx |
| Database | Single PostgreSQL container | RDS Multi-AZ |
| Redis | Single Redis container | ElastiCache cluster (3 shards) |
| Secrets | `.env` files | AWS Secrets Manager → ESO → K8s Secret |
| File storage | Local `uploads/` directory | AWS S3 |
| Scale | 1 instance of everything | HPA: 3-30 pods |
| TLS/HTTPS | No (HTTP only) | ACM certificate on ALB |
| Logging | Container stdout | CloudWatch |

---

## Further Reading & Videos

- **YouTube**: Search "Docker Compose tutorial for beginners" — complete walkthrough of Compose
- **YouTube**: Search "FastAPI tutorial" — Sebastián Ramírez (FastAPI creator) official tutorial
- **YouTube**: Search "Next.js tutorial for beginners" — Vercel official channel
- **Official Docs**: [Docker Compose documentation](https://docs.docker.com/compose/)
- **Official Docs**: [FastAPI documentation](https://fastapi.tiangolo.com/)
- **Official Docs**: [Next.js documentation](https://nextjs.org/docs)

---

*Next: [Module 12 — Full Production Deployment Walkthrough](../12-production-deployment/README.md)*
