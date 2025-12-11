# Copilot Instructions for Audit Pit-Crew

This file provides guidance for AI coding agents (GitHub Copilot, Claude, etc.) working on the **Audit Pit-Crew** project—an automated pre-audit security scanner for Solidity smart contracts.

---

## Project Overview

**Audit Pit-Crew** is a GitHub App that automatically scans Solidity smart contracts for security vulnerabilities when Pull Requests are opened. It integrates multiple static analysis tools (Slither, Mythril, Aderyn) and provides:

- **GitHub Check Runs**: PR-blocking security gates
- **Fix Suggestions**: Educational remediation snippets for detected issues
- **PDF Reports**: Pre-Audit Clearance Certificates for passing contracts

### Tech Stack

| Component | Technology |
|-----------|------------|
| API Server | Python 3.10+, FastAPI |
| Task Queue | Celery + Redis |
| Scanners | Slither 0.11.0, Mythril 0.23.0, Aderyn v0.6.5 |
| Container Runtime | Docker, Docker Compose |
| GitHub Integration | GitHub App (webhooks, Check Runs API) |
| PDF Generation | reportlab |
| Config | Pydantic + YAML |
| Testing | pytest |

---

## Architecture

```
┌─────────────────────┐
│   GitHub Webhook    │
│  (Pull Request)     │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   FastAPI Server    │  ← src/api/main.py
│   (Port 8000)       │
└─────────┬───────────┘
          │ Celery task dispatch
          ▼
┌─────────────────────┐
│   Celery Worker     │  ← src/worker/tasks.py
│                     │
│  ┌───────────────┐  │
│  │ GitManager    │  │  Clone repo, diff changes
│  └───────────────┘  │
│  ┌───────────────┐  │
│  │UnifiedScanner │  │  Orchestrate security tools
│  └───────────────┘  │
│  ┌───────────────┐  │
│  │ChecksManager  │  │  Report to GitHub Check Runs
│  └───────────────┘  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   Redis             │  ← Baselines, scan results, PDF data
└─────────────────────┘
```

---

## Key Files & Their Purposes

### Entry Points

| File | Purpose |
|------|---------|
| `src/api/main.py` | FastAPI app, webhook endpoint `/webhook/github`, PDF report endpoints |
| `src/worker/tasks.py` | Celery task `scan_repo_task` - main orchestration logic |
| `src/worker/celery_app.py` | Celery app configuration |

### Core Modules

| File | Purpose |
|------|---------|
| `src/core/analysis/unified_scanner.py` | Orchestrates all security scanners |
| `src/core/analysis/base_scanner.py` | Abstract base class for scanners (severity mapping, fingerprinting) |
| `src/core/analysis/slither_scanner.py` | Slither integration |
| `src/core/analysis/mythril_scanner.py` | Mythril integration |
| `src/core/analysis/aderyn_scanner.py` | Aderyn integration (Rust-based) |
| `src/core/github_checks.py` | GitHub Check Runs API (PR blocking) |
| `src/core/github_reporter.py` | GitHub PR comment reporter |
| `src/core/remediation/patterns.py` | Fix suggestion patterns (24+ patterns) |
| `src/core/remediation/suggester.py` | RemediationSuggester class |
| `src/core/reports/pdf_generator.py` | Pre-Audit PDF Certificate generation |
| `src/core/git_manager.py` | Git operations (clone, diff, checkout) |
| `src/core/config.py` | AuditConfig Pydantic models |
| `src/core/redis_client.py` | Redis storage abstraction |

### Configuration

| File | Purpose |
|------|---------|
| `audit-pit-crew.yml` | Main scanner configuration (enabled tools, severity thresholds) |
| `pyproject.toml` | Python dependencies and tool configs |
| `docker-compose.yml` | Local development stack |
| `.env` / `.env.example` | Environment variables |

---

## Design Patterns & Conventions

### 1. Scanner Interface Pattern

All scanners extend `BaseScanner` and implement:

```python
class MyScanner(BaseScanner):
    def run(self, target_path: str, files: Optional[List[str]] = None, config = None) -> Tuple[List[Dict], Dict[str, List[str]]]:
        """
        Returns:
            - List of issue dicts with standard format
            - Dict of log file paths
        """
        pass
```

**Standard Issue Format:**
```python
{
    "type": "reentrancy-eth",           # Detector/SWC ID
    "severity": "High",                  # Critical/High/Medium/Low/Informational
    "title": "Reentrancy vulnerability",
    "description": "...",
    "file": "contracts/Vulnerable.sol",
    "line": 42,
    "tool": "slither",                   # Tool that found it
    "fingerprint": "slither|reentrancy-eth|contracts/Vulnerable.sol|42"
}
```

### 2. Differential Scanning

For PRs, we compare against baseline:
1. **Baseline scan**: Full scan on main branch, stored in Redis
2. **PR scan**: Scan changed files only
3. **Diff**: Report only NEW issues (not in baseline)

### 3. Error Handling

Tool-specific exceptions inherit from `ToolExecutionError`:
```python
class SlitherExecutionError(ToolExecutionError): pass
class MythrilExecutionError(ToolExecutionError): pass
class AderynExecutionError(ToolExecutionError): pass
```

### 4. Configuration Hierarchy

1. Environment variables (`.env`)
2. YAML config (`audit-pit-crew.yml` in repo root)
3. Defaults in `src/core/config.py`

---

## Development Workflow

### Common Commands (via Makefile)

```bash
make setup        # Install deps, setup pre-commit
make test         # Run unit tests
make test-cov     # Run tests with coverage
make run-dev      # Start full stack (Docker)
make lint         # Auto-fix code style (black, isort)
make lint-check   # Check style without fixing
make clean        # Remove temp files and caches
make logs         # View Docker container logs
make health       # Check API health endpoint
```

### Running Locally

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Configure GitHub App credentials in .env
# GITHUB_APP_ID, GITHUB_PRIVATE_KEY_PATH, GITHUB_WEBHOOK_SECRET

# 3. Start the stack
make run-dev

# 4. Expose webhook (for GitHub integration)
ngrok http 8000
```

### Testing

```bash
# Unit tests only
pytest tests/unit -v

# All tests with coverage
pytest tests/ -v --cov=src --cov-report=html

# Specific test file
pytest tests/unit/test_scanner.py -v
```

---

## Code Style Guidelines

- **Python version**: 3.10+
- **Formatter**: Black (line length 100)
- **Import sorting**: isort (black profile)
- **Type hints**: Required for function signatures
- **Docstrings**: Google-style for public functions/classes
- **Logging**: Use `logger = logging.getLogger(__name__)` pattern

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `UnifiedScanner` |
| Functions | snake_case | `scan_repo_task` |
| Constants | UPPER_SNAKE | `SEVERITY_MAP` |
| Private methods | _leading_underscore | `_filter_by_severity` |
| Test files | test_*.py | `test_scanner.py` |
| Test functions | test_* | `test_scanner_returns_issues` |

---

## Adding New Features

### Adding a New Scanner

1. Create `src/core/analysis/<tool>_scanner.py`
2. Extend `BaseScanner`:
   ```python
   from src.core.analysis.base_scanner import BaseScanner

   class NewToolScanner(BaseScanner):
       def run(self, target_path, files=None, config=None):
           # Implementation
           return issues, {"new_tool": [log_path]}
   ```
3. Register in `UnifiedScanner.ALL_SCANNERS`:
   ```python
   ALL_SCANNERS = {
       'slither': SlitherScanner,
       'mythril': MythrilScanner,
       'aderyn': AderynScanner,
       'new_tool': NewToolScanner,  # Add here
   }
   ```
4. Add exception class in `base_scanner.py`
5. Add to Dockerfile (install tool)
6. Write unit tests in `tests/unit/test_<tool>_scanner.py`

### Adding New Fix Suggestions

1. Add pattern to `src/core/remediation/patterns.py`:
   ```python
   SLITHER_PATTERNS["new-detector"] = {
       "title": "New Issue Pattern",
       "description": "Educational explanation...",
       "snippet": '''// Suggested fix code...''',
       "references": ["https://..."]
   }
   ```
2. For Mythril, use SWC ID as key in `MYTHRIL_PATTERNS`

### Adding New API Endpoints

1. For new routes, create router in `src/api/routers/`
2. Include in `src/api/main.py`:
   ```python
   from src.api.routers import new_router
   app.include_router(new_router.router, prefix="/api/new")
   ```

---

## Docker & Deployment

### Services

| Service | Port | Purpose |
|---------|------|---------|
| api | 8000 | FastAPI webhook server |
| worker | - | Celery task processor |
| redis | 6379 | Message broker + storage |

### Building

```bash
# Development build
docker compose build

# Production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Health Checks

All services have health checks configured:
- **API**: `GET /health`
- **Worker**: `celery -A src.worker.celery_app inspect ping`
- **Redis**: `redis-cli ping`

---

## Important Context for AI Agents

### When Modifying Scanner Code

- Always maintain the standard issue format
- Include `tool` field for source attribution
- Use `get_issue_fingerprint()` for deduplication
- Handle tool failures gracefully with specific exceptions

### When Modifying GitHub Integration

- Check Runs are created early, updated on completion
- Use `conclusion: "action_required"` for issues found
- Use `conclusion: "success"` for clean scans
- Include detailed summary with issue counts by severity

### When Adding Dependencies

- Add to `pyproject.toml` `dependencies` array
- Update Dockerfile if system packages needed
- Document any version constraints

### When Writing Tests

- Mock external services (GitHub API, Redis)
- Use fixtures in `tests/unit/fixtures/`
- Test both success and error paths
- Verify standard issue format compliance

---

## Quick Reference

```bash
# Check what's running
docker compose ps

# View worker logs
docker compose logs -f worker

# Test webhook locally
curl -X POST http://localhost:8000/webhook/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -d @payload.json

# Check Redis keys
docker compose exec redis redis-cli KEYS '*'

# Run specific scanner manually
docker compose exec worker python -c "
from src.core.analysis.slither_scanner import SlitherScanner
s = SlitherScanner()
issues, logs = s.run('/path/to/contracts')
print(issues)
"
```

---

## Files to Avoid Modifying

- `*.pem` files (private keys)
- `autofix_logs/` (generated reports)
- `temp_scan/` (temporary scan artifacts)
- `__pycache__/` directories

---

## Additional Resources

- [README.md](../README.md) - Full project documentation
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines
- [docs/ARCHITECTURE_V2_0_COMPLIANCE_REPORT.md](../docs/ARCHITECTURE_V2_0_COMPLIANCE_REPORT.md) - Architecture details
- [docs/QUICK_REFERENCE.md](../docs/QUICK_REFERENCE.md) - Operational commands
