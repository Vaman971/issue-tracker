# Module 07-04 — ConfigMaps, Secrets & External Secrets Operator

---

## Learning Objectives

After this module you will:
- Understand ConfigMaps for non-sensitive configuration
- Know how Kubernetes Secrets work (and their limitations)
- Understand the External Secrets Operator and AWS Secrets Manager integration
- See how pods consume configuration in this project

---

## The Configuration Problem

Your application needs configuration to run:
- Database URL
- API keys and secrets
- Feature flags
- Environment names

**Don't hardcode these in your Docker image.** The same image should run in development, staging, and production with different configuration.

```
WRONG: Bake config into image
  ENV DATABASE_URL=postgresql://prod-db:5432/...  ← hardcoded in Dockerfile
  → Same image can't be used in staging

RIGHT: Inject config at runtime
  Docker: -e DATABASE_URL=...
  Kubernetes: ConfigMap + Secret → injected as environment variables
```

---

## ConfigMap — Non-Sensitive Configuration

ConfigMap stores key-value pairs that are NOT secrets (no passwords, no tokens):

```yaml
# infra/kubernetes/configmap.yaml

apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: issue-tracker
data:
  # These are injected as environment variables into pods
  APP_ENV: "production"
  WEB_CONCURRENCY: "4"       # Number of gunicorn workers
  FILE_STORAGE_BACKEND: "s3"
  AWS_REGION: "ap-south-1"
  LOG_LEVEL: "INFO"
```

```yaml
# How pods consume ConfigMap (in deployment.yaml):
spec:
  containers:
    - name: backend
      envFrom:
        # Inject ALL keys from ConfigMap as environment variables
        - configMapRef:
            name: app-config
      # Result: APP_ENV=production, WEB_CONCURRENCY=4, etc. in the container
```

You can also mount ConfigMaps as files (useful for nginx.conf):

```yaml
# infra/kubernetes/nginx/deployment.yaml
volumes:
  - name: nginx-config
    configMap:
      name: nginx-config  # The nginx.conf content is in this ConfigMap

containers:
  - name: nginx
    volumeMounts:
      - name: nginx-config
        mountPath: /etc/nginx/nginx.conf
        subPath: nginx.conf  # Mount just this key as a file
```

```yaml
# infra/kubernetes/nginx/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nginx-config
data:
  nginx.conf: |
    upstream backend {
      server backend:8000;
    }
    ...
    # (full nginx.conf content here)
```

---

## Kubernetes Secret — Sensitive Configuration

Secrets are like ConfigMaps but for sensitive data:

```yaml
# How you SHOULD NOT create secrets (plain text in YAML is risky!):
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
type: Opaque
data:
  # Values must be base64 encoded (NOT encryption, just encoding)
  JWT_SECRET_KEY: bXlzZWNyZXRrZXk=  # base64("mysecretkey")
  DATABASE_URL: cG9zdGdyZXM6Ly8u...
```

**Critical limitation**: Kubernetes Secrets are base64 encoded, NOT encrypted. By default:
- They're stored as plain text in etcd
- Anyone with access to etcd can read them
- YAML files with secrets should NEVER be committed to git

### The Better Way: External Secrets Operator

Instead of storing secrets in Kubernetes (which are not truly secure), store them in AWS Secrets Manager (truly encrypted) and use the External Secrets Operator to sync them:

```
AWS Secrets Manager (encrypted):
  Secret: "issue-tracker/production/app-secrets"
  Value: {
    "JWT_SECRET_KEY": "super-secret-jwt-key",
    "DATABASE_URL": "postgresql://...",
    "SMTP_PASSWORD": "...",
    ...
  }
        │
        ▼ External Secrets Operator (pod in cluster)
        │ Watches ExternalSecret objects
        │ Reads from AWS Secrets Manager
        │ Creates/updates Kubernetes Secret
        ▼
Kubernetes Secret "app-secrets":
  JWT_SECRET_KEY=super-secret-jwt-key
  DATABASE_URL=postgresql://...
```

---

## External Secrets Operator

```yaml
# infra/kubernetes/secrets/external-secrets.yaml

# This tells the External Secrets Operator WHERE to find secrets
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-secrets
  namespace: issue-tracker
spec:
  # How often to refresh from AWS Secrets Manager
  refreshInterval: 1h
  
  # Which secret store to use (AWS Secrets Manager)
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  
  # What Kubernetes Secret to create/update
  target:
    name: app-secrets        # Name of the K8s Secret to create
    creationPolicy: Owner    # Delete K8s secret when ExternalSecret is deleted
  
  # Which AWS secrets to pull and what keys to use
  data:
    - secretKey: JWT_SECRET_KEY      # Key name in K8s Secret
      remoteRef:
        key: issue-tracker/production/app-secrets  # AWS Secrets Manager path
        property: JWT_SECRET_KEY     # Key inside the JSON secret
    
    - secretKey: JWT_REFRESH_SECRET_KEY
      remoteRef:
        key: issue-tracker/production/app-secrets
        property: JWT_REFRESH_SECRET_KEY
    
    - secretKey: DATABASE_URL
      remoteRef:
        key: issue-tracker/production/app-secrets
        property: DATABASE_URL
    
    - secretKey: SMTP_PASSWORD
      remoteRef:
        key: issue-tracker/production/app-secrets
        property: SMTP_PASSWORD
    
    # ... more secrets
```

```yaml
# The ClusterSecretStore tells ESO how to authenticate to AWS
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: ap-south-1
      auth:
        # Use IRSA (IAM Roles for Service Accounts)
        # The pod's service account has IAM permissions to read secrets
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
            namespace: external-secrets
```

---

## IRSA — IAM Roles for Service Accounts

Pods need AWS credentials to access Secrets Manager, S3, etc. IRSA lets Kubernetes Service Accounts assume IAM roles:

```
Traditional approach (WRONG for production):
  Store AWS access key + secret key in Kubernetes Secret
  Every pod with the secret has full AWS access
  If one pod is compromised → attacker has AWS access

IRSA (right approach):
  EKS creates an OIDC provider
  IAM roles can trust the OIDC provider
  Service Accounts annotated with role ARN
  Pods using that Service Account automatically get credentials
  Credentials are temporary + automatically rotated
  Least-privilege: only the specific pod type gets access

Setup:
  1. IAM role for external-secrets pods:
     Trust: "Allow EKS OIDC JWT from service account external-secrets-sa"
     Permission: "secretsmanager:GetSecretValue"
  
  2. IAM role for backend pods:
     Trust: "Allow EKS OIDC JWT from service account backend-sa"
     Permission: "s3:GetObject, s3:PutObject, s3:DeleteObject"
  
  3. Service Account annotation:
     kubectl annotate serviceaccount backend-sa \
       eks.amazonaws.com/role-arn=arn:aws:iam::123456:role/backend-role
  
  4. Pod uses serviceAccountName: backend-sa
     → Automatically gets AWS credentials for that role
```

```yaml
# infra/kubernetes/backend/serviceaccount.yaml

apiVersion: v1
kind: ServiceAccount
metadata:
  name: backend-sa
  namespace: issue-tracker
  annotations:
    # This annotation is what enables IRSA
    eks.amazonaws.com/role-arn: "arn:aws:iam::123456789:role/issue-tracker-backend-role"
```

---

## Consuming Secrets in Pods

```yaml
# backend/deployment.yaml (consuming both ConfigMap and Secret)

containers:
  - name: backend
    envFrom:
      # Non-sensitive config from ConfigMap
      - configMapRef:
          name: app-config
      # Sensitive config from Secret (synced from AWS Secrets Manager)
      - secretRef:
          name: app-secrets
    
    # Result: all these environment variables are available in the container:
    # APP_ENV=production          (from ConfigMap)
    # WEB_CONCURRENCY=4           (from ConfigMap)
    # JWT_SECRET_KEY=...          (from Secret)
    # DATABASE_URL=...            (from Secret)
```

You can also use specific Secret keys:

```yaml
env:
  - name: MY_DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: app-secrets
        key: DATABASE_URL
```

---

## Secret Rotation

AWS Secrets Manager supports automatic secret rotation (e.g., RDS passwords rotated every 30 days). With External Secrets Operator:

```
AWS Secrets Manager rotates database password
        │
        ▼ (External Secrets Operator checks every 1 hour)
        │
        ▼ ESO detects new secret value
        │
        ▼ Updates Kubernetes Secret "app-secrets"
        │
        ▼ But pods are already running with old password in env!
        │
        ▼ You need to restart pods to pick up new env vars:
          kubectl rollout restart deployment/backend
          
          OR configure ESO to trigger automatic rollout on secret change
```

---

## Best Practices for Secrets

```
1. Never commit secrets to git
   ✓ .gitignore .env files
   ✓ Use External Secrets Operator

2. Use least-privilege IAM roles
   ✓ Backend gets only S3 access
   ✓ ESO gets only Secrets Manager access
   ✗ Don't give one role access to everything

3. Encrypt secrets at rest
   ✓ AWS Secrets Manager: KMS encryption
   ✓ Enable etcd encryption in EKS

4. Audit secret access
   ✓ AWS CloudTrail logs all Secrets Manager access
   ✓ Know who accessed what, when

5. Rotate secrets regularly
   ✓ Database passwords (automated with RDS)
   ✓ JWT secrets (manual rotation with rollout)
   ✓ API keys (when you discover they might be leaked)
```

---

## Further Reading & Videos

- **YouTube**: Search "Kubernetes Secrets Management" — covers security implications
- **YouTube**: Search "External Secrets Operator Tutorial" — how to set up ESO
- **YouTube**: Search "IRSA IAM Roles Service Accounts EKS" — AWS-specific setup
- **Official Docs**: [Kubernetes ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/)
- **Official Docs**: [External Secrets Operator](https://external-secrets.io/latest/)
- **AWS Docs**: [IAM Roles for Service Accounts](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)

---

*Next: [Module 07-05 — HPA, PDB & Autoscaling](./05-autoscaling.md)*
