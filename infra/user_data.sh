#!/bin/bash
set -euo pipefail

# EC2 bootstrap script — runs once on first launch.
# Installs Docker, pulls the Sentinel backend image, and starts it.

# ── System update and Docker install ──────────────────────────────────────────
apt-get update -y
apt-get install -y ca-certificates curl gnupg

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

systemctl enable docker
systemctl start docker

# ── Write .env file ────────────────────────────────────────────────────────────
mkdir -p /opt/sentinel
cat > /opt/sentinel/.env <<EOF
LLM_PROVIDER=ollama
OLLAMA_MODEL=${ollama_model}
OLLAMA_BASE_URL=${ollama_base_url}
SENTINEL_API_KEY=${sentinel_api_key}
EOF

# ── Write production docker-compose ───────────────────────────────────────────
cat > /opt/sentinel/docker-compose.yml <<'COMPOSE'
version: "3.9"
services:
  backend:
    image: sentinel-backend:latest
    container_name: sentinel-backend
    ports:
      - "8000:8000"
    env_file: /opt/sentinel/.env
    volumes:
      - sentinel_data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 15s
      timeout: 5s
      retries: 5
volumes:
  sentinel_data:
COMPOSE

# ── Note: the Docker image is pushed by GitHub Actions CI/CD ─────────────────
# The deploy workflow runs: docker pull <ecr-image> && docker compose up -d
# This script only sets up the environment — image deploy is handled by CI.

echo "Sentinel EC2 bootstrap complete."
