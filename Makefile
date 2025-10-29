.PHONY: help local remote up down restart logs test clean

help:
	@echo "Makapix Development Commands"
	@echo ""
	@echo "Environment Management:"
	@echo "  make local          - Switch to local development (localhost)"
	@echo "  make remote         - Switch to remote development (dev.makapix.club)"
	@echo ""
	@echo "Docker Commands:"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make logs           - Show logs for all services"
	@echo "  make logs-api       - Show logs for API service"
	@echo "  make logs-web       - Show logs for web service"
	@echo ""
	@echo "Development:"
	@echo "  make test           - Run API tests"
	@echo "  make shell-api      - Open shell in API container"
	@echo "  make shell-db       - Open PostgreSQL shell"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          - Remove all containers, volumes, and generated files"

local:
	@./scripts/switch-env.sh local || powershell -ExecutionPolicy Bypass -File ./scripts/switch-env.ps1 local

remote:
	@./scripts/switch-env.sh remote || powershell -ExecutionPolicy Bypass -File ./scripts/switch-env.ps1 remote

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-web:
	docker compose logs -f web

logs-proxy:
	docker compose logs -f proxy

test:
	docker compose run --rm api-test

shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec db psql -U makapix -d makapix

clean:
	docker compose down -v
	rm -f .env docker-compose.override.yml proxy/Caddyfile
	@echo "Cleaned up containers, volumes, and generated files"

status:
	@echo "Current environment:"
	@grep "^ENVIRONMENT=" .env 2>/dev/null || echo "  No .env file found"
	@echo ""
	@echo "Docker services:"
	@docker compose ps
