<p align="center"># **Audit Pit Crew \- GitHub Repository Security Scanner**

  <img src="https://img.shields.io/badge/Solidity-Security-blue?style=for-the-badge&logo=ethereum" alt="Solidity Security"/>

  <img src="https://img.shields.io/badge/Python-3.10+-green?style=for-the-badge&logo=python" alt="Python 3.10+"/>The Audit Pit Crew is a multi-container application designed to perform automated security scans (using tools like Slither) on Solidity smart contract repositories whenever a new Pull Request is opened or synchronized on GitHub.

  <img src="https://img.shields.io/badge/Docker-Ready-blue?style=for-the-badge&logo=docker" alt="Docker Ready"/>

  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="MIT License"/>The architecture uses **FastAPI** for the Webhook API, **Redis** as the Celery message broker, and a dedicated **Celery Worker** for asynchronous, resource-intensive scanning tasks.

</p>

## **🚀 Getting Started**

# 🏎️ Audit Pit-Crew

These instructions will get your Dockerized system up and running for development and testing.

> **The automated pre-audit security scanner for Solidity smart contracts.**  

> Don't pay $500/hr for an auditor to find bugs our bot catches for free.### **Prerequisites**



Audit Pit-Crew is a GitHub-integrated security scanner that automatically analyzes your Solidity smart contracts on every Pull Request. It runs industry-standard tools (Slither, Mythril) and provides actionable fix suggestions—all before your code reaches a human auditor.* Docker and Docker Compose installed.  

* A GitHub Personal Access Token (PAT) with repo scope (or an installed GitHub App token, if you are beyond the MVP stage) for cloning private repositories and reporting results.

---

### **Installation**

## ✨ Features

1. **Clone the Repository**  

| Feature | Description |   git clone \[https://github.com/your-username/audit-pit-crew.git\](https://github.com/your-username/audit-pit-crew.git)  

|---------|-------------|   cd audit-pit-crew

| 🔒 **Multi-Tool Analysis** | Runs Slither + Mythril for comprehensive coverage |

| 🚦 **PR Quality Gate** | Blocks PRs with Critical/High severity issues (GitHub Check Runs) |2. Configure Environment Variables  

| 💡 **Fix Suggestions** | Provides code snippets and best practices for each issue |   Create a file named .env in the root directory. This file must contain the following variables:  

| 📄 **PDF Certificates** | Generate "Pre-Audit Clearance" reports for investors |   \# API Settings  

| ⚡ **Differential Scanning** | Only scans changed files for fast feedback |   APP\_NAME=Audit-Pit-Crew

| ⚙️ **Configurable** | Per-repo `audit-pit-crew.yml` for custom rules |

   \# GitHub Webhook Security  

---   \# MUST be a strong, random string that you will also configure in GitHub's webhook settings.  

   GITHUB\_WEBHOOK\_SECRET=a\_very\_secure\_random\_string\_here

## 🎯 Why Audit Pit-Crew?

   \# Redis Configuration (Used by Celery)  

Smart contract audits cost **$50k-$200k** and take weeks. Auditors waste time on basic issues that automated tools can catch.   REDIS\_HOST=audit\_pit\_redis  

   REDIS\_PORT=6379

**With Audit Pit-Crew:**

- ✅ Clean your code *before* the audit starts3. Build and Run the Containers  

- ✅ Reduce audit costs by fixing low-hanging fruit early     Start all services (API, Redis, Worker) using Docker Compose:  

- ✅ Show investors your "Pre-Audit Clearance Certificate"   sudo docker compose up \--build

- ✅ Catch regressions on every PR automatically

   The system is ready when you see logs confirming that the audit\_pit\_api is running on http://0.0.0.0:8000 and the audit\_pit\_worker is connected to Redis.

---

## **🔗 Webhook Integration & End-to-End Testing**

## 🚀 Quick Start

To test the entire pipeline (API signature verification, task queuing, worker execution, and reporting), you must configure a GitHub Webhook and trigger it with a Pull Request.

### Prerequisites

### **Step 1: Expose Your Local API**

- Docker & Docker Compose

- A GitHub App (for production) or GitHub PAT (for testing)Since your Docker service runs locally, GitHub cannot reach it directly. You must use a tunneling service like **ngrok** to create a public URL.

- ngrok (for local webhook testing)

1. Install ngrok (if you haven't already).  

### 1. Clone & Configure2. Run the tunnel:  

   ngrok http 8000

```bash

git clone https://github.com/athanase-matabaro/audit-pit-crew.git3. **Copy the public HTTPS URL** (e.g., https://a1b2c3d4e5f6.ngrok-free.app).

cd audit-pit-crew

### **Step 2: Configure the GitHub Webhook**

# Copy environment template

cp .env.example .env1. Go to the repository where you want to test the scanner.  

2. Navigate to **Settings** \> **Webhooks** \> **Add webhook**.

# Edit .env with your GitHub App credentials

nano .env| Setting | Value |

```| :---- | :---- |

| **Payload URL** | Paste the ngrok HTTPS URL, followed by your endpoint: https://\<YOUR\_NGROK\_URL\>/webhook/github |

### 2. Start the Stack| **Content type** | Select **application/json** (This is the required format) |

| **Secret** | Enter the exact value from your .env file: GITHUB\_WEBHOOK\_SECRET |

```bash| **Which events should trigger this webhook?** | Select **"Let me select individual events"** and choose only **"Pull requests"**. |

# Development mode (with hot reload)| **Active** | Ensure this box is checked. |

make run-dev

3. Click **"Add webhook"**.

# Or manually:

docker compose up --build### **Step 3: Trigger the End-to-End Test**

```

Now, you can perform the full test:

### 3. Expose for GitHub (Local Testing)

1. Ensure your Docker logs are running (sudo docker compose up).  

```bash2. **In the configured GitHub repository, create a new branch and open a Pull Request.**

ngrok http 8000

# Copy the HTTPS URL for your webhook#### **Expected Log Sequence (Success)**

```

Monitor your Docker terminal for the following sequence, which confirms your entire multi-container architecture is working:

### 4. Configure GitHub Webhook

| Service | Log Message | Meaning |

In your target repository: **Settings → Webhooks → Add webhook**| :---- | :---- | :---- |

| audit\_pit\_api | INFO: "POST /webhook/github HTTP/1.1" 202 Accepted | API received and validated the webhook, and queued the task. |

| Setting | Value || audit\_pit\_worker | Task scan\_repo\_task\[...\] received | Worker picked up the task from the Redis queue. |

|---------|-------|| audit\_pit\_worker | ✅ Clone successful. | Repository was cloned into the workspace. |

| Payload URL | `https://<your-ngrok-url>/webhook/github` || audit\_pit\_worker | 🔍 Starting Slither scan... | Scanning process initiated. |

| Content type | `application/json` || audit\_pit\_worker | ℹ️ \[Task ...\] Skipping GitHub posting (No issues found...) | Worker successfully checked for issues and skipped reporting because none were found. (If issues are found, it will attempt to post the report.) |

| Secret | Your `GITHUB_WEBHOOK_SECRET` from `.env` || audit\_pit\_worker | Task scan\_repo\_task\[...\] succeeded... | Task completed cleanly. |

| Events | Select "Pull requests" only |

If this sequence runs without raising a TypeError (the bug we fixed) or a signature mismatch error, your webhook integration is robust and ready for development.
### 5. Open a PR and Watch! 🎉

Create a PR with Solidity changes and watch the magic happen.

---

## 📋 Configuration

Create `audit-pit-crew.yml` in your repository root:

```yaml
# audit-pit-crew.yml
scan:
  # Minimum severity to report (Critical, High, Medium, Low, Informational)
  min_severity: "Low"
  
  # Severity that blocks PR merge
  block_on_severity: "High"
  
  # Path to your contracts (relative to repo root)
  contracts_path: "contracts/"
  
  # Paths to ignore
  ignore_paths:
    - "contracts/mocks/"
    - "contracts/test/"
  
  # Tools to run (default: all available)
  enabled_tools:
    - "slither"
    - "mythril"
```

See [audit-pit-crew.yml.example](audit-pit-crew.yml.example) for all options.

---

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/webhook/github` | POST | GitHub webhook receiver |
| `/api/reports/{owner}/{repo}/summary` | GET | Get scan summary (JSON) |
| `/api/reports/{owner}/{repo}/pdf` | GET | Download Pre-Audit Certificate (PDF) |

---

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   GitHub PR     │────▶│   FastAPI       │────▶│   Redis         │
│   Webhook       │     │   (Port 8000)   │     │   (Message Q)   │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   GitHub        │◀────│   Celery        │◀────│   Slither       │
│   PR Comment    │     │   Worker        │     │   Mythril       │
│   Check Run     │     │                 │     │   (Scanners)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

**Components:**
- **FastAPI**: Receives GitHub webhooks, validates signatures, queues tasks
- **Redis**: Message broker for Celery task queue
- **Celery Worker**: Clones repos, runs security tools, posts results
- **Slither/Mythril**: Industry-standard Solidity security analyzers

---

## 🛠️ Development

### Setup Local Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Setup pre-commit hooks
pre-commit install
```

### Run Tests

```bash
make test          # Unit tests
make test-cov      # With coverage report
make test-all      # All tests
```

### Code Style

```bash
make lint          # Auto-format with black & isort
make lint-check    # Check without fixing
```

### Available Make Commands

```bash
make help          # Show all commands
```

---

## 🐳 Docker Commands

```bash
# Development
docker compose up --build           # Start all services
docker compose logs -f              # Follow logs
docker compose down                 # Stop services

# Production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 📈 Roadmap

- [x] GitHub Webhook Integration
- [x] Multi-tool Scanning (Slither, Mythril)
- [x] Differential PR Scanning
- [x] GitHub Check Runs (PR Blocker)
- [x] Fix Suggestions with Code Snippets
- [x] Pre-Audit PDF Certificates
- [ ] Property Test Generation (Foundry)
- [ ] Web Dashboard
- [ ] Slack/Discord Notifications

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Slither](https://github.com/crytic/slither) - Static analysis framework
- [Mythril](https://github.com/ConsenSys/mythril) - Security analysis tool
- [Trail of Bits](https://www.trailofbits.com/) - Security research inspiration

---

<p align="center">
  <b>Built with ❤️ for the Web3 security community</b>
</p>

<p align="center">
  <a href="https://github.com/athanase-matabaro/audit-pit-crew/issues">Report Bug</a>
  ·
  <a href="https://github.com/athanase-matabaro/audit-pit-crew/issues">Request Feature</a>
</p>
