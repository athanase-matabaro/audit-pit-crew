.PHONY: setup test run-dev clean lint build push help

# Default target
.DEFAULT_GOAL := help

setup: ## Install dependencies and setup development environment
	pip install -e ".[dev]"
	pre-commit install

test: ## Run unit tests
	pytest tests/unit -v --tb=short

test-cov: ## Run tests with coverage report
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

test-all: ## Run all tests including integration
	pytest tests/ -v

run-dev: ## Start the full stack (API + Worker + Redis) locally
	docker compose up --build

run-prod: ## Start production stack
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

stop: ## Stop all containers
	docker compose down

logs: ## View container logs
	docker compose logs -f

lint: ## Fix code style automatically
	black src/ tests/
	isort src/ tests/

lint-check: ## Check code style without fixing
	black --check src/ tests/
	isort --check-only src/ tests/

build: ## Build Docker image
	docker build . -t audit-pit-crew:latest

clean: ## Remove temporary scan folders and cache
	rm -rf .pytest_cache htmlcov .coverage
	find . -type d -name "__pycache__" -delete
	rm -rf /tmp/audit_pit_crew_*
	docker compose down -v --remove-orphans 2>/dev/null || true

health: ## Check API health
	curl -s http://localhost:8000/health | python3 -m json.tool

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'