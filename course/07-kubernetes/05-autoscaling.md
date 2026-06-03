# Module 07-05 — HPA, PDB, Topology Spread & Resource Management

---

## Learning Objectives

After this module you will:
- Understand Horizontal Pod Autoscaler (HPA) and how it scales pods
- Know Pod Disruption Budgets (PDB) for availability during maintenance
- Understand topology spread constraints for high availability
- See the complete autoscaling configuration for this project

---

## Horizontal Pod Autoscaler (HPA)

HPA automatically scales the number of pod replicas based on metrics (CPU, memory, or custom metrics).

```
Without HPA:
  You manually set replicas: 3
  Traffic doubles → pods are overwhelmed → app is slow
  Traffic drops → 3 idle pods wasting money
  You must manually intervene

With HPA:
  replicas: 3 is the starting point
  Traffic doubles → HPA detects CPU > 60% → scales to 5, 7, 10 pods
  Traffic drops → HPA detects CPU < 30% → scales back to 3, 4 pods
  Happens automatically, within minutes
```

---

## HPA Internals

```
┌─────────────────────────────────────────────────────────────────┐
│                    HPA Control Loop                             │
│                    (runs every 15 seconds)                      │
│                                                                 │
│  1. Query metrics-server for current CPU/memory usage           │
│                                                                 │
│  2. Calculate desired replicas:                                 │
│     desired = ceil(current_replicas × current_metric/target)   │
│                                                                 │
│     Example:                                                    │
│     current_replicas = 3                                        │
│     current_CPU = 90% (each pod)                                │
│     target_CPU = 60%                                            │
│     desired = ceil(3 × 90/60) = ceil(4.5) = 5                  │
│                                                                 │
│  3. Scale if needed (within min/max bounds)                     │
│     min: 3 pods  max: 30 pods                                   │
│                                                                 │
│  4. Stabilization window (prevents flapping):                   │
│     Scale UP: immediate                                         │
│     Scale DOWN: wait 300s before reducing                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## HPA Configuration for This Project

```yaml
# infra/kubernetes/backend/hpa.yaml

apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
  namespace: issue-tracker
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  
  minReplicas: 3   # Never go below 3
  maxReplicas: 30  # Never go above 30
  
  metrics:
    # Scale based on average CPU utilization
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60  # Scale when avg CPU > 60%
    
    # Also scale based on memory
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 75  # Scale when avg memory > 75%
  
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0  # Scale up immediately
      policies:
        - type: Pods
          value: 5           # Add at most 5 pods at once
          periodSeconds: 60  # Per 60-second window
    
    scaleDown:
      stabilizationWindowSeconds: 300  # Wait 5 min before scaling down
      policies:
        - type: Pods
          value: 2           # Remove at most 2 pods at once
          periodSeconds: 60
```

### Why Different Scale-Up vs Scale-Down Behavior?

```
Scale up FAST (stabilizationWindowSeconds: 0):
  Traffic spike happens NOW → need more capacity NOW
  Adding pods takes ~60 seconds → respond immediately
  Cost of too many pods: slightly higher AWS bill

Scale down SLOW (stabilizationWindowSeconds: 300):
  Traffic spike ends → wait 5 minutes before removing pods
  Why? Traffic might spike again in the next few minutes
  Removing pods and re-adding is wasteful
  Also: prevents "flapping" (constant scale up/down cycles)
```

---

## HPA for Other Components

```yaml
# infra/kubernetes/frontend/hpa.yaml
spec:
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70

# infra/kubernetes/celery/worker-hpa.yaml
spec:
  minReplicas: 2
  maxReplicas: 15
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
  # Workers scale up when CPU is high (tasks are CPU-intensive)
  # Workers scale down when queue is empty
```

**Celery Beat has NO HPA** — it always runs as exactly 1 replica. Scaling Beat would cause duplicate scheduled task execution.

---

## How HPA Works with requests and limits

HPA calculates utilization as a percentage of the **request**:

```yaml
resources:
  requests:
    cpu: "500m"   # 0.5 CPU cores reserved
  limits:
    cpu: "2000m"  # 2 CPU cores max
```

```
If the pod is using 400m CPU:
  400m / 500m (request) = 80% utilization
  → 80% > 60% target → HPA triggers scale up

NOT: 400m / 2000m = 20% (that would be relative to limit)

This is why requests must be set correctly!
If requests are too low, HPA triggers too early.
If requests are too high, HPA triggers too late.
```

**Right-sizing requests**: In production, look at actual pod CPU/memory usage in CloudWatch or Prometheus, then set requests at ~75% of average usage.

---

## Pod Disruption Budget (PDB)

PDB ensures a minimum number of pods are always running during **voluntary disruptions**:
- Node upgrades (AWS EKS node group update)
- Manual node draining
- Cluster autoscaler removing a node

```yaml
# infra/kubernetes/backend/pdb.yaml

apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: backend-pdb
  namespace: issue-tracker
spec:
  # "At least 2 backend pods must be available at all times"
  minAvailable: 2
  selector:
    matchLabels:
      app: backend
```

```
Scenario: AWS upgrades a node (voluntary disruption)
  Node has: [backend-a, backend-b, frontend-a]
  
  Without PDB:
    AWS drains node → all 3 pods evicted simultaneously
    Briefly: 0 backend pods → downtime!
  
  With PDB (minAvailable: 2):
    AWS tries to evict backend-a
    PDB check: "currently 3 pods, 3-1=2 ≥ 2 (minAvailable) → OK"
    backend-a evicted, rescheduled on another node
    
    AWS tries to evict backend-b
    PDB check: "currently 2 pods (backend-c already started), 2-1=1 < 2 → BLOCKED"
    Eviction denied! Backend-c must become ready first.
    
    Backend-c becomes ready (3 pods again)
    backend-b evicted → rescheduled → 3 pods total
    
    Zero downtime during node upgrade!
```

---

## Topology Spread Constraints

Ensures pods are distributed across availability zones:

```yaml
# In backend deployment.yaml:
topologySpreadConstraints:
  - maxSkew: 1  # At most 1 more pod in one zone than another
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule
    labelSelector:
      matchLabels:
        app: backend
```

```
AWS region: ap-south-1
Availability zones: ap-south-1a, ap-south-1b, ap-south-1c

Without topology spread:
  Scheduler might put all 3 pods on ap-south-1a
  ap-south-1a data center fails → ALL backend pods gone → downtime!

With topology spread (maxSkew: 1):
  ap-south-1a: 1 pod
  ap-south-1b: 1 pod
  ap-south-1c: 1 pod
  
  ap-south-1a data center fails:
  → 1 pod gone, 2 pods still running on 1b and 1c
  → HPA kicks in, adds pods to 1b and 1c
  → App continues serving traffic!

maxSkew: 1 means:
  "The pod count difference between any two zones must be ≤ 1"
  With 6 pods: 2-2-2 or 2-2-1 are OK
  With 6 pods: 6-0-0 is NOT OK (skew = 6, which is > 1)
```

---

## Cluster Autoscaler — Scaling Nodes

HPA scales pods. Cluster Autoscaler (CA) scales **nodes** (EC2 instances):

```
HPA says: "Need 15 backend pods"
Scheduler: "I can only place 8 pods — not enough node capacity!"
Scheduler: "5 pods are Pending (unschedulable)"

Cluster Autoscaler:
  Watches for pending pods
  "7 pods can't be scheduled → need more nodes"
  Calls AWS API: add 2 more EC2 instances to the node group
  
  EC2 instances start up (~3 minutes)
  kubelet registers with API server
  Scheduler places pending pods on new nodes
  
Cluster Autoscaler scale down:
  Nodes with utilization < 50% for 10 minutes
  Are all pods on that node reschedulable to other nodes?
  If yes → drain node → terminate EC2 → save money
```

```hcl
# infra/terraform/modules/eks/main.tf
resource "aws_eks_node_group" "main" {
  scaling_config {
    desired_size = 3
    min_size     = 3    # Never fewer than 3 nodes
    max_size     = 10   # Never more than 10 nodes
  }
}
```

---

## Resource Right-Sizing Guidelines

```
Setting requests and limits is an art. Here's a starting guide:

Backend (FastAPI + Gunicorn):
  requests.cpu: 500m (0.5 cores) — typical idle CPU
  limits.cpu: 2000m (2 cores) — max under load
  requests.memory: 512Mi — RSS memory (actual resident set)
  limits.memory: 2Gi — max before OOM kill

Frontend (Next.js):
  requests.cpu: 200m — Next.js is mostly I/O
  limits.cpu: 1000m
  requests.memory: 256Mi — Node.js heap
  limits.memory: 1Gi

Celery Worker:
  requests.cpu: 200m — depends on task CPU intensity
  limits.cpu: 1000m
  requests.memory: 256Mi
  limits.memory: 1Gi

Celery Beat (scheduler only):
  requests.cpu: 100m — very low, just scheduling
  limits.cpu: 500m
  requests.memory: 128Mi
  limits.memory: 512Mi
```

### Memory OOM Kill

If a container exceeds its memory limit, the Linux kernel kills it (OOM = Out of Memory):

```
Container using 1.8Gi memory (approaching 2Gi limit):
  Memory limit exceeded → kernel sends SIGKILL
  Container dies immediately (no graceful shutdown)
  Kubernetes sees: "container exited with code 137 (OOM kill)"
  Kubernetes restarts the container

This appears as:
  kubectl describe pod backend-xyz
  State: Terminated
  Reason: OOMKilled
  
Solution:
  Increase memory limit
  OR: Find memory leak in application code
```

---

## Resource Quotas (Optional Enforcement)

You can enforce resource limits at the namespace level:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: issue-tracker-quota
  namespace: issue-tracker
spec:
  hard:
    # Total CPU across all pods in namespace
    requests.cpu: "10"      # 10 cores max requested
    limits.cpu: "40"        # 40 cores max limited
    
    # Total memory
    requests.memory: 20Gi
    limits.memory: 80Gi
    
    # Max pods
    pods: "100"
```

This prevents one team's namespace from consuming all cluster resources.

---

## Further Reading & Videos

- **YouTube**: Search "Kubernetes HPA Horizontal Pod Autoscaler" — TechWorld with Nana
- **YouTube**: Search "Kubernetes Resource Management CPU Memory" — practical guidance
- **YouTube**: Search "Kubernetes Pod Disruption Budget" — for production reliability
- **Official Docs**: [HPA documentation](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- **Official Docs**: [PDB documentation](https://kubernetes.io/docs/tasks/run-application/configure-pdb/)
- **Official Docs**: [Topology spread constraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)

---

*Next: [Module 08-01 — AWS Fundamentals](../08-aws/01-aws-fundamentals.md)*
