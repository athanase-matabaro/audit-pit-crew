# Contributing to Audit Pit-Crew

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites
- Python 3.10+
- Docker and Docker Compose
- Git

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/athanase-matabaro/audit-pit-crew.git
   cd audit-pit-crew
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or: .venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Set up pre-commit hooks**
   ```bash
   pre-commit install
   ```

5. **Copy environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

6. **Run with Docker Compose**
   ```bash
   docker compose up --build
   ```

## Code Style

We use the following tools to maintain code quality:

- **Black** for Python formatting (line length: 100)
- **isort** for import sorting
- **pytest** for testing

Run formatters:
```bash
make lint
```

Run tests:
```bash
make test
```

## Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write tests for new functionality
   - Ensure all tests pass
   - Follow the existing code style

3. **Commit with descriptive messages**
   ```bash
   git commit -m "feat: add new feature description"
   ```
   
   We follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `refactor:` - Code refactoring
   - `test:` - Adding or updating tests

4. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a Pull Request on GitHub.

## Project Structure

```
audit-pit-crew/
├── src/
│   ├── api/           # FastAPI application
│   ├── core/          # Business logic
│   │   ├── analysis/  # Security scanners
│   │   ├── remediation/  # Fix suggestions
│   │   └── reports/   # PDF generation
│   └── worker/        # Celery tasks
├── tests/
│   ├── unit/          # Unit tests
│   ├── integrations/  # Integration tests
│   └── fixtures/      # Test data
├── scripts/           # Utility scripts
└── docs/              # Documentation
```

## Testing

- **Unit tests**: `pytest tests/unit`
- **All tests**: `pytest tests/`
- **With coverage**: `pytest --cov=src tests/`

## Questions?

Feel free to open an issue for any questions or discussions.
