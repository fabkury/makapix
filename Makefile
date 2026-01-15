.PHONY: help up down restart rebuild logs logs-api logs-web logs-db test shell-api shell-db fmt clean deploy

# Default stack directory
STACK_DIR := deploy/stack

help:
	@echo "Makapix Commands"
	@echo ""
	@echo "Services:"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make rebuild        - Rebuild and restart all services"
	@echo ""
	@echo "Logs:"
	@echo "  make logs           - Show logs for all services"
	@echo "  make logs-api       - Show logs for API service"
	@echo "  make logs-web       - Show logs for web service"
	@echo "  make logs-db        - Show logs for database"
	@echo ""
	@echo "Development:"
	@echo "  make test           - Run API tests"
	@echo "  make shell-api      - Open shell in API container"
	@echo "  make shell-db       - Open PostgreSQL shell (db.shell)"
	@echo "  make fmt            - Format Python code"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy         - Pull latest code and restart services"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          - Remove all containers and volumes"

up:
	@cd $(STACK_DIR) && docker compose up -d

down:
	@cd $(STACK_DIR) && docker compose down

restart:
	@cd $(STACK_DIR) && docker compose restart

rebuild:
	@cd $(STACK_DIR) && docker compose down && docker compose up -d --build

logs:
	@cd $(STACK_DIR) && docker compose logs -f

logs-api:
	@cd $(STACK_DIR) && docker compose logs -f api

logs-web:
	@cd $(STACK_DIR) && docker compose logs -f web

logs-db:
	@cd $(STACK_DIR) && docker compose logs -f db

test:
	@cd $(STACK_DIR) && docker compose exec api pytest tests/

shell-api:
	@cd $(STACK_DIR) && docker compose exec api bash

shell-db db.shell:
	@cd $(STACK_DIR) && docker compose exec db psql -U makapix -d makapix

fmt:
	@cd $(STACK_DIR) && docker compose exec api black .

clean:
	@cd $(STACK_DIR) && docker compose down -v
	@echo "Cleaned up containers and volumes"

deploy:
	@echo "Deploying Makapix..."
	@git pull origin main
	@cd $(STACK_DIR) && docker compose down
	@cd $(STACK_DIR) && docker compose up -d --build
	@echo ""
	@echo "Deployment complete!"
	@cd $(STACK_DIR) && docker compose ps
