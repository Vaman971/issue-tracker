# Module 07-01 — Kubernetes: Control Plane, etcd, Scheduler & Kubelet

---

## Learning Objectives

After this module you will:
- Understand what Kubernetes is and why it exists
- Know every component of the Kubernetes control plane and what it does
- Understand how a pod is created (from `kubectl apply` to running container)
- Know how EKS manages the control plane for you

---

## What Problem Does Kubernetes Solve?

```
WITHOUT Kubernetes:
  You have 3 servers and 10 containers to run.
  
  Problems:
  - Which container goes on which server?
  - What happens when Server 2 dies? (3 containers suddenly gone)
  - How do you add more containers when traffic spikes?
  - How do you update containers without downtime?
  - How do you route traffic to healthy containers only?
  
  Answer: Someone has to manually handle all of this.

WITH Kubernetes:
  You declare: "I want 3 copies of my backend running at all times"
  Kubernetes handles:
  - Placing them across servers
  - Restarting them if they crash
  - Adding more when CPU is high (HPA)
  - Rolling updates with zero downtime
  - Health checking and traffic routing
  
  Answer: Kubernetes handles all of this automatically.
```

---

## Kubernetes Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         KUBERNETES CLUSTER                              │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      CONTROL PLANE (EKS managed)                │   │
│  │                                                                 │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │   │
│  │  │  API Server  │  │   etcd       │  │   Scheduler          │  │   │
│  │  │              │  │              │  │                      │  │   │
│  │  │  REST API:   │  │  Distributed │  │  Watches for pods    │  │   │
│  │  │  All K8s     │  │  key-value   │  │  with no node        │  │   │
│  │  │  operations  │  │  store       │  │  assigned.           │  │   │
│  │  │  go through  │  │  (cluster    │  │  Picks best node     │  │   │
│  │  │  here        │  │   state)     │  │  based on resources  │  │   │
│  │  └──────┬───────┘  └──────────────┘  └──────────────────────┘  │   │
│  │         │                                                        │   │
│  │  ┌──────▼───────────────────────────────────────────────────┐   │   │
│  │  │           Controller Manager                             │   │   │
│  │  │  Runs control loops that reconcile desired vs actual:    │   │   │
│  │  │  - ReplicaSet controller (maintains pod count)           │   │   │
│  │  │  - Deployment controller (manages rollouts)              │   │   │
│  │  │  - Service controller (syncs endpoints)                  │   │   │
│  │  │  - HPA controller (autoscales pods)                      │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │
│  │   WORKER NODE   │  │   WORKER NODE   │  │   WORKER NODE       │   │
│  │   (EC2 instance)│  │   (EC2 instance)│  │   (EC2 instance)    │   │
│  │                 │  │                 │  │                     │   │
│  │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────────┐  │   │
│  │  │  kubelet  │  │  │  │  kubelet  │  │  │  │   kubelet     │  │   │
│  │  │           │  │  │  │           │  │  │  │               │  │   │
│  │  │  Node     │  │  │  │  Node     │  │  │  │   Node agent  │  │   │
│  │  │  agent    │  │  │  │  agent    │  │  │  │   Runs pods   │  │   │
│  │  └───────────┘  │  │  └───────────┘  │  │  └───────────────┘  │   │
│  │                 │  │                 │  │                     │   │
│  │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────────┐  │   │
│  │  │ kube-proxy│  │  │  │ kube-proxy│  │  │  │  kube-proxy   │  │   │
│  │  │           │  │  │  │           │  │  │  │               │  │   │
│  │  │ Network   │  │  │  │ Network   │  │  │  │  iptables     │  │   │
│  │  │ rules     │  │  │  │ rules     │  │  │  │  rules for    │  │   │
│  │  └───────────┘  │  │  └───────────┘  │  │  │  services     │  │   │
│  │                 │  │                 │  │  └───────────────┘  │   │
│  │  [backend pod]  │  │  [frontend pod] │  │  [nginx pod]        │   │
│  │  [celery pod]   │  │  [backend pod]  │  │  [backend pod]      │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Control Plane Components in Detail

### 1. etcd — The Brain's Memory

etcd is a **distributed key-value store** that is the single source of truth for the entire cluster state.

```
etcd stores EVERYTHING:
  /registry/pods/issue-tracker/backend-xyz123: { spec, status, ... }
  /registry/deployments/issue-tracker/backend: { replicas: 3, image: ... }
  /registry/services/issue-tracker/backend: { clusterIP: 10.96.0.1, ... }
  /registry/configmaps/issue-tracker/app-config: { key: value, ... }

etcd is RAFT-based:
  Typically 3 or 5 etcd nodes (odd number for quorum)
  A write is committed when majority agrees
  
  3 nodes: can tolerate 1 failure
  5 nodes: can tolerate 2 failures
  
  Leader election: if leader dies, remaining nodes elect new leader
  Reads/writes still work as long as majority is alive
```

**If etcd dies, the cluster stops working** (no new pods can be scheduled, no changes accepted). That's why EKS manages etcd with automatic backups and HA.

### 2. API Server — The Gatekeeper

Every operation in Kubernetes goes through the API Server. It's the only component that communicates with etcd.

```
kubectl apply -f deployment.yaml
        │
        ▼
API Server:
  1. Authentication (who are you?)
  2. Authorization (are you allowed to do this?)
  3. Admission Controllers (validate/mutate the request)
  4. Validation (is this valid Kubernetes YAML?)
  5. Write to etcd
  6. Acknowledge the request
```

### 3. Scheduler — The Placement Algorithm

When a pod is created without an assigned node, the Scheduler finds the best node:

```
New pod needs to be placed:
  Requirements: 500m CPU, 512Mi memory

Scheduler evaluates each node:
  Node 1: 2 CPUs, 4GB RAM → 1.5 CPUs free, 2.5GB RAM free → FITS ✓
  Node 2: 2 CPUs, 4GB RAM → 1.8 CPUs free, 0.3GB RAM free → RAM too low ✗
  Node 3: 2 CPUs, 4GB RAM → 1.9 CPUs free, 3GB RAM free → FITS ✓

Scoring (among fitting nodes):
  Node 1: score 72 (less free resources)
  Node 3: score 89 (more free resources, preferred)

Assignment: Pod → Node 3

Scheduling policies considered:
  - Resource availability (CPU, memory, storage)
  - Affinity/anti-affinity rules (must/must-not be near these pods)
  - Topology spread (spread across availability zones)
  - Taints/tolerations (nodes that reject certain pods)
  - Priority class (high-priority pods get scheduled first)
```

### 4. Controller Manager — The Reconciliation Loop

Controllers watch the cluster state and continuously reconcile "desired" vs "actual":

```
Desired state (in etcd):
  Deployment: backend, replicas: 3

Actual state (what's running):
  [backend-abc, backend-def]  ← only 2!

ReplicaSet Controller wakes up:
  "3 desired, 2 actual → need 1 more!"
  Creates a new Pod spec in etcd

Scheduler sees new unscheduled pod
  → Assigns to Node 2

kubelet on Node 2 sees the new pod spec
  → Starts the container

Actual state:
  [backend-abc, backend-def, backend-ghi]  ← 3!

Controller checks again: 3 desired, 3 actual → nothing to do
```

This **control loop** (also called a **reconciliation loop**) runs constantly. If a pod crashes:
```
Actual → [backend-abc, backend-def]  (2)
Desired → 3
Controller → creates new pod → back to 3
```

This is why pods are self-healing — the controller loop automatically repairs deviations.

### 5. kubelet — The Node Agent

kubelet runs on every worker node. It's the bridge between Kubernetes and Docker (or containerd):

```
kubelet watches the API Server for pods assigned to its node

New pod assigned to Node 3:
  kubelet receives spec: { image: "ecr/backend:abc123", resources: {...} }
  
  kubelet → containerd (container runtime):
    "Pull image ecr/backend:abc123"
    "Create container with this spec"
    "Start container"
  
  kubelet monitors container:
    If container exits → restart (based on restartPolicy)
    Run liveness probe → if fails → restart
    Run readiness probe → if fails → remove from Service endpoints
    
  kubelet reports back to API Server:
    Pod status: { phase: Running, conditions: [{ready: true}] }
```

### 6. kube-proxy — Network Rules

kube-proxy maintains network rules on each node for Service routing:

```
Service "backend" has 3 pods: [10.0.1.5, 10.0.1.6, 10.0.1.7]

kube-proxy sets up iptables rules:
  "Traffic to Service ClusterIP 10.96.0.1:8000"
    → randomly route to one of: [10.0.1.5, 10.0.1.6, 10.0.1.7]:8000

When pod 10.0.1.6 goes down:
  Endpoints object updated
  kube-proxy updates iptables rules:
  "Traffic to Service ClusterIP 10.96.0.1:8000"
    → randomly route to one of: [10.0.1.5, 10.0.1.7]:8000
```

---

## What Happens When You Deploy

Let's trace `kubectl apply -f backend/deployment.yaml`:

```
1. kubectl → API Server (HTTPS)
   "Apply this Deployment spec"
   
2. API Server:
   - Authenticate (your AWS IAM identity)
   - Authorize (does your IAM role have permission?)
   - Validate YAML (is this a valid Deployment?)
   - Write Deployment object to etcd
   - Return 200 OK
   
3. Deployment Controller (in Controller Manager):
   - Watches etcd for Deployment changes
   - Sees new Deployment with replicas: 3
   - Creates a ReplicaSet object
   
4. ReplicaSet Controller:
   - Sees ReplicaSet wants 3 pods
   - Creates 3 Pod objects in etcd
   - Pods are in "Pending" state (no node assigned)
   
5. Scheduler:
   - Watches for Pending pods
   - Evaluates 3 pods against all nodes
   - Assigns each pod to a node
   - Updates Pod objects with nodeName
   
6. kubelet on assigned nodes:
   - Watches for pods assigned to its node
   - Pulls Docker image from ECR (if not cached)
   - Creates and starts container
   - Runs health probes
   - Updates Pod status to Running
   
7. Endpoint Controller:
   - Watches for Running, Ready pods
   - Updates Service Endpoints with pod IPs
   
8. kube-proxy on all nodes:
   - Updates iptables rules
   - New pods now receive traffic
   
Total time: ~30-60 seconds
```

---

## EKS — Managed Kubernetes

AWS EKS (Elastic Kubernetes Service) manages the control plane:

```
What AWS manages:
  - API Server (multi-AZ, HA)
  - etcd (replicated, automatic backups)
  - Controller Manager
  - Scheduler
  - Kubernetes version upgrades
  - Control plane security patches

What you manage:
  - Worker nodes (EC2 instances)
  - Your workloads (pods, services, etc.)
  - Node upgrades (when you choose)
```

This means you never have to:
- Set up etcd clusters
- Configure HA for the control plane
- Manually backup etcd
- Handle control plane failures

In this project, the EKS cluster is created by Terraform:
```hcl
# infra/terraform/modules/eks/main.tf

resource "aws_eks_cluster" "main" {
  name     = "${var.cluster_name}"
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version  # "1.30"
  
  vpc_config {
    subnet_ids = var.private_subnet_ids  # Private subnets for security
    endpoint_private_access = true
    endpoint_public_access  = true       # Allow kubectl from internet
  }
}

resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "main"
  instance_types  = [var.node_instance_type]  # c6i.xlarge
  
  scaling_config {
    desired_size = 3
    min_size     = 3
    max_size     = 10  # Cluster autoscaler can add up to 10 nodes
  }
}
```

---

## Kubectl — The Kubernetes CLI

```bash
# View cluster info
kubectl cluster-info

# View all pods in all namespaces
kubectl get pods --all-namespaces

# View pods in our namespace
kubectl get pods -n issue-tracker

# Describe a pod (troubleshooting)
kubectl describe pod backend-xyz123 -n issue-tracker

# View pod logs
kubectl logs backend-xyz123 -n issue-tracker --follow

# Execute command in pod
kubectl exec -it backend-xyz123 -n issue-tracker -- bash

# View all resources
kubectl get all -n issue-tracker

# Apply manifest
kubectl apply -f backend/deployment.yaml

# Delete a pod (will be recreated by ReplicaSet)
kubectl delete pod backend-xyz123 -n issue-tracker
```

---

## Further Reading & Videos

- **YouTube**: Search "Kubernetes Tutorial for Beginners FULL COURSE" — TechWorld with Nana (4 hours, excellent)
- **YouTube**: Search "Kubernetes Architecture Explained" — TechWorld with Nana covers each component
- **YouTube**: Search "EKS Getting Started" — AWS events channel
- **Official Docs**: [Kubernetes documentation](https://kubernetes.io/docs/home/)
- **Interactive**: [Kubernetes by Example](https://kubernetesbyexample.com)

---

*Next: [Module 07-02 — Pods, Deployments, ReplicaSets & Rolling Updates](./02-workloads.md)*
