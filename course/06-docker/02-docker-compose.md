# Module 06-02 — Docker Compose: Local Dev & Production Stacks

---

## Learning Objectives

After this module you will:
- Understand what Docker Compose is and why we need it
- Read and understand both compose files in this project
- Know the difference between development and production stacks
- Be able to run and debug the full local stack

---

## What Is Docker Compose?

Running one container is simple with `docker run`. But our application has 9+ services:

```
postgres, redis, backend, frontend, nginx, celery_worker, 
celery_beat, flower, pgadmin, redis_commander
```

Running each manually with `docker run` is impossible to manage. Docker Compose solves this:

```yaml
# One file describes ALL services:
services:
  db:
    image: postgres:16
    ...
  redis:
    image: redis:7
    ...
  backend:
    build: ./backend
    depends_on: [db, redis]
    ...

# One command starts everything:
docker compose up
```

Docker Compose also handles:
- **Network**: All services on a shared virtual network, accessible by name
- **Dependencies**: Start services in the right order (`depends_on`)
- **Volumes**: Persistent data across container restarts
- **Environment**: Load `.env` files

---

## Service Communication

In Docker Compose, all services are on a shared network. Services can reach each other **by service name**:

```
Backend code:         DATABASE_URL = "postgresql://db:5432/issuetracker"
                                             ↑
                                       service name resolves to container IP

Nginx config:         proxy_pass http://backend:8000;
                                          ↑
                                   "backend" service name

Celery config:        REDIS_URL = "redis://redis:6379/0"
                                          ↑
                                   "redis" service name
```

No IP addresses needed — Docker's internal DNS resolves service names automatically.

---

## Development Stack Walkthrough

```yaml
# docker-compose.dev.yml
# Run with: docker compose -f docker-compose.dev.yml up

services:
  # ── DATABASE ─────────────────────────────────────────────────
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: issuetracker
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      # Named volume: persists data between restarts
      - postgres_data:/var/lib/postgresql/data
    ports:
      # Expose on host so you can use pgAdmin, psql, etc.
      - "5431:5432"  # Host 5431 → Container 5432
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ── REDIS ─────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s

  # ── BACKEND ───────────────────────────────────────────────────
  backend:
    # Build from Dockerfile.dev (different from production)
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    volumes:
      # Mount source code for HOT RELOAD
      # Changes in ./backend/ appear instantly inside container
      - ./backend:/app
    ports:
      - "8000:8000"
    environment:
      APP_ENV: development
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/issuetracker
      REDIS_URL: redis://redis:6379/0
      JWT_SECRET_KEY: dev-secret-change-in-production
      JWT_REFRESH_SECRET_KEY: dev-refresh-secret
    # Wait for db and redis to be healthy before starting
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    #                                                                ↑
    #                                        --reload: restarts on file change
    
  # ── FRONTEND ──────────────────────────────────────────────────
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    volumes:
      - ./frontend:/app
      - /app/node_modules  # Prevent host node_modules from overwriting container's
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_BASE_URL: http://localhost
      BACKEND_INTERNAL_URL: http://backend:8000
    command: npm run dev  # Next.js dev server with hot reload

  # ── NGINX ─────────────────────────────────────────────────────
  nginx:
    image: nginx:1.27-alpine
    ports:
      - "80:80"    # Access app at http://localhost
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro  # Mount nginx config
    depends_on:
      - backend
      - frontend

  # ── CELERY WORKER ─────────────────────────────────────────────
  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    volumes:
      - ./backend:/app  # Hot reload for task changes too
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/issuetracker
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/1
      CELERY_RESULT_BACKEND: redis://redis:6379/2
    depends_on:
      - db
      - redis
    command: celery -A app.worker.celery_app worker --loglevel=info --concurrency=2

  # ── CELERY BEAT ────────────────────────────────────────────────
  celery_beat:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    volumes:
      - ./backend:/app
    environment:
      CELERY_BROKER_URL: redis://redis:6379/1
    depends_on:
      - redis
    command: celery -A app.worker.celery_app beat --loglevel=info

  # ── DEVELOPER TOOLS (not in production) ───────────────────────
  
  flower:  # Celery monitoring UI
    image: mher/flower:2.0
    ports:
      - "5555:5555"
    environment:
      CELERY_BROKER_URL: redis://redis:6379/1
    command: celery --broker=redis://redis:6379/1 flower --port=5555
    depends_on:
      - redis

  pgadmin:  # PostgreSQL GUI
    image: dpage/pgadmin4
    ports:
      - "5050:80"
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@admin.com
      PGADMIN_DEFAULT_PASSWORD: admin
    depends_on:
      - db

  redis_commander:  # Redis GUI
    image: rediscommander/redis-commander
    ports:
      - "8081:8081"
    environment:
      REDIS_HOSTS: local:redis:6379
    depends_on:
      - redis

volumes:
  postgres_data:
  redis_data:
```

---

## Production Stack

```yaml
# docker-compose.yml
# No hot reload, no dev tools, production images

services:
  db:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    # No exposed ports! Only internal network access
    environment:
      POSTGRES_DB: issuetracker
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}  # From .env file

  redis:
    image: redis:7-alpine
    # No exposed ports

  migrate:  # Run migrations before starting app
    build: ./backend
    command: /app/scripts/migrate.sh
    environment:
      DATABASE_URL: ${DATABASE_URL}
    depends_on:
      db:
        condition: service_healthy
    restart: "no"  # Run once and exit

  backend:
    build: ./backend  # Uses production Dockerfile (not Dockerfile.dev)
    environment:
      APP_ENV: production
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: redis://redis:6379/0
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
    depends_on:
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
    # No --reload, no port exposure
    command: /app/scripts/start.sh  # Gunicorn production server

  frontend:
    build:
      context: ./frontend
      args:
        NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL}
    environment:
      BACKEND_INTERNAL_URL: http://backend:8000
    # No port exposure

  nginx:
    image: nginx:1.27-alpine
    ports:
      - "80:80"    # Only nginx is exposed to the internet
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - backend
      - frontend

  celery_worker:
    build: ./backend
    environment:
      DATABASE_URL: ${DATABASE_URL}
      CELERY_BROKER_URL: redis://redis:6379/1
    depends_on:
      - db
      - redis

  celery_beat:
    build: ./backend
    command: celery -A app.worker.celery_app beat --loglevel=info
    depends_on:
      - redis

volumes:
  postgres_data:
```

---

## Development vs Production Differences

| Feature | Development | Production |
|---------|------------|------------|
| Code mounting | `./backend:/app` (hot reload) | No mount (image has code) |
| Server | `uvicorn --reload` | `gunicorn --workers 4` |
| Tools | flower, pgadmin, redis_commander | None |
| Port exposure | All services exposed | Only nginx on port 80 |
| Environment | `.env.dev` | `.env` / secrets |
| Image | `Dockerfile.dev` (with dev tools) | `Dockerfile` (production) |

---

## Volumes — Persistent Data

```yaml
volumes:
  postgres_data:  # Named volume
  redis_data:

services:
  db:
    volumes:
      - postgres_data:/var/lib/postgresql/data
      #       ↑                ↑
      # Named volume      Path inside container
      # (persists across container stops)
```

Without volumes, data is lost when the container stops:
```
Without volume:
  Start postgres container → create data → Stop container → Data GONE

With named volume:
  Start postgres container → data written to named volume (on host)
  Stop container → Data persists in named volume
  Start postgres container again → same data available
```

---

## Useful Docker Compose Commands

```bash
# Start everything
docker compose -f docker-compose.dev.yml up

# Start in background (detached)
docker compose -f docker-compose.dev.yml up -d

# View logs for a service
docker compose -f docker-compose.dev.yml logs backend --follow

# View logs for all services
docker compose -f docker-compose.dev.yml logs --follow

# Execute command in running container
docker compose -f docker-compose.dev.yml exec backend bash
docker compose -f docker-compose.dev.yml exec db psql -U postgres issuetracker

# Rebuild images (after Dockerfile changes)
docker compose -f docker-compose.dev.yml build
docker compose -f docker-compose.dev.yml up --build

# Stop all services
docker compose -f docker-compose.dev.yml stop

# Stop and remove containers (keeps volumes)
docker compose -f docker-compose.dev.yml down

# Stop, remove containers AND volumes (fresh start)
docker compose -f docker-compose.dev.yml down -v

# View resource usage
docker stats

# View all containers
docker ps -a
```

---

## Nginx Configuration

```nginx
# nginx/nginx.conf

# Upstream groups (load balancing across multiple containers)
upstream backend {
    server backend:8000;
}

upstream frontend {
    server frontend:3000;
}

server {
    listen 80;
    
    # Maximum request body size (file uploads)
    client_max_body_size 10m;
    
    # Route /api/* requests to backend
    location /api/ {
        # Strip the /api/ prefix before forwarding
        # /api/projects → /projects on the backend
        rewrite ^/api/(.*) /$1 break;
        
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Timeouts
        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Route everything else to frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        
        # WebSocket support (for Next.js hot reload in dev)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Health check endpoint (doesn't depend on backends)
    location /nginx-health {
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

---

## Troubleshooting Common Issues

```bash
# Container keeps restarting?
docker compose logs backend  # Check for startup errors

# Port already in use?
netstat -ano | findstr :8000  # Find what's using the port
# Then either kill that process or change the port in docker-compose

# Database connection refused?
# Usually means postgres isn't ready yet
# Check: is the healthcheck passing?
docker compose ps  # Should show "healthy" for db

# Changes not reflecting?
docker compose -f docker-compose.dev.yml build backend
docker compose -f docker-compose.dev.yml up --force-recreate backend

# Out of disk space?
docker system prune -a  # Remove unused images/containers/volumes
# WARNING: removes everything not currently in use

# "No such file or directory" on scripts?
# Check line endings — Windows CRLF vs Unix LF
# Git config: core.autocrlf=input (on Windows)
```

---

## Further Reading & Videos

- **YouTube**: Search "Docker Compose Tutorial" — TechWorld with Nana covers this in their Docker full course
- **YouTube**: Search "Nginx Reverse Proxy Docker" — Christian Lempa explains nginx+docker well
- **Official Docs**: [Docker Compose reference](https://docs.docker.com/compose/)
- **Official Docs**: [Nginx documentation](https://nginx.org/en/docs/)

---

*Next: [Module 07-01 — Kubernetes Architecture](../07-kubernetes/01-kubernetes-architecture.md)*
