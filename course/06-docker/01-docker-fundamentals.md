# Module 06-01 — Docker: Internals, Images, Containers & Multi-stage Builds

---

## Learning Objectives

After this module you will:
- Understand what Docker is and how containers work at the OS level
- Know the difference between images and containers
- Be able to read and write Dockerfiles
- Understand multi-stage builds for production images

---

## The Problem Docker Solves

```
2010, without Docker:
  Developer: "It works on my Mac!"
  Teammate: "It crashes on my Windows machine"
  DevOps: "It broke on the Linux production server"
  
  Reason: Different OS versions, different library versions, 
  different environment variables, different paths

2024, with Docker:
  Developer: builds a Docker image
  Teammate: runs the SAME image — identical environment
  Production server: runs the SAME image — identical environment
  
  "Works on my machine" → becomes → "It runs everywhere in a container"
```

---

## How Containers Work at the OS Level

Docker containers are NOT virtual machines. They use Linux kernel features:

```
Virtual Machine (heavyweight):
┌────────────────────────────────────────────────────────┐
│                    Host Machine                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │            Hypervisor (VMware, VirtualBox)       │  │
│  │  ┌────────────────┐  ┌────────────────────────┐  │  │
│  │  │ Guest OS       │  │ Guest OS               │  │  │
│  │  │ (full Linux)   │  │ (full Windows)         │  │  │
│  │  │ 2GB RAM        │  │ 4GB RAM                │  │  │
│  │  │ Your App       │  │ Your App               │  │  │
│  │  └────────────────┘  └────────────────────────┘  │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
Heavy: each VM needs its own OS kernel, GBs of RAM

Docker Container (lightweight):
┌────────────────────────────────────────────────────────┐
│                    Host Machine                         │
│              Linux Kernel (shared)                      │
│                                                        │
│  ┌─────────────────────────┐  ┌─────────────────────┐  │
│  │ Container 1             │  │ Container 2         │  │
│  │ (isolated process)      │  │ (isolated process)  │  │
│  │ NameSpace: own view     │  │ NameSpace: own view │  │
│  │   of filesystem, PIDs,  │  │   of everything     │  │
│  │   network, users        │  │                     │  │
│  │ CGroup: resource limits │  │ CGroup: limits      │  │
│  │ FastAPI app             │  │ Next.js app         │  │
│  └─────────────────────────┘  └─────────────────────┘  │
└────────────────────────────────────────────────────────┘
Lightweight: containers share the kernel, use ~10MB RAM overhead
```

### Linux Namespaces (Isolation)

Each container gets its own "view" of the system:

```
pid namespace:    Container sees its own processes (not host processes)
                  Process IDs start from 1 inside the container

net namespace:    Container has its own network interface, IP, ports
                  Container's port 8000 is isolated from host's port 8000

mnt namespace:    Container sees its own filesystem
                  Can't see host filesystem (unless explicitly mounted)

user namespace:   Container has its own user IDs
                  Root inside container ≠ Root on host

uts namespace:    Container has its own hostname
```

### Linux cgroups (Resource Limits)

```
Container resource limits (from Kubernetes deployment.yaml):
  CPU: 500m request, 2000m limit
  Memory: 512Mi request, 2Gi limit

How cgroups enforce this:
  If container tries to use >2000m CPU → kernel throttles it
  If container tries to use >2Gi memory → kernel kills the process (OOM)
```

---

## Docker Images — Layered Filesystem

A Docker image is built from **layers**. Each Dockerfile instruction creates a new layer:

```
Dockerfile:
  FROM python:3.12-slim        → Layer 1: Base OS (Ubuntu) + Python
  COPY requirements.txt .      → Layer 2: requirements file
  RUN pip install -r ...       → Layer 3: Python packages
  COPY . .                     → Layer 4: Application code
  CMD ["/app/scripts/start.sh"]→ Layer 5: Default command (metadata)

Image structure:
  ┌──────────────────────────────┐
  │ Layer 5: CMD metadata        │
  ├──────────────────────────────┤
  │ Layer 4: App code (50KB)     │ ← Changes often
  ├──────────────────────────────┤
  │ Layer 3: Packages (200MB)    │ ← Changes rarely (new deps)
  ├──────────────────────────────┤
  │ Layer 2: requirements.txt    │ ← Changes rarely
  ├──────────────────────────────┤
  │ Layer 1: python:3.12-slim    │ ← Never changes (external base)
  └──────────────────────────────┘
```

**Layers are cached**: If `requirements.txt` hasn't changed, Docker reuses Layer 2 and Layer 3 from cache — the slow `pip install` step is skipped.

```
Build time comparison:
  First build:     requirements.txt → pip install → 5 minutes
  Second build:    only code changed → pip install CACHED → 30 seconds
  Third build:     requirements.txt changed → pip install fresh → 5 minutes
```

**Optimization rule**: Put things that change rarely BEFORE things that change often.

---

## Backend Dockerfile

```dockerfile
# backend/Dockerfile

# ── Base image ──────────────────────────────────────────────────
# python:3.12-slim = Python 3.12 on minimal Debian
# 'slim' = no dev tools installed → smaller image
FROM python:3.12-slim

# ── System setup ─────────────────────────────────────────────────
# Set working directory inside container
WORKDIR /app

# Install system dependencies (not Python — OS level)
# curl: for health checks
# libpq-dev: needed by psycopg2 (C library for PostgreSQL)
RUN apt-get update && apt-get install -y \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*  # Clean up (reduces image size)

# ── Python dependencies ───────────────────────────────────────────
# Copy ONLY requirements.txt first
# This layer is cached until requirements.txt changes
COPY requirements.txt .

# Install dependencies
# --no-cache-dir: don't cache pip downloads (smaller image)
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────
# Copy app code AFTER dependencies
# This layer invalidates on every code change
# But the layer below (pip install) stays cached
COPY . .

# Make scripts executable
RUN chmod +x scripts/start.sh scripts/migrate.sh

# ── Security: non-root user ───────────────────────────────────────
# Create app user (don't run as root!)
RUN groupadd -r app && useradd -r -g app app
# Change ownership of /app to app user
RUN chown -R app:app /app
# Switch to non-root user
USER app

# ── Runtime configuration ─────────────────────────────────────────
# Port the app listens on (documentation only — doesn't actually open it)
EXPOSE 8000

# Default command
CMD ["/app/scripts/start.sh"]
```

---

## Frontend Dockerfile (Multi-Stage Build)

Multi-stage builds solve the problem of build tools in production images:

```dockerfile
# frontend/Dockerfile

# ── Stage 1: Install dependencies ──────────────────────────────
# Named stage "deps"
FROM node:22-alpine AS deps

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Clean install — reproducible builds
# Uses package-lock.json for exact versions
RUN npm ci

# ── Stage 2: Build the application ─────────────────────────────
# Named stage "builder"
FROM node:22-alpine AS builder

WORKDIR /app

# Copy node_modules from deps stage (NOT from host)
COPY --from=deps /app/node_modules ./node_modules

# Copy source code
COPY . .

# Build-time environment variable
# This value is BAKED INTO the JavaScript bundle at build time
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

# Build the Next.js application
# Produces .next/ directory with optimized output
RUN npm run build

# ── Stage 3: Production runner (SMALLEST POSSIBLE IMAGE) ────────
# Only contains what's needed to RUN the app (not build it)
FROM node:22-alpine AS runner

WORKDIR /app

# Security: non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy only the built output from the builder stage
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/package*.json ./

# Install only production dependencies (no dev tools, no build tools)
RUN npm ci --omit=dev

USER nextjs
EXPOSE 3000
CMD ["npm", "start"]
```

**Why multi-stage?**

```
Single-stage image size:
  node_modules/     → 800MB (all dev deps + prod deps)
  src/              → 50MB
  .next/ (build)    → 200MB
  node (runtime)    → 50MB
  Total: ~1.1GB

Multi-stage image size (production stage only):
  .next/ (output)   → 50MB  
  node_modules/     → 200MB (prod only, no dev tools)
  node (runtime)    → 50MB
  Total: ~300MB

73% smaller image = faster deployments, less storage cost
```

---

## Running Containers

```bash
# Build an image from a Dockerfile
docker build -t issue-tracker-backend:latest ./backend

# Run a container from an image
docker run \
  -p 8000:8000 \                    # Host:Container port mapping
  -e DATABASE_URL="..." \            # Environment variable
  -v /path/to/uploads:/app/uploads \ # Volume mount (persists files)
  issue-tracker-backend:latest

# Run detached (in background)
docker run -d --name backend issue-tracker-backend:latest

# View running containers
docker ps

# View logs
docker logs backend --follow

# Execute a command inside running container
docker exec -it backend bash

# Stop a container
docker stop backend

# Remove a container
docker rm backend
```

---

## .dockerignore — Exclude Files from Build Context

When you run `docker build`, Docker sends the entire directory to the daemon. `.dockerignore` prevents large or sensitive files from being sent:

```
# backend/.dockerignore
.git
.venv
__pycache__
*.pyc
*.egg-info
.pytest_cache
tests/
.env
.env.*
uploads/
*.log
```

Without `.dockerignore`, Docker would upload your `.git` folder (~100MB for large repos) to the daemon on every build — very slow.

---

## Image Tags and Registries

```
Image name format:
  [registry]/[repository]:[tag]

Examples:
  python:3.12-slim                    → Docker Hub official image
  nginx:1.27-alpine                   → Docker Hub
  123456789.dkr.ecr.ap-south-1.amazonaws.com/issue-tracker-backend:abc123
  → AWS ECR registry / repository name / git commit SHA tag

Tag conventions in this project:
  :latest       → most recently built image
  :abc1234      → exact git commit SHA (reproducible, for deployment)
  
Using commit SHA as tag means:
  "Deploy image abc1234" → always deploys exactly the same code
  "Deploy image latest" → moves target (less predictable in production)
```

---

## Container Internals — What Happens When You `docker run`

```
docker run nginx:latest
        │
        ▼
1. Docker checks local image cache for "nginx:latest"
   (If not found: pulls from Docker Hub)

2. Creates a container from the image:
   - New mount namespace: fresh filesystem from image layers
   - New network namespace: new virtual network interface
   - New pid namespace: process IDs start from 1
   - cgroup set up with resource limits

3. Docker copies/overlay filesystem:
   Read-only layers: [base OS | nginx packages | nginx config]
   Writable layer:   [empty, for runtime changes like logs]
   
   Changes during container runtime go to writable layer only
   Base image layers are never modified (immutable)

4. Starts PID 1 in the container:
   The CMD or ENTRYPOINT from the Dockerfile runs as PID 1
   (gunicorn, npm start, nginx, etc.)

5. Container is running
```

---

## Further Reading & Videos

- **YouTube**: Search "Docker Tutorial for Beginners" — TechWorld with Nana has an excellent full course (3-4 hours)
- **YouTube**: Search "Docker Containers vs Virtual Machines" — Fireship explains this clearly
- **YouTube**: Search "Docker Multi Stage Build" — for production optimization techniques
- **Official Docs**: [Dockerfile reference](https://docs.docker.com/engine/reference/builder/)
- **Official Docs**: [Docker overview](https://docs.docker.com/get-started/overview/)

---

*Next: [Module 06-02 — Docker Compose: Local Dev & Production Stacks](./02-docker-compose.md)*
