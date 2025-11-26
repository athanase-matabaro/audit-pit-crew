audit-pit-crew/
├── .github/                   # CI/CD pipelines (GitHub Actions)
├── infra/                     # Infrastructure as Code
│   ├── docker/                # Dockerfiles for different services
│   │   ├── api.Dockerfile
│   │   └── worker.Dockerfile
│   └── k8s/                   # (Future) Kubernetes manifests
├── scripts/                   # Dev tools (setup, local run, db migrations)
├── src/                       # 🧠 THE BRAIN (Application Code)
│   ├── api/                   # FastAPI Webhook Handler
│   │   ├── routers/           # Endpoints (e.g., /webhook/github)
│   │   └── dependencies.py    # Auth & DB dependency injection
│   ├── core/                  # Shared Business Logic (The "Secret Sauce")
│   │   ├── analysis/          # Wrappers for Slither, Aderyn
│   │   ├── patching/          # Logic to modify Solidity files
│   │   └── reporting/         # Logic to format GitHub comments
│   ├── db/                    # Database Models & Migrations
│   ├── worker/                # Celery Background Tasks
│   │   └── tasks.py           # The "Scan & Wipe" jobs
│   └── config.py              # Centralized Settings (Pydantic)
├── tests/                     # Mirrors src structure
│   ├── integration/
│   └── unit/
├── .env.example               # Template for environment variables
├── .gitignore
├── docker-compose.yml         # Local development orchestration
├── Makefile                   # Command center (shortcuts)
├── pyproject.toml             # Python dependencies & Tool config
└── README.md