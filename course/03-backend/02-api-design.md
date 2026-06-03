# Module 03-02 — REST API Design, Routes, RBAC & Middleware

---

## Learning Objectives

After this module you will:
- Understand REST API design principles
- Know how all 13 API route modules are organized
- Understand the middleware pipeline
- See how role-based access control is enforced on every endpoint

---

## REST — What It Means

REST (Representational State Transfer) is a set of architectural constraints for APIs:

```
Core principle: Resources + HTTP Verbs + Status Codes

Resources = Things in your system:
  /projects          → collection of all projects
  /projects/42       → a specific project
  /projects/42/issues → issues belonging to project 42

HTTP Verbs = Actions on resources:
  GET    → Read (never changes anything)
  POST   → Create
  PUT    → Replace entirely
  PATCH  → Update partially
  DELETE → Delete

Status codes tell you what happened:
  2xx → Success
    200 OK          → Request succeeded
    201 Created     → Resource created
    204 No Content  → Success, no body returned
  
  4xx → Client error (you did something wrong)
    400 Bad Request      → Invalid input
    401 Unauthorized     → Not authenticated
    403 Forbidden        → Authenticated but not authorized
    404 Not Found        → Resource doesn't exist
    409 Conflict         → Conflict with current state
    422 Unprocessable    → Validation failed
    429 Too Many Requests → Rate limit exceeded
  
  5xx → Server error (we did something wrong)
    500 Internal Server Error → Bug in our code
    503 Service Unavailable   → Dependency is down
```

---

## The 13 API Route Modules

```
backend/app/api/routes/
├── auth.py           # /auth/*         Authentication flows
├── users.py          # /users/*        Profile management
├── admin.py          # /admin/*        Admin operations
├── projects.py       # /projects/*     Project CRUD
├── project_member.py # /projects/{id}/members/* Team management
├── issues.py         # /issues/*       Issue CRUD
├── comments.py       # /comments/*     Issue comments
├── attachments.py    # /attachments/*  File uploads
├── labels.py         # /labels/*       Issue labels
├── notifications.py  # /notifications/* User notifications
├── activity.py       # /activity/*     Project activity feed
├── search.py         # /search/*       Full-text search
└── stats.py          # /stats/*        Dashboard statistics
```

### Auth Routes — The Most Important

```python
# backend/app/api/routes/auth.py

router = APIRouter()

# --- PUBLIC ENDPOINTS (no auth required) ---

@router.post("/register", status_code=201)
async def register(body: UserCreate, db=Depends(get_db)):
    """Create a new user account."""
    # Check email not taken
    # Hash password with bcrypt
    # Create user record
    # Queue verification email via Celery
    
@router.post("/login")
async def login(
    body: LoginRequest, 
    db=Depends(get_db),
    request: Request = None
):
    """Authenticate and return JWT tokens."""
    # Rate limit check (5 attempts/60s per IP)
    # Verify email + password
    # Check email verified
    # Generate access token + refresh token
    # Store refresh token hash in DB
    # Return tokens + user data
    
@router.post("/refresh")
async def refresh(body: RefreshRequest, db=Depends(get_db)):
    """Exchange refresh token for new access token."""
    # Verify refresh JWT signature
    # Look up hash in DB (not revoked?)
    # Issue new access token
    
@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db=Depends(get_db)):
    """Send password reset email."""
    
@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db=Depends(get_db)):
    """Set new password using reset token."""
    
@router.get("/verify-email")
async def verify_email(token: str, db=Depends(get_db)):
    """Mark email as verified."""

# --- AUTHENTICATED ENDPOINTS ---

@router.post("/logout")
async def logout(
    body: LogoutRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Revoke refresh token."""
    # Delete refresh token from DB

@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    """Return current user profile."""
    return UserResponse.from_orm(current_user)
```

### Projects Routes

```python
# backend/app/api/routes/projects.py

# Everyone authenticated can list and view projects
@router.get("/")
async def list_projects(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List projects the current user is a member of."""
    return await project_helper.get_user_projects(db, current_user)

# Only authenticated users can create (then they become leader)
@router.post("/", status_code=201)
async def create_project(
    body: ProjectCreate,
    db=Depends(get_db),
    current_user=Depends(require_roles(
        UserRole.ADMIN, UserRole.PROJECT_LEADER
    )),
):
    """Create a new project."""

@router.get("/{project_id}")
async def get_project(project_id: int, db=Depends(get_db), current_user=...):
    """Get project details."""
    # Check user is a member of this project first

@router.patch("/{project_id}")
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    db=Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_LEADER)),
):
    """Update project details."""

@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: int,
    db=Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN)),
):
    """Delete a project. ADMIN only."""
```

### Issues Routes — The Core Resource

```python
# backend/app/api/routes/issues.py

@router.get("/")
async def list_issues(
    project_id: Optional[int] = None,
    status: Optional[IssueStatus] = None,
    priority: Optional[IssuePriority] = None,
    assignee_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List issues with filtering and pagination."""

@router.post("/", status_code=201)
async def create_issue(
    body: IssueCreate,
    db=Depends(get_db),
    current_user=Depends(require_roles(
        UserRole.DEVELOPER, UserRole.QA, UserRole.ADMIN, UserRole.PROJECT_LEADER
    )),
):
    """Create a new issue."""
    # Validate project exists and user is a member
    # Create issue record
    # Queue notification for assignees (Celery)
    # Create activity record

@router.patch("/{issue_id}")
async def update_issue(
    issue_id: int,
    body: IssueUpdate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update issue fields."""
    # Check user can update (is member of project)
    # Log status change to activity

@router.patch("/{issue_id}/assign")
async def assign_issue(
    issue_id: int,
    body: AssignIssueRequest,
    db=Depends(get_db),
    current_user=Depends(require_roles(
        UserRole.ADMIN, UserRole.PROJECT_LEADER, UserRole.DEVELOPER
    )),
):
    """Assign/unassign users to an issue."""
    # Queue notification for new assignees (Celery)
```

---

## API Response Patterns

### Paginated Responses

```python
# backend/app/schemas/shared.py

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

# Usage:
@router.get("/issues")
async def list_issues(...) -> PaginatedResponse[IssueResponse]:
    total = await db.scalar(select(func.count()).select_from(query))
    items = await db.execute(query.offset(offset).limit(page_size))
    
    return PaginatedResponse(
        items=items.scalars().all(),
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size)
    )
```

### Error Response Format

```python
# When you raise HTTPException, FastAPI returns:
{
    "detail": "Project not found"
}

# For validation errors (422), FastAPI returns:
{
    "detail": [
        {
            "loc": ["body", "title"],
            "msg": "field required",
            "type": "value_error.missing"
        }
    ]
}
```

---

## Middleware Pipeline

Middleware is code that runs for EVERY request, before it reaches the route handler:

```
Request arrives
        │
        ▼
1. CORSMiddleware
   - Is Origin header allowed?
   - If preflight OPTIONS → return CORS headers immediately
   - Add CORS headers to response
        │
        ▼
2. RequestLoggingMiddleware
   - Generate unique request ID
   - Log: "→ GET /projects request_id=req-abc123"
   - After response: "← GET /projects 200 45ms request_id=req-abc123"
        │
        ▼
3. Router (URL matching)
        │
        ▼
4. Dependency resolution
   - get_db() — create session
   - get_current_user() — verify JWT
   - require_roles() — check permission
        │
        ▼
5. Handler function
        │
        ▼
6. Response serialization
   - Pydantic converts ORM model to JSON
        │
        ▼
Response returns back through middleware (in reverse order)
```

### Request Logging Middleware

```python
# backend/app/core/request_context.py and logging.py

import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Before request
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        # Add request_id to context (accessible throughout request lifecycle)
        request.state.request_id = request_id
        
        logger.info(
            f"→ {request.method} {request.url.path}",
            extra={"request_id": request_id}
        )
        
        # Process request
        response = await call_next(request)
        
        # After request
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info(
            f"← {request.method} {request.url.path} {response.status_code} {duration_ms:.0f}ms",
            extra={"request_id": request_id}
        )
        
        # Add request ID to response headers (for debugging)
        response.headers["X-Request-ID"] = request_id
        
        return response
```

---

## Rate Limiting

```python
# backend/app/services/rate_limit.py

import redis.asyncio as redis
from fastapi import HTTPException, Request

class RateLimiter:
    def __init__(self, redis_client, max_requests: int, window_seconds: int):
        self.redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    async def check(self, request: Request, identifier: str):
        # Key: "ratelimit:login:192.168.1.1"
        key = f"ratelimit:{identifier}:{request.client.host}"
        
        # Increment counter
        current = await self.redis.incr(key)
        
        # Set expiry on first request
        if current == 1:
            await self.redis.expire(key, self.window_seconds)
        
        if current > self.max_requests:
            ttl = await self.redis.ttl(key)
            raise HTTPException(
                status_code=429,
                detail=f"Too many attempts. Try again in {ttl} seconds."
            )

# Used in auth routes:
login_limiter = RateLimiter(redis_client, max_requests=5, window_seconds=60)

@router.post("/login")
async def login(body: LoginRequest, request: Request, db=Depends(get_db)):
    await login_limiter.check(request, "login")
    # ... rest of login logic
```

---

## CORS — Cross-Origin Resource Sharing

```
PROBLEM:
Browser is at http://localhost:3000
Browser tries to fetch http://localhost:8000/api/projects
→ Different origin! (different port = different origin)
→ Browser blocks the request by default (CORS policy)

SOLUTION: Server tells browser which origins are allowed

Server includes in response:
  Access-Control-Allow-Origin: http://localhost:3000
  Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE
  Access-Control-Allow-Headers: Authorization, Content-Type

Browser sees these headers:
  "OK, the server explicitly allows http://localhost:3000"
  Allows the response to be read by JavaScript
```

```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,  # ["http://localhost:3000"]
    allow_credentials=True,   # Allow Authorization header
    allow_methods=["*"],       # All HTTP methods
    allow_headers=["*"],       # All headers
)
```

In production, `BACKEND_CORS_ORIGINS` is set to your actual domain: `https://yourdomain.com`

---

## Activity Feed — Event Sourcing Lite

Every significant change creates an Activity record:

```python
# backend/app/models/activity.py

class IssueActivity(Base):
    __tablename__ = "activities"
    
    id: int
    project_id: int           # Which project
    issue_id: Optional[int]   # Which issue (if applicable)
    user_id: int              # Who did it
    activity_type: str        # "issue_created", "status_changed", "assigned"
    old_value: Optional[str]  # Previous value
    new_value: Optional[str]  # New value
    created_at: datetime

# Example activity entries:
{
    "activity_type": "status_changed",
    "old_value": "TODO",
    "new_value": "IN_PROGRESS",
    "user_id": 2,
    "issue_id": 42,
}
{
    "activity_type": "assigned",
    "new_value": "bob@example.com",
    "user_id": 1,
    "issue_id": 42,
}
```

This creates a complete audit trail — you can reconstruct the full history of every issue.

---

## Search Endpoint

```python
# backend/app/api/routes/search.py

@router.get("/")
async def search(
    q: str = Query(..., min_length=2),  # Search query required
    project_id: Optional[int] = None,
    page: int = 1,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Full-text search across issues."""
    # PostgreSQL full-text search using ts_vector/ts_query
    query = select(Issue).where(
        func.to_tsvector('english', Issue.title + ' ' + Issue.description)
        .match(q)
    )
    # Also filter by projects user has access to
    ...
```

---

## Helper Functions — DRY Business Logic

```
backend/app/api/helpers/
├── issue_helper.py    # Complex issue queries + business rules
└── project_helper.py  # Complex project queries
```

These extract reusable logic used by multiple routes:

```python
# backend/app/api/helpers/project_helper.py

async def get_user_projects(db: AsyncSession, user: User) -> List[Project]:
    """Get projects where user is a member or leader."""
    if user.role == UserRole.ADMIN:
        # Admins see all projects
        result = await db.execute(select(Project))
        return result.scalars().all()
    
    # Regular users see projects they're members of
    result = await db.execute(
        select(Project)
        .join(ProjectMember)
        .where(ProjectMember.user_id == user.id)
    )
    return result.scalars().all()

async def check_project_access(
    db: AsyncSession, 
    project_id: int, 
    user: User
) -> Project:
    """Get project and verify user has access. Raises 404 if not found or forbidden."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    
    if user.role != UserRole.ADMIN:
        membership = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id
            )
        )
        if not membership.scalar():
            raise HTTPException(404, "Project not found")  # Don't reveal it exists!
    
    return project
```

Note: We return 404 instead of 403 when a project exists but the user isn't a member — this prevents **enumeration attacks** (attackers discovering which project IDs exist).

---

## Further Reading & Videos

- **YouTube**: Search "REST API Design Best Practices" — Milan Jovanovic or Fireship
- **YouTube**: Search "FastAPI CRUD API with SQLAlchemy" — Amigoscode
- **Official Docs**: [FastAPI routing documentation](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- **Reference**: [HTTP Status Codes cheatsheet](https://httpstatuses.io)

---

*Next: [Module 03-03 — Authentication, JWT & Rate Limiting](./03-auth-security.md)*
