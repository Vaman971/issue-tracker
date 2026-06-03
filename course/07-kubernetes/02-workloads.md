# Module 07-02 — Pods, Deployments, ReplicaSets & Rolling Updates

---

## Learning Objectives

After this module you will:
- Understand the Kubernetes workload hierarchy (Pod → ReplicaSet → Deployment)
- Read and understand the actual deployment manifests in this project
- Know how rolling updates work and why they prevent downtime
- Understand health probes (liveness + readiness)

---

## Pod — The Basic Unit

A Pod is the smallest deployable unit in Kubernetes. It wraps one or more containers.

```yaml
# The simplest possible pod:
apiVersion: v1
kind: Pod
metadata:
  name: backend-pod
spec:
  containers:
    - name: backend
      image: 123456.dkr.ecr.ap-south-1.amazonaws.com/issue-tracker-backend:abc123
      ports:
        - containerPort: 8000
```

**You almost never create pods directly**. Pods are ephemeral — when they die, they're gone. Use Deployments which manage pod lifecycle.

---

## ReplicaSet — Maintaining Multiple Copies

A ReplicaSet ensures N copies of a pod are always running:

```yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: backend-rs
spec:
  replicas: 3  # Always maintain exactly 3 pods
  selector:
    matchLabels:
      app: backend  # Manages pods with this label
  template:
    # Pod template — what each pod looks like
    metadata:
      labels:
        app: backend
    spec:
      containers:
        - name: backend
          image: issue-tracker-backend:abc123
```

**You almost never create ReplicaSets directly either**. Use Deployments which manage ReplicaSets.

---

## Deployment — The Right Abstraction

A Deployment manages ReplicaSets and enables rolling updates:

```
Deployment
    │
    ├── ReplicaSet v1 (replicas: 0)   ← old version, scaled down
    │   ├── Pod (terminated)
    │   └── Pod (terminated)
    │
    └── ReplicaSet v2 (replicas: 3)   ← new version, scaled up
        ├── Pod (running)
        ├── Pod (running)
        └── Pod (running)
```

---

## The Backend Deployment

```yaml
# infra/kubernetes/backend/deployment.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: issue-tracker
  labels:
    app: backend
spec:
  # Start with 3 replicas (HPA will auto-scale from here)
  replicas: 3
  
  # How to find which pods belong to this Deployment
  selector:
    matchLabels:
      app: backend
  
  # Rolling update strategy
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2       # Create at most 2 new pods at once
      maxUnavailable: 1 # At most 1 old pod can be unavailable during update
  
  template:
    metadata:
      labels:
        app: backend
    spec:
      # Use service account for AWS IAM access (S3, Secrets Manager)
      serviceAccountName: backend-sa
      
      containers:
        - name: backend
          # Image updated by GitHub Actions deploy step
          image: 123456789.dkr.ecr.ap-south-1.amazonaws.com/issue-tracker-backend:latest
          
          ports:
            - containerPort: 8000
          
          # Load all config from ConfigMap and Secret
          envFrom:
            - configMapRef:
                name: app-config    # Non-sensitive config (APP_ENV, WEB_CONCURRENCY)
            - secretRef:
                name: app-secrets   # Sensitive config (DB password, JWT secret)
          
          # Resource requests and limits
          resources:
            requests:
              # Kubernetes reserves this much on the node for this container
              cpu: "500m"       # 0.5 CPU cores
              memory: "512Mi"   # 512 megabytes RAM
            limits:
              # Container cannot exceed these
              cpu: "2000m"      # 2 CPU cores
              memory: "2Gi"     # 2 gigabytes RAM
          
          # LIVENESS PROBE: Is the container alive?
          # If this fails → Kubernetes KILLS and RESTARTS the container
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8000
            initialDelaySeconds: 30   # Wait 30s after start before first check
            periodSeconds: 10          # Check every 10 seconds
            failureThreshold: 3        # Restart after 3 consecutive failures
          
          # READINESS PROBE: Is the container ready to receive traffic?
          # If this fails → Kubernetes removes pod from Service endpoints
          # Pod stays running but doesn't receive traffic until ready
          readinessProbe:
            httpGet:
              path: /health/ready   # Checks DB + Redis connectivity
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 5
            failureThreshold: 3
      
      # Spread pods across availability zones
      topologySpreadConstraints:
        - maxSkew: 1           # At most 1 more pod in one zone than another
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: backend
      
      # Graceful shutdown: allow 60s for in-flight requests to complete
      terminationGracePeriodSeconds: 60
```

---

## Health Probes in Detail

```python
# backend/app/main.py

@app.get("/health/live")
async def liveness():
    """
    Liveness probe: "Is the process alive?"
    Should ALWAYS return 200 if the process is running.
    Only fails if the process is truly stuck/deadlocked.
    Kubernetes will RESTART the container if this fails.
    """
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness():
    """
    Readiness probe: "Is this container ready to serve traffic?"
    Checks dependencies are reachable.
    Kubernetes removes pod from load balancer if this fails.
    Pod is NOT killed — stays running but gets no traffic.
    """
    # Check database connection
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(select(1))  # Simple test query
    except Exception:
        raise HTTPException(503, "Database unavailable")
    
    # Check Redis connection
    if not await check_redis_connection():
        raise HTTPException(503, "Redis unavailable")
    
    return {"status": "ready"}
```

### Why Two Probes?

```
Scenario: Database temporarily unreachable

Liveness probe (only checks process is alive):
  → backend process is alive → returns 200
  → Kubernetes: "OK, don't restart it"

Readiness probe (checks dependencies):
  → can't reach database → returns 503
  → Kubernetes: "Remove from service endpoints"
  → No new traffic sent to this pod
  → Other pods (that can reach DB) still serve traffic

When DB recovers:
  → Readiness probe succeeds again
  → Kubernetes: "Add back to service endpoints"
  → Pod starts receiving traffic again

WITHOUT separate probes:
  Database down → ALL pods fail readiness → Kubernetes kills them all
  → All pods restart → All hit same DB issue → Restart loop!
```

---

## Rolling Update — Zero-Downtime Deployment

```
Before update: 3 pods running backend:v1
  [pod-v1-a] [pod-v1-b] [pod-v1-c]  ← all serving traffic

kubectl set image deployment/backend backend=backend:v2

Kubernetes rolling update begins:

Step 1: Create 2 new pods (maxSurge: 2)
  [pod-v1-a] [pod-v1-b] [pod-v1-c]  ← old, still serving
  [pod-v2-x] [pod-v2-y]              ← new, starting up

Step 2: Wait for new pods to be Ready
  New pods pass readiness probe
  Service endpoints updated: now includes v2 pods

Step 3: Terminate 1 old pod (maxUnavailable: 1)
  [pod-v1-b] [pod-v1-c]  ← old (2 remaining)
  [pod-v2-x] [pod-v2-y]  ← new (2 running)
  Traffic spread across all 4 pods

Step 4: Create more v2 pods until replicas: 3
  [pod-v1-c]              ← last old pod
  [pod-v2-x] [pod-v2-y] [pod-v2-z]  ← 3 new pods

Step 5: Terminate last old pod
  [pod-v2-x] [pod-v2-y] [pod-v2-z]  ← all v2, update complete

During the entire update:
  ✓ At least 2 pods always serving traffic
  ✓ Zero downtime for users
  ✗ Briefly, both v1 and v2 pods serve traffic (OK for most updates)
```

### If the New Version Is Broken

```
New pods fail their readiness probe
  → Kubernetes stops the rolling update
  → Old pods remain (still 3 old pods serving traffic)
  
kubectl rollout undo deployment/backend
  → Kubernetes rolls back to previous ReplicaSet (v1)
  → No downtime
```

---

## Frontend and Nginx Deployments

```yaml
# infra/kubernetes/frontend/deployment.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: issue-tracker
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2
      maxUnavailable: 0  # Never have fewer than 2 pods (zero unavailability)
  template:
    spec:
      containers:
        - name: frontend
          image: 123456.dkr.ecr.ap-south-1.amazonaws.com/issue-tracker-frontend:latest
          ports:
            - containerPort: 3000
          resources:
            requests:
              cpu: "200m"
              memory: "256Mi"
            limits:
              cpu: "1000m"
              memory: "1Gi"
          livenessProbe:
            httpGet:
              path: /
              port: 3000
            initialDelaySeconds: 20
          readinessProbe:
            httpGet:
              path: /
              port: 3000
            initialDelaySeconds: 15
      terminationGracePeriodSeconds: 30
```

```yaml
# infra/kubernetes/nginx/deployment.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
  namespace: issue-tracker
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: nginx
          image: nginx:1.27-alpine
          ports:
            - containerPort: 80
          volumeMounts:
            - name: nginx-config
              mountPath: /etc/nginx/nginx.conf
              subPath: nginx.conf
          resources:
            requests:
              cpu: "200m"
              memory: "128Mi"
            limits:
              cpu: "1000m"
              memory: "512Mi"
          
          # IMPORTANT: nginx health check is independent of backend/frontend
          # We check nginx itself, not whether backends are reachable
          livenessProbe:
            httpGet:
              path: /nginx-health    # Returns 200 if nginx process is alive
              port: 80
            initialDelaySeconds: 5
          readinessProbe:
            httpGet:
              path: /nginx-health
              port: 80
            initialDelaySeconds: 5
      
      volumes:
        - name: nginx-config
          configMap:
            name: nginx-config  # Nginx config stored in ConfigMap
```

---

## Celery Deployments

```yaml
# infra/kubernetes/celery/worker-deployment.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-worker
  namespace: issue-tracker
spec:
  replicas: 2  # HPA scales this 2-15
  template:
    spec:
      containers:
        - name: celery-worker
          image: 123456.dkr.ecr.ap-south-1.amazonaws.com/issue-tracker-backend:latest
          command:
            - celery
            - -A
            - app.worker.celery_app
            - worker
            - --loglevel=info
            - --concurrency=2    # 2 parallel task executions per pod
            - -Q
            - default,email,notifications
          resources:
            requests:
              cpu: "200m"
              memory: "256Mi"
            limits:
              cpu: "1000m"
              memory: "1Gi"
```

```yaml
# infra/kubernetes/celery/beat-deployment.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-beat
  namespace: issue-tracker
spec:
  replicas: 1  # ALWAYS exactly 1
  
  # Recreate: kill old pod BEFORE starting new one
  # Prevents two Beat schedulers running simultaneously
  strategy:
    type: Recreate
  
  template:
    spec:
      containers:
        - name: celery-beat
          image: 123456.dkr.ecr.ap-south-1.amazonaws.com/issue-tracker-backend:latest
          command:
            - celery
            - -A
            - app.worker.celery_app
            - beat
            - --loglevel=info
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
```

---

## Namespace — Logical Isolation

All our resources are in the `issue-tracker` namespace:

```yaml
# infra/kubernetes/namespace.yaml

apiVersion: v1
kind: Namespace
metadata:
  name: issue-tracker
  labels:
    name: issue-tracker
```

Namespaces provide logical isolation within a cluster:
```
- Development team can have their own namespace
- Staging and production can share a cluster (different namespaces)
- Resource quotas can be set per namespace
- RBAC permissions can be namespace-scoped

This project uses one namespace for all components:
  issue-tracker: backend, frontend, nginx, celery, etc.
```

---

## The Pre-Deployment Migration Job

```yaml
# infra/kubernetes/jobs/migrate-job.yaml

apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate-${IMAGE_TAG}  # Unique name prevents duplicate runs
  namespace: issue-tracker
spec:
  backoffLimit: 3  # Retry up to 3 times
  activeDeadlineSeconds: 300  # Must finish within 5 minutes
  
  template:
    spec:
      restartPolicy: OnFailure  # Retry on failure, don't restart on success
      
      containers:
        - name: migrate
          image: 123456.dkr.ecr.ap-south-1.amazonaws.com/issue-tracker-backend:latest
          command: ["/bin/sh", "-c", "/app/scripts/migrate.sh"]
          envFrom:
            - configMapRef:
                name: app-config
            - secretRef:
                name: app-secrets
```

In the CI/CD pipeline:
```bash
# Apply migration job
kubectl apply -f infra/kubernetes/jobs/migrate-job.yaml

# Wait for job to complete (fail fast if migration fails)
kubectl wait --for=condition=complete \
  job/db-migrate-${IMAGE_TAG} \
  --timeout=300s \
  -n issue-tracker

# Only if migration succeeded → deploy new pods
kubectl set image deployment/backend backend=${NEW_IMAGE}
```

---

## Further Reading & Videos

- **YouTube**: Search "Kubernetes Deployments Rolling Updates" — TechWorld with Nana
- **YouTube**: Search "Kubernetes Liveness Readiness Startup Probes" — clear explanation of all three probe types
- **Official Docs**: [Kubernetes Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- **Official Docs**: [Configure liveness, readiness probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)

---

*Next: [Module 07-03 — Services, Ingress & Load Balancing](./03-networking.md)*
