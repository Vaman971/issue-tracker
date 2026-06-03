# Module 08-06 — ALB & Secrets Manager: Load Balancing & Secret Storage

---

## AWS ALB — Application Load Balancer

ALB is a Layer 7 (HTTP/HTTPS) load balancer. It understands HTTP and can route based on URL paths, headers, and host names.

```
ALB capabilities:
  - HTTPS termination (handles TLS, so your app doesn't need to)
  - Path-based routing (/api/* → backend, /* → frontend)
  - Host-based routing (api.yourdomain.com vs app.yourdomain.com)
  - Health checks (only send traffic to healthy targets)
  - Target groups (logical group of servers/pods to distribute to)
  - WebSocket support
  - HTTP/2 support
  - Access logs (log every request to S3)
  - WAF integration (Web Application Firewall)
```

### ALB Architecture in This Project

```
Internet
    │
    ▼ HTTPS (443)
┌─────────────────────────────────────────────────────────────────────┐
│                        AWS ALB                                      │
│  DNS: abc123.ap-south-1.elb.amazonaws.com                          │
│                                                                     │
│  Listeners:                                                         │
│    Port 80 HTTP:  Redirect → HTTPS 301                             │
│    Port 443 HTTPS: ACM certificate                                  │
│                                                                     │
│  Target Group: nginx-tg                                             │
│    Target type: ip (pod IPs, not node IPs)                         │
│    Targets: [nginx-pod-1-ip, nginx-pod-2-ip]                       │
│    Health check: GET / returns 200?                                 │
│    Algorithm: Round Robin                                           │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼ HTTP (decrypted)
nginx pods (2 replicas)
```

### Why ALB Instead of NLB?

```
ALB (Application Load Balancer) — Layer 7:
  ✓ Understands HTTP/HTTPS
  ✓ Path-based routing
  ✓ Can set HTTP headers
  ✓ WebSocket support
  ✓ Certificates from ACM
  Use for: web applications, APIs
  Cost: higher

NLB (Network Load Balancer) — Layer 4 (TCP):
  ✓ Extremely high throughput (millions of requests/second)
  ✓ Fixed IP address (useful for whitelisting)
  ✓ Ultra-low latency
  ✗ No HTTP routing capabilities
  Use for: gaming, IoT, ultra-high throughput
  Cost: lower
```

### SSL Certificate with ACM

```
AWS Certificate Manager (ACM) provides FREE SSL certificates:

1. Request certificate in ACM:
   domain: yourdomain.com
   method: DNS validation (add CNAME record to Route53)

2. ACM validates you own the domain

3. Certificate issued, attached to ALB listener

4. ACM automatically renews 60 days before expiry (zero maintenance!)

5. Users see the padlock 🔒 in browser

Result: HTTPS for free, with automatic renewal
```

### ALB Configuration via Ingress Annotations

```yaml
# infra/kubernetes/ingress/ingress.yaml

annotations:
  # Connection settings
  alb.ingress.kubernetes.io/load-balancer-attributes: |
    routing.http2.enabled=true,
    idle_timeout.timeout_seconds=60,
    deletion_protection.enabled=true,
    access_logs.s3.enabled=true,
    access_logs.s3.bucket=my-alb-logs-bucket,
    deregistration_delay.timeout_seconds=30,
    slow_start.duration_seconds=30
  
  # Health check settings
  alb.ingress.kubernetes.io/healthcheck-path: "/"
  alb.ingress.kubernetes.io/healthcheck-interval-seconds: "15"
  alb.ingress.kubernetes.io/healthy-threshold-count: "2"
  alb.ingress.kubernetes.io/unhealthy-threshold-count: "3"
  
  # Use HTTPS (with ACM certificate)
  alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS": 443}]'
  alb.ingress.kubernetes.io/ssl-redirect: "443"
  alb.ingress.kubernetes.io/certificate-arn: "arn:aws:acm:ap-south-1:123456:certificate/..."
```

**Deregistration delay (30s)**: When a pod is removed (e.g., during a rolling update), the ALB waits 30 seconds before stopping sending traffic to it. This allows in-flight requests to complete gracefully.

**Slow start (30s)**: When a new pod is added, the ALB gradually increases traffic to it over 30 seconds. This prevents overwhelming a freshly-started pod.

---

## AWS Secrets Manager

Secrets Manager securely stores and manages access to secrets (database passwords, API keys, JWT secrets).

### Why Secrets Manager Over Kubernetes Secrets?

```
Kubernetes Secrets (basic):
  - base64 encoded (NOT encrypted by default)
  - Stored in etcd (must enable etcd encryption separately)
  - Can be seen by anyone with kubectl access
  - Rotation requires manual process

AWS Secrets Manager:
  + AES-256 encryption via AWS KMS
  + Fine-grained IAM access control
  + Automatic rotation for RDS passwords
  + Full audit trail (who accessed what, when)
  + Cross-account access possible
  + CLI/SDK for manual secret access
  - Additional cost ($0.40/secret/month)
```

### Creating and Accessing Secrets

```bash
# Create a secret in AWS Secrets Manager
aws secretsmanager create-secret \
  --name "issue-tracker/production/app-secrets" \
  --description "Application secrets for issue tracker production" \
  --secret-string '{
    "JWT_SECRET_KEY": "your-very-long-random-secret",
    "JWT_REFRESH_SECRET_KEY": "another-very-long-random-secret",
    "DATABASE_URL": "postgresql+asyncpg://postgres:PASSWORD@HOST:5432/issuetracker",
    "SMTP_PASSWORD": "your-smtp-password",
    "SEED_ADMIN_PASSWORD": "initial-admin-password"
  }' \
  --region ap-south-1

# Update a secret value
aws secretsmanager update-secret \
  --secret-id "issue-tracker/production/app-secrets" \
  --secret-string '{"JWT_SECRET_KEY": "new-rotated-key", ...}' \
  --region ap-south-1

# Read a secret (for debugging, requires IAM permission)
aws secretsmanager get-secret-value \
  --secret-id "issue-tracker/production/app-secrets" \
  --query SecretString \
  --output text \
  --region ap-south-1
```

### Secret Rotation for RDS

```hcl
# infra/terraform/modules/rds/main.tf

# Enable automatic password rotation (every 30 days)
resource "aws_secretsmanager_secret_rotation" "db_password" {
  secret_id           = aws_secretsmanager_secret.db_password.id
  rotation_lambda_arn = aws_lambda_function.rotate_db_password.arn
  
  rotation_rules {
    automatically_after_days = 30
  }
}

# AWS provides a Lambda function for RDS rotation
# It:
#  1. Creates a new strong random password
#  2. Updates the RDS instance password
#  3. Updates the Secrets Manager secret
#  4. Verifies the new password works
#  5. External Secrets Operator syncs to Kubernetes
#  6. You restart pods to pick up new password
```

---

## AWS Certificate Manager (ACM)

ACM is covered briefly here because it's used with ALB:

```bash
# Request a certificate via Terraform:

resource "aws_acm_certificate" "main" {
  domain_name       = "yourdomain.com"
  subject_alternative_names = ["*.yourdomain.com"]  # Wildcard for subdomains
  validation_method = "DNS"
  
  lifecycle {
    create_before_destroy = true  # Zero downtime when rotating certs
  }
}

# Add DNS validation records to Route53
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }
  
  name    = each.value.name
  records = [each.value.record]
  type    = each.value.type
  ttl     = 60
  zone_id = var.route53_zone_id
}

resource "aws_acm_certificate_validation" "main" {
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}
```

---

## Further Reading & Videos

- **YouTube**: Search "AWS ALB Application Load Balancer" — AWS official tutorials
- **YouTube**: Search "AWS Secrets Manager Tutorial" — how to use and integrate
- **Official Docs**: [ALB documentation](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/)
- **Official Docs**: [Secrets Manager documentation](https://docs.aws.amazon.com/secretsmanager/)
- **Official Docs**: [ACM documentation](https://docs.aws.amazon.com/acm/)

---

*Next: [Module 09-01 — Terraform Fundamentals](../09-terraform/01-terraform-fundamentals.md)*
