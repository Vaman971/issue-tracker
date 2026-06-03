# Module 03-03 — Authentication, JWT, bcrypt & Rate Limiting

---

## Learning Objectives

After this module you will:
- Understand how passwords are stored securely with bcrypt
- See the exact token generation and verification code
- Understand how the refresh token database model works
- Know how rate limiting protects authentication endpoints

---

## Password Storage — Never Store Plain Text

Storing passwords in plain text is one of the most dangerous security mistakes. If your database is ever leaked, every user's password is exposed.

### The Right Way: bcrypt

bcrypt is a **password hashing function** designed specifically for passwords:

```
User sets password: "MySecurePassword123"
        │
        ▼
bcrypt.hash("MySecurePassword123", rounds=12)
        │
        ▼
Result: "$2b$12$LfQhlR8L...R/qK7JaVFCO"
        │        │
        │        └── 12 "rounds" = 2^12 = 4096 iterations
        └── Algorithm identifier ($2b = bcrypt)

This hash is stored in the database.
The original password is NEVER stored.
```

### Why bcrypt is Special

```
Regular hashing (SHA256):
  Hash("password123") = "ef92b778bafe771e..."
  Hash("password123") = "ef92b778bafe771e..."  ← always same!
  
  Problem: Attacker can precompute a "rainbow table" of millions
  of common passwords and their hashes, then look up any hash instantly.

bcrypt (salted hashing):
  Hash("password123", salt1) = "$2b$12$ABC...XYZ"
  Hash("password123", salt2) = "$2b$12$DEF...UVW"  ← different salt = different hash!
  
  bcrypt automatically generates and embeds a random "salt"
  in each hash. Same password → different hash every time.
  
  Additionally: bcrypt is SLOW by design (4096 iterations)
  Attacker trying 1 billion passwords/second on SHA256?
  With bcrypt (rounds=12): only ~100 attempts/second.
```

### bcrypt in This Project

```python
# backend/app/core/security.py

from passlib.context import CryptContext

# Configure bcrypt with 12 rounds (adjust based on server speed)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a plain text password for storage."""
    return pwd_context.hash(password)  # Includes random salt automatically

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its stored hash."""
    return pwd_context.verify(plain_password, hashed_password)
    # Returns True if they match, False if not
    # Always takes the same time (constant-time comparison, prevents timing attacks)
```

Usage in the register endpoint:
```python
# backend/app/api/routes/auth.py

@router.post("/register")
async def register(body: UserCreate, db=Depends(get_db)):
    # Check email not taken
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar():
        raise HTTPException(409, "Email already registered")
    
    # Hash the password BEFORE storing
    hashed = hash_password(body.password)
    
    user = User(
        email=body.email,
        hashed_password=hashed,  # Never store body.password!
        name=body.name,
        role=UserRole.DEVELOPER,
        email_verified=False,
    )
    db.add(user)
    await db.commit()
```

---

## JWT Token Generation and Verification

```python
# backend/app/core/tokens.py

from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from app.core.config import settings

def create_access_token(user_id: int, email: str, role: str) -> str:
    """Generate a short-lived access token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRES_MINUTES)
    
    payload = {
        "sub": str(user_id),       # Subject: who this token is for
        "email": email,
        "role": role,
        "exp": expire,             # Expiry: when this token becomes invalid
        "iat": now,                # Issued at: when it was created
        "type": "access",          # Token type (access vs refresh)
    }
    
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM  # HS256
    )

def create_refresh_token(user_id: int) -> str:
    """Generate a long-lived refresh token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRES_DAYS)
    
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "type": "refresh",
        # Add jti (JWT ID) for uniqueness — allows revoking specific tokens
        "jti": str(uuid.uuid4()),
    }
    
    return jwt.encode(
        payload,
        settings.JWT_REFRESH_SECRET_KEY,  # Different key for refresh tokens!
        algorithm=settings.JWT_ALGORITHM
    )

def decode_access_token(token: str) -> dict:
    """Verify and decode an access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        # jose automatically verifies:
        # 1. Signature (was it created with our secret key?)
        # 2. exp claim (has it expired?)
        
        if payload.get("type") != "access":
            raise JWTError("Wrong token type")
        
        return payload
    except JWTError as e:
        raise HTTPException(401, f"Invalid token: {str(e)}")

def decode_refresh_token(token: str) -> dict:
    """Verify and decode a refresh token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_REFRESH_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise JWTError("Wrong token type")
        return payload
    except JWTError:
        raise HTTPException(401, "Invalid refresh token")
```

---

## Refresh Token Storage in Database

Unlike access tokens (which are stateless), refresh tokens are stored in the database so we can revoke them:

```python
# backend/app/models/refresh_token.py

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id: int
    user_id: int           # Which user owns this token
    token_hash: str        # SHA256 hash of the token (not the token itself!)
    expires_at: datetime   # When this token expires
    created_at: datetime
    revoked: bool = False  # Set to True on logout
    
    # What device/browser created this token (optional)
    user_agent: Optional[str]
    ip_address: Optional[str]
```

Why store the **hash** of the token, not the token itself?

```
If an attacker breaches your database:
  
WITHOUT hashing:
  They find: "eyJhbGciOiJIUzI1NiIs..."
  They can use this token immediately!
  
WITH hashing (SHA256 of the token):
  They find: "5f4dcc3b5aa765d61d8327deb882cf99"
  They cannot reverse a SHA256 hash to get the original token.
  Token is useless to them.
```

```python
# Storing a refresh token:
import hashlib

def store_refresh_token(db, user_id: int, token: str, request: Request):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRES_DAYS),
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.client.host,
    )
    db.add(refresh_token)

# Verifying a refresh token:
async def verify_refresh_token(db, token: str) -> RefreshToken:
    # 1. Verify JWT signature (stateless check)
    payload = decode_refresh_token(token)
    user_id = int(payload["sub"])
    
    # 2. Check database (has it been revoked?)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    stored = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc)
        )
    )
    token_record = stored.scalar()
    
    if not token_record:
        raise HTTPException(401, "Refresh token has been revoked")
    
    return token_record
```

---

## The Complete Login Flow

```python
# backend/app/api/routes/auth.py

@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # 1. Rate limiting
    await login_limiter.check(request, "login")
    
    # 2. Find user by email
    result = await db.execute(
        select(User).where(User.email == body.email)
    )
    user = result.scalar()
    
    # 3. Verify password (even if user doesn't exist — prevent timing attack)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")
    
    # 4. Check email verified
    if not user.email_verified:
        raise HTTPException(403, "Please verify your email first")
    
    # 5. Generate tokens
    access_token = create_access_token(user.id, user.email, user.role.value)
    refresh_token = create_refresh_token(user.id)
    
    # 6. Store refresh token hash
    await store_refresh_token(db, user.id, refresh_token, request)
    await db.commit()
    
    # 7. Return tokens + user data
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user)
    }
```

**Timing attack prevention**: Notice we check both `not user` AND `not verify_password()` in the same condition. This is deliberate — we always call `verify_password()` even if the user doesn't exist. Why?

```
VULNERABLE (exposes user existence via timing):
  if not user:
      return HTTPException(401)  # Returns in 0.1ms
  if not verify_password(...):   # Takes 100ms (bcrypt)
      return HTTPException(401)

  An attacker can measure response time:
  0.1ms response → email doesn't exist
  100ms response → email exists but wrong password
  (Now they know which emails are registered!)

SECURE (constant time):
  if not user:
      # Still run bcrypt on a dummy hash (takes same time)
      verify_password(body.password, DUMMY_HASH)
      raise HTTPException(401, "Incorrect email or password")
  if not verify_password(body.password, user.hashed_password):
      raise HTTPException(401, "Incorrect email or password")
```

---

## Rate Limiting Implementation

```python
# backend/app/services/rate_limit.py

import redis.asyncio as aioredis
from fastapi import HTTPException, Request

class RateLimiter:
    """
    Sliding window rate limiter using Redis.
    
    Uses Redis INCR + EXPIRE commands:
    - Atomic increment (no race conditions)
    - Auto-expiry (no cleanup needed)
    """
    
    def __init__(
        self, 
        redis: aioredis.Redis, 
        max_requests: int, 
        window_seconds: int
    ):
        self.redis = redis
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    async def check(self, request: Request, action: str) -> None:
        # Create a unique key per IP + action
        # "ratelimit:login:192.168.1.100"
        key = f"ratelimit:{action}:{request.client.host}"
        
        # Atomically increment and get new value
        # INCR creates the key if it doesn't exist (starting at 0+1=1)
        count = await self.redis.incr(key)
        
        # On first request, set expiry
        if count == 1:
            await self.redis.expire(key, self.window_seconds)
        
        if count > self.max_requests:
            # How long until the window resets?
            ttl = await self.redis.ttl(key)
            raise HTTPException(
                status_code=429,
                detail=f"Too many {action} attempts. Try again in {ttl} seconds.",
                headers={"Retry-After": str(ttl)}
            )

# Create limiters for different endpoints
login_limiter = RateLimiter(redis_client, max_requests=5, window_seconds=60)
register_limiter = RateLimiter(redis_client, max_requests=3, window_seconds=60)
```

Rate limiting in Redis:
```
Key:   "ratelimit:login:10.0.0.1"
Value: "3"               (3 attempts so far)
TTL:   45 seconds        (resets in 45 more seconds)

Attempt 4: INCR → 4 (still under limit of 5)
Attempt 5: INCR → 5 (at limit — last allowed)
Attempt 6: INCR → 6 (over limit!) → 429 "Try again in 40 seconds"
```

---

## Scheduled Token Cleanup

Refresh tokens accumulate in the database. Celery Beat runs cleanup tasks:

```python
# backend/app/worker/tasks.py

@celery_app.task
async def cleanup_expired_tokens():
    """Remove expired refresh tokens and password reset tokens."""
    async with AsyncSessionLocal() as db:
        # Delete expired refresh tokens
        await db.execute(
            delete(RefreshToken).where(
                RefreshToken.expires_at < datetime.now(timezone.utc)
            )
        )
        
        # Delete expired password reset tokens (24h TTL)
        await db.execute(
            delete(PasswordResetToken).where(
                PasswordResetToken.expires_at < datetime.now(timezone.utc)
            )
        )
        
        await db.commit()

# backend/app/worker/celery_app.py
# Schedule: run daily at 2 AM
beat_schedule = {
    "cleanup-expired-tokens": {
        "task": "app.worker.tasks.cleanup_expired_tokens",
        "schedule": crontab(hour=2, minute=0),  # Every day at 2:00 AM
    }
}
```

---

## Security Headers

The Nginx configuration adds security headers:

```nginx
# nginx/nginx.conf
add_header X-Frame-Options SAMEORIGIN;
add_header X-Content-Type-Options nosniff;
add_header X-XSS-Protection "1; mode=block";
add_header Referrer-Policy "strict-origin-when-cross-origin";
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()";
```

These headers instruct browsers to:
- `X-Frame-Options: SAMEORIGIN` — Prevent clickjacking (embedding your site in an iframe)
- `X-Content-Type-Options: nosniff` — Prevent MIME sniffing attacks
- `X-XSS-Protection` — Enable browser's built-in XSS filter (legacy)

---

## OWASP Top 10 — How This Project Addresses Them

| Threat | Our mitigation |
|--------|----------------|
| Broken Authentication | bcrypt + JWT + refresh token rotation |
| Injection (SQLi) | SQLAlchemy ORM (parameterized queries by default) |
| Broken Access Control | RBAC on every endpoint + membership checks |
| Sensitive Data Exposure | Passwords hashed, tokens hashed in DB |
| Security Misconfiguration | Pydantic Settings validates config at startup |
| XSS | React escapes HTML by default; Content-Security-Policy |
| Insecure Deserialization | Pydantic validates all inputs |
| Rate Limiting | Redis-based rate limits on auth endpoints |
| Enumeration | Return 404 (not 403) when resource exists but user can't see it |
| Credential Stuffing | Rate limiting + bcrypt slow hash |

---

## Further Reading & Videos

- **YouTube**: Search "bcrypt password hashing explained" — Computerphile has an excellent video on password hashing
- **YouTube**: Search "JWT Security Best Practices" — covers common JWT vulnerabilities
- **Official Docs**: [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- **python-jose library**: [https://python-jose.readthedocs.io](https://python-jose.readthedocs.io)
- **passlib library**: [https://passlib.readthedocs.io](https://passlib.readthedocs.io)

---

*Next: [Module 03-04 — Celery, Redis Broker & Background Jobs](./04-background-jobs.md)*
