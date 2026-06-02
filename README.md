# Team Issue Tracker

A full-stack project and issue tracking application built to learn intermediate software engineering concepts.

## Tech Stack

### Backend
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis
- JWT access and refresh tokens
- RBAC authorization
- Pytest

### Frontend
- Next.js
- Redux Toolkit
- RTK Query
- React Hook Form
- Zod
- CSS Modules
- Jest
- React Testing Library

### DevOps
- Docker
- Docker Compose
- nginx reverse proxy
- GitHub Actions CI

## Local Development

Start all services:

```bash
docker compose up --build
````

Frontend:

```text
http://localhost
```

Backend through nginx:

```text
http://localhost/api
```

Backend directly:

```text
http://localhost:8000
```

## Backend Tests

```bash
cd backend
pytest
```

## Frontend Tests

```bash
cd frontend
npm test
```

## Environment Files

Copy examples:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

## Default Admin Seed

Run:

```bash
cd backend
python -m app.db.seed
```

## Main Concepts Practiced

* Authentication vs authorization
* OAuth2-style access/refresh token flow
* Role-based access control
* Resource-based authorization
* Database migrations
* Pagination
* Background tasks
* Structured logging
* RTK Query caching
* Form validation
* Optimistic updates
* Protected layouts
* Dockerized services
* Reverse proxy routing
* CI pipelines
```
