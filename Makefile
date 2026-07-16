.PHONY: help up down restart rebuild logs ps deploy sync deploy-to-prod test shell-api shell-db fmt openapi check check-full install-hooks clean

# Stack directory
STACK_DIR := deploy/stack

# Auto-detect environment based on directory
ifeq ($(shell pwd),/opt/makapix)
    ENV := prod
    COMPOSE := docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod -p makapix-prod
else
    ENV := dev
    COMPOSE := docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev -p makapix-dev
endif

help:
ifeq ($(ENV),prod)
	@echo "Makapix PRODUCTION Commands"
	@echo "==========================="
	@echo ""
	@echo "  make up        - Start production services"
	@echo "  make down      - Stop production services"
	@echo "  make restart   - Restart production services"
	@echo "  make rebuild   - Rebuild and restart production"
	@echo "  make logs      - Show production logs"
	@echo "  make ps        - Show container status"
	@echo "  make deploy    - Pull latest main and rebuild"
	@echo ""
	@echo "  make test      - Run API tests"
	@echo "  make shell-api - Open shell in API container"
	@echo "  make shell-db  - Open PostgreSQL shell"
	@echo "  make fmt       - Format Python code"
	@echo ""
	@echo "Environment: PRODUCTION (/opt/makapix)"
else
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
	@echo "Environment: DEVELOPMENT (/opt/makapix-dev)"
endif

up:
	@cd $(STACK_DIR) && $(COMPOSE) up -d

down:
	@cd $(STACK_DIR) && $(COMPOSE) down

restart:
	@cd $(STACK_DIR) && $(COMPOSE) restart

rebuild:
	# Build first, then let `up -d` recreate only changed containers. Building
	# before touching the running stack means a failed build leaves the current
	# stack up instead of taking the site down for the whole build duration.
	@cd $(STACK_DIR) && $(COMPOSE) build
	@cd $(STACK_DIR) && $(COMPOSE) up -d
	@docker builder prune -f --reserved-space=7GB

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
ifeq ($(ENV),prod)
	@echo "Deploying to Production..."
	@git pull origin main
	# Build before recreating so a failed build leaves the running stack up
	# (no full-site outage for the image-build duration, and a broken build is
	# recoverable without downtime).
	@cd $(STACK_DIR) && $(COMPOSE) build
	@cd $(STACK_DIR) && $(COMPOSE) up -d
	@docker builder prune -f --reserved-space=7GB
	@echo ""
	@echo "Production deployment complete!"
	@cd $(STACK_DIR) && $(COMPOSE) ps
else
	@echo "Deploying to Development..."
	@git pull origin develop
	# Build before recreating (see prod branch) so a failed build doesn't take
	# the environment down.
	@cd $(STACK_DIR) && $(COMPOSE) build
	@cd $(STACK_DIR) && $(COMPOSE) up -d
	@docker builder prune -f --reserved-space=7GB
	@echo ""
	@echo "Development deployment complete!"
	@cd $(STACK_DIR) && $(COMPOSE) ps
endif

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
ifeq ($(ENV),prod)
	@echo "REFUSING: 'make test' runs against the PRODUCTION stack (it writes to"
	@echo "the live DB/Redis/broker). Run tests from /opt/makapix-dev instead."
	@exit 1
else
	@cd $(STACK_DIR) && $(COMPOSE) exec -T api python scripts/run_tests.py
endif

shell-api:
	@cd $(STACK_DIR) && $(COMPOSE) exec api bash

shell-db db.shell:
	@cd $(STACK_DIR) && $(COMPOSE) exec db psql -U owner -d makapix

fmt:
	@cd $(STACK_DIR) && $(COMPOSE) exec api black .

# Regenerate the committed OpenAPI 3.1 contract from the running api container.
openapi:
	@cd $(STACK_DIR) && $(COMPOSE) exec -T api python scripts/export_openapi.py > ../../api/openapi.json
	@echo "Wrote api/openapi.json"

# Fast contract gate run by the pre-push hook (this repo has no cloud CI).
# Deliberately cheap — OpenAPI drift + formatting only — so pushes return in
# seconds, not minutes. The full test suite is NOT run here: it spins up a fresh
# app per test (~300 tests, several minutes) and is too slow to gate every push.
# Run `make check-full` before merging to main / deploying to prod.
check:
	@$(MAKE) openapi
	@git diff --exit-code -- api/openapi.json \
		|| { echo "ERROR: OpenAPI schema drifted. Commit the regenerated api/openapi.json."; exit 1; }
	@echo "OpenAPI schema up to date."
	@cd $(STACK_DIR) && $(COMPOSE) exec -T api black --check app tests scripts

# Full gate: the fast contract gate above plus the complete test suite.
# Run this before merging to main and deploying to production.
check-full: check
	@cd $(STACK_DIR) && $(COMPOSE) exec -T api python scripts/run_tests.py

# Symlink the pre-push hook into .git/hooks so `make check` runs before pushes.
install-hooks:
	@ln -sf ../../deploy/hooks/pre-push .git/hooks/pre-push
	@chmod +x deploy/hooks/pre-push
	@echo "Installed pre-push hook -> deploy/hooks/pre-push (runs 'make check')."

e2e:
	@cd web && set -a && [ -f .env.e2e ] && . ./.env.e2e; npx playwright test

e2e-report:
	cd web && npx playwright show-report

clean:
	@echo "WARNING: This will remove all development containers and volumes!"
	@echo "Press Ctrl+C within 10 seconds to cancel..."
	@sleep 10
	@cd $(STACK_DIR) && $(COMPOSE) down -v
	@echo "Cleaned up development containers and volumes"
