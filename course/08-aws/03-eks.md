# Module 08-03 — EKS: Managed Kubernetes, Node Groups & OIDC

---

## What EKS Provides

AWS EKS manages the Kubernetes control plane. You provide:
- Worker nodes (EC2 instances via Node Groups)
- Your workloads (deployments, services, etc.)

EKS provides:
- API Server (HA, multi-AZ)
- etcd (replicated, automatically backed up)
- Controller Manager + Scheduler
- Kubernetes version upgrades
- Security patches

---

## EKS Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    EKS Cluster: issue-tracker-prod                  │
│                                                                     │
│  Control Plane (AWS managed):                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  API Server (HA)  │  etcd (HA)  │  Controller Manager        │  │
│  │  Endpoints:                                                   │  │
│  │  Public: api.eks.ap-south-1.amazonaws.com (your kubeconfig)  │  │
│  │  Private: internal DNS (for nodes to communicate)            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                          │                                          │
│  Worker Nodes (you manage):                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │ EC2 c6i.xlarge  │  │ EC2 c6i.xlarge  │  │ EC2 c6i.xlarge  │   │
│  │ ap-south-1a     │  │ ap-south-1b     │  │ ap-south-1c     │   │
│  │                 │  │                 │  │                 │   │
│  │ [backend pods]  │  │ [frontend pods] │  │ [nginx pods]    │   │
│  │ [celery pods]   │  │ [backend pods]  │  │ [worker pods]   │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘   │
│                                                                     │
│  Add-ons (installed on cluster):                                    │
│  - AWS Load Balancer Controller (creates ALBs from Ingress)        │
│  - External Secrets Operator (syncs from Secrets Manager)          │
│  - Cluster Autoscaler (scales EC2 node count)                      │
│  - CoreDNS (cluster DNS)                                            │
│  - kube-proxy (network rules)                                       │
│  - Amazon VPC CNI (networking for pods)                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Terraform EKS Module

```hcl
# infra/terraform/modules/eks/main.tf

resource "aws_eks_cluster" "main" {
  name     = var.cluster_name   # "issue-tracker-prod"
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version  # "1.30"
  
  vpc_config {
    # Put control plane in private subnets
    subnet_ids              = var.private_subnet_ids
    endpoint_private_access = true   # Nodes can reach API via private network
    endpoint_public_access  = true   # kubectl can reach API from internet
    
    # Allow kubectl from specific IPs only (optional security enhancement)
    # public_access_cidrs = ["YOUR_IP/32"]
  }
  
  # Enable EKS add-ons
  enabled_cluster_log_types = ["api", "audit", "authenticator"]
  # Logs API calls, audit events, authentication attempts to CloudWatch
}

# Node Group: Managed group of EC2 instances
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "main"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids  # Nodes in private subnets
  
  instance_types = [var.node_instance_type]  # ["c6i.xlarge"]
  
  scaling_config {
    desired_size = 3
    min_size     = 3
    max_size     = 10  # Cluster Autoscaler can scale up to 10 nodes
  }
  
  # Allow in-place node updates
  update_config {
    max_unavailable = 1  # One node can be updated at a time
  }
  
  # Tagging nodes for Cluster Autoscaler discovery
  labels = {
    role = "worker"
  }
}

# OIDC Provider — enables IRSA (IAM Roles for Service Accounts)
data "tls_certificate" "eks" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "eks" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer
}
# This OIDC provider allows Kubernetes Service Accounts
# to assume IAM roles (IRSA - covered in Module 07-04)
```

---

## Why c6i.xlarge?

```
c6i.xlarge specifications:
  - 4 vCPUs
  - 8 GB RAM
  - Network: up to 12.5 Gbps
  - Cost: ~$0.17/hour (~$126/month)

Workload fit:
  Backend (3 replicas): 3 × 500m CPU = 1.5 vCPUs, 3 × 512Mi = 1.5 GB
  Frontend (2 replicas): 2 × 200m = 0.4 vCPUs, 2 × 256Mi = 0.5 GB
  Nginx (2 replicas): 2 × 200m = 0.4 vCPUs, 2 × 128Mi = 0.25 GB
  Celery workers (2 replicas): 2 × 200m = 0.4 vCPUs, 2 × 256Mi = 0.5 GB
  Celery beat (1 replica): 100m, 128Mi
  System pods (CoreDNS, kube-proxy): ~500m, ~512Mi
  
  Total requests per node: ~1.5-2 vCPUs, ~1.5-2 GB
  With 3 nodes: plenty of headroom for HPA scaling
```

---

## Accessing EKS with kubectl

```bash
# Update kubeconfig (sets up credentials for kubectl)
aws eks update-kubeconfig \
  --name issue-tracker-prod \
  --region ap-south-1

# This creates/updates ~/.kube/config
# kubectl now knows how to reach your EKS cluster

# Verify
kubectl get nodes
# NAME                                         STATUS   ROLES
# ip-10-0-10-5.ap-south-1.compute.internal    Ready    <none>
# ip-10-0-11-7.ap-south-1.compute.internal    Ready    <none>
# ip-10-0-12-3.ap-south-1.compute.internal    Ready    <none>
```

How authentication works:
```
kubectl get nodes
  ↓ reads ~/.kube/config
  ↓ executes: aws eks get-token --cluster-name issue-tracker-prod
  ↓ AWS CLI: sts:GetCallerIdentity → signed token
  ↓ kubectl: sends token to EKS API Server
  ↓ EKS: validates token against IAM
  ↓ Returns node list
```

Your AWS IAM identity maps to a Kubernetes RBAC group — the EKS admin role has cluster-admin permissions.

---

## EKS Add-ons

```hcl
# infra/terraform/modules/eks/main.tf

# AWS Load Balancer Controller
# Creates AWS ALBs from Kubernetes Ingress objects
resource "helm_release" "aws_load_balancer_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"
  
  set {
    name  = "clusterName"
    value = var.cluster_name
  }
  
  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.aws_load_balancer_controller.arn
  }
}

# External Secrets Operator
resource "helm_release" "external_secrets" {
  name       = "external-secrets"
  repository = "https://charts.external-secrets.io"
  chart      = "external-secrets"
  namespace  = "external-secrets"
  
  create_namespace = true
}
```

---

## EKS Node AMI — Amazon Machine Image

EKS nodes run a specialized Amazon Linux 2 AMI:
- Pre-configured with containerd (container runtime)
- Pre-configured with kubelet
- Automatically registers with the EKS cluster on boot
- EKS-optimized kernel with performance tuning

```
Node starts:
  1. EC2 launches with EKS-optimized AMI
  2. Bootstrap script runs: /etc/eks/bootstrap.sh
  3. kubelet starts with cluster endpoint and credentials
  4. kubelet registers with EKS API Server
  5. Scheduler can now schedule pods on this node
```

---

## Fargate (Alternative to EC2 Nodes)

AWS also offers EKS Fargate — serverless node management:
```
EC2 nodes (what we use):
  + You choose instance type and size
  + Cost-effective for predictable workloads
  + Faster pod startup (no node boot needed)
  - You manage node upgrades
  - Fixed node capacity (Cluster Autoscaler needed to scale)

Fargate:
  + No node management (AWS manages the "nodes")
  + Pay per pod (not per node)
  + Automatic scaling (AWS provides capacity on demand)
  - More expensive for predictable workloads
  - Slower pod startup (Fargate provisions a new instance per pod)
  - No DaemonSets (special Kubernetes workloads that run on every node)
```

For our workload (stable traffic with predictable scaling), EC2 nodes are more cost-effective.

---

## Further Reading & Videos

- **YouTube**: Search "EKS Tutorial" — TechWorld with Nana or AWS official tutorials
- **YouTube**: Search "Amazon EKS Getting Started" — AWS re:Invent talks are excellent
- **Official Docs**: [EKS documentation](https://docs.aws.amazon.com/eks/latest/userguide/)
- **Official Docs**: [EKS Best Practices Guide](https://aws.github.io/aws-eks-best-practices/) — comprehensive guide

---

*Next: [Module 08-04 — RDS & ElastiCache: Managed PostgreSQL & Redis](./04-rds-elasticache.md)*
