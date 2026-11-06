"""API v1 routes."""
from __future__ import annotations

import csv
import io
import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import actor_id, correlation_id, engine, tenant_id
from app.api.errors import APIError
from app.core.config import get_settings
from app.services.engine import Engine
from audit_sdk import get_audit_store
from canonical_schemas.evaluation import EvaluationProfile, MetricDefinition, normalize_weights
from llm_gateway import EmbeddingProfile, LLMProfile
from shared.ids import new_id
from vector_adapters import VectorSinkProfile, create_sink

router = APIRouter()


def _eng(e: Engine = Depends(engine)) -> Engine:
    return e


def _tenant(t: str = Depends(tenant_id)) -> str:
    return t


# ---------- System ----------
@router.get("/health/live")
async def live():
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(e: Engine = Depends(_eng)):
    return {"status": "ready", "seeded": bool(e.tenants)}


@router.get("/health/dependencies")
async def deps(e: Engine = Depends(_eng)):
    return e.health_dependencies()


@router.get("/version")
async def version():
    s = get_settings()
    return {"name": s.app_name, "version": s.app_version, "environment": s.environment}


@router.post("/admin/seed")
async def seed(e: Engine = Depends(_eng)):
    return e.seed_development()


# ---------- Documents ----------
@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    tenant: str = Depends(_tenant),
    e: Engine = Depends(_eng),
):
    content = await file.read()
    try:
        return e.upload_document(
            tenant_id=tenant,
            filename=file.filename or "upload.bin",
            content=content,
            content_type=file.content_type,
            title=title,
        )
    except ValueError as exc:
        raise APIError("UPLOAD_REJECTED", str(exc), status_code=400) from exc


@router.get("/documents/{document_id}")
async def get_document(document_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    doc = e.documents.get(document_id)
    if not doc or doc["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Document not found", status_code=404)
    return doc


@router.get("/documents/{document_id}/versions")
async def list_versions(document_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    return [v for v in e.versions.values() if v["document_id"] == document_id and v["tenant_id"] == tenant]


@router.post("/document-versions/{version_id}/parse")
async def parse_version(version_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng), cid: str = Depends(correlation_id)):
    try:
        # Prefer celery when available; execute inline for reliability
        try:
            from workers.parser.tasks import parse_document_task
            parse_document_task.delay(version_id, tenant, cid)
        except Exception:
            pass
        return e.parse_document_version(version_id, tenant_id=tenant, correlation_id=cid)
    except KeyError as exc:
        raise APIError("NOT_FOUND", str(exc), status_code=404) from exc
    except Exception as exc:
        raise APIError("PARSE_FAILED", str(exc), status_code=500, retryable=True) from exc


@router.get("/document-versions/{version_id}/logical-units")
async def list_units(version_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    return [u for u in e.logical_units.values() if u["document_version_id"] == version_id and u["tenant_id"] == tenant]


@router.get("/logical-units/{unit_id}/elements")
async def list_elements(unit_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    unit = e.logical_units.get(unit_id)
    if not unit or unit["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Logical unit not found", status_code=404)
    return [el for el in e.elements.values() if el["logical_unit_id"] == unit_id]


# ---------- Strategies / Plans ----------
@router.get("/strategies")
async def strategies(e: Engine = Depends(_eng)):
    return e.list_strategies()


@router.get("/strategies/{strategy_id}/parameter-schema")
async def strategy_schema(strategy_id: str, e: Engine = Depends(_eng)):
    try:
        return e.get_strategy_schema(strategy_id)
    except KeyError as exc:
        raise APIError("NOT_FOUND", str(exc), status_code=404) from exc


@router.post("/document-versions/{version_id}/chunk-plans:auto")
async def auto_plan(version_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    try:
        return await e.auto_plan(version_id, tenant_id=tenant)
    except KeyError as exc:
        raise APIError("NOT_FOUND", str(exc), status_code=404) from exc


class PlanCreate(BaseModel):
    document_version_id: str
    effective_plan: dict[str, Any]


@router.post("/chunk-plans")
async def create_plan(body: PlanCreate, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    validated = e.validate_plan(body.effective_plan, version_id=body.document_version_id, tenant_id=tenant)
    plan_id = new_id()
    plan = {
        "plan_id": plan_id,
        "tenant_id": tenant,
        "document_version_id": body.document_version_id,
        "status": "validated" if validated["valid"] else "invalid",
        "proposed_plan": body.effective_plan,
        "effective_plan": validated.get("effective_plan") or body.effective_plan,
        "validation": validated,
        "version": 1,
    }
    e.chunk_plans[plan_id] = plan
    if not validated["valid"]:
        raise APIError("PLAN_INVALID", "Plan validation failed", status_code=422, allowed=validated["errors"])
    return plan


@router.patch("/chunk-plans/{plan_id}")
async def patch_plan(plan_id: str, body: dict[str, Any], tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    try:
        return e.patch_plan(plan_id, tenant_id=tenant, patch=body)
    except KeyError as exc:
        raise APIError("NOT_FOUND", str(exc), status_code=404) from exc
    except ValueError as exc:
        raise APIError("VALIDATION_ERROR", str(exc), status_code=422) from exc


@router.patch("/chunk-plans/{plan_id}/logical-units/{unit_id}")
async def patch_unit(plan_id: str, unit_id: str, body: dict[str, Any], tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    try:
        return e.patch_unit_strategy(plan_id, unit_id, tenant_id=tenant, update=body)
    except KeyError as exc:
        raise APIError("NOT_FOUND", str(exc), status_code=404) from exc


@router.patch("/chunk-plans/{plan_id}/regions/{region_id}")
async def patch_region(plan_id: str, region_id: str, body: dict[str, Any], tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    try:
        return e.patch_region_strategy(plan_id, region_id, tenant_id=tenant, update=body)
    except KeyError as exc:
        raise APIError("NOT_FOUND", str(exc), status_code=404) from exc


@router.post("/chunk-plans/{plan_id}/validate")
async def validate_plan(plan_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    plan = e.chunk_plans.get(plan_id)
    if not plan or plan["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Plan not found", status_code=404)
    result = e.validate_plan(plan["effective_plan"], version_id=plan["document_version_id"], tenant_id=tenant)
    plan["validation"] = result
    plan["status"] = "validated" if result["valid"] else "invalid"
    if result["valid"]:
        plan["effective_plan"] = result["effective_plan"]
    return result


@router.post("/chunk-plans/{plan_id}/review")
async def review_plan(plan_id: str, body: dict[str, Any], tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    plan = e.chunk_plans.get(plan_id)
    if not plan or plan["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Plan not found", status_code=404)
    decision = body.get("decision", "approve")
    plan["status"] = "approved" if decision == "approve" else "rejected"
    return plan


# ---------- Chunk runs ----------
class ChunkRunCreate(BaseModel):
    plan_id: str
    experiment_id: Optional[str] = None


@router.post("/chunk-runs")
async def create_chunk_run(body: ChunkRunCreate, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    try:
        run = e.create_chunk_run(tenant_id=tenant, plan_id=body.plan_id, experiment_id=body.experiment_id)
        # enqueue when celery/workers importable; always ensure inline execution for MVP reliability
        try:
            from workers.chunk.tasks import chunk_run_task
            chunk_run_task.delay(run["chunk_run_id"])
        except Exception:
            pass
        if e.chunk_runs[run["chunk_run_id"]]["status"] != "READY":
            e.execute_chunk_run(run["chunk_run_id"])
        return e.chunk_runs[run["chunk_run_id"]]
    except Exception as exc:
        raise APIError("CHUNK_RUN_FAILED", str(exc), status_code=400) from exc


@router.get("/chunk-runs/{run_id}")
async def get_chunk_run(run_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    run = e.chunk_runs.get(run_id)
    if not run or run["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Chunk run not found", status_code=404)
    return run


@router.get("/chunk-runs/{run_id}/chunks")
async def list_chunks(run_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    return [c for c in e.chunks.values() if c["chunk_run_id"] == run_id and c["tenant_id"] == tenant]


@router.get("/chunks/{chunk_id}")
async def get_chunk(chunk_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    c = e.chunks.get(chunk_id)
    if not c or c["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Chunk not found", status_code=404)
    return c


@router.get("/chunks/{chunk_id}/evidence")
async def chunk_evidence(chunk_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    c = e.chunks.get(chunk_id)
    if not c or c["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Chunk not found", status_code=404)
    return {
        "chunk_id": chunk_id,
        "element_ids": c.get("element_ids"),
        "locators": c.get("locators"),
        "source_spans": c.get("source_spans"),
        "decision": {
            "decision_id": c.get("decision_id"),
            "reason_codes": c.get("reason_codes"),
            "explanation": c.get("explanation"),
            "confidence": c.get("confidence"),
        },
    }


@router.post("/chunk-runs/{run_id}/reindex")
async def reindex(run_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    run = e.chunk_runs.get(run_id)
    if not run or run["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Chunk run not found", status_code=404)
    indexing = e.create_indexing_run(tenant_id=tenant, chunk_run_id=run_id, experiment_id=run.get("experiment_id"))
    indexing["status"] = "PENDING"
    result = e.execute_indexing_run(indexing["indexing_run_id"])
    run["indexing_run_id"] = indexing["indexing_run_id"]
    run["indexing_status"] = result.get("status")
    return result


# ---------- QA ----------
class QADatasetCreate(BaseModel):
    document_version_id: str
    name: str
    distribution: Optional[dict[str, Any]] = None


@router.post("/qa-datasets")
async def create_qa_dataset(body: QADatasetCreate, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    try:
        return e.create_qa_dataset(tenant_id=tenant, document_version_id=body.document_version_id, name=body.name, distribution=body.distribution)
    except ValueError as exc:
        raise APIError("QA_DISTRIBUTION_INVALID", str(exc), status_code=422) from exc


@router.post("/qa-datasets/{dataset_id}/generate")
async def generate_qa(dataset_id: str, body: dict[str, Any] | None = None, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    body = body or {}
    return await e.generate_qa(dataset_id, tenant_id=tenant, count=body.get("count"))


@router.post("/qa-datasets/{dataset_id}/upload")
async def upload_qa(
    dataset_id: str,
    file: UploadFile | None = File(None),
    items_json: Optional[str] = Form(None),
    tenant: str = Depends(_tenant),
    e: Engine = Depends(_eng),
):
    items: list[dict] = []
    if items_json:
        items = json.loads(items_json)
    elif file:
        raw = (await file.read()).decode("utf-8", errors="replace")
        name = (file.filename or "").lower()
        if name.endswith(".json"):
            data = json.loads(raw)
            items = data if isinstance(data, list) else data.get("items", [])
        elif name.endswith(".jsonl"):
            items = [json.loads(line) for line in raw.splitlines() if line.strip()]
        elif name.endswith(".csv"):
            reader = csv.DictReader(io.StringIO(raw))
            items = list(reader)
        else:
            # try json
            items = json.loads(raw) if raw.strip().startswith("[") else [{"question": raw, "answer": ""}]
    else:
        raise APIError("NO_INPUT", "Provide file or items_json")
    return await e.upload_qa(dataset_id, tenant_id=tenant, items=items)


@router.post("/qa-datasets/{dataset_id}/complete-schema")
async def complete_schema(dataset_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    return await e.complete_qa_schema(dataset_id, tenant_id=tenant)


@router.get("/qa-datasets/{dataset_id}/items")
async def qa_items(dataset_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    return [i for i in e.qa_items.values() if i["qa_dataset_id"] == dataset_id and i["tenant_id"] == tenant]


@router.patch("/qa-items/{qa_id}")
async def patch_qa(qa_id: str, body: dict[str, Any], tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    try:
        return e.patch_qa_item(qa_id, tenant_id=tenant, update=body)
    except KeyError as exc:
        raise APIError("NOT_FOUND", str(exc), status_code=404) from exc


@router.post("/qa-items/{qa_id}/review")
async def review_qa(qa_id: str, body: dict[str, Any], tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    return e.patch_qa_item(qa_id, tenant_id=tenant, update={"review_status": body.get("decision", "approved")})


@router.get("/qa-items/{qa_id}/evidence")
async def qa_evidence(qa_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    qa = e.qa_items.get(qa_id)
    if not qa or qa["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "QA not found", status_code=404)
    return {
        "qa_id": qa_id,
        "evidence_quotes": qa.get("evidence_quotes"),
        "expected_element_ids": qa.get("expected_element_ids"),
        "expected_logical_unit_ids": qa.get("expected_logical_unit_ids"),
    }


# ---------- Evaluation ----------
@router.post("/evaluation-profiles")
async def create_eval_profile(body: dict[str, Any], tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    profile = EvaluationProfile(tenant_id=tenant, **{k: v for k, v in body.items() if k != "tenant_id"})
    if body.get("metrics"):
        profile.metrics = [MetricDefinition.model_validate(m) for m in body["metrics"]]
    # validate at least one enabled
    try:
        normalize_weights(profile.metrics)
    except ValueError as exc:
        raise APIError("EVAL_PROFILE_INVALID", str(exc), status_code=422) from exc
    e.eval_profiles[profile.evaluation_profile_id] = profile.model_dump()
    return profile.model_dump()


@router.patch("/evaluation-profiles/{profile_id}")
async def patch_eval_profile(profile_id: str, body: dict[str, Any], tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    profile = e.eval_profiles.get(profile_id)
    if not profile or profile["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Profile not found", status_code=404)
    profile.update(body)
    try:
        p = EvaluationProfile.model_validate(profile)
        normalize_weights(p.metrics)
    except ValueError as exc:
        raise APIError("EVAL_PROFILE_INVALID", str(exc), status_code=422) from exc
    e.eval_profiles[profile_id] = p.model_dump()
    return e.eval_profiles[profile_id]


@router.get("/evaluation-profiles")
async def list_eval_profiles(tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    return [p for p in e.eval_profiles.values() if p["tenant_id"] == tenant]


class ExperimentCreate(BaseModel):
    document_version_id: str
    chunk_plan_id: str
    name: Optional[str] = None


@router.post("/experiments")
async def create_experiment(body: ExperimentCreate, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    exp_id = new_id()
    exp = {
        "experiment_id": exp_id,
        "tenant_id": tenant,
        "document_version_id": body.document_version_id,
        "name": body.name or "Experiment",
        "chunk_plan_id": body.chunk_plan_id,
        "status": "draft",
        "round_number": 1,
        "snapshot": {},
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    e.experiments[exp_id] = exp
    return exp


@router.post("/experiments/{experiment_id}/evaluate")
async def evaluate(experiment_id: str, body: dict[str, Any] | None = None, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    body = body or {}
    try:
        return await e.evaluate_experiment(
            experiment_id, tenant_id=tenant,
            profile_id=body.get("evaluation_profile_id"),
            sink_profile_id=body.get("sink_profile_id"),
        )
    except Exception as exc:
        raise APIError("EVAL_FAILED", str(exc), status_code=400) from exc


@router.get("/evaluation-runs/{run_id}")
async def get_eval(run_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    run = e.eval_runs.get(run_id)
    if not run or run["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Evaluation run not found", status_code=404)
    return run


@router.get("/evaluation-runs/{run_id}/metrics")
async def eval_metrics(run_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    run = e.eval_runs.get(run_id)
    if not run or run["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Evaluation run not found", status_code=404)
    return {
        "metrics": (run.get("result") or {}).get("metrics"),
        "composite_retrieval_score": run.get("composite_retrieval_score"),
        "evaluation_accuracy": run.get("composite_retrieval_score"),
        "accepted": run.get("accepted"),
    }


@router.get("/evaluation-runs/{run_id}/query-results")
async def eval_queries(run_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    run = e.eval_runs.get(run_id)
    if not run or run["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Evaluation run not found", status_code=404)
    return run.get("query_results") or {}


@router.get("/evaluation-runs/{run_id}/failures")
async def eval_failures(run_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    run = e.eval_runs.get(run_id)
    if not run or run["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Evaluation run not found", status_code=404)
    return run.get("failures") or []


@router.get("/evaluation-runs/{run_id}/comparison")
async def eval_comparison(run_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    run = e.eval_runs.get(run_id)
    if not run or run["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Evaluation run not found", status_code=404)
    others = [r for r in e.eval_runs.values() if r["tenant_id"] == tenant and r["evaluation_run_id"] != run_id]
    best = max(others, key=lambda r: r.get("composite_retrieval_score") or 0) if others else None
    prior = others[-1] if others else None
    return {
        "current": {"id": run_id, "score": run.get("composite_retrieval_score"), "accepted": run.get("accepted")},
        "prior": {"id": prior["evaluation_run_id"], "score": prior.get("composite_retrieval_score")} if prior else None,
        "best": {"id": best["evaluation_run_id"], "score": best.get("composite_retrieval_score")} if best else None,
        "stopping_recommendation": (run.get("result") or {}).get("stopping_recommendation"),
    }


# ---------- Optimization ----------
@router.post("/evaluation-runs/{run_id}/optimization-proposals")
async def create_proposal(run_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    try:
        return e.create_optimization_proposal(run_id, tenant_id=tenant)
    except Exception as exc:
        raise APIError("PROPOSAL_FAILED", str(exc), status_code=400) from exc


@router.get("/optimization-proposals/{proposal_id}")
async def get_proposal(proposal_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    p = e.proposals.get(proposal_id)
    if not p or p["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Proposal not found", status_code=404)
    return p


@router.patch("/optimization-proposals/{proposal_id}")
async def patch_proposal(proposal_id: str, body: dict[str, Any], tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    p = e.proposals.get(proposal_id)
    if not p or p["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Proposal not found", status_code=404)
    if "changes" in body:
        p["changes"] = body["changes"]
        p["status"] = "EDITED"
    return p


@router.post("/optimization-proposals/{proposal_id}/review")
async def review_proposal(proposal_id: str, body: dict[str, Any], tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    try:
        return e.review_proposal(proposal_id, tenant_id=tenant, decision=body.get("decision", "accept"), edited_changes=body.get("changes"))
    except Exception as exc:
        raise APIError("REVIEW_FAILED", str(exc), status_code=400) from exc


@router.post("/optimization-proposals/{proposal_id}/create-next-experiment")
async def next_experiment(proposal_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    """Explicit human action required — never automatic."""
    try:
        return e.create_next_experiment(proposal_id, tenant_id=tenant)
    except Exception as exc:
        raise APIError("NEXT_EXPERIMENT_FAILED", str(exc), status_code=400) from exc


# ---------- Connections ----------
class LLMProfileIn(BaseModel):
    name: str
    provider: str
    model: str = "gpt-4o-mini"
    base_url: Optional[str] = None
    deployment_name: Optional[str] = None
    auth_mode: str = "api_key"
    api_key: Optional[str] = None  # write-only


@router.get("/llm-profiles")
async def list_llm(tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    return [p for p in e.llm_profiles.values() if p.get("tenant_id") == tenant]


@router.post("/llm-profiles")
async def create_llm(body: LLMProfileIn, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    profile = LLMProfile(tenant_id=tenant, name=body.name, provider=body.provider, model=body.model,
                         base_url=body.base_url, deployment_name=body.deployment_name, auth_mode=body.auth_mode)
    secret = body.api_key
    if secret:
        ref = f"cred_{profile.llm_profile_id}"
        profile.credential_ref = ref
        e.secrets[ref] = secret
    e.gateway.register_profile(profile, secret=secret)
    public = e.gateway.public_profile(profile)
    e.llm_profiles[profile.llm_profile_id] = public
    return public  # never returns secret


@router.post("/llm-profiles/{profile_id}/test")
async def test_llm(profile_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    profile = e.llm_profiles.get(profile_id)
    if not profile or profile.get("tenant_id") != tenant:
        raise APIError("NOT_FOUND", "Profile not found", status_code=404)
    resp = await e.gateway.complete(task="generic", messages=[{"role": "user", "content": "ping"}], response_json=True, profile_id=profile_id)
    return {"ok": True, "provider": resp.provider, "request_id": resp.request_id, "latency_ms": resp.latency_ms}


@router.get("/embedding-profiles")
async def list_emb(tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    return [p for p in e.embedding_profiles.values() if p.get("tenant_id") == tenant]


@router.post("/embedding-profiles")
async def create_emb(body: dict[str, Any], tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    secret = body.pop("api_key", None)
    profile = EmbeddingProfile(tenant_id=tenant, **body)
    if secret:
        ref = f"cred_{profile.embedding_profile_id}"
        profile.credential_ref = ref
        e.secrets[ref] = secret
    e.gateway.register_embedding_profile(profile, secret=secret)
    data = profile.model_dump()
    # never expose secret
    e.embedding_profiles[profile.embedding_profile_id] = data
    return data


@router.post("/embedding-profiles/{profile_id}/test")
async def test_emb(profile_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    vecs = await e.gateway.embed(texts=["ping"], embedding_profile_id=profile_id)
    return {"ok": True, "dimensions": vecs.dimensions, "provider": vecs.provider, "request_id": vecs.request_id}


@router.get("/vector-sink-profiles")
async def list_sinks(tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    out = []
    for p in e.sink_profiles.values():
        if p.get("tenant_id") != tenant:
            continue
        d = dict(p)
        d["has_credential"] = bool(d.get("credential_ref") and d["credential_ref"] in e.secrets)
        # never return secret
        out.append(d)
    return out


@router.post("/vector-sink-profiles")
async def create_sink_profile(body: dict[str, Any], tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    secret = body.pop("api_key", None)
    profile = VectorSinkProfile(tenant_id=tenant, **body)
    if secret:
        ref = f"cred_{profile.vector_sink_profile_id}"
        profile.credential_ref = ref
        e.secrets[ref] = secret
    data = profile.model_dump()
    e.sink_profiles[profile.vector_sink_profile_id] = data
    return data


@router.post("/vector-sink-profiles/{profile_id}/test")
async def test_sink(profile_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    p = e.sink_profiles.get(profile_id)
    if not p or p.get("tenant_id") != tenant:
        raise APIError("NOT_FOUND", "Sink not found", status_code=404)
    sink = create_sink(VectorSinkProfile.model_validate(p), secret=e.secrets.get(p.get("credential_ref") or ""))
    return await sink.health_check()


@router.post("/vector-sink-profiles/{profile_id}/validate-schema")
async def validate_sink_schema(profile_id: str, body: dict[str, Any] | None = None, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    p = e.sink_profiles.get(profile_id)
    if not p:
        raise APIError("NOT_FOUND", "Sink not found", status_code=404)
    sink = create_sink(VectorSinkProfile.model_validate(p), secret=e.secrets.get(p.get("credential_ref") or ""))
    dims = (body or {}).get("expected_vector_size", 384)
    return await sink.validate_schema(expected_vector_size=dims)


@router.post("/vector-sink-profiles/{profile_id}/sample-upsert")
async def sample_upsert(profile_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    from vector_adapters import CanonicalVectorRecord
    p = e.sink_profiles.get(profile_id)
    if not p:
        raise APIError("NOT_FOUND", "Sink not found", status_code=404)
    sink = create_sink(VectorSinkProfile.model_validate(p), secret=e.secrets.get(p.get("credential_ref") or ""))
    vecs = await e.gateway.embed(texts=["sample"], embedding_profile_id=next(iter(e.embedding_profiles), None))
    await sink.ensure_collection(vector_size=vecs.dimensions or 384)
    rec = CanonicalVectorRecord(
        chunk_id=new_id(), chunk_run_id="sample", document_id="sample", document_version_id="sample",
        tenant_id=tenant, content="sample", embedding_text="sample", vector=vecs.vectors[0],
    )
    return await sink.upsert([rec])


@router.post("/vector-sink-profiles/{profile_id}/sample-search")
async def sample_search(profile_id: str, body: dict[str, Any] | None = None, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    p = e.sink_profiles.get(profile_id)
    if not p:
        raise APIError("NOT_FOUND", "Sink not found", status_code=404)
    sink = create_sink(VectorSinkProfile.model_validate(p), secret=e.secrets.get(p.get("credential_ref") or ""))
    q = (body or {}).get("query", "sample")
    if p["sink_type"] == "dify":
        hits = await sink.search(query_text=q, top_k=3)
    else:
        vecs = await e.gateway.embed(texts=[q], embedding_profile_id=next(iter(e.embedding_profiles), None))
        hits = await sink.search(query_vector=vecs.vectors[0], top_k=3)
    return [h.model_dump() for h in hits]


# ---------- Indexing ----------
@router.get("/indexing-runs/{run_id}")
async def get_indexing(run_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    run = e.indexing_runs.get(run_id)
    if not run or run["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Indexing run not found", status_code=404)
    return run


@router.get("/indexing-runs/{run_id}/targets")
async def indexing_targets(run_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    run = e.indexing_runs.get(run_id)
    if not run or run["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Indexing run not found", status_code=404)
    return [e.indexing_targets[t] for t in run.get("targets", [])]


@router.post("/indexing-runs/{run_id}/retry")
async def retry_indexing(run_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    run = e.indexing_runs.get(run_id)
    if not run or run["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Indexing run not found", status_code=404)
    run["status"] = "PENDING"
    return e.execute_indexing_run(run_id)


@router.post("/indexing-runs/{run_id}/cancel")
async def cancel_indexing(run_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    run = e.indexing_runs.get(run_id)
    if not run or run["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Indexing run not found", status_code=404)
    run["status"] = "CANCELLED"
    return run


# ---------- Audit ----------
@router.get("/audit-events")
async def audit_events(tenant: str = Depends(_tenant), entity_type: Optional[str] = None, entity_id: Optional[str] = None):
    store = get_audit_store()
    return [ev.model_dump(mode="json") for ev in store.list_events(tenant_id=tenant, entity_type=entity_type, entity_id=entity_id)]


@router.get("/documents/{document_id}/strategy-history")
async def doc_strategy_history(document_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    return [h for h in e.strategy_history if h["tenant_id"] == tenant]


@router.get("/logical-units/{unit_id}/strategy-history")
async def unit_strategy_history(unit_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    return [h for h in e.strategy_history if h["tenant_id"] == tenant and h.get("entity_id") == unit_id]


@router.get("/experiments/{experiment_id}/reproduction-manifest")
async def reproduction_manifest(experiment_id: str, tenant: str = Depends(_tenant)):
    store = get_audit_store()
    m = store.get_reproduction(experiment_id)
    if not m or m.tenant_id != tenant:
        raise APIError("NOT_FOUND", "Reproduction manifest not found", status_code=404)
    return m.model_dump(mode="json")


# ---------- Visual ----------
@router.post("/document-versions/{version_id}/visual-process")
async def visual_process(version_id: str, body: dict[str, Any] | None = None, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    from visual_processing import process_visual
    from canonical_schemas.visual import VisualProcessingPolicy
    body = body or {}
    policy = VisualProcessingPolicy.model_validate(body.get("policy") or {})
    elements = [el for el in e.elements.values() if el["document_version_id"] == version_id and el.get("element_type") in ("image", "IMAGE")]
    results = []
    for el in elements or [None]:
        result = process_visual(
            tenant_id=tenant,
            document_version_id=version_id,
            source_element_id=el["element_id"] if el else None,
            image_path=None,
            existing_svg=body.get("existing_svg"),
            native_vectors=body.get("native_vectors"),
            image_kind=body.get("image_kind", "diagram"),
            policy=policy,
            scene_graph_proposal=body.get("scene_graph"),
            ocr_text=(el or {}).get("text") if el and el.get("element_type") == "ocr_text" else body.get("ocr_text"),
            caption=body.get("caption"),
        )
        for art in result["artifacts"]:
            e.visual_artifacts[art.visual_artifact_id] = art.model_dump(mode="json")
        results.append({
            "strategy": result.get("strategy"),
            "warnings": result.get("warnings"),
            "artifacts": [a.model_dump(mode="json") for a in result["artifacts"]],
            "quality": result["quality"].model_dump() if result.get("quality") else None,
        })
    return {"results": results}


@router.get("/visual-artifacts/{artifact_id}")
async def get_visual(artifact_id: str, tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    art = e.visual_artifacts.get(artifact_id)
    if not art or art["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Artifact not found", status_code=404)
    # Only return sanitized SVG path for preview
    return art


@router.post("/visual-artifacts/{artifact_id}/review")
async def review_visual(artifact_id: str, body: dict[str, Any], tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    art = e.visual_artifacts.get(artifact_id)
    if not art or art["tenant_id"] != tenant:
        raise APIError("NOT_FOUND", "Artifact not found", status_code=404)
    art["review_status"] = body.get("decision", "approved")
    art["review_notes"] = body.get("notes", "")
    return art


# ---------- Dashboard helpers ----------
@router.get("/dashboard")
async def dashboard(tenant: str = Depends(_tenant), e: Engine = Depends(_eng)):
    return {
        "documents": len([d for d in e.documents.values() if d["tenant_id"] == tenant]),
        "chunk_runs": len([r for r in e.chunk_runs.values() if r["tenant_id"] == tenant]),
        "experiments": len([x for x in e.experiments.values() if x["tenant_id"] == tenant]),
        "evaluation_runs": len([x for x in e.eval_runs.values() if x["tenant_id"] == tenant]),
        "indexing_runs": len([x for x in e.indexing_runs.values() if x["tenant_id"] == tenant]),
        "qa_items": len([x for x in e.qa_items.values() if x["tenant_id"] == tenant]),
    }
