.PHONY: dev start stop reset logs migrate test lint e2e seed eval eval-openrouter download-public-benchmarks eval-public-smoke eval-public-openrouter-smoke eval-public-openrouter eval-stage-a eval-stage-b eval-stage-c eval-stage-d

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

# Live OpenRouter eval (requires OPENROUTER_API_KEY).
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

# Staged upgrade experiments (A→B→C→D)
# A: add Cohere rerank-v3.5 (keep text-embedding-3-small)
eval-stage-a:
	PYTHONUNBUFFERED=1 \
	ACE_EMBED_MODEL=openai/text-embedding-3-small \
	ACE_RERANK_MODEL=cohere/rerank-v3.5 \
	ACE_USE_RERANK=1 \
	ACE_ADAPTIVE_MODE=intrinsic \
	ACE_RESULTS_DIR=results/openrouter_stage_a_rerank \
	PYTHONPATH=apps/api:packages/python python3 benchmarks/adaptive_chunking_eval/run_eval_openrouter.py

# B: switch embedding to Qwen3-Embedding-8B (+ rerank)
eval-stage-b:
	PYTHONUNBUFFERED=1 \
	ACE_EMBED_MODEL=Qwen/Qwen3-Embedding-8B \
	ACE_RERANK_MODEL=cohere/rerank-v3.5 \
	ACE_USE_RERANK=1 \
	ACE_ADAPTIVE_MODE=intrinsic \
	ACE_RESULTS_DIR=results/openrouter_stage_b_qwen8b \
	PYTHONPATH=apps/api:packages/python python3 benchmarks/adaptive_chunking_eval/run_eval_openrouter.py

# C: RAG micro-loop selection (+ Qwen8B + rerank)
eval-stage-c:
	PYTHONUNBUFFERED=1 \
	ACE_EMBED_MODEL=Qwen/Qwen3-Embedding-8B \
	ACE_RERANK_MODEL=cohere/rerank-v3.5 \
	ACE_USE_RERANK=1 \
	ACE_ADAPTIVE_MODE=rag_microloop \
	ACE_RESULTS_DIR=results/openrouter_stage_c_microloop \
	PYTHONPATH=apps/api:packages/python python3 benchmarks/adaptive_chunking_eval/run_eval_openrouter.py

# D: full public benchmarks with stage-C stack
# CLAIR=all docs; FB expanded beyond smoke; ORB=selected docs; live QA ≤3/doc
eval-stage-d:
	PYTHONUNBUFFERED=1 \
	ACE_EMBED_MODEL=Qwen/Qwen3-Embedding-8B \
	ACE_RERANK_MODEL=cohere/rerank-v3.5 \
	ACE_USE_RERANK=1 \
	ACE_ADAPTIVE_MODE=rag_microloop \
	ACE_LIVE_MAX_QA_PER_DOC=3 \
	ACE_FB_MAX_QUESTIONS=36 \
	ACE_ORB_MAX_QUERIES=40 \
	ACE_EMBED_BATCH=16 \
	ACE_BENCH_PROFILE=full \
	PYTHONPATH=apps/api:packages/python python3 benchmarks/adaptive_chunking_eval/run_public_benchmarks.py \
	  --mode openrouter --profile full --out-name openrouter_full_stage_d
