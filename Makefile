.PHONY: dev start stop reset logs migrate test lint e2e seed eval

dev:
	docker compose -f compose.yaml -f compose.dev.yaml up -d --build

start:
	docker compose up -d --build

stop:
	docker compose down

reset:
	docker compose down -v
	docker compose up -d --build

logs:
	docker compose logs -f --tail=200

migrate:
	docker compose run --rm migration

test:
	cd apps/api && uv run pytest -q
	cd apps/web && pnpm test

lint:
	cd apps/api && uv run ruff check app tests || true
	cd apps/web && pnpm lint || true

e2e:
	cd apps/web && pnpm e2e

seed:
	curl -s -X POST http://localhost:8000/api/v1/admin/seed | python3 -m json.tool

eval:
	PYTHONPATH=apps/api:packages/python python benchmarks/adaptive_chunking_eval/run_eval.py
