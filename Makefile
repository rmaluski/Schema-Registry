.PHONY: help install test lint format clean docker-build docker-run docker-stop validate-schemas

help: ## Show this help message
	@echo "Schema Registry - Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -r requirements.txt

test: ## Run tests
	pytest tests/ -v

lint: ## Run linting
	black app/ tests/ scripts/ --check
	isort app/ tests/ scripts/ --check-only
	mypy app/

format: ## Format code
	black app/ tests/ scripts/
	isort app/ tests/ scripts/

clean: ## Clean up generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .mypy_cache

docker-build: ## Build Docker image
	docker build -t schema-registry .

docker-run: ## Run with Docker Compose
	docker-compose up -d

docker-stop: ## Stop Docker Compose services
	docker-compose down

validate-schemas: ## Validate all schema files
	python scripts/validate_all.py schemas/

diff-schemas: ## Run schema diff (requires two commit SHAs)
	@if [ -z "$(FROM)" ] || [ -z "$(TO)" ]; then \
		echo "Usage: make diff-schemas FROM=<commit1> TO=<commit2>"; \
		exit 1; \
	fi
	python scripts/diff_schemas.py $(FROM) $(TO)

start-dev: ## Start development environment
	docker-compose up -d etcd
	sleep 5
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

stop-dev: ## Stop development environment
	docker-compose down

load-example-schemas: ## Load example schemas into registry
	@echo "Loading example schemas..."
	curl -X POST "http://localhost:8000/schema/ticks_v1" \
		-H "Content-Type: application/json" \
		-d @schemas/ticks_v1.json
	curl -X POST "http://localhost:8000/schema/ticks_v1" \
		-H "Content-Type: application/json" \
		-d @schemas/ticks_v1.1.0.json
	curl -X POST "http://localhost:8000/schema/ticks_v1" \
		-H "Content-Type: application/json" \
		-d @schemas/ticks_v2.0.0.json

test-api: ## Test API endpoints
	@echo "Testing API endpoints..."
	@echo "1. Health check:"
	curl -s http://localhost:8000/health | jq .
	@echo "\n2. List schemas:"
	curl -s http://localhost:8000/schemas | jq .
	@echo "\n3. Get ticks_v1 schema:"
	curl -s http://localhost:8000/schema/ticks_v1 | jq .
	@echo "\n4. Check compatibility:"
	curl -X POST "http://localhost:8000/schema/ticks_v1/compat" \
		-H "Content-Type: application/json" \
		-d '{"data": {"ts": "2023-01-01T10:00:00Z", "symbol": "AAPL", "price": 150.50, "size": 100, "side": "B"}}' | jq .

setup-monitoring: ## Setup monitoring directories
	mkdir -p monitoring/grafana/dashboards
	mkdir -p monitoring/grafana/datasources
	@echo "Created monitoring directories"

all: install format lint test ## Run all checks 