.PHONY: help up down restart rebuild logs ps deploy sync deploy-to-prod test shell-api shell-db fmt clean

# Stack directory
STACK_DIR := deploy/stack

# Docker compose command for development
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev -p makapix-dev

help:
	@echo "Makapix Development Commands"
	@echo "============================"
	@echo ""
	@echo "  make up        - Start development services"
	@echo "  make down      - Stop development services"
	@echo "  make restart   - Restart development services"
	@echo "  make rebuild   - Rebuild and restart development"
	@echo "  make logs      - Show development logs"
	@echo "  make ps        - Show container status"
	@echo "  make deploy    - Pull latest code and rebuild"
	@echo "  make sync      - Sync with develop branch"
	@echo ""
	@echo "  make test      - Run API tests"
	@echo "  make shell-api - Open shell in API container"
	@echo "  make shell-db  - Open PostgreSQL shell"
	@echo "  make fmt       - Format Python code"
	@echo ""
	@echo "  make deploy-to-prod - Instructions for production deployment"
	@echo ""
	@echo "NOTE: This is the DEVELOPMENT environment."
	@echo "      For production, use /opt/makapix/"

up:
	@cd $(STACK_DIR) && $(COMPOSE) up -d

down:
	@cd $(STACK_DIR) && $(COMPOSE) down

restart:
	@cd $(STACK_DIR) && $(COMPOSE) restart

rebuild:
	@cd $(STACK_DIR) && $(COMPOSE) down && $(COMPOSE) up -d --build

logs:
	@cd $(STACK_DIR) && $(COMPOSE) logs -f

logs-api:
	@cd $(STACK_DIR) && $(COMPOSE) logs -f api

logs-web:
	@cd $(STACK_DIR) && $(COMPOSE) logs -f web

logs-db:
	@cd $(STACK_DIR) && $(COMPOSE) logs -f db

ps:
	@cd $(STACK_DIR) && $(COMPOSE) ps

deploy:
	@echo "Deploying to Development..."
	@git pull origin develop
	@cd $(STACK_DIR) && $(COMPOSE) down
	@cd $(STACK_DIR) && $(COMPOSE) up -d --build
	@echo ""
	@echo "Development deployment complete!"
	@cd $(STACK_DIR) && $(COMPOSE) ps

sync:
	@echo "Syncing with develop branch..."
	@git fetch origin
	@git pull origin develop
	@echo "Development environment synced"

deploy-to-prod:
	@echo "============================================"
	@echo "Deploy to Production via GitHub PR"
	@echo "============================================"
	@echo ""
	@echo "Current branch: $$(git branch --show-current)"
	@echo ""
	@echo "To deploy to production:"
	@echo "  1. Push your changes: git push origin develop"
	@echo "  2. Create PR on GitHub: develop -> main"
	@echo "  3. Merge the PR"
	@echo "  4. In production: cd /opt/makapix && make deploy"
	@echo ""
	@echo "Opening GitHub PR page..."
	@xdg-open "https://github.com/fabkury/makapix/compare/main...develop" 2>/dev/null || \
		echo "Visit: https://github.com/fabkury/makapix/compare/main...develop"

test:
	@cd $(STACK_DIR) && $(COMPOSE) exec api pytest tests/

shell-api:
	@cd $(STACK_DIR) && $(COMPOSE) exec api bash

shell-db db.shell:
	@cd $(STACK_DIR) && $(COMPOSE) exec db psql -U owner -d makapix

fmt:
	@cd $(STACK_DIR) && $(COMPOSE) exec api black .

clean:
	@echo "WARNING: This will remove all development containers and volumes!"
	@echo "Press Ctrl+C within 10 seconds to cancel..."
	@sleep 10
	@cd $(STACK_DIR) && $(COMPOSE) down -v
	@echo "Cleaned up development containers and volumes"
