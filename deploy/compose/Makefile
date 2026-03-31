.PHONY: all env build build-bot-image up down ps logs test migrate migrate-or-init makemigrations init-db stamp-db migration-status check_docker

# --- Paths ---
ROOT := $(shell git rev-parse --show-toplevel)
COMPOSE_FILE := $(ROOT)/deploy/compose/docker-compose.yml
COMPOSE_LOCAL_DB := $(ROOT)/deploy/compose/docker-compose.local-db.yml
ENV_FILE := $(ROOT)/.env
ENV_EXAMPLE := $(ROOT)/deploy/env/env-example

BOT_IMAGE_NAME ?= vexa-bot:dev

-include $(ENV_FILE)

# --- Compose files: add local-db overlay unless REMOTE_DB=true ---
COMPOSE_CMD = docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE)
ifneq ($(REMOTE_DB),true)
  COMPOSE_CMD += -f $(COMPOSE_LOCAL_DB)
endif

# ============================================================================
# Main targets
# ============================================================================

all: env build up migrate-or-init test

# --- Environment ---
env:
	@if [ ! -f $(ENV_FILE) ]; then \
		cp $(ENV_EXAMPLE) $(ENV_FILE); \
		echo "Created .env from env-example. Edit $(ENV_FILE) before running."; \
		echo "  - Set TRANSCRIPTION_SERVICE_URL to your transcription endpoint"; \
		echo "  - Set TRANSCRIPTION_SERVICE_TOKEN"; \
	else \
		echo ".env already exists. Delete it to regenerate from env-example."; \
	fi

# --- Docker check ---
check_docker:
	@if ! docker info > /dev/null 2>&1; then \
		echo "ERROR: Docker is not running."; \
		exit 1; \
	fi

# --- Build ---
build-bot-image: check_docker
	@BOT=$$(grep -E '^BOT_IMAGE_NAME=' $(ENV_FILE) 2>/dev/null | cut -d= -f2); \
	BOT=$${BOT:-$(BOT_IMAGE_NAME)}; \
	docker build --platform linux/amd64 -t $$BOT -f $(ROOT)/services/vexa-bot/Dockerfile $(ROOT)/services/vexa-bot

build: check_docker build-bot-image
	$(COMPOSE_CMD) build

# --- Up / Down ---
up: check_docker
	@if ! docker network ls | grep -q "vexa-network"; then \
		docker network create vexa-network || true; \
	fi
	$(COMPOSE_CMD) up -d
	@if grep -qE '^LOCAL_TRANSCRIPTION=true' $(ENV_FILE) 2>/dev/null; then \
		echo "LOCAL_TRANSCRIPTION=true — starting transcription-service..."; \
		cd $(ROOT)/services/transcription-service && docker compose up -d; \
	fi

down: check_docker
	$(COMPOSE_CMD) down
	@cd $(ROOT)/services/transcription-service && docker compose down 2>/dev/null || true

# --- Status ---
ps: check_docker
	$(COMPOSE_CMD) ps

logs:
	$(COMPOSE_CMD) logs -f

# --- Test ---
test: check_docker
	@echo ""
	@echo "============================================"
	@echo "  Validating Vexa stack..."
	@echo "============================================"
	@PASS=0; FAIL=0; BLOCK=""; \
	API_PORT=$$(grep -E '^API_GATEWAY_HOST_PORT=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "8056"); \
	API_PORT=$${API_PORT:-8056}; \
	ADMIN_PORT=$$(grep -E '^ADMIN_API_HOST_PORT=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "8057"); \
	ADMIN_PORT=$${ADMIN_PORT:-8057}; \
	DASH_PORT=$$(grep -E '^DASHBOARD_HOST_PORT=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "3001"); \
	DASH_PORT=$${DASH_PORT:-3001}; \
	\
	if curl -sf "http://localhost:$$API_PORT/" > /dev/null 2>&1; then \
		echo "  ✓ API Gateway (localhost:$$API_PORT)"; PASS=$$((PASS+1)); \
	else \
		echo "  ✗ API Gateway not responding"; FAIL=$$((FAIL+1)); BLOCK="API Gateway down on port $$API_PORT"; \
	fi; \
	\
	if curl -sf "http://localhost:$$ADMIN_PORT/" > /dev/null 2>&1; then \
		echo "  ✓ Admin API (localhost:$$ADMIN_PORT)"; PASS=$$((PASS+1)); \
	else \
		echo "  ✗ Admin API not responding"; FAIL=$$((FAIL+1)); BLOCK="Admin API down on port $$ADMIN_PORT"; \
	fi; \
	\
	if curl -sf "http://localhost:$$DASH_PORT/" > /dev/null 2>&1; then \
		echo "  ✓ Dashboard (localhost:$$DASH_PORT)"; PASS=$$((PASS+1)); \
	else \
		echo "  ✗ Dashboard not responding"; FAIL=$$((FAIL+1)); \
		if [ -z "$$BLOCK" ]; then BLOCK="Dashboard down — check DASHBOARD_PATH in .env"; fi; \
	fi; \
	\
	if $(COMPOSE_CMD) exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then \
		echo "  ✓ Redis"; PASS=$$((PASS+1)); \
	else \
		echo "  ✗ Redis not responding"; FAIL=$$((FAIL+1)); \
		if [ -z "$$BLOCK" ]; then BLOCK="Redis down"; fi; \
	fi; \
	\
	DB_OK=$$($(COMPOSE_CMD) exec -T postgres psql -U $${DB_USER:-postgres} -d $${DB_NAME:-vexa} -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' '); \
	if [ -n "$$DB_OK" ] && [ "$$DB_OK" -gt "0" ] 2>/dev/null; then \
		echo "  ✓ Database ($$DB_OK tables)"; PASS=$$((PASS+1)); \
	else \
		echo "  ✗ Database not ready or no tables"; FAIL=$$((FAIL+1)); \
		if [ -z "$$BLOCK" ]; then BLOCK="Database has no tables — migration may have failed"; fi; \
	fi; \
	\
	TX_URL=$$(grep -E '^TRANSCRIPTION_SERVICE_URL=' $(ENV_FILE) 2>/dev/null | cut -d= -f2); \
	if [ -n "$$TX_URL" ] && [ "$$TX_URL" != "https://your-transcription-url/v1/audio/transcriptions" ]; then \
		if curl -sf "$$(echo $$TX_URL | sed 's|/v1/audio/transcriptions||')" > /dev/null 2>&1; then \
			echo "  ✓ Transcription service reachable"; PASS=$$((PASS+1)); \
		else \
			echo "  ⚠ Transcription service not reachable ($$TX_URL)"; \
			echo "    Bots will start but transcription will fail."; \
			echo "    Get a key at vexa.ai or self-host services/transcription-service/"; \
		fi; \
	else \
		echo "  ⚠ TRANSCRIPTION_SERVICE_URL not configured"; \
		echo "    Set it in .env — get a key at vexa.ai or self-host services/transcription-service/"; \
	fi; \
	\
	echo ""; \
	echo "============================================"; \
	if [ $$FAIL -eq 0 ]; then \
		echo "  ✓ Vexa is ready! ($$PASS/$$PASS checks passed)"; \
		echo ""; \
		echo "  Dashboard:  http://localhost:$$DASH_PORT"; \
		echo "  API docs:   http://localhost:$$API_PORT/docs"; \
		echo "  Admin docs: http://localhost:$$ADMIN_PORT/docs"; \
		echo ""; \
		echo "  Next: open the dashboard and join a meeting."; \
	else \
		echo "  ✗ BLOCKED: $$BLOCK"; \
		echo "    $$PASS passed, $$FAIL failed. Fix the issue and run 'make test'."; \
		exit 1; \
	fi; \
	echo "============================================"

# ============================================================================
# Database migrations
# ============================================================================

migrate-or-init: check_docker
	@set -e; \
	if [ "$(REMOTE_DB)" != "true" ]; then \
		if ! $(COMPOSE_CMD) ps -q postgres | grep -q .; then \
			echo "ERROR: postgres not running. Run 'make up' first."; exit 1; \
		fi; \
		count=0; \
		DB_USER=$$(grep -E '^DB_USER=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "postgres"); \
		DB_NAME=$$(grep -E '^DB_NAME=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "vexa"); \
		DB_USER=$${DB_USER:-postgres}; DB_NAME=$${DB_NAME:-vexa}; \
		while ! $(COMPOSE_CMD) exec -T postgres pg_isready -U $$DB_USER -d $$DB_NAME -q; do \
			if [ $$count -ge 12 ]; then echo "ERROR: DB not ready in 60s."; exit 1; fi; \
			sleep 5; count=$$((count+1)); \
		done; \
	fi; \
	$(COMPOSE_CMD) exec -T transcription-collector python /app/libs/shared-models/fix_alembic_version.py --repair-stale; \
	HAS_ALEMBIC=$$($(COMPOSE_CMD) exec -T postgres psql -U $${DB_USER:-postgres} -d $${DB_NAME:-vexa} -t -c "SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version';" 2>/dev/null | tr -d '[:space:]' || echo ""); \
	if [ "$$HAS_ALEMBIC" = "1" ]; then \
		$(MAKE) migrate; \
	else \
		$(COMPOSE_CMD) exec -T transcription-collector python -c "import asyncio; from shared_models.database import init_db; asyncio.run(init_db())"; \
		$(COMPOSE_CMD) exec -T transcription-collector python /app/libs/shared-models/fix_alembic_version.py --create-if-missing; \
	fi

migrate: check_docker
	@set -e; \
	if [ "$(REMOTE_DB)" != "true" ]; then \
		DB_USER=$$(grep -E '^DB_USER=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "postgres"); \
		DB_NAME=$$(grep -E '^DB_NAME=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "vexa"); \
		DB_USER=$${DB_USER:-postgres}; DB_NAME=$${DB_NAME:-vexa}; \
		if ! $(COMPOSE_CMD) ps postgres | grep -q "Up"; then \
			echo "ERROR: postgres not running. Run 'make up' first."; exit 1; \
		fi; \
	fi; \
	$(COMPOSE_CMD) exec -T transcription-collector python /app/libs/shared-models/fix_alembic_version.py --repair-stale; \
	current_version=$$($(COMPOSE_CMD) exec -T transcription-collector alembic -c /app/alembic.ini current 2>/dev/null | grep -E '^[a-f0-9]{12}' | head -1 || echo ""); \
	if [ "$$current_version" = "dc59a1c03d1f" ]; then \
		if $(COMPOSE_CMD) exec -T postgres psql -U $${DB_USER:-postgres} -d $${DB_NAME:-vexa} -t -c "SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'data';" | grep -q 1; then \
			$(COMPOSE_CMD) exec -T transcription-collector alembic -c /app/alembic.ini stamp 5befe308fa8b; \
		fi; \
	fi; \
	$(COMPOSE_CMD) exec -T transcription-collector alembic -c /app/alembic.ini upgrade head

makemigrations: check_docker
	@if [ -z "$(M)" ]; then echo "Usage: make makemigrations M=\"your message\""; exit 1; fi
	$(COMPOSE_CMD) exec -T transcription-collector alembic -c /app/alembic.ini revision --autogenerate -m "$(M)"

init-db: check_docker
	$(COMPOSE_CMD) run --rm transcription-collector python -c "import asyncio; from shared_models.database import init_db; asyncio.run(init_db())"
	$(COMPOSE_CMD) run --rm transcription-collector alembic -c /app/alembic.ini stamp head

stamp-db: check_docker
	@if [ "$(REMOTE_DB)" != "true" ]; then \
		if ! $(COMPOSE_CMD) ps postgres | grep -q "Up"; then \
			echo "ERROR: postgres not running. Run 'make up' first."; exit 1; \
		fi; \
	fi
	$(COMPOSE_CMD) exec -T transcription-collector alembic -c /app/alembic.ini stamp head

migration-status: check_docker
	@if [ "$(REMOTE_DB)" != "true" ]; then \
		if ! $(COMPOSE_CMD) ps postgres | grep -q "Up"; then \
			echo "ERROR: postgres not running. Run 'make up' first."; exit 1; \
		fi; \
	fi
	$(COMPOSE_CMD) exec -T transcription-collector alembic -c /app/alembic.ini current
	$(COMPOSE_CMD) exec -T transcription-collector alembic -c /app/alembic.ini history --verbose
