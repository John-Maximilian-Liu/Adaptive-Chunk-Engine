.PHONY: dev start stop reset logs migrate test lint e2e seed eval eval-openrouter download-public-benchmarks eval-public-smoke eval-public-openrouter-smoke eval-public-openrouter

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
	PYTHONPATH=apps/api:packages/python python3 benchmarks/adaptive_chunking_eval/run_eval.py

# Live OpenRouter eval (requires OPENROUTER_API_KEY). Defaults: gpt-4o + text-embedding-3-small.
eval-openrouter:
	PYTHONPATH=apps/api:packages/python python3 benchmarks/adaptive_chunking_eval/run_eval_openrouter.py

download-public-benchmarks:
	python3 benchmarks/adaptive_chunking_eval/datasets/download.py

eval-public-smoke:
	PYTHONPATH=apps/api:packages/python python3 benchmarks/adaptive_chunking_eval/run_public_benchmarks.py --mode offline --profile smoke

eval-public-openrouter-smoke:
	PYTHONPATH=apps/api:packages/python python3 benchmarks/adaptive_chunking_eval/run_public_benchmarks.py --mode openrouter --profile smoke

eval-public-openrouter:
	PYTHONPATH=apps/api:packages/python python3 benchmarks/adaptive_chunking_eval/run_public_benchmarks.py --mode openrouter --profile $${ACE_BENCH_PROFILE:-full}
