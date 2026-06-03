# Module 03-01 — FastAPI: Async Python, Pydantic & Dependency Injection

---

## Learning Objectives

After this module you will:
- Understand what FastAPI is and how ASGI works
- Know what async/await means and why it matters for web servers
- Understand Pydantic for data validation
- Know how dependency injection works in FastAPI
- Navigate the project's main.py and understand every piece

---

## What Is FastAPI?

FastAPI is a modern Python web framework for building APIs. It's built on three pillars:

```
FastAPI = Starlette (ASGI web framework)
        + Pydantic (data validation)
        + Python type hints (for automatic docs + validation)
```

Why FastAPI over older frameworks (Flask, Django)?
- **Async-native**: handles thousands of concurrent connections
- **Automatic API documentation**: visit `/docs` to see interactive Swagger UI
- **Type safety**: Python type hints = automatic request/response validation
- **Performance**: one of the fastest Python frameworks (on par with Node.js)

---

## Sync vs Async — The Fundamental Difference

### Synchronous (Blocking) I/O

```python
# Old-style synchronous server
def handle_request():
    # This BLOCKS the thread for 50ms
    db_result = database.query("SELECT * FROM users")  # 50ms
    
    # Thread is SITTING IDLE waiting for DB
    # Can't handle other requests during this time!
    
    return {"users": db_result}
```

With a synchronous server:
```
Thread 1: Request A → DB query (50ms wait) → Response
Thread 2: Request B → DB query (50ms wait) → Response
Thread 3: Request C → DB query (50ms wait) → Response
...need 1 thread per concurrent request!

1000 concurrent users = 1000 threads = ~2GB RAM just for threads
```

### Asynchronous (Non-Blocking) I/O

```python
# FastAPI async handler
async def handle_request():
    # This does NOT block — execution is suspended at 'await'
    # Python can handle other requests while waiting for DB
    db_result = await database.query("SELECT * FROM users")  # 50ms
    
    return {"users": db_result}
```

With an async server (event loop model):
```
Single thread, Event Loop running:

Time 0ms:  Request A arrives → starts DB query → AWAIT (suspend)
Time 0ms:  Request B arrives → starts DB query → AWAIT (suspend)
Time 0ms:  Request C arrives → starts DB query → AWAIT (suspend)
Time 50ms: Request A's DB query completes → resume → send response
Time 50ms: Request B's DB query completes → resume → send response
Time 50ms: Request C's DB query completes → resume → send response

All 3 handled in 50ms total (not 150ms)!
1000 concurrent users = 1 thread (event loop)
```

### The Event Loop — How Python Async Works

```
┌─────────────────────────────────────────────────────────────────┐
│                       EVENT LOOP                                │
│                                                                 │
│   Task Queue:                                                   │
│   [Request_A_handler, Request_B_handler, Request_C_handler]    │
│                                                                 │
│   Running:                                                      │
│   Request_A_handler:                                            │
│     → reaches "await db.execute(query)"                        │
│     → suspends itself, adds to waiting set                     │
│     → picks up Request_B_handler from queue                    │
│     → Request_B also reaches "await" → suspends                │
│     → picks up Request_C_handler                               │
│     → ...                                                       │
│                                                                 │
│   I/O event arrives (DB response for Request_A):               │
│     → resumes Request_A_handler from after the await           │
│     → continues until next await or return                     │
└─────────────────────────────────────────────────────────────────┘
```

This is called the **Reactor pattern** (or event-driven I/O). Node.js uses the same model.

---

## ASGI — The Protocol

ASGI (Asynchronous Server Gateway Interface) is the protocol between Python web frameworks and web servers.

```
Internet
    │
    ▼
Gunicorn (manages 4 worker processes)
    │
    ▼
Uvicorn (ASGI server — runs event loop)
    │
    ▼
FastAPI (ASGI application — handles routing)
    │
    ▼
Your handler function
```

- **Gunicorn**: Process manager — starts multiple worker processes for multi-CPU utilization
- **Uvicorn**: ASGI server — runs the asyncio event loop inside each worker
- **FastAPI**: Your application code

```bash
# How the backend starts in production (backend/scripts/start.sh):
gunicorn app.main:app \
  --workers 4 \                    # 4 worker processes (one per CPU core)
  --worker-class uvicorn.workers.UvicornWorker \  # Each uses uvicorn event loop
  --bind 0.0.0.0:8000 \
  --timeout 120                    # Kill workers that don't respond in 120s
```

With 4 workers, each running an event loop handling hundreds of concurrent connections, you get high throughput with a small memory footprint.

---

## FastAPI Application Factory

```python
# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Lifespan context manager — runs on startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP code (runs when app starts)
    await init_redis()       # Connect to Redis
    await run_migrations()   # Run any pending DB migrations
    # ── yield ─ app runs here ──
    yield
    # SHUTDOWN code (runs when app stops)
    await close_redis()      # Clean up connections

# Create the FastAPI app
app = FastAPI(
    title="Issue Tracker API",
    version="2.0.0",
    lifespan=lifespan,
    # OpenAPI docs available at /docs
)

# Add CORS middleware (allows frontend to call the API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,  # ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register custom middleware
app.add_middleware(RequestLoggingMiddleware)

# Register all route modules
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(projects_router, prefix="/projects", tags=["projects"])
app.include_router(issues_router, prefix="/issues", tags=["issues"])
# ... 10 more routers

# Health check endpoints (used by Kubernetes probes)
@app.get("/health/live")
async def liveness():
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness():
    # Check dependencies are reachable
    await check_db_connection()
    await check_redis_connection()
    return {"status": "ready"}
```

---

## Pydantic — Data Validation

Pydantic validates data at runtime using Python type hints:

```python
# backend/app/schemas/issue.py

from pydantic import BaseModel, Field, validator
from enum import Enum
from datetime import datetime
from typing import Optional, List

class IssuePriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class IssueStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    DONE = "DONE"

# REQUEST schema (what the client sends)
class IssueCreate(BaseModel):
    title: str = Field(
        ...,               # "..." means required
        min_length=1,
        max_length=200,
        description="Issue title"
    )
    description: Optional[str] = Field(
        None,
        max_length=5000
    )
    priority: IssuePriority = IssuePriority.MEDIUM
    project_id: int
    assignee_ids: List[int] = []
    
    @validator('title')
    def title_must_not_be_blank(cls, v):
        if not v.strip():
            raise ValueError('Title cannot be blank')
        return v.strip()  # Also strips whitespace

# RESPONSE schema (what the server sends back)
class IssueResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: IssueStatus
    priority: IssuePriority
    project_id: int
    creator_id: int
    assignees: List[UserBrief]  # Nested schema
    created_at: datetime
    updated_at: datetime
    
    class Config:
        # Allow ORM objects (SQLAlchemy models) to be serialized
        from_attributes = True
```

### How Pydantic Validates

```python
# FastAPI automatically:
# 1. Reads the request body as JSON
# 2. Passes it to IssueCreate(**json_body)
# 3. Pydantic validates every field
# 4. If validation fails → returns 422 Unprocessable Entity with details

# If you POST this body:
{
    "title": "",         # Fails: min_length=1
    "priority": "URGENT" # Fails: not a valid IssuePriority enum value
}

# FastAPI automatically returns:
{
    "detail": [
        {
            "loc": ["body", "title"],
            "msg": "ensure this value has at least 1 character",
            "type": "value_error.any_str.min_length"
        },
        {
            "loc": ["body", "priority"],
            "msg": "value is not a valid enumeration member",
            "type": "type_error.enum"
        }
    ]
}
```

No manual validation code needed — Pydantic handles everything.

---

## Dependency Injection

Dependency Injection (DI) is a way to provide shared resources (database sessions, current user, etc.) to route handlers without repeating code.

### The Problem Without DI

```python
# Without DI — repetitive and error-prone
@app.get("/projects")
async def get_projects(request: Request, token: str = Header(...)):
    # Every endpoint must do this manually:
    user = verify_jwt_and_get_user(token)
    if not user:
        raise HTTPException(401)
    
    async with AsyncSession(engine) as db:
        projects = await db.execute(select(Project).where(...))
        return projects.all()

@app.get("/issues")
async def get_issues(request: Request, token: str = Header(...)):
    # Same auth boilerplate repeated!
    user = verify_jwt_and_get_user(token)
    if not user:
        raise HTTPException(401)
    
    async with AsyncSession(engine) as db:
        ...
```

### With FastAPI Dependency Injection

```python
# backend/app/api/deps.py

async def get_db() -> AsyncGenerator:
    """Provides a database session for the duration of the request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session           # Request uses this session
            await session.commit()  # Auto-commit on success
        except Exception:
            await session.rollback()  # Auto-rollback on error
            raise
        finally:
            await session.close()   # Always close

async def get_current_user(
    token: str = Depends(oauth2_scheme),  # Extract Bearer token
    db: AsyncSession = Depends(get_db)    # Get DB session
) -> User:
    """Verifies JWT and returns the current user."""
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await db.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

# Usage in routes — clean and declarative:
@router.get("/projects")
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # db is already connected, current_user is already verified
    projects = await get_user_projects(db, current_user)
    return projects
```

### Dependency Chain

Dependencies can depend on other dependencies:

```
list_projects endpoint
    │
    ├── Depends(get_db)
    │       └── Creates AsyncSession from pool
    │
    └── Depends(get_current_user)
            ├── Depends(oauth2_scheme) → extracts JWT from header
            ├── Depends(get_db) → same session reused!
            │
            └── Verifies JWT → queries User from DB
```

FastAPI resolves dependencies in the right order and reuses shared dependencies within the same request.

---

## Role-Based Access Control (RBAC)

```python
# backend/app/api/rbac.py

from functools import wraps
from fastapi import HTTPException

def require_roles(*allowed_roles: UserRole):
    """Dependency factory — creates a dependency that checks user role."""
    
    async def check_role(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}"
            )
        return current_user
    
    return check_role

# Usage:
@router.delete("/projects/{id}")
async def delete_project(
    id: int,
    db: AsyncSession = Depends(get_db),
    # Only ADMIN can delete projects:
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    project = await db.get(Project, id)
    await db.delete(project)
    await db.commit()
    return {"message": "Deleted"}
```

---

## Path Parameters, Query Parameters, Request Body

```python
@router.get("/projects/{project_id}/issues")
async def list_issues(
    # PATH PARAMETER — from URL: /projects/42/issues
    project_id: int,
    
    # QUERY PARAMETERS — from URL: ?status=IN_PROGRESS&page=2
    status: Optional[IssueStatus] = None,
    page: int = Query(default=1, ge=1),      # ge=1 means "greater than or equal to 1"
    page_size: int = Query(default=20, le=100),
    
    # DEPENDENCIES
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    query = select(Issue).where(Issue.project_id == project_id)
    if status:
        query = query.where(Issue.status == status)
    query = query.offset(offset).limit(page_size)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/projects/{project_id}/issues")
async def create_issue(
    project_id: int,
    
    # REQUEST BODY — parsed from JSON body
    body: IssueCreate,
    
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(
        UserRole.DEVELOPER, UserRole.QA, UserRole.ADMIN
    )),
):
    ...
```

---

## HTTP Status Codes and Error Handling

```python
from fastapi import HTTPException

# Return appropriate status codes:
@router.post("/issues", status_code=201)  # 201 Created
async def create_issue(...):
    ...

@router.delete("/issues/{id}", status_code=204)  # 204 No Content
async def delete_issue(...):
    ...

# Raise errors when something goes wrong:
raise HTTPException(status_code=404, detail="Issue not found")
raise HTTPException(status_code=403, detail="Not allowed")
raise HTTPException(status_code=400, detail="Invalid input")
raise HTTPException(status_code=409, detail="Email already exists")
raise HTTPException(status_code=429, detail="Too many requests")
```

---

## Automatic OpenAPI Documentation

FastAPI generates interactive API documentation at `/docs`:

```
Visit http://localhost:8000/docs

You'll see:
- All endpoints organized by tag
- Request schemas (what to send)
- Response schemas (what you get back)
- "Try it out" button — test endpoints directly in browser
- Authentication header input

This is generated from your Python code — no manual docs needed!
```

---

## The Settings System

```python
# backend/app/core/config.py

from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # FastAPI
    APP_ENV: str = "development"
    
    # Database
    DATABASE_URL: str  # Required — no default
    
    # JWT
    JWT_SECRET_KEY: str  # Required
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRES_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRES_DAYS: int = 7
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    class Config:
        env_file = ".env"  # Load from .env file
        case_sensitive = True
    
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

# Singleton settings object — import this throughout the codebase
settings = Settings()
```

Pydantic Settings:
- Reads from environment variables and `.env` file
- Validates types at startup
- Fails fast if required vars are missing (can't start with broken config)

---

## Further Reading & Videos

- **YouTube**: Search "FastAPI Tutorial" — Sebastián Ramírez (creator of FastAPI) has talks, or search "FastAPI Full Course" on Amigoscode
- **YouTube**: Search "Python async await explained" — ArjanCodes covers Python async deeply
- **Official Docs**: [FastAPI documentation](https://fastapi.tiangolo.com) — exceptionally well written
- **Official Docs**: [Pydantic v2 documentation](https://docs.pydantic.dev)

---

*Next: [Module 03-02 — REST API Design, Routes & Middleware](./02-api-design.md)*
