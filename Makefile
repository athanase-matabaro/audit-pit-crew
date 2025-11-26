.PHONY: setup test run-dev clean lint

setup: ## Install dependencies and setup tools
	pip install -e .
	pre-commit install

test: ## Run unit and integration tests
	pytest tests/

run-dev: ## Start the full stack (API + Worker + Redis) locally
	docker-compose up --build

lint: ## Fix code style automatically
	black src/ tests/
	isort src/ tests/

clean: ## Remove temporary scan folders and cache
	rm -rf .pytest_cache
	find . -type d -name "__pycache__" -delete
	rm -rf /tmp/audit_pit_crew_*