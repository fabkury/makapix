.PHONY: help local remote up down restart logs test clean deploy deploy-vps stack-up stack-down stack-logs stack-restart

help:
	@echo "Makapix Development Commands"
	@echo ""
	@echo "Environment Management:"
	@echo "  make local          - Switch to local development (localhost)"
	@echo "  make remote         - Switch to remote development (dev.makapix.club)"
	@echo "  make status         - Show current environment and service status"
	@echo ""
	@echo "Docker Commands (Full Stack):"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make rebuild        - Rebuild and restart all services"
	@echo "  make logs           - Show logs for all services"
	@echo "  make logs-api       - Show logs for API service"
	@echo "  make logs-web       - Show logs for web service"
	@echo ""
	@echo "VPS Stack Commands (CTA + Dev Preview):"
	@echo "  make stack-up       - Start VPS stack (CTA + dev.makapix.club)"
	@echo "  make stack-down     - Stop VPS stack"
	@echo "  make stack-restart  - Restart VPS stack"
	@echo "  make stack-logs     - Show VPS stack logs"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy         - Deploy to current environment (pull, rebuild, restart)"
	@echo "  make deploy-vps     - Full VPS deployment (git pull + switch to remote + restart)"
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

rebuild:
	docker compose down
	docker compose up -d --build

deploy:
	@echo "Deploying to current environment..."
	@docker compose down
	@docker compose up -d --build
	@echo ""
	@echo "Deployment complete!"
	@make status

deploy-vps:
	@echo "🚀 Starting VPS deployment..."
	@echo ""
	@echo "Step 1: Pulling latest code from Git..."
	git pull origin main
	@echo ""
	@echo "Step 2: Switching to remote environment..."
	@make remote
	@echo ""
	@echo "Step 3: Stopping current services..."
	@docker compose down
	@echo ""
	@echo "Step 4: Starting services with new configuration..."
	@docker compose up -d --build
	@echo ""
	@echo "Step 5: Waiting for services to be healthy..."
	@sleep 10
	@echo ""
	@echo "Step 6: Checking service status..."
	@docker compose ps
	@echo ""
	@echo "✅ VPS deployment complete!"
	@echo ""
	@echo "Verify deployment:"
	@echo "  - Visit: https://dev.makapix.club"
	@echo "  - Check logs: make logs"
	@echo "  - Check network: docker network inspect caddy_net"

stack-up:
	@cd deploy/stack && docker compose up -d

stack-down:
	@cd deploy/stack && docker compose down

stack-restart:
	@cd deploy/stack && docker compose restart

stack-logs:
	@cd deploy/stack && docker compose logs -f
