# PaceTrail - local development
.PHONY: help db-up db-down migrate seed backend backend-run worker frontend install ranks-daily verify

help:
	@echo "PaceTrail targets:"
	@echo "  make db-up      - Start PostgreSQL and Redis (Docker)"
	@echo "  make db-down    - Stop Docker services"
	@echo "  make migrate    - Run Alembic migrations (from backend/)"
	@echo "  make seed       - Seed DB with 5 users and 30 activities"
	@echo "  make backend    - Run FastAPI backend (uvicorn)"
	@echo "  make worker     - Run RQ worker for activity processing"
	@echo "  make frontend   - Run Next.js frontend"
	@echo "  make install    - Install backend + frontend deps"
	@echo "  make ranks-daily - Run daily rank recompute job for all users"
	@echo "  make verify     - Run end-to-end verification (requires backend running)"

db-up:
	docker compose up -d db redis

db-down:
	docker compose down

migrate:
	cd backend && alembic upgrade head

seed:
	cd backend && python -m scripts.seed_db

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-run:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd backend && rq worker default

frontend:
	cd frontend && npm run dev

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

ranks-daily:
	cd backend && python -m scripts.daily_rank_job

verify:
	cd backend && python -m scripts.verify_e2e
