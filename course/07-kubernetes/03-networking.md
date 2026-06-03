# Module 07-03 — Kubernetes Services, Ingress, DNS & Load Balancing

---

## Learning Objectives

After this module you will:
- Understand why Services exist (pods have ephemeral IPs)
- Know the difference between ClusterIP, NodePort, and LoadBalancer services
- Understand how Ingress routes traffic
- See how the AWS ALB Ingress Controller works with EKS

---

## The Pod IP Problem

Pods are ephemeral — they start and die constantly. Each gets a new IP address:

```
Day 1:
  backend-pod-abc → IP: 10.0.1.15
  backend-pod-def → IP: 10.0.1.16

Day 2: pod-abc crashes, new pod starts:
  backend-pod-ghi → IP: 10.0.1.22  (NEW IP!)
  backend-pod-def → IP: 10.0.1.16  (same)

Question: How does nginx know where to send traffic?
  It can't hardcode 10.0.1.15 — that pod is gone!
```

**Solution: Services**. A Service gets a stable virtual IP (ClusterIP) and automatically routes to healthy pods.

---

## Service Types

### ClusterIP (Internal Only)

```yaml
# infra/kubernetes/backend/service.yaml

apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: issue-tracker
spec:
  type: ClusterIP  # Only accessible within the cluster
  
  # Match all pods with this label
  selector:
    app: backend
  
  ports:
    - port: 8000       # Port on the Service
      targetPort: 8000 # Port on the pod
```

```
ClusterIP Service created:
  Service "backend" gets stable IP: 10.96.0.1

kube-proxy creates iptables rules:
  "Traffic to 10.96.0.1:8000 → randomly route to pod IPs"

When nginx sends to "backend:8000":
  DNS resolves "backend" → 10.96.0.1
  iptables catches → routes to a backend pod

When pod-abc dies, new pod pod-ghi starts:
  Endpoints controller: updates backend Service endpoints
  Service now points to [pod-def, pod-ghi]
  Traffic automatically goes to healthy pods
```

### LoadBalancer (External)

```yaml
# infra/kubernetes/nginx/service.yaml

apiVersion: v1
kind: Service
metadata:
  name: nginx
  namespace: issue-tracker
  annotations:
    # Tell AWS to create an ALB (Application Load Balancer)
    service.beta.kubernetes.io/aws-load-balancer-type: "alb"
spec:
  type: LoadBalancer
  selector:
    app: nginx
  ports:
    - port: 80
      targetPort: 80
```

When Kubernetes sees a LoadBalancer service:
- In AWS (EKS): creates an AWS ELB/ALB automatically
- The ALB gets a public DNS name (e.g., `abc123.ap-south-1.elb.amazonaws.com`)
- Traffic: Internet → ALB → Nginx pods

In this project, we actually use **Ingress** instead (more powerful), but the nginx Service still uses LoadBalancer type to get an AWS ALB.

---

## Kubernetes DNS — How Service Discovery Works

Every Service gets a DNS entry in the cluster:

```
Format: <service-name>.<namespace>.svc.cluster.local

Our services:
  backend.issue-tracker.svc.cluster.local → 10.96.0.1
  frontend.issue-tracker.svc.cluster.local → 10.96.0.2
  nginx.issue-tracker.svc.cluster.local → 10.96.0.3

Short forms also work within the same namespace:
  backend → 10.96.0.1  (nginx can reach backend with just "backend")
  frontend → 10.96.0.2
```

CoreDNS runs in the cluster and handles all DNS lookups. When nginx sends a request to `backend:8000`, CoreDNS resolves "backend" to the Service's ClusterIP.

---

## The Ingress — Advanced Routing

An Ingress is a higher-level abstraction for HTTP routing. Instead of one LoadBalancer per service, you have one Ingress with rules:

```yaml
# infra/kubernetes/ingress/ingress.yaml

apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: main-ingress
  namespace: issue-tracker
  annotations:
    # Use AWS ALB Ingress Controller
    kubernetes.io/ingress.class: "alb"
    
    # Internet-facing (not internal)
    alb.ingress.kubernetes.io/scheme: "internet-facing"
    
    # Route to pod IPs directly (not node IPs)
    alb.ingress.kubernetes.io/target-type: "ip"
    
    # HTTPS certificate (ACM cert for your domain)
    alb.ingress.kubernetes.io/certificate-arn: "arn:aws:acm:..."
    
    # Health check for ALB
    alb.ingress.kubernetes.io/healthcheck-path: "/"
    alb.ingress.kubernetes.io/healthcheck-interval-seconds: "15"
    alb.ingress.kubernetes.io/healthy-threshold-count: "2"
    alb.ingress.kubernetes.io/unhealthy-threshold-count: "3"
    
    # Load balancing algorithm
    alb.ingress.kubernetes.io/load-balancer-attributes: >
      routing.http2.enabled=true,
      idle_timeout.timeout_seconds=60,
      deregistration_delay.timeout_seconds=30,
      slow_start.duration_seconds=30
spec:
  rules:
    - host: yourdomain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: nginx    # Send all traffic to nginx service
                port:
                  number: 80
```

---

## AWS ALB Ingress Controller

The ALB Ingress Controller is a Kubernetes controller that watches Ingress objects and creates/configures AWS ALBs:

```
You apply ingress.yaml
        │
        ▼
ALB Ingress Controller (pod in kube-system namespace):
  Watches for Ingress objects
  Sees new Ingress → calls AWS APIs:
    - Creates ALB
    - Creates Target Group (pointing to nginx pod IPs)
    - Creates Listener (port 443 HTTPS)
    - Creates HTTPS redirect rule (80 → 443)
    - Attaches SSL certificate from ACM
        │
        ▼
AWS creates ALB:
  DNS: abc123.ap-south-1.elb.amazonaws.com
        │
        ▼
Add DNS record in Route53:
  yourdomain.com ALIAS → abc123.ap-south-1.elb.amazonaws.com
        │
        ▼
Users access: https://yourdomain.com
  → Route53 resolves to ALB IP
  → ALB sends to nginx pods
  → nginx routes to backend or frontend
```

---

## The Complete Traffic Flow

```
User types: https://yourdomain.com/api/projects

1. DNS: yourdomain.com → ALB IP (via Route53 ALIAS record)

2. ALB: HTTPS request received
   - TLS termination (decrypts HTTPS)
   - Health check: is target group healthy?
   - Forward to nginx pod (round-robin across nginx pods)

3. Nginx pod:
   - Receives HTTP request (ALB handles TLS)
   - URL starts with /api/ → proxy to backend:8000
   - Strips /api/ prefix
   - Sets X-Real-IP, X-Forwarded-For headers

4. Backend Service (ClusterIP):
   - Nginx sends to "backend:8000"
   - DNS resolves to Service ClusterIP
   - kube-proxy routes to one of [pod1, pod2, pod3]

5. Backend pod:
   - FastAPI handles request
   - Queries PostgreSQL (RDS)
   - Returns JSON response

6. Response flows back:
   Backend pod → Service → Nginx pod → ALB → User
```

---

## Services in This Project

```
Service            Type          Exposed          Port
──────────────────────────────────────────────────────
backend            ClusterIP     Internal only    8000
frontend           ClusterIP     Internal only    3000
nginx              LoadBalancer  Internet (ALB)   80
celery-worker      ClusterIP     Internal only    N/A
```

Nginx is the ONLY service exposed to the internet. All other services are internal.

---

## Network Policies (Security)

Although not explicitly configured in this project's manifests, Kubernetes supports NetworkPolicies to control pod-to-pod traffic:

```yaml
# Example: backend pods can only talk to postgres and redis
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-policy
spec:
  podSelector:
    matchLabels:
      app: backend
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: postgres
      ports:
        - port: 5432
    - to:
        - podSelector:
            matchLabels:
              app: redis
      ports:
        - port: 6379
```

In production, this adds defense-in-depth — even if the backend is compromised, it can't reach the user database or other services it shouldn't.

---

## External DNS (Optional Enhancement)

EKS can automatically update Route53 DNS records when your Ingress gets an ALB:

```
Without External DNS:
  You manually create Route53 ALIAS record pointing to ALB DNS name
  If ALB changes → you manually update Route53

With External DNS:
  Controller watches Ingress objects for host annotations
  Automatically creates/updates Route53 ALIAS records
  ALB changes → Route53 updated automatically
```

---

## Further Reading & Videos

- **YouTube**: Search "Kubernetes Services Explained ClusterIP NodePort LoadBalancer" — TechWorld with Nana
- **YouTube**: Search "Kubernetes Ingress Explained" — 
- **YouTube**: Search "AWS ALB Ingress Controller EKS" — AWS containers channel
- **Official Docs**: [Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/)
- **Official Docs**: [Kubernetes Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- **AWS Docs**: [AWS Load Balancer Controller](https://docs.aws.amazon.com/eks/latest/userguide/aws-load-balancer-controller.html)

---

*Next: [Module 07-04 — ConfigMaps, Secrets & External Secrets Operator](./04-configuration.md)*
