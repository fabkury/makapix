COMPOSE ?= docker compose

.PHONY: up down restart logs api.test web.lint fmt db.reset seed

up:
	@$(COMPOSE) up -d

down:
	@$(COMPOSE) down --remove-orphans

restart:
	@$(COMPOSE) restart

logs:
	@$(COMPOSE) logs -f

api.test:
	@$(COMPOSE) --profile test run --rm api-test

web.lint:
	@$(COMPOSE) run --rm web npm run lint

fmt:
	@$(COMPOSE) run --rm api bash -lc "ruff check app --fix && black app"
	@$(COMPOSE) run --rm web npm run format

db.reset:
	@echo "Stopping application services..."
	@$(COMPOSE) stop api worker web proxy >/dev/null 2>&1 || true
	@echo "Removing database container and volume..."
	@$(COMPOSE) rm -f db >/dev/null 2>&1 || true
	@docker volume ls -q | grep '_pg_data$$' | xargs -r docker volume rm >/dev/null
	@echo "Recreating database and reapplying migrations..."
	@$(COMPOSE) up -d db
	@$(COMPOSE) run --rm api alembic upgrade head
	@$(COMPOSE) run --rm api python -m app.seed

seed:
	@$(COMPOSE) run --rm api python -m app.seed
