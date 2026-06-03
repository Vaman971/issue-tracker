# Module 05-01 — Redis: Internals, Caching Strategies & Message Queue

---

## Learning Objectives

After this module you will:
- Understand what Redis is and why it's so fast
- Know how Redis is used for caching in this project
- Understand Redis as a Celery message broker
- Know the different Redis data structures

---

## What Is Redis?

Redis (Remote Dictionary Server) is an **in-memory data store**. Unlike PostgreSQL (which stores data on disk), Redis stores everything in RAM — making it orders of magnitude faster.

```
RAM access time:    ~100 nanoseconds
SSD access time:    ~0.1 milliseconds   (1,000x slower than RAM)
HDD access time:    ~10 milliseconds    (100,000x slower than RAM)
Network round-trip: ~1 millisecond      (10,000x slower than RAM)

Redis is essentially as fast as RAM access.
```

Redis is **single-threaded** (for data operations) — this might sound like a limitation, but it's actually a strength:
- No lock contention between threads
- Commands are atomic by design
- Predictable performance
- Can handle millions of operations per second

---

## Redis Internal Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         REDIS SERVER                            │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Event Loop (I/O Multiplexing)          │   │
│  │                                                         │   │
│  │   Client 1: "SET key1 value1"  ──►  ┌──────────┐       │   │
│  │   Client 2: "GET key2"         ──►  │ Command  │       │   │
│  │   Client 3: "INCR counter"     ──►  │ Queue    │       │   │
│  │                                     └────┬─────┘       │   │
│  │                                          │              │   │
│  │                                          ▼              │   │
│  │                                 ┌──────────────┐        │   │
│  │                                 │Single-threaded│        │   │
│  │                                 │  Executor    │        │   │
│  │                                 │  (processes  │        │   │
│  │                                 │  one at once)│        │   │
│  │                                 └──────┬───────┘        │   │
│  └─────────────────────────────────────── │ ───────────────┘   │
│                                           │                     │
│  ┌────────────────────────────────────────▼──────────────────┐  │
│  │                    In-Memory Data Store                   │  │
│  │                                                           │  │
│  │   DB 0: { "project:1": {...}, "user:42": {...}, ... }    │  │
│  │   DB 1: { "celery-task-1234": {...}, ... }  (Celery broker)│ │
│  │   DB 2: { "celery-result-1234": {...}, ... } (Celery results)│ │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              Persistence (Optional)                       │  │
│  │  RDB: Periodic snapshots to disk                         │  │
│  │  AOF: Append-only file of all commands (for recovery)    │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Redis Data Structures

Redis isn't just a simple key-value store — it has rich data types:

### String (simplest)
```
SET user:1:name "Alice"        → Sets key=value
GET user:1:name                → Returns "Alice"
INCR page_views                → Atomic increment (returns new value)
EXPIRE session:abc123 3600     → Auto-delete in 3600 seconds (1 hour)
```

### Hash (like a Python dict within a key)
```
HSET project:1 name "Website" leader_id 1 created_at 1706123456
HGET project:1 name            → "Website"
HGETALL project:1              → {"name": "Website", "leader_id": "1", ...}
```

### List (ordered list, push/pop from either end)
```
RPUSH notifications:user:1 "You were assigned..."
LRANGE notifications:user:1 0 -1  → all notifications
LPOP queue:email               → pop from left (dequeue)
```

### Set (unordered unique values)
```
SADD project:1:members 1 2 3 5
SMEMBERS project:1:members     → {1, 2, 3, 5}
SISMEMBER project:1:members 4  → 0 (false)
```

### Sorted Set (like a set but with scores — used for leaderboards)
```
ZADD issue:priority 100 "issue:1" 50 "issue:2" 75 "issue:3"
ZRANGE issue:priority 0 -1 REV   → ["issue:1", "issue:3", "issue:2"]
```

---

## Caching in This Project

```python
# backend/app/services/cache.py

import redis.asyncio as aioredis
import json
from typing import Any, Optional

class CacheService:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache. Returns None if not found."""
        value = await self.redis.get(key)
        if value is None:
            return None
        return json.loads(value)  # Deserialize JSON
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: int = 300  # 5 minutes default
    ) -> None:
        """Store a value in cache with expiry."""
        await self.redis.set(
            key,
            json.dumps(value, default=str),  # Serialize to JSON
            ex=ttl  # Expire after ttl seconds
        )
    
    async def delete(self, key: str) -> None:
        """Remove a value from cache."""
        await self.redis.delete(key)
    
    async def delete_pattern(self, pattern: str) -> None:
        """Remove all keys matching a pattern."""
        # e.g., "project:*" deletes all project cache entries
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
            if keys:
                await self.redis.delete(*keys)
            if cursor == 0:
                break

# Initialize with Redis connection
cache = CacheService(redis_client)
```

### Cache Usage in Routes

```python
# backend/app/api/routes/projects.py

@router.get("/")
async def list_projects(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Cache key includes user ID (different users see different projects)
    cache_key = f"projects:user:{current_user.id}"
    
    # Try cache first
    cached = await cache.get(cache_key)
    if cached:
        return cached  # Fast path: return from cache
    
    # Cache miss — query database
    projects = await project_helper.get_user_projects(db, current_user)
    
    # Serialize to dict for caching
    projects_data = [ProjectResponse.model_validate(p).model_dump() for p in projects]
    
    # Store in cache (5 minutes TTL)
    await cache.set(cache_key, projects_data, ttl=300)
    
    return projects_data

@router.post("/")
async def create_project(...):
    # ... create project ...
    
    # Invalidate cache for this user (their project list changed)
    await cache.delete(f"projects:user:{current_user.id}")
    
    return new_project
```

---

## Cache Hit/Miss Flow

```
Request: GET /projects

1. FastAPI handler runs
2. Check Redis: GET "projects:user:42"
   │
   ├─► FOUND (cache HIT):
   │     Redis returns JSON string
   │     Deserialize to list
   │     Return immediately (< 1ms)
   │
   └─► NOT FOUND (cache MISS):
         Query PostgreSQL (50-100ms)
         Serialize result to JSON
         SET "projects:user:42" TTL=300
         Return data

After 300 seconds: Redis auto-deletes the key
Next request: cache miss → fresh database query
```

### Cache Invalidation Strategy

```
When does the cache become stale?
  - User creates a new project
  - User is added to/removed from a project
  - Project is renamed

Strategy used here: DELETE on write
  - After any write operation → delete related cache keys
  - Next read → fresh from database → re-cached

Alternative strategies:
  - TTL-only: Accept stale data for TTL duration (simpler, may show old data)
  - Write-through: Update cache on write (complex, keeps cache fresh)
  - Event-driven: Pub/sub to notify cache invalidation (complex, very fresh)
```

---

## Redis as Celery Broker

Celery uses Redis as a message broker — it stores task messages in Redis lists:

```
How Celery uses Redis:

Queue: "email" → Redis LIST key: "celery-{email}"
Queue: "notifications" → Redis LIST key: "celery-{notifications}"
Queue: "default" → Redis LIST key: "celery"

Publishing a task (in FastAPI):
  RPUSH "celery-{notifications}" '{
    "task": "app.worker.tasks.notify_issue_assigned",
    "id": "task-abc-123",
    "kwargs": {"issue_id": 42, "assignee_ids": [1, 3]},
    "retries": 0,
    ...
  }'

Consuming a task (in Celery Worker):
  BLPOP "celery-{notifications}" "celery-{email}" "celery" TIMEOUT=1
  → Blocks up to 1 second waiting for a task
  → Returns the next task message
  → Worker executes the task
```

**BLPOP** (Blocking Left Pop) is key — workers don't poll the queue, they block waiting for tasks. This is very efficient and has near-zero latency.

```
Task Lifecycle in Redis:

1. RPUSH → task added to queue (tiny JSON blob in list)
2. BLPOP → worker picks up task (removed from list)
3. Task executes
4. SET "celery-result-{task_id}" → result stored
   (expires after 1 day by default)
```

---

## Redis Connection Setup

```python
# backend/app/core/redis.py

import redis.asyncio as aioredis
from app.core.config import settings

# Global Redis connection pool
redis_client: aioredis.Redis = None

async def init_redis():
    """Create Redis connection pool on startup."""
    global redis_client
    redis_client = aioredis.from_url(
        settings.REDIS_URL,  # "redis://redis:6379/0"
        encoding="utf-8",
        decode_responses=True,  # Always return strings, not bytes
        max_connections=20,     # Max connections in pool
    )

async def close_redis():
    """Close Redis connection pool on shutdown."""
    global redis_client
    if redis_client:
        await redis_client.close()

async def check_redis_connection() -> bool:
    """Used by readiness probe."""
    try:
        return await redis_client.ping()
    except Exception:
        return False
```

---

## Rate Limiting with Redis

Redis's atomic INCR + EXPIRE is perfect for rate limiting:

```python
# Rate limit: 5 login attempts per 60 seconds per IP

# Attempt 1:
INCR "ratelimit:login:10.0.0.1"    → 1
EXPIRE "ratelimit:login:10.0.0.1" 60

# Attempts 2-5: 
INCR "ratelimit:login:10.0.0.1"    → 2, 3, 4, 5

# Attempt 6:
INCR "ratelimit:login:10.0.0.1"    → 6
# 6 > 5 → return 429 Too Many Requests
# TTL "ratelimit:login:10.0.0.1" → 45 (tells user to wait 45 more seconds)

# After 60 seconds:
# Redis automatically deletes the key
# INCR → 1 again (window reset)
```

Why INCR is safe for rate limiting:
- Redis is single-threaded → INCR is atomic
- No two requests can increment simultaneously and both see value "1"
- No race condition possible (unlike SQL `UPDATE counter = counter + 1`)

---

## ElastiCache Redis — Production Setup

In production, we use AWS ElastiCache Redis 7 in **cluster mode**:

```
Cluster mode enabled: 3 shards × 2 nodes each = 6 Redis nodes

Why cluster mode?
  - Horizontal scaling: data spread across 3 shards
  - 6 nodes can handle millions of ops/second
  - Multi-AZ: each shard has a primary + replica
  - Automatic failover: if primary fails, replica promotes in ~60s

Data distribution (consistent hashing):
  Key "project:1" → hash slot 1234 → Shard 1
  Key "user:42"   → hash slot 5678 → Shard 2
  Key "cache:abc" → hash slot 9012 → Shard 3
  
  Client automatically routes to correct shard
  (transparent to application code)
```

---

## Redis Monitoring

Access Redis Commander in development:

```
http://localhost:8081

You can see:
  - All databases (0, 1, 2)
  - All keys with their types and values
  - TTL remaining on cached items
  - Memory usage
```

Useful Redis CLI commands for debugging:
```bash
# Connect to Redis
docker exec -it redis redis-cli

# Count keys matching pattern
KEYS "ratelimit:*"
KEYS "projects:user:*"

# Get TTL of a key (seconds until expiry)
TTL "projects:user:42"

# Get all keys and memory usage
INFO memory
INFO keyspace

# Monitor all commands in real-time (for debugging)
MONITOR
```

---

## Further Reading & Videos

- **YouTube**: Search "Redis in 100 Seconds" — Fireship gives a quick excellent overview
- **YouTube**: Search "Redis Internals Deep Dive" — Hussein Nasser covers Redis architecture thoroughly
- **YouTube**: Search "Redis Caching Strategies" — patterns for cache invalidation
- **Official Docs**: [Redis documentation](https://redis.io/docs/) — very comprehensive
- **Interactive Tutorial**: [Try Redis](https://try.redis.io) — run Redis commands in the browser

---

*Next: [Module 05-02 — AWS S3: Object Storage & Presigned URLs](./02-s3-file-storage.md)*
