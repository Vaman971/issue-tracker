# Module 08-02 — VPC: Subnets, NAT Gateway, Security Groups & Routing

---

## Learning Objectives

After this module you will:
- Understand what a VPC is and why it's needed
- Know the difference between public and private subnets
- Understand NAT Gateway for outbound internet access
- Know how Security Groups act as virtual firewalls

---

## What Is a VPC?

A Virtual Private Cloud (VPC) is your own private network within AWS. By default, nothing in your VPC can reach the internet and nothing from the internet can reach your VPC.

Think of it as setting up a network inside a secure building:
- The building walls = VPC boundary
- Rooms inside = subnets
- Door to outside world = Internet Gateway
- Security guards at each room = Security Groups

---

## VPC Architecture for This Project

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    VPC: 10.0.0.0/16                                      │
│                    (65,536 IP addresses)                                  │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                     INTERNET GATEWAY                                │ │
│  │  (attached to VPC, enables internet access for public subnets)     │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                │                                                         │
│  PUBLIC SUBNETS (resources that need direct internet access):           │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌────────────────┐  │
│  │ ap-south-1a         │  │ ap-south-1b          │  │ ap-south-1c   │  │
│  │ 10.0.1.0/24         │  │ 10.0.2.0/24          │  │ 10.0.3.0/24  │  │
│  │                     │  │                      │  │               │  │
│  │ [ALB node]          │  │ [ALB node]           │  │ [ALB node]    │  │
│  │ [NAT Gateway]       │  │ [NAT Gateway]        │  │               │  │
│  └─────────────────────┘  └─────────────────────┘  └────────────────┘  │
│                │                  │                         │            │
│  PRIVATE SUBNETS (resources that should NOT be directly internet-facing):│
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌────────────────┐  │
│  │ ap-south-1a         │  │ ap-south-1b          │  │ ap-south-1c   │  │
│  │ 10.0.10.0/24        │  │ 10.0.11.0/24         │  │ 10.0.12.0/24 │  │
│  │                     │  │                      │  │               │  │
│  │ [EKS nodes]         │  │ [EKS nodes]          │  │ [EKS nodes]   │  │
│  │ [RDS primary]       │  │ [RDS standby]        │  │               │  │
│  │ [ElastiCache node]  │  │ [ElastiCache node]   │  │ [EC node]     │  │
│  └─────────────────────┘  └─────────────────────┘  └────────────────┘  │
│                │                  │                                       │
│           Route table:                                                    │
│           Outbound to internet → NAT Gateway → Internet Gateway           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Subnets

A subnet is a subset of the VPC's IP address range, confined to a single AZ.

```
VPC CIDR: 10.0.0.0/16
  → gives 10.0.0.0 through 10.0.255.255
  → 65,536 addresses

Public subnet 1a: 10.0.1.0/24
  → 10.0.1.0 through 10.0.1.255
  → 256 addresses

Public subnet 1b: 10.0.2.0/24
  → 10.0.2.0 through 10.0.2.255

Private subnet 1a: 10.0.10.0/24
  → 10.0.10.0 through 10.0.10.255
```

**Public subnet**: Has a route to the Internet Gateway. Resources with public IPs can receive inbound internet traffic (e.g., the ALB).

**Private subnet**: No route to Internet Gateway. Resources cannot be reached from the internet directly (EKS nodes, RDS, ElastiCache).

---

## Internet Gateway vs NAT Gateway

```
Internet Gateway (for public subnets):
  - Attached to the VPC
  - Allows bidirectional internet access
  - Resources in public subnet must have a PUBLIC IP to use it
  - Free (no charge for the gateway itself)
  - ALB uses this to receive traffic from the internet

NAT Gateway (for private subnets):
  - Lives in a public subnet
  - Allows private subnet resources to INITIATE outbound connections
  - But does NOT allow inbound connections from internet
  
  Use cases:
    - EKS nodes need to pull Docker images from ECR (outbound)
    - Backend pods need to call external APIs (outbound)
    - But nothing from internet can reach EKS nodes directly (no inbound)
  
  Cost: ~$0.045/hour per AZ + data processing charges
```

```
Private EKS node needs to pull image from ECR:
  EKS node (10.0.10.5) → Route table → NAT Gateway (10.0.1.10 public IP)
  NAT Gateway → Internet Gateway → ECR
  Response: ECR → Internet Gateway → NAT Gateway → EKS node

Internet user tries to directly reach EKS node:
  Request to 10.0.10.5 (private IP) → IMPOSSIBLE from internet
  Private IPs are not routable on the public internet
```

---

## Security Groups

Security Groups act as stateful virtual firewalls for AWS resources:

```yaml
# Conceptual representation of security group rules

ALB Security Group:
  Inbound:
    - HTTPS (443) from 0.0.0.0/0  ← Anyone on the internet
    - HTTP  (80)  from 0.0.0.0/0  ← For HTTP→HTTPS redirect
  Outbound:
    - HTTP (80) to EKS nodes security group  ← Forward to nginx pods

EKS Nodes Security Group:
  Inbound:
    - All traffic from ALB security group   ← Accept from ALB only
    - All traffic from within EKS nodes sg  ← Pod-to-pod communication
    - SSH (22) from admin IPs only          ← For emergency access
  Outbound:
    - All traffic to 0.0.0.0/0              ← Outbound to internet (via NAT)

RDS Security Group:
  Inbound:
    - PostgreSQL (5432) from EKS nodes sg   ← Only our app can connect
    - PostgreSQL (5432) from admin IPs      ← For emergency DBA access
  Outbound:
    - None needed (DB doesn't initiate connections)

ElastiCache Security Group:
  Inbound:
    - Redis (6379) from EKS nodes sg        ← Only our app can connect
  Outbound:
    - None needed
```

**Stateful** means: if you allow inbound traffic, the response is automatically allowed outbound (and vice versa). You don't need separate rules for return traffic.

---

## Terraform VPC Module

```hcl
# infra/terraform/modules/vpc/main.tf

# Create the VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr  # "10.0.0.0/16"
  enable_dns_hostnames = true  # Enable DNS for EKS
  enable_dns_support   = true
  
  tags = {
    Name = "${var.name}-vpc"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

# Public subnets (for ALB, NAT Gateways)
resource "aws_subnet" "public" {
  count  = length(var.availability_zones)
  vpc_id = aws_vpc.main.id
  
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 1)
  # For "10.0.0.0/16", count.index=0 → "10.0.1.0/24"
  # count.index=1 → "10.0.2.0/24"
  # count.index=2 → "10.0.3.0/24"
  
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true  # Auto-assign public IPs to resources
  
  tags = {
    Name = "${var.name}-public-${var.availability_zones[count.index]}"
    # EKS Load Balancer Controller needs this tag to find public subnets for ALB
    "kubernetes.io/role/elb" = "1"
  }
}

# Private subnets (for EKS, RDS, ElastiCache)
resource "aws_subnet" "private" {
  count  = length(var.availability_zones)
  vpc_id = aws_vpc.main.id
  
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  # count.index=0 → "10.0.10.0/24"
  # count.index=1 → "10.0.11.0/24"
  
  availability_zone = var.availability_zones[count.index]
  
  tags = {
    Name = "${var.name}-private-${var.availability_zones[count.index]}"
    # EKS Load Balancer Controller: use these for internal load balancers
    "kubernetes.io/role/internal-elb" = "1"
    # EKS needs these tags to find subnets for nodes
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}

# NAT Gateways (one per AZ for high availability)
resource "aws_eip" "nat" {
  count  = length(var.availability_zones)
  domain = "vpc"
}

resource "aws_nat_gateway" "main" {
  count = length(var.availability_zones)
  
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  # NAT Gateway lives in PUBLIC subnet
}

# Route tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
    # "All internet traffic → Internet Gateway"
  }
}

resource "aws_route_table" "private" {
  count  = length(var.availability_zones)
  vpc_id = aws_vpc.main.id
  
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
    # "All internet traffic → NAT Gateway (per AZ)"
  }
}

# Associate subnets with route tables
resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}
```

---

## VPC Endpoints (Cost Optimization)

Without VPC Endpoints, traffic from EKS to S3/ECR goes:
```
EKS node → NAT Gateway ($$$) → Internet → S3/ECR
```

With VPC Endpoints (free for S3, small cost for ECR):
```
EKS node → VPC Endpoint → S3/ECR (stays inside AWS network, no NAT cost!)
```

For high-volume ECR pulls (large Docker images on every deployment), this can save significant costs.

---

## Security Group Rules in Terraform

```hcl
# Security group for RDS
resource "aws_security_group" "rds" {
  name   = "${var.name}-rds-sg"
  vpc_id = var.vpc_id
  
  # Allow PostgreSQL only from EKS nodes
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.eks_nodes_sg_id]  # Only EKS nodes can connect
  }
  
  # No outbound rules needed (DB doesn't initiate connections)
}

# Security group for ElastiCache
resource "aws_security_group" "elasticache" {
  name   = "${var.name}-elasticache-sg"
  vpc_id = var.vpc_id
  
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [var.eks_nodes_sg_id]
  }
}
```

---

## Further Reading & Videos

- **YouTube**: Search "AWS VPC Tutorial" — TechWorld with Nana or Network Chuck
- **YouTube**: Search "AWS VPC Subnets Public Private" — very well explained by many channels
- **YouTube**: Search "AWS NAT Gateway vs Internet Gateway" — common confusion, well-explained
- **Official Docs**: [AWS VPC documentation](https://docs.aws.amazon.com/vpc/latest/userguide/)
- **Visual**: [AWS VPC Designer tool](https://console.aws.amazon.com/vpc/home#create-vpc) — use the visual editor to design VPCs

---

*Next: [Module 08-03 — EKS: Managed Kubernetes on AWS](./03-eks.md)*
