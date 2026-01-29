.PHONY: help up down restart rebuild logs ps deploy test shell-api shell-db fmt clean

# Stack directory
STACK_DIR := deploy/stack

# Docker compose command for production
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod -p makapix-prod

help:
	@echo "Makapix Production (EA) Commands"
	@echo "================================="
	@echo ""
	@echo "  make up        - Start production services"
	@echo "  make down      - Stop production services"
	@echo "  make restart   - Restart production services"
	@echo "  make rebuild   - Rebuild and restart production"
	@echo "  make logs      - Show production logs"
	@echo "  make ps        - Show container status"
	@echo "  make deploy    - Pull latest code and rebuild"
	@echo ""
	@echo "  make test      - Run API tests"
	@echo "  make shell-api - Open shell in API container"
	@echo "  make shell-db  - Open PostgreSQL shell"
	@echo "  make fmt       - Format Python code"
	@echo ""
	@echo "NOTE: This is the PRODUCTION environment."
	@echo "      For development, use /opt/makapix-dev/"

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
	@echo "Deploying to Production..."
	@echo ""
	@echo "WARNING: This will update the LIVE production site!"
	@echo "Press Ctrl+C within 5 seconds to cancel..."
	@sleep 5
	@git pull origin main
	@cd $(STACK_DIR) && $(COMPOSE) down
	@cd $(STACK_DIR) && $(COMPOSE) up -d --build
	@echo ""
	@echo "Production deployment complete!"
	@cd $(STACK_DIR) && $(COMPOSE) ps

test:
	@cd $(STACK_DIR) && $(COMPOSE) exec api pytest tests/

shell-api:
	@cd $(STACK_DIR) && $(COMPOSE) exec api bash

shell-db db.shell:
	@cd $(STACK_DIR) && $(COMPOSE) exec db psql -U owner -d makapix

fmt:
	@cd $(STACK_DIR) && $(COMPOSE) exec api black .

clean:
	@echo "WARNING: This will remove all production containers and volumes!"
	@echo "Press Ctrl+C within 10 seconds to cancel..."
	@sleep 10
	@cd $(STACK_DIR) && $(COMPOSE) down -v
	@echo "Cleaned up production containers and volumes"
