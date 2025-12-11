# Audit Pit-Crew Deployment Guide

A comprehensive guide to deploying Audit Pit-Crew in production. This document covers platform selection, step-by-step deployment instructions, and operational best practices.

---

## Table of Contents

1. [Platform Comparison & Recommendation](#platform-comparison--recommendation)
2. [Prerequisites](#prerequisites)
3. [Option A: Railway (Recommended)](#option-a-railway-recommended)
4. [Option B: DigitalOcean App Platform](#option-b-digitalocean-app-platform)
5. [Option C: AWS ECS with Fargate](#option-c-aws-ecs-with-fargate)
6. [Option D: Self-Hosted VPS](#option-d-self-hosted-vps)
7. [GitHub App Configuration](#github-app-configuration)
8. [Domain & SSL Setup](#domain--ssl-setup)
9. [Monitoring & Alerting](#monitoring--alerting)
10. [Cost Optimization](#cost-optimization)
11. [Troubleshooting](#troubleshooting)

---

## Platform Comparison & Recommendation

### Your Project Requirements

| Requirement | Details |
|-------------|---------|
| **Architecture** | 3 services (API, Worker, Redis) |
| **Worker Resources** | 2 CPU cores, 4GB RAM (for Slither/Mythril) |
| **Persistent Storage** | Redis for baselines and scan results |
| **Networking** | Public webhook endpoint with HTTPS |
| **Build Time** | ~10-15 min (Rust compilation for Aderyn) |

### Platform Comparison Matrix

| Platform | Ease of Deploy | Cost/Month | Multi-Service | Worker Resources | Best For |
|----------|----------------|------------|---------------|------------------|----------|
| **🏆 Railway** | ⭐⭐⭐⭐⭐ | $20-50 | ✅ Native | ✅ 8GB RAM | Best overall |
| **DigitalOcean** | ⭐⭐⭐⭐ | $40-80 | ✅ Native | ✅ Flexible | Production scale |
| **AWS ECS** | ⭐⭐ | $50-100 | ✅ Complex | ✅ Unlimited | Enterprise |
| **Render** | ⭐⭐⭐⭐ | $25-60 | ✅ Native | ⚠️ 2GB max* | Simple apps |
| **Fly.io** | ⭐⭐⭐ | $30-70 | ✅ Native | ✅ 8GB RAM | Global edge |
| **VPS (Hetzner)** | ⭐⭐ | $15-30 | Manual | ✅ Full control | Budget |

*Render's free/starter tiers cap at 2GB RAM which is insufficient for Mythril.

### 🏆 Recommendation: **Railway**

**Why Railway is the best choice for Audit Pit-Crew:**

1. **Native Docker Compose Support** - Deploy your existing `docker-compose.yml` directly
2. **Sufficient Resources** - Up to 8GB RAM per service (Mythril needs 4GB)
3. **Managed Redis** - One-click Redis with persistence
4. **Automatic HTTPS** - Free SSL certificates
5. **GitHub Integration** - Auto-deploy on push
6. **Predictable Pricing** - Pay for what you use (~$20-50/month)
7. **Zero DevOps** - No Kubernetes, no infrastructure management

---

## Prerequisites

Before deploying, ensure you have:

### 1. GitHub App Credentials

You need a GitHub App with the following:

```
✅ App ID (numeric)
✅ Private Key (.pem file)
✅ Webhook Secret (random string you generated)
```

If you don't have one yet, see [GitHub App Configuration](#github-app-configuration).

### 2. Your Code Ready

```bash
# Ensure you're on the main branch with latest code
git checkout main
git pull origin main

# Verify Docker builds locally
docker compose build
```

### 3. Environment Variables Prepared

Create a secure note with these values ready:

```bash
APP_NAME="Audit-Pit-Crew"
ENV="production"
GITHUB_APP_ID="123456"
GITHUB_WEBHOOK_SECRET="your-strong-random-secret"
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
REDIS_URL="redis://default:password@redis-host:6379"
LOG_LEVEL="INFO"
```

---

## Option A: Railway (Recommended)

### Step 1: Create Railway Account

1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub (recommended for easy repo access)
3. Verify your account

### Step 2: Create New Project

1. Click **"New Project"** → **"Deploy from GitHub repo"**
2. Select `athanase-matabaro/audit-pit-crew`
3. Railway will auto-detect the Dockerfile

### Step 3: Add Redis Service

1. In your project, click **"+ New"** → **"Database"** → **"Redis"**
2. Railway provisions a managed Redis instance
3. Copy the `REDIS_URL` from the Redis service variables

### Step 4: Configure API Service

1. Click on the deployed service (your app)
2. Go to **Settings** → **General**:
   - **Service Name**: `api`
   - **Start Command**: `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
   
3. Go to **Variables** and add:

```bash
APP_NAME=Audit-Pit-Crew
ENV=production
GITHUB_APP_ID=<your-app-id>
GITHUB_WEBHOOK_SECRET=<your-webhook-secret>
LOG_LEVEL=INFO
PORT=8000
```

4. For the private key, add as a variable:

```bash
GITHUB_PRIVATE_KEY=<paste-entire-pem-content-with-newlines-as-\n>
```

> **Tip**: Convert your PEM file to a single line:
> ```bash
> awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' your-private-key.pem
> ```

5. Link Redis:
   - Click **"+ Variable"** → **"Add Reference"**
   - Select your Redis service → `REDIS_URL`

### Step 5: Add Worker Service

1. Click **"+ New"** → **"GitHub Repo"** → Select same repo
2. Go to **Settings**:
   - **Service Name**: `worker`
   - **Start Command**: `celery -A src.worker.celery_app worker --loglevel=INFO --concurrency=2`
   
3. Go to **Variables**:
   - Click **"+ Variable"** → **"Add Reference"** → Link all variables from `api` service
   - Add reference to `REDIS_URL` from Redis service

4. Go to **Settings** → **Resources**:
   - **Memory**: 4096 MB (4GB) - Required for Mythril
   - **CPU**: 2 vCPU

### Step 6: Configure Networking

1. Click on `api` service → **Settings** → **Networking**
2. Click **"Generate Domain"**
3. You'll get a URL like: `audit-pit-crew-api-production.up.railway.app`
4. (Optional) Add custom domain if you have one

### Step 7: Deploy

1. Railway auto-deploys on every push to `main`
2. First deploy takes ~15 minutes (Rust compilation)
3. Monitor logs: Click service → **"Deployments"** → **"View Logs"**

### Step 8: Update GitHub Webhook

1. Go to your GitHub App settings
2. Update **Webhook URL** to:
   ```
   https://audit-pit-crew-api-production.up.railway.app/webhook/github
   ```
3. Save changes

### Step 9: Verify Deployment

```bash
# Health check
curl https://your-railway-url.up.railway.app/health

# Expected response:
# {"status":"ok","app":"Audit-Pit-Crew"}
```

### Railway Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Railway Project                          │
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │   API Service   │    │  Worker Service │                │
│  │   (FastAPI)     │    │   (Celery)      │                │
│  │                 │    │                 │                │
│  │ Port: 8000      │    │ Memory: 4GB     │                │
│  │ Domain: *.railway│   │ CPU: 2 vCPU     │                │
│  └────────┬────────┘    └────────┬────────┘                │
│           │                      │                          │
│           └──────────┬───────────┘                          │
│                      │                                      │
│                      ▼                                      │
│           ┌─────────────────┐                              │
│           │  Redis Service  │                              │
│           │  (Managed)      │                              │
│           │  Persistent     │                              │
│           └─────────────────┘                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
          │
          │ HTTPS (automatic SSL)
          ▼
    ┌─────────────┐
    │   GitHub    │
    │  Webhooks   │
    └─────────────┘
```

### Railway Cost Estimate

| Service | Resource | Cost/Month |
|---------|----------|------------|
| API | 1GB RAM, 0.5 vCPU | ~$5 |
| Worker | 4GB RAM, 2 vCPU | ~$20-30 |
| Redis | 256MB | ~$5 |
| **Total** | | **~$30-40** |

*Costs vary based on usage. Railway charges per-minute for resources used.*

---

## Option B: DigitalOcean App Platform

### Step 1: Create DigitalOcean Account

1. Go to [digitalocean.com](https://www.digitalocean.com)
2. Sign up (get $200 free credit for 60 days with referral)

### Step 2: Create App

1. Go to **Apps** → **Create App**
2. Choose **GitHub** as source
3. Select `athanase-matabaro/audit-pit-crew`
4. Branch: `main`

### Step 3: Configure Services

DigitalOcean will detect your Dockerfile. Configure:

**API Component:**
```yaml
Name: api
Type: Web Service
Run Command: uvicorn src.api.main:app --host 0.0.0.0 --port 8080
HTTP Port: 8080
Instance Size: Basic ($12/mo)
Instance Count: 1
```

**Worker Component:**
```yaml
Name: worker
Type: Worker
Run Command: celery -A src.worker.celery_app worker --loglevel=INFO
Instance Size: Professional 2 vCPU, 4GB RAM ($48/mo)
Instance Count: 1
```

### Step 4: Add Managed Redis

1. In App settings, click **"Add Resource"** → **"Database"**
2. Choose **Redis**
3. Select development tier (~$15/mo)

### Step 5: Configure Environment Variables

Go to **Settings** → **App-Level Environment Variables**:

```bash
APP_NAME=Audit-Pit-Crew
ENV=production
GITHUB_APP_ID=<your-app-id>
GITHUB_WEBHOOK_SECRET=<your-webhook-secret>
GITHUB_PRIVATE_KEY=<your-pem-content>
LOG_LEVEL=INFO
```

Redis URL is automatically injected as `DATABASE_URL`.

### Step 6: Deploy

1. Click **"Deploy"**
2. Wait for build (~15 minutes)
3. Get your app URL from the dashboard

### DigitalOcean Cost Estimate

| Component | Spec | Cost/Month |
|-----------|------|------------|
| API | Basic | $12 |
| Worker | Pro 2vCPU/4GB | $48 |
| Redis | Dev | $15 |
| **Total** | | **~$75** |

---

## Option C: AWS ECS with Fargate

For enterprise deployments requiring AWS infrastructure.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS VPC                                  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    ECS Cluster                            │   │
│  │                                                           │   │
│  │  ┌─────────────────┐      ┌─────────────────┐            │   │
│  │  │  API Service    │      │  Worker Service │            │   │
│  │  │  (Fargate)      │      │  (Fargate)      │            │   │
│  │  │  1 vCPU, 2GB    │      │  2 vCPU, 4GB    │            │   │
│  │  └────────┬────────┘      └────────┬────────┘            │   │
│  │           │                        │                      │   │
│  └───────────┼────────────────────────┼──────────────────────┘   │
│              │                        │                          │
│              └──────────┬─────────────┘                          │
│                         │                                        │
│                         ▼                                        │
│              ┌─────────────────────┐                            │
│              │   ElastiCache       │                            │
│              │   (Redis)           │                            │
│              └─────────────────────┘                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                Application Load Balancer                  │   │
│  │                + ACM SSL Certificate                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Step 1: Prerequisites

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure credentials
aws configure
```

### Step 2: Create ECR Repository

```bash
# Create repository
aws ecr create-repository --repository-name audit-pit-crew --region us-east-1

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t audit-pit-crew .
docker tag audit-pit-crew:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/audit-pit-crew:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/audit-pit-crew:latest
```

### Step 3: Create Task Definitions

**api-task-definition.json:**
```json
{
  "family": "audit-pit-crew-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::<account>:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "<account>.dkr.ecr.us-east-1.amazonaws.com/audit-pit-crew:latest",
      "portMappings": [{"containerPort": 8000, "protocol": "tcp"}],
      "command": ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"],
      "environment": [
        {"name": "APP_NAME", "value": "Audit-Pit-Crew"},
        {"name": "ENV", "value": "production"}
      ],
      "secrets": [
        {"name": "GITHUB_APP_ID", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "GITHUB_WEBHOOK_SECRET", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "GITHUB_PRIVATE_KEY", "valueFrom": "arn:aws:secretsmanager:..."}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/audit-pit-crew",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "api"
        }
      }
    }
  ]
}
```

**worker-task-definition.json:**
```json
{
  "family": "audit-pit-crew-worker",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "executionRoleArn": "arn:aws:iam::<account>:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "worker",
      "image": "<account>.dkr.ecr.us-east-1.amazonaws.com/audit-pit-crew:latest",
      "command": ["celery", "-A", "src.worker.celery_app", "worker", "--loglevel=INFO"],
      "environment": [...],
      "secrets": [...],
      "logConfiguration": {...}
    }
  ]
}
```

### Step 4: Create ECS Cluster and Services

```bash
# Create cluster
aws ecs create-cluster --cluster-name audit-pit-crew

# Create services
aws ecs create-service \
  --cluster audit-pit-crew \
  --service-name api \
  --task-definition audit-pit-crew-api \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"

aws ecs create-service \
  --cluster audit-pit-crew \
  --service-name worker \
  --task-definition audit-pit-crew-worker \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"
```

### AWS Cost Estimate

| Resource | Spec | Cost/Month |
|----------|------|------------|
| API (Fargate) | 0.5 vCPU, 1GB | ~$15 |
| Worker (Fargate) | 2 vCPU, 4GB | ~$60 |
| ElastiCache (Redis) | cache.t3.micro | ~$15 |
| ALB | Basic | ~$20 |
| **Total** | | **~$110** |

---

## Option D: Self-Hosted VPS

For budget-conscious deployments with technical expertise.

### Recommended: Hetzner Cloud

Best price/performance ratio in Europe.

### Step 1: Create Server

1. Go to [hetzner.com/cloud](https://www.hetzner.com/cloud)
2. Create account
3. New project → Add Server:
   - **Location**: Nuremberg or Helsinki
   - **Image**: Ubuntu 22.04
   - **Type**: CPX31 (4 vCPU, 8GB RAM) - €15/month
   - **SSH Key**: Add your public key

### Step 2: Initial Server Setup

```bash
# SSH into server
ssh root@your-server-ip

# Update system
apt update && apt upgrade -y

# Create non-root user
adduser deployer
usermod -aG sudo deployer
su - deployer
```

### Step 3: Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### Step 4: Clone and Configure

```bash
# Clone repository
git clone https://github.com/athanase-matabaro/audit-pit-crew.git
cd audit-pit-crew

# Create production .env
cat > .env << 'EOF'
APP_NAME=Audit-Pit-Crew
ENV=production
GITHUB_APP_ID=your-app-id
GITHUB_WEBHOOK_SECRET=your-webhook-secret
GITHUB_PRIVATE_KEY_PATH=/usr/src/app/private-key.pem
REDIS_URL=redis://redis:6379/0
LOG_LEVEL=INFO
EOF

# Copy your private key
nano private-key.pem  # Paste your PEM content
chmod 600 private-key.pem
```

### Step 5: Deploy with Docker Compose

```bash
# Build and start
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Check status
docker compose ps
docker compose logs -f
```

### Step 6: Setup Nginx Reverse Proxy with SSL

```bash
# Install Nginx and Certbot
sudo apt install nginx certbot python3-certbot-nginx -y

# Create Nginx config
sudo nano /etc/nginx/sites-available/audit-pit-crew
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Important for webhooks
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/audit-pit-crew /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

### Step 7: Setup Systemd Service (Auto-restart)

```bash
sudo nano /etc/systemd/system/audit-pit-crew.service
```

```ini
[Unit]
Description=Audit Pit-Crew Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/deployer/audit-pit-crew
ExecStart=/usr/local/bin/docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose down
User=deployer

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable audit-pit-crew
sudo systemctl start audit-pit-crew
```

### VPS Cost Estimate

| Resource | Spec | Cost/Month |
|----------|------|------------|
| Hetzner CPX31 | 4 vCPU, 8GB RAM | €15 (~$16) |
| Domain | Optional | $10/year |
| **Total** | | **~$17** |

---

## GitHub App Configuration

If you haven't created a GitHub App yet:

### Step 1: Create GitHub App

1. Go to **GitHub Settings** → **Developer settings** → **GitHub Apps**
2. Click **"New GitHub App"**

### Step 2: Configure App Settings

| Setting | Value |
|---------|-------|
| **Name** | `Audit Pit-Crew Scanner` (must be unique) |
| **Homepage URL** | `https://your-deployment-url.com` |
| **Webhook URL** | `https://your-deployment-url.com/webhook/github` |
| **Webhook Secret** | Generate: `openssl rand -hex 32` |

### Step 3: Set Permissions

**Repository permissions:**
| Permission | Access |
|------------|--------|
| Checks | Read & Write |
| Contents | Read-only |
| Pull requests | Read & Write |
| Metadata | Read-only |

**Subscribe to events:**
- ✅ Pull request

### Step 4: Generate Private Key

1. Scroll to bottom of App settings
2. Click **"Generate a private key"**
3. Save the downloaded `.pem` file securely

### Step 5: Install App

1. Go to your GitHub App's page
2. Click **"Install App"**
3. Select the repositories you want to scan

### Step 6: Note Your Credentials

```
App ID: 123456  (visible in app settings)
Webhook Secret: <the-secret-you-generated>
Private Key: <contents-of-downloaded-pem-file>
```

---

## Domain & SSL Setup

### Option 1: Platform-Provided Domain (Easiest)

- **Railway**: `*.up.railway.app` (automatic SSL)
- **DigitalOcean**: `*.ondigitalocean.app` (automatic SSL)

### Option 2: Custom Domain

1. **Purchase domain** from Namecheap, Cloudflare, or Google Domains

2. **Add DNS records**:
   ```
   Type: CNAME
   Name: api (or @)
   Value: your-platform-url.up.railway.app
   ```

3. **Configure in platform**:
   - Railway: Settings → Networking → Custom Domain
   - DigitalOcean: Settings → Domains

4. **SSL is automatic** on all recommended platforms

---

## Monitoring & Alerting

### Basic Health Monitoring

```bash
# Create monitoring script
cat > /home/deployer/healthcheck.sh << 'EOF'
#!/bin/bash
WEBHOOK_URL="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
HEALTH_URL="https://your-api-url.com/health"

response=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ "$response" != "200" ]; then
    curl -X POST -H 'Content-type: application/json' \
        --data '{"text":"🚨 Audit Pit-Crew API is DOWN! Status: '"$response"'"}' \
        $WEBHOOK_URL
fi
EOF

chmod +x /home/deployer/healthcheck.sh

# Add to crontab (every 5 minutes)
(crontab -l 2>/dev/null; echo "*/5 * * * * /home/deployer/healthcheck.sh") | crontab -
```

### Recommended: UptimeRobot (Free)

1. Go to [uptimerobot.com](https://uptimerobot.com)
2. Create free account
3. Add monitor:
   - **Type**: HTTP(s)
   - **URL**: `https://your-api-url.com/health`
   - **Interval**: 5 minutes
4. Configure alerts (email, Slack, Discord)

### Advanced: Grafana Cloud (Free tier)

For metrics, logs, and dashboards:

1. Sign up at [grafana.com](https://grafana.com/products/cloud/)
2. Add Docker logging driver to compose:

```yaml
services:
  api:
    logging:
      driver: loki
      options:
        loki-url: "https://your-loki-url/loki/api/v1/push"
```

---

## Cost Optimization

### Tips for Reducing Costs

1. **Use Spot/Preemptible Instances** (AWS/GCP)
   - 60-90% cheaper for worker service
   - Workers are stateless, can handle interruptions

2. **Scale Workers to Zero** when not needed
   - Railway: Set minimum replicas to 0
   - Workers only needed during PR activity

3. **Optimize Build Time**
   - Pre-build and push to registry
   - Saves Railway/DO build minutes

4. **Use Redis Caching Wisely**
   - Set TTL on baseline scans
   - Don't store full reports, just summaries

### Cost by Usage Level

| PRs/Month | Platform | Est. Cost |
|-----------|----------|-----------|
| < 50 | Railway | $15-25 |
| 50-200 | Railway | $30-50 |
| 200-500 | DigitalOcean | $75-100 |
| 500+ | AWS ECS | $100+ |

---

## Troubleshooting

### Common Issues

#### 1. Webhook Not Receiving Events

```bash
# Check webhook delivery in GitHub
# Go to: GitHub App Settings → Advanced → Recent Deliveries

# Verify URL is correct
curl -X POST https://your-url.com/webhook/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: ping" \
  -d '{"zen": "test"}'
```

#### 2. Worker Running Out of Memory

```bash
# Check memory usage
docker stats

# Increase worker memory in docker-compose.prod.yml
worker:
  deploy:
    resources:
      limits:
        memory: 6144M  # Increase to 6GB
```

#### 3. Scans Timing Out

```bash
# Check worker logs
docker compose logs -f worker

# Increase Celery timeout
# In src/worker/celery_app.py:
app.conf.task_time_limit = 600  # 10 minutes
```

#### 4. Redis Connection Refused

```bash
# Check Redis is running
docker compose ps redis
docker compose logs redis

# Test Redis connection
docker compose exec redis redis-cli ping
```

#### 5. SSL Certificate Issues

```bash
# Renew Let's Encrypt cert
sudo certbot renew

# Check certificate
openssl s_client -connect your-domain.com:443 -servername your-domain.com
```

### Debug Commands

```bash
# View all logs
docker compose logs -f

# Check API health
curl https://your-url.com/health | jq

# Check Redis keys
docker compose exec redis redis-cli KEYS '*'

# Restart specific service
docker compose restart worker

# Full rebuild
docker compose down
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## Deployment Checklist

Before going live, verify:

- [ ] **GitHub App** created with correct permissions
- [ ] **Private key** securely stored (never in git!)
- [ ] **Webhook URL** updated in GitHub App settings
- [ ] **Health check** returns `{"status":"ok"}`
- [ ] **Test PR** triggers scan and posts results
- [ ] **SSL certificate** valid and auto-renewing
- [ ] **Monitoring** alerts configured
- [ ] **Backups** for Redis data (if using VPS)
- [ ] **Documentation** updated with production URL

---

## Quick Start Summary

### For Most Users: Railway

```bash
# 1. Fork/push repo to GitHub
# 2. Create Railway project from repo
# 3. Add Redis service
# 4. Add environment variables
# 5. Deploy!
# Total time: ~20 minutes
# Cost: ~$30/month
```

### For Budget Users: Hetzner VPS

```bash
# 1. Create €15/month server
# 2. Install Docker
# 3. Clone repo, configure .env
# 4. docker compose up -d
# 5. Setup Nginx + Certbot
# Total time: ~1 hour
# Cost: ~$17/month
```

---

## Support

If you encounter issues:

1. Check [Troubleshooting](#troubleshooting) section
2. Review logs: `docker compose logs -f`
3. Open an issue on GitHub

---

*Last updated: December 2025*
