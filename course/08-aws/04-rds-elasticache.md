# Module 08-04 — RDS & ElastiCache: Managed PostgreSQL & Redis

---

## AWS RDS — Managed PostgreSQL

RDS (Relational Database Service) is AWS's managed database service. Instead of running PostgreSQL on an EC2 instance yourself, AWS handles:
- Installation and configuration
- Automated backups (daily + transaction logs)
- Software patching
- Multi-AZ failover (automatic promotion of standby)
- Performance Insights (query analysis)
- Storage auto-scaling

### Multi-AZ Architecture

```
                     APPLICATION
                          │
                          ▼
              ┌─────────────────────┐
              │    RDS Endpoint     │
              │ (DNS name, stable)  │
              └─────────────────────┘
                          │
                          ▼ (normally routes to)
              ┌─────────────────────┐
              │    PRIMARY DB       │
              │    ap-south-1a      │
              │    db.r6g.large     │
              │    Writes + Reads   │
              └──────────┬──────────┘
                         │ Synchronous replication
                         │ (every write committed to
                         │  standby before acknowledged)
                         ▼
              ┌─────────────────────┐
              │    STANDBY DB       │
              │    ap-south-1b      │
              │    db.r6g.large     │
              │    No traffic       │
              └─────────────────────┘

If ap-south-1a data center fails:
  AWS detects failure (~30 seconds)
  DNS endpoint updated → now points to standby
  Standby promoted to primary in ap-south-1b
  New standby created in ap-south-1c
  Total downtime: ~1-2 minutes
```

### RDS Terraform Configuration

```hcl
# infra/terraform/modules/rds/main.tf

# Subnet group: tells RDS which subnets to use
resource "aws_db_subnet_group" "main" {
  name       = "${var.identifier}-subnet-group"
  subnet_ids = var.private_subnet_ids  # Private subnets only
}

resource "aws_db_instance" "main" {
  identifier = var.identifier  # "issue-tracker-db-prod"
  
  # Engine
  engine         = "postgres"
  engine_version = "16"
  
  # Instance size
  instance_class = var.instance_class  # "db.r6g.large"
  # r6g = memory-optimized, 6th gen, ARM (Graviton) = cheaper than x86
  # large = 2 vCPUs, 16 GB RAM
  
  # Storage
  allocated_storage     = 100   # GB (initial)
  max_allocated_storage = 500   # Auto-grow up to 500 GB
  storage_type          = "gp3" # General Purpose SSD (better than gp2)
  storage_encrypted     = true  # Encrypt data at rest
  kms_key_id           = var.kms_key_arn
  
  # Database credentials
  db_name  = "issuetracker"
  username = "postgres"
  password = var.db_password  # From Terraform secrets/variables
  
  # High Availability
  multi_az = true  # Primary + Standby in different AZs
  
  # Network
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.rds_security_group_id]
  publicly_accessible    = false  # Private, not internet-accessible
  
  # Backups
  backup_retention_period = 7    # Keep 7 days of automated backups
  backup_window           = "02:00-03:00"  # Backup at 2 AM UTC
  maintenance_window      = "Mon:03:00-Mon:04:00"  # Maintenance at 3 AM UTC Monday
  
  # Enable enhanced monitoring
  monitoring_interval = 60  # CloudWatch metrics every 60 seconds
  monitoring_role_arn = var.monitoring_role_arn
  
  # Deletion protection (must explicitly disable before deleting)
  deletion_protection = true
  
  # Parameter group for performance tuning
  parameter_group_name = aws_db_parameter_group.main.name
  
  # Snapshots
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.identifier}-final-snapshot"
}

# Parameter group: PostgreSQL configuration
resource "aws_db_parameter_group" "main" {
  family = "postgres16"
  name   = "${var.identifier}-params"
  
  parameter {
    name  = "max_connections"
    value = "500"
    # With HPA up to 30 backend pods × 5 connections = 150
    # Plus workers, admin tools — 500 gives plenty of headroom
  }
  
  parameter {
    name  = "work_mem"
    value = "4096"  # 4MB per query operation (sort, hash join)
  }
  
  parameter {
    name  = "maintenance_work_mem"
    value = "131072"  # 128MB for VACUUM, CREATE INDEX
  }
  
  parameter {
    name  = "log_min_duration_statement"
    value = "500"  # Log queries slower than 500ms
  }
  
  parameter {
    name  = "log_connections"
    value = "1"  # Log every new connection
  }
  
  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"  # Query statistics
  }
}
```

### Connecting to RDS from EKS

```
EKS pods connect to RDS using the endpoint DNS name:
  issue-tracker-db-prod.cluster-xyz.ap-south-1.rds.amazonaws.com:5432

This DNS name:
  - Always resolves to the current PRIMARY (even after failover)
  - Accessible only within the VPC (private)
  - Blocked by security group for anything outside EKS nodes

Connection string in application:
  DATABASE_URL = "postgresql+asyncpg://postgres:PASSWORD@ENDPOINT:5432/issuetracker"
```

---

## AWS ElastiCache — Managed Redis

ElastiCache is AWS's managed Redis/Memcached service. Like RDS for databases, it handles the operational work of running Redis.

### Cluster Mode Architecture

```
ElastiCache Redis 7 — Cluster mode enabled

Cluster: 3 shards × 2 nodes = 6 Redis nodes
  
  Shard 1:
    Primary: redis-cluster-0001-001 (ap-south-1a) — handles writes + reads
    Replica: redis-cluster-0001-002 (ap-south-1b) — handles reads, failover standby
  
  Shard 2:
    Primary: redis-cluster-0002-001 (ap-south-1b)
    Replica: redis-cluster-0002-002 (ap-south-1c)
  
  Shard 3:
    Primary: redis-cluster-0003-001 (ap-south-1c)
    Replica: redis-cluster-0003-002 (ap-south-1a)

Data distribution via consistent hashing:
  Key "project:1" → hash slot 1234 → Shard 1
  Key "user:42" → hash slot 5678 → Shard 2
  Key "cache:xyz" → hash slot 9012 → Shard 3

If Shard 1 primary fails:
  Replica in ap-south-1b promoted to primary (~30 seconds)
  Traffic automatically routed to new primary
  No data loss (replication was synchronous)
```

### ElastiCache Terraform Configuration

```hcl
# infra/terraform/modules/elasticache/main.tf

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.name}-subnet-group"
  subnet_ids = var.private_subnet_ids
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.name}-redis"
  description          = "Redis cluster for ${var.name}"
  
  # Redis version
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = var.node_type  # "cache.r6g.large" (2 vCPUs, 13GB RAM)
  
  # Cluster mode
  cluster_mode         = "enabled"
  num_node_groups      = var.num_shards           # 3 shards
  replicas_per_node_group = var.replicas_per_shard # 1 replica per shard
  
  # Network
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [var.elasticache_security_group_id]
  
  # High Availability
  automatic_failover_enabled = true  # Auto-promote replica on primary failure
  multi_az_enabled           = true  # Replicas in different AZs
  
  # Security
  at_rest_encryption_enabled  = true  # Encrypt data at rest
  transit_encryption_enabled  = true  # Encrypt data in transit (TLS)
  auth_token                  = var.redis_auth_token  # Password for Redis
  
  # Maintenance
  maintenance_window = "sun:05:00-sun:06:00"
  
  # Snapshots
  snapshot_retention_limit = 5  # Keep 5 days of snapshots
  snapshot_window          = "04:00-05:00"
}
```

### Connecting to ElastiCache from EKS

```
ElastiCache cluster mode uses a configuration endpoint:
  issue-tracker-redis.xyz.cache.amazonaws.com:6379

The Redis client automatically:
  1. Connects to configuration endpoint
  2. Gets the cluster topology (which shards, which nodes)
  3. Routes each key to the correct shard

Application connection string:
  REDIS_URL = "redis://AUTH_TOKEN@ENDPOINT:6379/0"
  
Note: In cluster mode, database selection (DB 0/1/2) doesn't work.
All databases map to the same cluster keyspace.
For production, use different key prefixes instead of DB numbers.
```

---

## RDS Read Replicas (Optional)

For read-heavy workloads, you can add read replicas:

```
Primary DB (writes + some reads)
    │ async replication
    ├──► Read Replica 1 (ap-south-1b) — for reporting queries
    └──► Read Replica 2 (ap-south-1c) — for analytics
```

Not configured in this project (single read workload doesn't need it), but you'd add a `replica_source_db_identifier` in Terraform.

---

## Database Connection Pooling

RDS's `max_connections = 500` is the total across ALL clients. With SQLAlchemy's pool:

```
pool_size=10    → 10 idle connections per pod
max_overflow=5  → up to 5 extra connections under load

With 30 backend pods (HPA max):
  30 × 10 = 300 idle connections
  30 × (10+5) = 450 peak connections
  < 500 limit ✓
```

For production workloads with many pods, consider using **PgBouncer** (a connection pooler) between the app and RDS:

```
EKS pods → PgBouncer (connection pooler) → RDS
  100 pods × 20 connections = 2000 "connections"
  But PgBouncer multiplexes to only 100 real connections to RDS
```

---

## Monitoring RDS and ElastiCache

### CloudWatch Metrics to Watch

```
RDS:
  DatabaseConnections — are you near max_connections?
  CPUUtilization — database is CPU-bound?
  FreeStorageSpace — will the disk fill up?
  ReadIOPS, WriteIOPS — I/O bound?
  ReadLatency, WriteLatency — slow queries?

ElastiCache:
  CurrConnections — how many connections?
  CacheHitRate — cache effectiveness (want >80%)
  Evictions — cache is too small (keys being ejected)
  CPUUtilization — Redis CPU usage
  NetworkBytesIn/Out — network saturation?
```

---

## Further Reading & Videos

- **YouTube**: Search "AWS RDS Tutorial" — AWS official tutorials
- **YouTube**: Search "AWS ElastiCache Redis" — practical setup guides
- **YouTube**: Search "RDS Multi-AZ vs Read Replicas" — key AWS concept
- **Official Docs**: [RDS documentation](https://docs.aws.amazon.com/rds/latest/userguide/)
- **Official Docs**: [ElastiCache documentation](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/)

---

*Next: [Module 08-05 — S3 & ECR: Object Storage & Container Registry](./05-s3-ecr.md)*
