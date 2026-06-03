# Module 05-02 — AWS S3: Object Storage, Presigned URLs & Security

---

## Learning Objectives

After this module you will:
- Understand what object storage is and how S3 works
- Know the storage abstraction used in this project
- Understand presigned URLs for secure file access
- Know how file uploads flow from browser to S3

---

## What Is Object Storage?

Traditional file systems (like your hard drive) organize files in folders:
```
/home/user/projects/website/index.html
/home/user/images/avatar.jpg
```

**Object storage** is different — objects are flat (no real folders), identified by a key:
```
bucket: "issue-tracker-attachments"
objects:
  "uploads/issues/42/screenshot.png"      → file content + metadata
  "uploads/issues/42/error-log.txt"       → file content + metadata
  "uploads/avatars/user-1-avatar.jpg"     → file content + metadata
```

Each object has:
- **Key**: the path-like identifier
- **Body**: the actual file bytes
- **Metadata**: content-type, size, custom headers
- **Permissions**: public/private access settings

---

## Why S3 Instead of Local Filesystem?

```
LOCAL FILESYSTEM storage:
  ✓ Simple
  ✗ Files only exist on one server
  ✗ When server restarts/dies → files GONE
  ✗ Multiple backend pods can't share files
  ✗ No scalability (disk runs out)
  ✗ No built-in CDN, encryption, versioning

AWS S3 storage:
  ✓ 11 nines durability (99.999999999% — virtually indestructible)
  ✓ Files persist independently of servers
  ✓ All backend pods access the same files
  ✓ Infinite storage capacity
  ✓ Built-in encryption, versioning, lifecycle policies
  ✓ Global CDN integration (CloudFront)
  ✗ Costs money (very cheap, ~$0.023/GB/month)
  ✗ Requires AWS credentials
```

This is why the project defaults to local storage in development (simple, no AWS needed) and S3 in production (scalable, durable).

---

## S3 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS S3                                   │
│                                                                 │
│  Bucket: "issue-tracker-attachments-prod"                       │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Objects (files)                       │   │
│  │                                                         │   │
│  │  Key: "uploads/issues/42/screenshot.png"                │   │
│  │  Size: 245,632 bytes                                    │   │
│  │  Content-Type: image/png                                │   │
│  │  Server-side encryption: AES-256                        │   │
│  │  Versioning: enabled (keeps all versions)               │   │
│  │                                                         │   │
│  │  Key: "uploads/avatars/user-1.jpg"                      │   │
│  │  ...                                                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Security:                                                      │
│  - All public access BLOCKED (no accidental exposure)          │
│  - IAM roles grant access to backend pods only                 │
│  - Encryption at rest (AES-256) + in transit (HTTPS)          │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Storage Abstraction

This project uses a storage abstraction layer — the application code doesn't know or care if storage is S3 or local:

```python
# backend/app/services/storage.py

from abc import ABC, abstractmethod
from typing import BinaryIO
import boto3
import aiofiles
import os

class StorageBackend(ABC):
    """Abstract interface for file storage."""
    
    @abstractmethod
    async def upload(self, file: BinaryIO, key: str, content_type: str) -> str:
        """Upload a file. Returns the storage path."""
    
    @abstractmethod
    async def get_download_url(self, key: str) -> str:
        """Get a URL to download the file."""
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a file."""


class LocalStorageBackend(StorageBackend):
    """Stores files on the local filesystem (development only)."""
    
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)
    
    async def upload(self, file: BinaryIO, key: str, content_type: str) -> str:
        file_path = os.path.join(self.upload_dir, key)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)
        
        return key  # Return the local path as the storage key
    
    async def get_download_url(self, key: str) -> str:
        # In development, serve files through FastAPI
        return f"/static/{key}"
    
    async def delete(self, key: str) -> None:
        file_path = os.path.join(self.upload_dir, key)
        if os.path.exists(file_path):
            os.remove(file_path)


class S3StorageBackend(StorageBackend):
    """Stores files in AWS S3 (production)."""
    
    def __init__(self, bucket_name: str, region: str):
        self.bucket_name = bucket_name
        self.region = region
        # boto3 automatically uses IAM role credentials in EKS
        # (from OIDC service account annotations — covered in AWS module)
        self.s3 = boto3.client("s3", region_name=region)
    
    async def upload(
        self, 
        file: BinaryIO, 
        key: str, 
        content_type: str
    ) -> str:
        content = await file.read()
        
        # Upload to S3
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=content,
            ContentType=content_type,
            # Server-side encryption
            ServerSideEncryption="AES256",
        )
        
        return key  # S3 key is the storage reference
    
    async def get_download_url(self, key: str) -> str:
        """Generate a presigned URL valid for 1 hour."""
        url = self.s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": key,
            },
            ExpiresIn=3600,  # 1 hour
        )
        return url
    
    async def delete(self, key: str) -> None:
        self.s3.delete_object(Bucket=self.bucket_name, Key=key)


# Factory: choose backend based on configuration
def get_storage_backend() -> StorageBackend:
    if settings.FILE_STORAGE_BACKEND == "s3":
        return S3StorageBackend(
            bucket_name=settings.S3_BUCKET_NAME,
            region=settings.AWS_REGION,
        )
    else:
        return LocalStorageBackend()

storage = get_storage_backend()
```

---

## Presigned URLs — Secure Temporary Access

Files in S3 are private (all public access blocked). How do users download them?

**Option 1 (Bad)**: Stream through FastAPI
```
Browser → FastAPI → S3 → FastAPI → Browser
  
Problem: All file bytes flow through FastAPI pods
         Wastes CPU and bandwidth
         Doesn't scale
```

**Option 2 (Good)**: Presigned URL
```
Browser → FastAPI: "I want to download attachment #42"
FastAPI → S3: "Generate a signed URL for this file"
S3 → FastAPI: "Here's a URL valid for 1 hour"
FastAPI → Browser: "Here's your download URL"
Browser → S3 directly: "GET https://s3.amazonaws.com/bucket/file?X-Amz-Signature=..."
S3 → Browser: file content

Files go directly from S3 to user's browser
FastAPI just hands out the URL
Scales infinitely
```

### How Presigned URLs Work

```
Normal S3 URL (blocked — public access off):
  GET https://bucket.s3.amazonaws.com/uploads/42/screenshot.png
  → 403 Forbidden

Presigned URL (temporary access):
  GET https://bucket.s3.amazonaws.com/uploads/42/screenshot.png
      ?X-Amz-Algorithm=AWS4-HMAC-SHA256
      &X-Amz-Credential=AKIAIOSFODNN7EXAMPLE/20240124/us-east-1/s3/aws4_request
      &X-Amz-Date=20240124T120000Z
      &X-Amz-Expires=3600        ← Valid for 3600 seconds
      &X-Amz-SignedHeaders=host
      &X-Amz-Signature=fe5f80f77d5fa3beca038a248ff027d0445342fe2855ddc963176630326f1024
  → 200 OK (for the next 3600 seconds only)
  → 403 Forbidden after 1 hour

The signature is computed using:
  - S3's secret key (only AWS knows this)
  - The expiry time
  - The specific file being accessed
  
Cannot be forged without the secret key.
```

---

## File Upload Flow

```python
# backend/app/api/routes/attachments.py

from fastapi import UploadFile, File
import uuid

@router.post("/{issue_id}/attachments", status_code=201)
async def upload_attachment(
    issue_id: int,
    file: UploadFile = File(...),  # Multipart form upload
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 1. Validate file size
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(400, "File too large (max 10MB)")
    
    # 2. Generate a unique storage key
    file_extension = os.path.splitext(file.filename)[1].lower()
    storage_key = f"uploads/issues/{issue_id}/{uuid.uuid4()}{file_extension}"
    
    # 3. Upload to storage backend (S3 or local)
    file.file.seek(0)  # Reset to start
    await storage.upload(
        file=file.file,
        key=storage_key,
        content_type=file.content_type,
    )
    
    # 4. Save attachment record to database
    attachment = IssueAttachment(
        issue_id=issue_id,
        uploader_id=current_user.id,
        filename=file.filename,    # Original filename for display
        storage_path=storage_key,  # Where it's actually stored
        file_size=len(content),
        content_type=file.content_type,
    )
    db.add(attachment)
    await db.commit()
    
    return AttachmentResponse.model_validate(attachment)


@router.get("/{attachment_id}/download")
async def get_download_url(
    attachment_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    attachment = await db.get(IssueAttachment, attachment_id)
    if not attachment:
        raise HTTPException(404, "Attachment not found")
    
    # Generate presigned URL
    download_url = await storage.get_download_url(attachment.storage_path)
    
    return {"url": download_url, "expires_in": 3600}
```

---

## S3 Bucket Configuration (Terraform)

```hcl
# infra/terraform/environments/production/main.tf (S3 section)

resource "aws_s3_bucket" "attachments" {
  bucket = "${var.app_name}-attachments-${var.environment}"
}

# Block ALL public access
resource "aws_s3_bucket_public_access_block" "attachments" {
  bucket = aws_s3_bucket.attachments.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "attachments" {
  bucket = aws_s3_bucket.attachments.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"  # AES-256 encryption for all objects
    }
  }
}

# Enable versioning (keeps deleted objects recoverable)
resource "aws_s3_bucket_versioning" "attachments" {
  bucket = aws_s3_bucket.attachments.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

# IAM policy: only our application role can access this bucket
resource "aws_s3_bucket_policy" "attachments" {
  bucket = aws_s3_bucket.attachments.id
  policy = jsonencode({
    Statement = [{
      Effect = "Allow"
      Principal = {
        AWS = aws_iam_role.app_role.arn  # Only our EKS pod role
      }
      Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
      Resource = "${aws_s3_bucket.attachments.arn}/*"
    }]
  })
}
```

---

## File Security Best Practices

```
1. Validate file types (not just by extension):
   Check the actual file magic bytes, not just the extension
   "malware.exe" renamed to "document.pdf" won't fool magic byte check

2. Limit file sizes:
   nginx: client_max_body_size 10m;
   FastAPI: check content length before reading

3. Use random filenames:
   uuid4() → "550e8400-e29b-41d4-a716-446655440000.pdf"
   Prevents directory traversal and enumeration attacks

4. Never serve files through your application server:
   Use presigned URLs → S3 serves directly
   Zero application server bandwidth

5. Virus scanning (not implemented here, but production consideration):
   After upload → trigger AWS Lambda to scan with ClamAV
   If malicious → delete and notify user
```

---

## Further Reading & Videos

- **YouTube**: Search "AWS S3 Tutorial" — AWS events channel has official tutorials
- **YouTube**: Search "S3 Presigned URLs Python" — practical examples
- **Official Docs**: [S3 documentation](https://docs.aws.amazon.com/s3/)
- **Official Docs**: [boto3 S3 reference](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)

---

*Next: [Module 06-01 — Docker: Internals, Images & Multi-stage Builds](../06-docker/01-docker-fundamentals.md)*
