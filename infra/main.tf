# =============================================================================
# Project Sentinel — AWS Free Tier Deployment (PoC)
# Region: ap-south-1 (Mumbai)
#
# Resources:
#   1. S3 bucket — public static website hosting for the React frontend
#   2. EC2 t2.micro — FastAPI backend with Ollama pre-installed via user_data
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
  # No remote state — keeping it simple for PoC
}

provider "aws" {
  region = var.aws_region  # ap-south-1 (Mumbai)
}

# =============================================================================
# 1. FRONTEND — S3 Static Website Hosting
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
# 2. BACKEND — EC2 t2.micro (Free Tier)
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
  description = "Sentinel FastAPI backend — SSH + port 8000"

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

# EC2 t2.micro — runs on first boot via user_data
resource "aws_instance" "sentinel_api" {
  ami                    = data.aws_ami.ubuntu_24_04.id
  instance_type          = var.instance_type  # t2.micro (Free Tier)
  vpc_security_group_ids = [aws_security_group.sentinel_api.id]
  key_name               = var.key_pair_name  # set to your existing EC2 key pair name

  # 8 GB gp3 root volume (Free Tier gives 30 GB EBS total)
  root_block_device {
    volume_size           = 8
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
    # ollama pull gemma3:4b      # ~3 GB — runs fine on t2.micro swap
    # ollama pull llama3.2:3b   # ~2 GB alternative

    echo "Sentinel EC2 bootstrap complete." >> /var/log/sentinel-bootstrap.log
  EOF

  tags = {
    Name    = "sentinel-api"
    Project = "sentinel"
  }
}
