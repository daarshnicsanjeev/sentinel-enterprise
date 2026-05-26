# =============================================================================
# Project Sentinel — AWS Free Tier Deployment
# Region: ap-south-1 (Mumbai)
#
# Live architecture (as of 2026-05-25):
#   Frontend: Vercel (HTTPS CDN, free Hobby tier) — NOT S3/CloudFront
#   Backend:  EC2 t3.micro running FastAPI, exposed via Cloudflare Quick Tunnel
#             (trycloudflare.com HTTPS — no domain, no port 8000 public exposure)
#
# Resources managed here:
#   1. EC2 t3.micro — FastAPI backend
#   2. S3 bucket    — RETAINED for reference / fallback only; NOT the live frontend host.
#                     Vercel replaced S3 to provide HTTPS (S3 static sites are HTTP-only
#                     which causes Mixed Content errors from an HTTPS frontend).
#   3. CloudFront   — RETAINED for reference / fallback only; Vercel is the live CDN.
#
# NOTE: Port 8000 does NOT need to be open in the security group when using
#       the Cloudflare Quick Tunnel — the tunnel establishes an outbound QUIC
#       connection from EC2 to Cloudflare's edge. Only port 22 (SSH) is needed
#       for administration. The port 8000 ingress rule below is kept for local
#       development / health-check convenience only.
#
# Usage:
#   terraform init
#   terraform plan
#   terraform apply
# =============================================================================

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # S3 remote state — configured at init time via -backend-config flags
  # (bucket / key / region are injected by GitHub Actions or the developer's
  #  local terraform init command; no values are hard-coded here)
  #
  # One-time bootstrap (run ONCE, before terraform init):
  #   aws s3api create-bucket \
  #     --bucket sentinel-tf-state-<your-account-id> \
  #     --region ap-south-1 \
  #     --create-bucket-configuration LocationConstraint=ap-south-1
  #   aws s3api put-bucket-versioning \
  #     --bucket sentinel-tf-state-<your-account-id> \
  #     --versioning-configuration Status=Enabled
  #
  # Then init locally with:
  #   terraform init \
  #     -backend-config="bucket=sentinel-tf-state-<your-account-id>" \
  #     -backend-config="key=sentinel/terraform.tfstate" \
  #     -backend-config="region=ap-south-1" \
  #     -backend-config="encrypt=true"
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region  # ap-south-1 (Mumbai)
}

# Used to inject the AWS account ID into the OpenSearch access policy ARN
data "aws_caller_identity" "current" {}

# =============================================================================
# 1. FRONTEND — S3 Static Website Hosting (RETAINED FOR REFERENCE / FALLBACK)
#    The live frontend is hosted on Vercel, not S3.
#    S3 static websites are HTTP-only; Mixed Content errors block API calls
#    from an HTTPS page. Vercel provides HTTPS + global CDN for free.
#    To use Vercel: cd frontend/sentinel-ui && vercel --prod
# =============================================================================

resource "aws_s3_bucket" "frontend" {
  bucket        = var.frontend_bucket_name
  force_destroy = true

  tags = {
    Name    = "sentinel-frontend"
    Project = "sentinel"
  }
}

# Allow public access (required for static website hosting)
resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# Configure the bucket for static website hosting
resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"  # React Router — all 404s serve index.html
  }
}

# Bucket policy — allow public read so anyone can load the React app
resource "aws_s3_bucket_policy" "frontend_public_read" {
  bucket = aws_s3_bucket.frontend.id

  # Must wait for the public access block to be disabled first
  depends_on = [aws_s3_bucket_public_access_block.frontend]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend.arn}/*"
      }
    ]
  })
}

# =============================================================================
# 2. BACKEND — EC2 t2.micro (Free Tier eligible)
# =============================================================================

# Latest Ubuntu 24.04 LTS AMI for ap-south-1
data "aws_ami" "ubuntu_24_04" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Security group — SSH (22) + FastAPI (8000) inbound, all outbound
resource "aws_security_group" "sentinel_api" {
  name        = "sentinel-api-sg"
  description = "Sentinel FastAPI backend SSH and port 8000"

  # SSH — for manual debugging
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # FastAPI — the main application port
  ingress {
    description = "FastAPI"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # All outbound — needed for pip, apt, Ollama model downloads
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "sentinel-api-sg"
    Project = "sentinel"
  }
}

# EC2 t3.micro — runs on first boot via user_data
resource "aws_instance" "sentinel_api" {
  ami                    = data.aws_ami.ubuntu_24_04.id
  instance_type          = var.instance_type  # t3.micro (Free Tier eligible in ap-south-1)
  vpc_security_group_ids = [aws_security_group.sentinel_api.id]
  key_name               = var.key_pair_name  # set to your existing EC2 key pair name

  # 20 GB gp3 root volume (Free Tier gives 30 GB EBS total — needs 20GB for torch+sentence-transformers)
  root_block_device {
    volume_size           = 25
    volume_type           = "gp3"
    delete_on_termination = true
  }

  # Bootstrap script — runs once on first launch
  user_data = <<-EOF
    #!/bin/bash
    set -euo pipefail

    # ── System update ───────────────────────────────────────────────────────
    apt-get update -y
    apt-get upgrade -y

    # ── Python tooling ──────────────────────────────────────────────────────
    apt-get install -y python3-pip python3-venv git curl

    # ── Ollama (serves Gemma 4 locally) ─────────────────────────────────────
    curl -fsSL https://ollama.com/install.sh | sh

    # ── Pull Ollama model in the background so it's ready when you deploy ───
    # Uncomment the model you want (requires enough RAM / disk):
    # ollama pull gemma3:4b      # ~3 GB — runs fine on t3.micro swap
    # ollama pull llama3.2:3b   # ~2 GB alternative

    # ── Write a minimal .env so the service can start before deploy-backend.sh ─
    mkdir -p /opt/sentinel/backend
    cat > /opt/sentinel/backend/.env <<ENVEOF
LLM_PROVIDER=ollama
OLLAMA_MODEL=gemma3:4b
OLLAMA_BASE_URL=http://localhost:11434
RATE_LIMIT=20
EVAL_THRESHOLD=0.7
REVIEW_MIN_EVIDENCE=${var.review_min_evidence}
SENTINEL_API_KEY=
ENVEOF

    echo "Sentinel EC2 bootstrap complete." >> /var/log/sentinel-bootstrap.log
  EOF

  tags = {
    Name    = "sentinel-api"
    Project = "sentinel"
  }
}

# =============================================================================
# 3. OPENSEARCH SERVICE — Persistent Vector Store (optional, free tier 12 months)
# =============================================================================
#
# Activated by: enable_opensearch = true in terraform.tfvars (or -var flag).
#
# Free-tier entitlements used:
#   • t2.small.search — 750 instance-hours/month for 12 months
#   • 10 GB gp2 EBS   — included in free tier
#
# Authentication: Fine-Grained Access Control (FGAC) with an internal
#   master user (admin / opensearch_master_password).  The EC2 backend
#   connects with HTTP basic auth over HTTPS — no IAM signing required.
#
# After provisioning, inject into EC2 backend/.env (see deploy-backend.sh):
#   VECTOR_STORE=opensearch
#   OPENSEARCH_HOST=<opensearch_endpoint output>
#   OPENSEARCH_PORT=443
#   OPENSEARCH_USER=admin
#   OPENSEARCH_PASSWORD=<opensearch_master_password>
#   OPENSEARCH_USE_SSL=true
# =============================================================================

resource "aws_opensearch_domain" "vectors" {
  count          = var.enable_opensearch ? 1 : 0
  domain_name    = "sentinel-vectors"
  engine_version = "OpenSearch_2.13"

  cluster_config {
    instance_type            = "t2.small.search" # free tier: 750 hrs/month for 12 months
    instance_count           = 1
    dedicated_master_enabled = false
    zone_awareness_enabled   = false # single-AZ — no HA needed for demo
  }

  ebs_options {
    ebs_enabled = true
    volume_type = "gp2"
    volume_size = 10 # GB — free tier maximum
  }

  # Fine-Grained Access Control — enables HTTP basic auth with a master user.
  # FGAC requires encrypt_at_rest + node_to_node_encryption + enforce_https.
  advanced_security_options {
    enabled                        = true
    anonymous_auth_enabled         = false
    internal_user_database_enabled = true
    master_user_options {
      master_user_name     = "admin"
      master_user_password = var.opensearch_master_password
    }
  }

  encrypt_at_rest {
    enabled = true # required for FGAC
  }

  node_to_node_encryption {
    enabled = true # required for FGAC
  }

  domain_endpoint_options {
    enforce_https       = true                    # required for FGAC
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  # Domain-level access policy: allow all requests.
  # Actual user-level enforcement is handled by FGAC (username + password).
  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { AWS = "*" }
        Action    = "es:*"
        Resource  = "arn:aws:es:${var.aws_region}:${data.aws_caller_identity.current.account_id}:domain/sentinel-vectors/*"
      }
    ]
  })

  tags = {
    Name    = "sentinel-vectors"
    Project = "sentinel"
  }
}

# =============================================================================
# 5. CLOUDFRONT — RETAINED FOR REFERENCE / FALLBACK
#    The live CDN is Vercel. CloudFront is defined here in case the team
#    wants to switch back to S3 hosting (e.g. if Vercel free tier limits are hit).
#    CloudFront free tier: 1 TB transfer/month, 10M requests/month.
# =============================================================================

locals {
  s3_origin_id = "sentinel-s3-frontend"
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  price_class         = "PriceClass_All"

  comment = "Sentinel frontend CDN"

  origin {
    domain_name = aws_s3_bucket_website_configuration.frontend.website_endpoint
    origin_id   = local.s3_origin_id

    # S3 website endpoint is HTTP-only; CloudFront terminates HTTPS and talks
    # HTTP to the origin — this is the standard pattern for S3 static sites.
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = local.s3_origin_id

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  # React Router — all 404s from S3 get rewritten to index.html
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Use the default CloudFront certificate (*.cloudfront.net) — no custom domain needed
  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Name    = "sentinel-frontend-cdn"
    Project = "sentinel"
  }
}
