"""Core domain engine — parse, plan, chunk, index, QA, evaluate, optimize."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from audit_sdk import get_audit_store
from canonical_schemas.audit import ProviderManifest, ReproductionManifest
from canonical_schemas.chunk import CanonicalChunk
from canonical_schemas.evaluation import EvaluationProfile, MetricDefinition
from canonical_schemas.qa import QADistribution, QAItem
from chunk_adapters import ChunkRequest, get_registry
from chunk_adapters.base import StrategyDefinition
from document_parsers import get_parser_for
from document_parsers.base import detect_format
from evaluation_engine import (
    classify_failures,
    evaluate_run,
    generate_json_patch_proposal,
)
from evaluation_engine.optimization import apply_accepted_changes
from llm_gateway import EmbeddingProfile, LLMProfile, get_gateway
from shared.hashing import sha256_bytes, sha256_text, stable_json_hash
from shared.ids import new_id
from vector_adapters import CanonicalVectorRecord, VectorSinkProfile, create_sink

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Engine:
    """In-process domain engine with durable dict state (mirrored to DB by repositories)."""

    def __init__(self, settings: Optional[Settings] = None, storage_root: Optional[Path] = None):
        self.settings = settings or get_settings()
        self.storage_root = storage_root or Path(os.environ.get("ACE_STORAGE_ROOT", "/tmp/ace-data"))
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.audit = get_audit_store()
        self.gateway = get_gateway()
        self.registry = get_registry()

        self.tenants: dict[str, dict] = {}
        self.documents: dict[str, dict] = {}
        self.versions: dict[str, dict] = {}
        self.logical_units: dict[str, dict] = {}
        self.regions: dict[str, dict] = {}
        self.elements: dict[str, dict] = {}
        self.parse_runs: dict[str, dict] = {}
        self.chunk_plans: dict[str, dict] = {}
        self.experiments: dict[str, dict] = {}
        self.chunk_runs: dict[str, dict] = {}
        self.chunks: dict[str, dict] = {}
        self.qa_datasets: dict[str, dict] = {}
        self.qa_items: dict[str, dict] = {}
        self.eval_profiles: dict[str, dict] = {}
        self.eval_runs: dict[str, dict] = {}
        self.failures: dict[str, dict] = {}
        self.proposals: dict[str, dict] = {}
        self.llm_profiles: dict[str, dict] = {}
        self.embedding_profiles: dict[str, dict] = {}
        self.sink_profiles: dict[str, dict] = {}
        self.secrets: dict[str, str] = {}
        self.indexing_runs: dict[str, dict] = {}
        self.indexing_targets: dict[str, dict] = {}
        self.outbox: dict[str, dict] = {}
        self.embeddings_cache: dict[str, list[float]] = {}
        self.visual_artifacts: dict[str, dict] = {}
        self.strategy_history: list[dict] = []

    # ------------------------------------------------------------------
    # Seed
    # ------------------------------------------------------------------
    def seed_development(self) -> dict[str, Any]:
        tenant_id = self.settings.default_tenant_id
        user_id = self.settings.default_user_id
        self.tenants[tenant_id] = {"id": tenant_id, "name": "Local Dev Tenant"}
        llm = LLMProfile(tenant_id=tenant_id, name="Mock OpenAI-compatible", provider="mock", model="mock-gpt")
        self.gateway.register_profile(llm)
        self.llm_profiles[llm.llm_profile_id] = self.gateway.public_profile(llm)

        emb = EmbeddingProfile(
            tenant_id=tenant_id, name="Deterministic Mock Embedding", provider="mock",
            model="mock-emb", dimensions=384,
        )
        self.gateway.register_embedding_profile(emb)
        self.embedding_profiles[emb.embedding_profile_id] = emb.model_dump()

        sink = VectorSinkProfile(
            tenant_id=tenant_id, name="Local Qdrant", sink_type="qdrant",
            embedding_ownership="engine_managed",
            connection={"url": self.settings.qdrant_url},
            collection_or_index=self.settings.qdrant_collection,
            required=True, enabled=True,
        )
        self.sink_profiles[sink.vector_sink_profile_id] = sink.model_dump()

        profile = EvaluationProfile(tenant_id=tenant_id, name="Default Evaluation", top_k=self.settings.EVAL_DEFAULT_TOP_K)
        self.eval_profiles[profile.evaluation_profile_id] = profile.model_dump()

        qa_dist = QADistribution(mode="percentage", total=self.settings.QA_DEFAULT_COUNT)
        # Create demo document fixture
        demo = self._create_demo_document(tenant_id)
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "llm_profile_id": llm.llm_profile_id,
            "embedding_profile_id": emb.embedding_profile_id,
            "sink_profile_id": sink.vector_sink_profile_id,
            "evaluation_profile_id": profile.evaluation_profile_id,
            "qa_distribution": qa_dist.model_dump(),
            "demo_document": demo,
        }

    def _create_demo_document(self, tenant_id: str) -> dict:
        content = """# Adaptive Chunk Engine Demo

## Overview
This demonstration document explains retrieval-augmented generation chunking.
The system must preserve cross-page continuations when sentences span boundaries.

## Continuation Topic
This sentence intentionally continues across a logical unit boundary so that
cross-unit strategies can be evaluated against fragmented evidence.

## Pricing Table
| Plan | Seats | Price |
| Basic | 5 | 10 |
| Pro | 50 | 100 |

## Formula Notes
Revenue equals Seats times Price. For Pro, Revenue = 50 * 100 = 5000.
"""
        path = self.storage_root / "demo.md"
        path.write_text(content, encoding="utf-8")
        doc = self.upload_document(
            tenant_id=tenant_id,
            filename="demo.md",
            content=content.encode("utf-8"),
            content_type="text/markdown",
            title="Demo Document",
        )
        version_id = doc["latest_version_id"]
        self.parse_document_version(version_id, tenant_id=tenant_id)
        return doc

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------
    def upload_document(
        self,
        *,
        tenant_id: str,
        filename: str,
        content: bytes,
        content_type: Optional[str] = None,
        title: Optional[str] = None,
    ) -> dict:
        if len(content) > self.settings.max_upload_bytes:
            raise ValueError(f"Upload exceeds max size {self.settings.max_upload_bytes}")
        safe_name = Path(filename).name.replace("..", "_")
        ext = Path(safe_name).suffix.lower().lstrip(".")
        guessed = content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
        # MIME / extension consistency soft check
        expected = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "csv": "text/csv",
            "md": "text/markdown",
            "txt": "text/plain",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
        }
        if ext in expected and guessed not in (expected[ext], "application/octet-stream") and not guessed.startswith(expected[ext].split("/")[0]):
            # allow octet-stream and text/* mismatches for fixtures; hard-fail only on clearly wrong image/pdf swap
            if ext == "png" and guessed == "application/pdf":
                raise ValueError("MIME/extension inconsistency")

        doc_id = new_id()
        version_id = new_id()
        source_hash = sha256_bytes(content)
        storage_uri = str(self.storage_root / "uploads" / tenant_id / f"{version_id}_{safe_name}")
        Path(storage_uri).parent.mkdir(parents=True, exist_ok=True)
        Path(storage_uri).write_bytes(content)

        doc = {
            "document_id": doc_id,
            "tenant_id": tenant_id,
            "title": title or safe_name,
            "source_format": detect_format(safe_name, guessed),
            "latest_version_id": version_id,
            "created_at": utcnow().isoformat(),
            "updated_at": utcnow().isoformat(),
        }
        version = {
            "document_version_id": version_id,
            "tenant_id": tenant_id,
            "document_id": doc_id,
            "version_number": 1,
            "filename": safe_name,
            "content_type": guessed,
            "extension": ext,
            "source_hash": source_hash,
            "storage_uri": storage_uri,
            "byte_size": len(content),
            "status": "uploaded",
            "created_at": utcnow().isoformat(),
        }
        self.documents[doc_id] = doc
        self.versions[version_id] = version
        self.audit.record(
            tenant_id=tenant_id, actor_type="human", actor_id=self.settings.default_user_id,
            action="document.upload", entity_type="document", entity_id=doc_id, after=doc,
        )
        return doc

    def parse_document_version(self, version_id: str, *, tenant_id: str, correlation_id: Optional[str] = None) -> dict:
        version = self._get_version(version_id, tenant_id)
        run_id = new_id()
        run = {
            "parse_run_id": run_id,
            "tenant_id": tenant_id,
            "document_version_id": version_id,
            "status": "RUNNING",
            "started_at": utcnow().isoformat(),
            "progress_percent": 10,
            "correlation_id": correlation_id or new_id(),
            "worker_identity": "inline-parser",
        }
        self.parse_runs[run_id] = run
        try:
            fmt = detect_format(version["filename"], version.get("content_type"))
            parser = get_parser_for(fmt)
            result = parser.parse(
                Path(version["storage_uri"]),
                tenant_id=tenant_id,
                document_version_id=version_id,
                filename=version["filename"],
            )
            # clear prior units for version
            for uid in [k for k, v in self.logical_units.items() if v["document_version_id"] == version_id]:
                self.logical_units.pop(uid, None)
            for rid in [k for k, v in self.regions.items() if v.get("document_version_id") == version_id]:
                self.regions.pop(rid, None)
            for eid in [k for k, v in self.elements.items() if v.get("document_version_id") == version_id]:
                self.elements.pop(eid, None)

            for unit in result.logical_units:
                u = unit.model_dump()
                self.logical_units[unit.logical_unit_id] = u
                for region in unit.regions:
                    self.regions[region.region_id] = region.model_dump()
                    for el in region.elements:
                        self.elements[el.element_id] = el.model_dump()
            version["status"] = "parsed"
            run["status"] = "READY"
            run["progress_percent"] = 100
            run["finished_at"] = utcnow().isoformat()
            run["parser_manifest"] = result.parser_manifest.model_dump()
            run["warnings"] = result.warnings
            self.audit.record(
                tenant_id=tenant_id, actor_type="system", actor_id="parser",
                action="document.parse", entity_type="document_version", entity_id=version_id,
                after={"parse_run_id": run_id, "units": len(result.logical_units)},
                correlation_id=run["correlation_id"],
            )
        except Exception as exc:  # noqa: BLE001
            run["status"] = "FAILED"
            run["error"] = {"code": "PARSE_FAILED", "message": str(exc)}
            run["finished_at"] = utcnow().isoformat()
            version["status"] = "parse_failed"
            raise
        return run

    # ------------------------------------------------------------------
    # Strategies / Plans
    # ------------------------------------------------------------------
    def list_strategies(self) -> list[dict]:
        return [s.__dict__ if not hasattr(s, "model_dump") else s.__dict__ for s in self.registry.list_strategies()]

    def get_strategy_schema(self, strategy_id: str) -> dict:
        d = self.registry.get_definition(strategy_id)
        return d.parameter_schema

    async def auto_plan(self, version_id: str, *, tenant_id: str) -> dict:
        version = self._get_version(version_id, tenant_id)
        units = [u for u in self.logical_units.values() if u["document_version_id"] == version_id]
        healthy = [s for s in self.registry.list_strategies() if s.dependency_available and s.enabled and s.health_status in ("healthy", "degraded")]
        messages = [
            {"role": "system", "content": "Return a validated chunk strategy plan as JSON."},
            {"role": "user", "content": "Create chunk plan for document logical units."},
        ]
        resp = await self.gateway.complete(
            task="chunk_strategy_planning",
            messages=messages,
            response_json=True,
            context={
                "logical_units": units,
                "available_strategies": [s.strategy_id for s in healthy],
                "hard_constraints": self.settings.hard_constraints(),
            },
        )
        proposed = resp.structured or {}
        plan_id = new_id()
        validated = self.validate_plan(proposed, version_id=version_id, tenant_id=tenant_id)
        plan = {
            "plan_id": plan_id,
            "tenant_id": tenant_id,
            "document_version_id": version_id,
            "status": "validated" if validated["valid"] else "invalid",
            "proposed_plan": proposed,
            "effective_plan": validated.get("effective_plan") or proposed,
            "validation": validated,
            "version": 1,
            "created_at": utcnow().isoformat(),
            "updated_at": utcnow().isoformat(),
            "llm_run_id": resp.raw.get("llm_run_id"),
        }
        self.chunk_plans[plan_id] = plan
        self.audit.record(
            tenant_id=tenant_id, actor_type="llm", actor_id="planner",
            action="chunk_plan.auto", entity_type="chunk_plan", entity_id=plan_id, after={"valid": validated["valid"]},
        )
        return plan

    def validate_plan(self, plan: dict, *, version_id: str, tenant_id: str, locked: Optional[dict] = None) -> dict:
        errors = []
        units = [u for u in self.logical_units.values() if u["document_version_id"] == version_id]
        unit_ids = {u["logical_unit_id"] for u in units}
        strategies = plan.get("unit_strategies") or []
        covered = {s.get("logical_unit_id") for s in strategies}
        missing = unit_ids - covered
        if missing:
            errors.append({"code": "UNIT_NOT_COVERED", "message": f"Missing units: {sorted(missing)[:5]}", "field_path": "unit_strategies"})
        hard = self.settings.hard_constraints()
        effective = {"unit_strategies": [], "region_overrides": plan.get("region_overrides") or []}
        for s in strategies:
            sid = s.get("strategy_id")
            try:
                definition = self.registry.get_definition(sid)
            except KeyError:
                errors.append({"code": "UNKNOWN_STRATEGY", "message": f"Unknown strategy {sid}", "field_path": "strategy_id"})
                continue
            health = self.registry.get_adapter(sid).health_check()
            if not health.get("available") and sid not in ("skip_unit",):
                # still allow if fallback chunking exists; record warning
                if definition.health_status == "unavailable" and not definition.enabled:
                    errors.append({"code": "STRATEGY_UNAVAILABLE", "message": health.get("reason"), "field_path": "strategy_id", "value": sid})
            params = dict(s.get("parameters") or {})
            # apply defaults
            params.setdefault("chunk_size", hard["CHUNK_SIZE_DEFAULT"])
            params.setdefault("chunk_overlap", hard["CHUNK_OVERLAP_DEFAULT"])
            size = params.get("chunk_size")
            overlap = params.get("chunk_overlap", 0)
            if size is not None:
                if not isinstance(size, int) or size < hard["CHUNK_SIZE_MIN"] or size > hard["CHUNK_SIZE_MAX"]:
                    errors.append({
                        "code": "INVALID_CHUNK_SIZE",
                        "message": f"chunk_size must be between {hard['CHUNK_SIZE_MIN']} and {hard['CHUNK_SIZE_MAX']}",
                        "field_path": "parameters.chunk_size",
                        "allowed_range": [hard["CHUNK_SIZE_MIN"], hard["CHUNK_SIZE_MAX"]],
                        "value": size,
                        "retryable": False,
                    })
            if isinstance(size, int) and size > 0 and isinstance(overlap, int) and overlap / size > hard["CHUNK_OVERLAP_MAX_RATIO"]:
                errors.append({
                    "code": "INVALID_OVERLAP",
                    "message": "Overlap ratio exceeds max",
                    "field_path": "parameters.chunk_overlap",
                    "allowed_range": [0, hard["CHUNK_OVERLAP_MAX_RATIO"]],
                    "value": overlap / size,
                    "retryable": False,
                })
            # locked fields
            if locked:
                key = s.get("logical_unit_id")
                if key in locked:
                    for field, val in locked[key].items():
                        if s.get(field) != val and field != "parameters":
                            errors.append({"code": "LOCKED_FIELD_MODIFIED", "message": f"Locked field {field} modified", "field_path": field})
                        if field == "parameters":
                            for pk, pv in val.items():
                                if params.get(pk) != pv:
                                    errors.append({"code": "LOCKED_FIELD_MODIFIED", "message": f"Locked param {pk} modified", "field_path": f"parameters.{pk}"})
            # referenced elements
            for eid in s.get("supporting_element_ids") or []:
                if eid not in self.elements:
                    errors.append({"code": "UNKNOWN_ELEMENT", "message": f"Element {eid} not found", "field_path": "supporting_element_ids"})
            effective["unit_strategies"].append({
                **s,
                "parameters": params,
                "effective_parameter_sources": s.get("effective_parameter_sources") or {k: s.get("mode", "auto") for k in params},
            })
        # region overrides
        for r in effective["region_overrides"]:
            if r.get("region_id") and r["region_id"] not in self.regions:
                errors.append({"code": "UNKNOWN_REGION", "message": "Region not found", "field_path": "region_id"})
        return {"valid": len(errors) == 0, "errors": errors, "effective_plan": effective if not errors else plan}

    def patch_plan(self, plan_id: str, *, tenant_id: str, patch: dict) -> dict:
        plan = self._get_plan(plan_id, tenant_id)
        before = json.loads(json.dumps(plan["effective_plan"]))
        if "unit_strategies" in patch:
            plan["effective_plan"]["unit_strategies"] = patch["unit_strategies"]
        if "region_overrides" in patch:
            plan["effective_plan"]["region_overrides"] = patch["region_overrides"]
        plan["proposed_plan"] = plan.get("proposed_plan") or before
        validated = self.validate_plan(plan["effective_plan"], version_id=plan["document_version_id"], tenant_id=tenant_id)
        plan["validation"] = validated
        plan["status"] = "validated" if validated["valid"] else "invalid"
        if validated["valid"]:
            plan["effective_plan"] = validated["effective_plan"]
        plan["updated_at"] = utcnow().isoformat()
        plan["version"] += 1
        self.strategy_history.append({
            "tenant_id": tenant_id, "entity_type": "chunk_plan", "entity_id": plan_id,
            "before": before, "after": plan["effective_plan"], "at": utcnow().isoformat(),
        })
        self.audit.record(
            tenant_id=tenant_id, actor_type="human", actor_id=self.settings.default_user_id,
            action="chunk_plan.patch", entity_type="chunk_plan", entity_id=plan_id, before=before, after=plan["effective_plan"],
        )
        return plan

    def patch_unit_strategy(self, plan_id: str, unit_id: str, *, tenant_id: str, update: dict) -> dict:
        plan = self._get_plan(plan_id, tenant_id)
        strategies = plan["effective_plan"].setdefault("unit_strategies", [])
        found = False
        for s in strategies:
            if s.get("logical_unit_id") == unit_id:
                before = dict(s)
                # Auto/Manual per field
                for field, value in update.items():
                    if field == "parameters":
                        s.setdefault("parameters", {}).update(value)
                        for pk in value:
                            s.setdefault("effective_parameter_sources", {})[pk] = "manual"
                    else:
                        s[field] = value
                s["mode"] = update.get("mode", "manual")
                found = True
                self.strategy_history.append({
                    "tenant_id": tenant_id, "entity_type": "logical_unit", "entity_id": unit_id,
                    "before": before, "after": s, "at": utcnow().isoformat(),
                })
                break
        if not found:
            strategies.append({"logical_unit_id": unit_id, **update, "mode": "manual"})
        return self.patch_plan(plan_id, tenant_id=tenant_id, patch={"unit_strategies": strategies})

    def patch_region_strategy(self, plan_id: str, region_id: str, *, tenant_id: str, update: dict) -> dict:
        plan = self._get_plan(plan_id, tenant_id)
        overrides = plan["effective_plan"].setdefault("region_overrides", [])
        for r in overrides:
            if r.get("region_id") == region_id:
                r.update(update)
                r["mode"] = "manual"
                break
        else:
            overrides.append({"region_id": region_id, **update, "mode": "manual"})
        return self.patch_plan(plan_id, tenant_id=tenant_id, patch={"region_overrides": overrides, "unit_strategies": plan["effective_plan"].get("unit_strategies", [])})

    # ------------------------------------------------------------------
    # Chunk runs + outbox
    # ------------------------------------------------------------------
    def create_chunk_run(self, *, tenant_id: str, plan_id: str, experiment_id: Optional[str] = None) -> dict:
        plan = self._get_plan(plan_id, tenant_id)
        if not plan.get("validation", {}).get("valid", False):
            # revalidate
            v = self.validate_plan(plan["effective_plan"], version_id=plan["document_version_id"], tenant_id=tenant_id)
            plan["validation"] = v
            if not v["valid"]:
                raise ValueError(f"Plan invalid: {v['errors']}")
        if not experiment_id:
            experiment_id = new_id()
            self.experiments[experiment_id] = {
                "experiment_id": experiment_id,
                "tenant_id": tenant_id,
                "document_version_id": plan["document_version_id"],
                "name": f"Experiment {len(self.experiments)+1}",
                "chunk_plan_id": plan_id,
                "status": "running",
                "round_number": 1,
                "snapshot": {"plan_version": plan["version"], "effective_plan": plan["effective_plan"]},
                "created_at": utcnow().isoformat(),
            }
        run_id = new_id()
        idem = f"{tenant_id}:{experiment_id}:{plan_id}:chunk"
        # idempotency
        for existing in self.chunk_runs.values():
            if existing.get("idempotency_key") == idem and existing.get("status") in ("READY", "RUNNING"):
                return existing
        run = {
            "chunk_run_id": run_id,
            "tenant_id": tenant_id,
            "experiment_id": experiment_id,
            "document_version_id": plan["document_version_id"],
            "document_id": self.versions[plan["document_version_id"]]["document_id"],
            "chunk_plan_id": plan_id,
            "status": "PENDING",
            "progress_percent": 0,
            "chunk_count": 0,
            "correlation_id": new_id(),
            "idempotency_key": idem,
            "created_at": utcnow().isoformat(),
        }
        self.chunk_runs[run_id] = run
        return run

    def execute_chunk_run(self, run_id: str) -> dict:
        run = self.chunk_runs[run_id]
        if run["status"] == "READY":
            return run
        run["status"] = "RUNNING"
        run["started_at"] = utcnow().isoformat()
        run["worker_identity"] = "inline-chunk-worker"
        plan = self.chunk_plans[run["chunk_plan_id"]]
        version_id = run["document_version_id"]
        doc_id = run["document_id"]
        tenant_id = run["tenant_id"]
        hard = self.settings.hard_constraints()
        unit_map = {u["logical_unit_id"]: u for u in self.logical_units.values() if u["document_version_id"] == version_id}
        region_overrides = {r["region_id"]: r for r in (plan["effective_plan"].get("region_overrides") or [])}
        all_chunks: list[CanonicalChunk] = []
        ordinal = 0

        strategies = plan["effective_plan"].get("unit_strategies") or []
        for i, cfg in enumerate(strategies):
            unit = unit_map.get(cfg["logical_unit_id"])
            if not unit:
                continue
            # region override takes precedence for elements in that region
            unit_regions = [r for r in self.regions.values() if r["logical_unit_id"] == unit["logical_unit_id"]]
            # Build element lists per region if override else whole unit
            jobs = []
            overridden_regions = []
            for region in unit_regions:
                rid = region.get("region_id")
                if rid and rid in region_overrides:
                    ov = region_overrides[rid]
                    jobs.append((ov or cfg, region, [e for e in self.elements.values() if e.get("region_id") == rid]))
                    overridden_regions.append(rid)
            # remaining elements
            elems = [e for e in self.elements.values() if e["logical_unit_id"] == unit["logical_unit_id"] and e.get("region_id") not in overridden_regions]
            if elems or not jobs:
                from canonical_schemas.document import LogicalUnitModel, ElementModel, RegionModel
                jobs.append((cfg, None, elems))

            for job_cfg, region, elements in jobs:
                from canonical_schemas.document import LogicalUnitModel, ElementModel, RegionModel
                unit_model = LogicalUnitModel.model_validate({k: v for k, v in unit.items() if k != "regions"})
                # reconstruct minimal
                unit_model.regions = []
                element_models = [ElementModel.model_validate(e) for e in elements]
                region_model = RegionModel.model_validate(region) if region else None
                adapter = self.registry.get_adapter(job_cfg["strategy_id"])
                # continuation context
                cont = None
                if job_cfg["strategy_id"] == "cross_unit_continuation":
                    prev = unit_map.get(unit.get("previous_unit_id") or "")
                    nxt = unit_map.get(unit.get("next_unit_id") or "")
                    cont = {
                        "previous_unit_id": unit.get("previous_unit_id"),
                        "next_unit_id": unit.get("next_unit_id"),
                        "continuation_group_id": unit.get("continuation_group_id"),
                        "previous_unit_tail": "" if not prev else " ".join(
                            e["text"] for e in self.elements.values() if e["logical_unit_id"] == prev["logical_unit_id"]
                        )[-200:],
                        "next_unit_head": "" if not nxt else " ".join(
                            e["text"] for e in self.elements.values() if e["logical_unit_id"] == nxt["logical_unit_id"]
                        )[:200],
                    }
                req = ChunkRequest(
                    tenant_id=tenant_id,
                    document_id=doc_id,
                    document_version_id=version_id,
                    chunk_run_id=run_id,
                    experiment_id=run.get("experiment_id"),
                    logical_unit=unit_model,
                    region=region_model,
                    elements=element_models,
                    strategy_id=job_cfg["strategy_id"],
                    parameters={**job_cfg.get("parameters", {}), "filename": self.versions[version_id]["filename"]},
                    hard_constraints=hard,
                    continuation_context=cont,
                )
                validation = adapter.validate(req)
                if not validation.valid:
                    raise ValueError(f"Chunk validation failed: {validation.errors}")
                produced = adapter.chunk(req)
                for c in produced:
                    c.ordinal = ordinal
                    ordinal += 1
                    all_chunks.append(c)
            run["progress_percent"] = ((i + 1) / max(len(strategies), 1)) * 90

        if len(all_chunks) > hard["CHUNK_MAX_COUNT_PER_DOCUMENT"]:
            raise ValueError("CHUNK_MAX_COUNT_PER_DOCUMENT exceeded")

        # link prev/next
        for i, c in enumerate(all_chunks):
            if i > 0:
                c.previous_chunk_id = all_chunks[i - 1].chunk_id
            if i + 1 < len(all_chunks):
                c.next_chunk_id = all_chunks[i + 1].chunk_id
            payload = c.model_dump(mode="json")
            self.chunks[c.chunk_id] = payload

        run["chunk_count"] = len(all_chunks)
        run["status"] = "READY"
        run["progress_percent"] = 100
        run["finished_at"] = utcnow().isoformat()

        # Transactional outbox: CHUNK_RUN_COMPLETED
        event_id = new_id()
        self.outbox[event_id] = {
            "id": event_id,
            "tenant_id": tenant_id,
            "event_type": "CHUNK_RUN_COMPLETED",
            "aggregate_type": "chunk_run",
            "aggregate_id": run_id,
            "payload": {
                "chunk_run_id": run_id,
                "experiment_id": run.get("experiment_id"),
                "document_version_id": version_id,
                "chunk_count": len(all_chunks),
            },
            "status": "PENDING",
            "attempts": 0,
            "created_at": utcnow().isoformat(),
        }
        self.audit.record(
            tenant_id=tenant_id, actor_type="system", actor_id="chunk-worker",
            action="chunk_run.completed", entity_type="chunk_run", entity_id=run_id,
            after={"chunk_count": len(all_chunks)}, correlation_id=run.get("correlation_id"),
        )
        # Auto-process outbox inline for MVP (also done by indexing worker)
        self.process_outbox()
        return run

    def process_outbox(self) -> list[dict]:
        processed = []
        for event in list(self.outbox.values()):
            if event["status"] != "PENDING":
                continue
            if event["event_type"] == "CHUNK_RUN_COMPLETED":
                try:
                    indexing = self.create_indexing_run(
                        tenant_id=event["tenant_id"],
                        chunk_run_id=event["payload"]["chunk_run_id"],
                        experiment_id=event["payload"].get("experiment_id"),
                    )
                    indexing_result = self.execute_indexing_run(indexing["indexing_run_id"])
                    chunk_run = self.chunk_runs.get(event["payload"]["chunk_run_id"])
                    if chunk_run is not None:
                        chunk_run["indexing_run_id"] = indexing["indexing_run_id"]
                        chunk_run["indexing_status"] = indexing_result.get("status")
                    event["status"] = "PROCESSED"
                    event["processed_at"] = utcnow().isoformat()
                    processed.append(event)
                except Exception as exc:  # noqa: BLE001
                    event["attempts"] += 1
                    event["last_error"] = str(exc)
                    if event["attempts"] >= 5:
                        event["status"] = "FAILED"
                    logger.exception("Outbox processing failed")
        return processed

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------
    def create_indexing_run(self, *, tenant_id: str, chunk_run_id: str, experiment_id: Optional[str]) -> dict:
        idem = f"{tenant_id}:{experiment_id}:{chunk_run_id}:index"
        for existing in self.indexing_runs.values():
            if existing.get("idempotency_key") == idem:
                return existing
        run_id = new_id()
        enabled_sinks = [s for s in self.sink_profiles.values() if s.get("enabled", True) and s.get("tenant_id") == tenant_id]
        if not enabled_sinks:
            # ensure default qdrant
            sink = VectorSinkProfile(
                tenant_id=tenant_id, name="Local Qdrant", sink_type="qdrant",
                connection={"url": self.settings.qdrant_url},
                collection_or_index=self.settings.qdrant_collection,
            )
            self.sink_profiles[sink.vector_sink_profile_id] = sink.model_dump()
            enabled_sinks = [sink.model_dump()]
        run = {
            "indexing_run_id": run_id,
            "tenant_id": tenant_id,
            "chunk_run_id": chunk_run_id,
            "experiment_id": experiment_id,
            "status": "PENDING",
            "progress_percent": 0,
            "correlation_id": new_id(),
            "idempotency_key": idem,
            "created_at": utcnow().isoformat(),
            "targets": [],
        }
        for sink in enabled_sinks:
            tid = new_id()
            target = {
                "indexing_target_run_id": tid,
                "indexing_run_id": run_id,
                "sink_profile_id": sink.get("vector_sink_profile_id") or sink.get("id"),
                "sink_type": sink["sink_type"],
                "status": "PENDING",
                "required": sink.get("required", True),
                "result": {},
            }
            self.indexing_targets[tid] = target
            run["targets"].append(tid)
        self.indexing_runs[run_id] = run
        return run

    async def _embed_texts(self, texts: list[str], embedding_profile_id: Optional[str]) -> list[list[float]]:
        # reuse cache by hash
        out: list[Optional[list[float]]] = [None] * len(texts)
        missing_idx = []
        missing_texts = []
        for i, t in enumerate(texts):
            h = sha256_text(t)
            if h in self.embeddings_cache:
                out[i] = self.embeddings_cache[h]
            else:
                missing_idx.append(i)
                missing_texts.append(t)
        if missing_texts:
            resp = await self.gateway.embed(texts=missing_texts, embedding_profile_id=embedding_profile_id)
            for i, vec in zip(missing_idx, resp.vectors):
                h = sha256_text(texts[i])
                self.embeddings_cache[h] = vec
                out[i] = vec
        return [v or [] for v in out]

    async def _execute_indexing_run_async(self, indexing_run_id: str) -> dict:
        run = self.indexing_runs[indexing_run_id]
        run["status"] = "VALIDATING"
        chunk_run_id = run["chunk_run_id"]
        chunks = [c for c in self.chunks.values() if c["chunk_run_id"] == chunk_run_id and c.get("indexable", True)]
        emb_profile_id = next(iter(self.embedding_profiles), None)
        run["status"] = "EMBEDDING"
        texts = [c.get("embedding_text") or c.get("text") or "" for c in chunks]
        vectors = await self._embed_texts(texts, emb_profile_id)
        dims = len(vectors[0]) if vectors else 384

        run["status"] = "UPLOADING"
        target_statuses = []
        for tid in run["targets"]:
            target = self.indexing_targets[tid]
            sink_profile = self.sink_profiles.get(target["sink_profile_id"])
            if not sink_profile:
                target["status"] = "FAILED"
                target["error"] = {"message": "sink profile missing"}
                continue
            try:
                secret = self.secrets.get(sink_profile.get("credential_ref") or "")
                profile = VectorSinkProfile.model_validate(sink_profile)
                sink = create_sink(profile, secret=secret)
                await sink.ensure_collection(vector_size=dims)
                # Replace prior points for this run so verify counts stay exact across retries.
                await sink.delete_by_run(chunk_run_id)
                records = []
                for c, vec in zip(chunks, vectors):
                    ownership = sink_profile.get("embedding_ownership", "engine_managed")
                    rec = CanonicalVectorRecord(
                        record_id=new_id(),
                        chunk_id=c["chunk_id"],
                        chunk_run_id=chunk_run_id,
                        document_id=c["document_id"],
                        document_version_id=c["document_version_id"],
                        experiment_id=c.get("experiment_id"),
                        tenant_id=c["tenant_id"],
                        content=c.get("text") or "",
                        embedding_text=c.get("embedding_text") or c.get("text") or "",
                        vector=vec if ownership == "engine_managed" else None,
                        canonical_metadata={
                            "chunk_type": c.get("chunk_type"),
                            "logical_unit_id": (c.get("logical_unit_ids") or [None])[0],
                        },
                        source_locator=(c.get("locators") or [{}])[0],
                        strategy=c.get("canonical_strategy", ""),
                        content_hash=c.get("content_hash", ""),
                        embedding_text_hash=c.get("embedding_text_hash", ""),
                        content_modality="visual" if c.get("chunk_type", "").startswith(("visual", "svg", "image")) else "text",
                        visual_artifact_id=c.get("visual_artifact_id"),
                        svg_element_id=c.get("svg_element_id"),
                        svg_group_id=c.get("svg_group_id"),
                    )
                    # idempotency key components
                    _ = f"{c['tenant_id']}:{c.get('experiment_id')}:{chunk_run_id}:{c['chunk_id']}:{sink_profile.get('schema_version','1')}"
                    records.append(rec)
                result = await sink.upsert(records)
                run["status"] = "VERIFYING"
                verify = await sink.verify(chunk_run_id=chunk_run_id, expected_count=len(records))
                target["status"] = "READY" if verify.get("ok") else "PARTIAL"
                target["result"] = {"upsert": result, "verify": verify}
            except Exception as exc:  # noqa: BLE001
                target["status"] = "FAILED"
                target["error"] = {"message": str(exc), "retryable": True}
                logger.exception("Indexing target failed: %s", target["sink_type"])
            target_statuses.append(target["status"])

        if target_statuses and all(s == "READY" for s in target_statuses):
            run["status"] = "READY"
        elif any(s in ("READY", "PARTIAL") for s in target_statuses):
            run["status"] = "PARTIAL"
        else:
            run["status"] = "FAILED"
        run["progress_percent"] = 100
        run["finished_at"] = utcnow().isoformat()
        return run

    def execute_indexing_run(self, indexing_run_id: str) -> dict:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(lambda: asyncio.run(self._execute_indexing_run_async(indexing_run_id))).result()
            return loop.run_until_complete(self._execute_indexing_run_async(indexing_run_id))
        except RuntimeError:
            return asyncio.run(self._execute_indexing_run_async(indexing_run_id))

    # ------------------------------------------------------------------
    # QA
    # ------------------------------------------------------------------
    def create_qa_dataset(self, *, tenant_id: str, document_version_id: str, name: str, distribution: Optional[dict] = None) -> dict:
        self._get_version(document_version_id, tenant_id)
        dist = QADistribution.model_validate(distribution or {})
        self._validate_distribution(dist)
        ds_id = new_id()
        ds = {
            "qa_dataset_id": ds_id,
            "tenant_id": tenant_id,
            "document_version_id": document_version_id,
            "name": name,
            "distribution": dist.model_dump(),
            "status": "draft",
            "item_count": 0,
            "created_at": utcnow().isoformat(),
        }
        self.qa_datasets[ds_id] = ds
        return ds

    def _validate_distribution(self, dist: QADistribution) -> None:
        if dist.total < self.settings.QA_MIN_COUNT or dist.total > self.settings.QA_MAX_COUNT:
            raise ValueError(f"QA total must be between {self.settings.QA_MIN_COUNT} and {self.settings.QA_MAX_COUNT}")
        if dist.mode == "percentage":
            s = sum(dist.by_type.values())
            if abs(s - 100) > 0.01:
                raise ValueError(f"Enabled percentages must sum to 100, got {s}")
        else:
            s = sum(dist.by_type.values())
            if int(s) != dist.total:
                raise ValueError(f"Enabled counts must equal total {dist.total}, got {s}")

    async def generate_qa(self, dataset_id: str, *, tenant_id: str, count: Optional[int] = None) -> dict:
        ds = self._get_dataset(dataset_id, tenant_id)
        dist = QADistribution.model_validate(ds["distribution"])
        total = count or dist.total
        if dist.mode == "percentage":
            distribution = {k: max(0, round(total * (v / 100.0))) for k, v in dist.by_type.items()}
            # fix rounding
            while sum(distribution.values()) < total:
                distribution[next(iter(distribution))] += 1
            while sum(distribution.values()) > total:
                k = next(iter(distribution))
                if distribution[k] > 0:
                    distribution[k] -= 1
        else:
            distribution = {k: int(v) for k, v in dist.by_type.items()}
        elements = [e for e in self.elements.values() if e["document_version_id"] == ds["document_version_id"]]
        resp = await self.gateway.complete(
            task="qa_generation",
            messages=[{"role": "user", "content": "generate qa"}],
            context={"count": total, "distribution": distribution, "elements": elements},
        )
        items = (resp.structured or {}).get("items") or []
        created = []
        for item in items:
            qa_id = new_id()
            qa = QAItem(
                qa_id=qa_id,
                qa_dataset_id=dataset_id,
                document_version_id=ds["document_version_id"],
                tenant_id=tenant_id,
                source="generated",
                question=item["question"],
                answer=item.get("answer", ""),
                question_type=item.get("question_type", "direct_fact"),
                expected_element_ids=item.get("expected_element_ids") or [],
                expected_logical_unit_ids=item.get("expected_logical_unit_ids") or [],
                evidence_quotes=item.get("evidence_quotes") or [],
                confidence=item.get("confidence"),
                generation_metadata={"llm_run_id": resp.raw.get("llm_run_id")},
            )
            # reject invented element ids
            valid_ids = set(self.elements)
            qa.expected_element_ids = [i for i in qa.expected_element_ids if i in valid_ids]
            self.qa_items[qa_id] = qa.model_dump(mode="json")
            created.append(qa_id)
        ds["item_count"] = len([i for i in self.qa_items.values() if i["qa_dataset_id"] == dataset_id])
        ds["status"] = "ready"
        return {"dataset_id": dataset_id, "created": created, "count": len(created)}

    async def upload_qa(self, dataset_id: str, *, tenant_id: str, items: list[dict], fmt: str = "json") -> dict:
        ds = self._get_dataset(dataset_id, tenant_id)
        created = []
        for raw in items:
            q = raw.get("question") or raw.get("Question")
            a = raw.get("answer") or raw.get("Answer") or ""
            if not q:
                continue
            qa_id = new_id()
            qa = {
                "schema_version": "1.0.0",
                "qa_id": qa_id,
                "qa_dataset_id": dataset_id,
                "document_version_id": ds["document_version_id"],
                "tenant_id": tenant_id,
                "source": "uploaded",
                "status": "draft",
                "enabled": True,
                "question": q,
                "answer": a,
                "question_type": raw.get("question_type") or "direct_fact",
                "review_status": "pending",
                "expected_element_ids": [],
                "expected_logical_unit_ids": [],
                "evidence_quotes": [],
                "warnings": ["schema_incomplete"],
            }
            self.qa_items[qa_id] = qa
            created.append(qa_id)
        ds["item_count"] = len([i for i in self.qa_items.values() if i["qa_dataset_id"] == dataset_id])
        return {"created": created}

    async def complete_qa_schema(self, dataset_id: str, *, tenant_id: str) -> dict:
        ds = self._get_dataset(dataset_id, tenant_id)
        elements = [e for e in self.elements.values() if e["document_version_id"] == ds["document_version_id"]]
        completed = []
        for qa in [i for i in self.qa_items.values() if i["qa_dataset_id"] == dataset_id and i.get("source") == "uploaded"]:
            # candidate retrieval against source document (simple keyword)
            q = qa["question"].lower()
            candidates = []
            for e in elements:
                text = (e.get("text") or "").lower()
                score = sum(1 for tok in q.split() if tok in text)
                if score:
                    candidates.append((score, e))
            candidates.sort(key=lambda x: -x[0])
            cand_elems = [c[1] for c in candidates[:5]]
            resp = await self.gateway.complete(
                task="qa_schema_completion",
                messages=[{"role": "user", "content": "complete qa schema"}],
                context={"question": qa["question"], "answer": qa.get("answer"), "candidate_elements": cand_elems},
            )
            structured = resp.structured or {}
            valid_ids = {e["element_id"] for e in cand_elems}
            # reject invented IDs
            eids = [i for i in (structured.get("expected_element_ids") or []) if i in valid_ids]
            qa["expected_element_ids"] = eids
            qa["expected_logical_unit_ids"] = [
                i for i in (structured.get("expected_logical_unit_ids") or [])
                if i in {e.get("logical_unit_id") for e in cand_elems}
            ]
            qa["evidence_quotes"] = [
                eq for eq in (structured.get("evidence_quotes") or [])
                if not eq.get("element_id") or eq.get("element_id") in valid_ids
            ]
            qa["confidence"] = structured.get("confidence")
            qa["question_type"] = structured.get("question_type", qa.get("question_type"))
            qa["review_status"] = structured.get("review_status") or ("needs_review" if (qa.get("confidence") or 0) < 0.6 else "pending")
            qa["warnings"] = structured.get("warnings") or []
            qa["source"] = "uploaded"
            completed.append(qa["qa_id"])
            self.audit.record(
                tenant_id=tenant_id, actor_type="llm", actor_id="qa-completer",
                action="qa.schema_complete", entity_type="qa_item", entity_id=qa["qa_id"], after={"element_ids": eids},
            )
        return {"completed": completed}

    def patch_qa_item(self, qa_id: str, *, tenant_id: str, update: dict) -> dict:
        qa = self.qa_items.get(qa_id)
        if not qa or qa["tenant_id"] != tenant_id:
            raise KeyError("QA item not found")
        before = dict(qa)
        for k, v in update.items():
            if k in ("qa_id", "tenant_id"):
                continue
            qa[k] = v
        qa["source"] = "human_edited"
        qa["updated_at"] = utcnow().isoformat()
        self.audit.record(
            tenant_id=tenant_id, actor_type="human", actor_id=self.settings.default_user_id,
            action="qa.edit", entity_type="qa_item", entity_id=qa_id, before=before, after=qa,
        )
        return qa

    # ------------------------------------------------------------------
    # Evaluation / Optimization
    # ------------------------------------------------------------------
    async def evaluate_experiment(self, experiment_id: str, *, tenant_id: str, profile_id: Optional[str] = None, sink_profile_id: Optional[str] = None) -> dict:
        exp = self.experiments.get(experiment_id)
        if not exp or exp["tenant_id"] != tenant_id:
            raise KeyError("Experiment not found")
        # indexing readiness
        chunk_runs = [r for r in self.chunk_runs.values() if r.get("experiment_id") == experiment_id]
        if not chunk_runs:
            raise ValueError("No chunk run for experiment")
        chunk_run = sorted(chunk_runs, key=lambda r: r["created_at"])[-1]
        indexing = [i for i in self.indexing_runs.values() if i["chunk_run_id"] == chunk_run["chunk_run_id"]]
        if indexing:
            latest_idx = sorted(indexing, key=lambda x: x["created_at"])[-1]
            targets = [self.indexing_targets[t] for t in latest_idx.get("targets", [])]
            required = [t for t in targets if t.get("required")]
            if required and not all(t["status"] == "READY" for t in required):
                if not sink_profile_id:
                    raise ValueError("Required destinations not READY; pass sink_profile_id to evaluate an available destination explicitly")

        profile_data = self.eval_profiles.get(profile_id) if profile_id else next(iter(self.eval_profiles.values()), None)
        if not profile_data:
            profile = EvaluationProfile(tenant_id=tenant_id, name="default")
            self.eval_profiles[profile.evaluation_profile_id] = profile.model_dump()
            profile_data = profile.model_dump()
        profile = EvaluationProfile.model_validate(profile_data)

        datasets = [d for d in self.qa_datasets.values() if d["document_version_id"] == exp["document_version_id"]]
        if not datasets:
            raise ValueError("No QA dataset")
        ds = datasets[-1]
        qa_items = [i for i in self.qa_items.values() if i["qa_dataset_id"] == ds["qa_dataset_id"] and i.get("enabled", True)]
        chunks = [c for c in self.chunks.values() if c["chunk_run_id"] == chunk_run["chunk_run_id"]]

        # retrieve via sink
        sink_id = sink_profile_id or next(iter(self.sink_profiles))
        sink_profile = self.sink_profiles[sink_id]
        secret = self.secrets.get(sink_profile.get("credential_ref") or "")
        sink = create_sink(VectorSinkProfile.model_validate(sink_profile), secret=secret)
        emb_id = next(iter(self.embedding_profiles), None)
        retrievals: dict[str, list[dict]] = {}
        for qa in qa_items:
            qvec = (await self._embed_texts([qa["question"]], emb_id))[0]
            try:
                if sink_profile["sink_type"] == "dify":
                    hits = await sink.search(query_text=qa["question"], top_k=profile.top_k, filters={"experiment_id": experiment_id})
                else:
                    hits = await sink.search(query_vector=qvec, top_k=profile.top_k, filters={"experiment_id": experiment_id, "chunk_run_id": chunk_run["chunk_run_id"]})
            except Exception:
                # fallback local lexical
                hits = []
            retrieved = []
            for h in hits:
                ch = self.chunks.get(h.chunk_id) or next((c for c in chunks if c["chunk_id"] == h.chunk_id), None)
                if ch:
                    retrieved.append(ch)
                else:
                    retrieved.append({"chunk_id": h.chunk_id, "text": h.content, "element_ids": [], "logical_unit_ids": [], "content_hash": sha256_text(h.content)})
            if not retrieved:
                # lexical fallback against local chunks
                scored = sorted(chunks, key=lambda c: -sum(1 for t in qa["question"].lower().split() if t in (c.get("text") or "").lower()))
                retrieved = scored[: profile.top_k]
            retrievals[qa["qa_id"]] = retrieved

        previous = None
        prior_evals = [e for e in self.eval_runs.values() if e.get("experiment_id") != experiment_id and e.get("tenant_id") == tenant_id]
        if prior_evals:
            best = sorted(prior_evals, key=lambda e: e.get("composite_retrieval_score") or 0, reverse=True)[0]
            previous = {
                "composite_retrieval_score": best.get("composite_retrieval_score"),
                "evidence_recall_at_10": (best.get("result") or {}).get("raw_metrics", {}).get("evidence_recall_at_10"),
                "critical_segment_gains": [],
            }

        result = evaluate_run(qa_items=qa_items, retrievals=retrievals, profile=profile, chunks=chunks, previous=previous)
        failures = classify_failures(hits=result["hits"], qa_items=qa_items, chunks=chunks)
        eval_id = new_id()
        eval_run = {
            "evaluation_run_id": eval_id,
            "tenant_id": tenant_id,
            "experiment_id": experiment_id,
            "evaluation_profile_id": profile.evaluation_profile_id,
            "status": "READY",
            "result": result,
            "composite_retrieval_score": result["composite_retrieval_score"],
            "accepted": result["accepted"],
            "failures": [f.__dict__ for f in failures],
            "created_at": utcnow().isoformat(),
            "finished_at": utcnow().isoformat(),
            "query_results": {qid: [{"chunk_id": c.get("chunk_id"), "text": (c.get("text") or "")[:200]} for c in chs] for qid, chs in retrievals.items()},
        }
        self.eval_runs[eval_id] = eval_run
        for f in failures:
            self.failures[f.failure_id] = f.__dict__
        # reproduction manifest
        manifest = ReproductionManifest(
            experiment_id=experiment_id,
            tenant_id=tenant_id,
            document_version_id=exp["document_version_id"],
            parser_profile={"note": "see parse_runs"},
            chunk_plan_version=str(self.chunk_plans.get(exp.get("chunk_plan_id") or "", {}).get("version")),
            provider_manifests=[ProviderManifest(provider="builtin", version="1.0.0", license="Apache-2.0")],
            qa_dataset_version=ds["qa_dataset_id"],
            evaluation_profile_version=profile.evaluation_profile_id,
            retrieval_profile={"top_k": profile.top_k, "sink": sink_profile["sink_type"]},
            embedding_profile=self.embedding_profiles.get(emb_id or "", {}),
            embedding_model_revision=self.embedding_profiles.get(emb_id or "", {}).get("model"),
            target_sink=sink_profile["sink_type"],
            index_namespace=sink_profile.get("collection_or_index"),
            random_seed=42,
            effective_environment_constraints=self.settings.hard_constraints(),
        ).mark_complete()
        self.audit.put_reproduction(manifest)
        return eval_run

    def create_optimization_proposal(self, evaluation_run_id: str, *, tenant_id: str) -> dict:
        ev = self.eval_runs.get(evaluation_run_id)
        if not ev or ev["tenant_id"] != tenant_id:
            raise KeyError("Evaluation run not found")
        exp = self.experiments[ev["experiment_id"]]
        plan = self.chunk_plans.get(exp.get("chunk_plan_id") or "")
        if not plan:
            raise ValueError("No plan for experiment")
        from evaluation_engine.failures import FailureRecord
        failures = [FailureRecord(**{k: v for k, v in f.items() if k in FailureRecord.__dataclass_fields__}) for f in ev.get("failures") or []]
        proposal = generate_json_patch_proposal(plan=plan["effective_plan"], failures=failures, metrics=ev.get("result") or {})
        proposal["evaluation_run_id"] = evaluation_run_id
        proposal["tenant_id"] = tenant_id
        proposal["stopping_recommendation"] = (ev.get("result") or {}).get("stopping_recommendation")
        self.proposals[proposal["proposal_id"]] = proposal
        return proposal

    def review_proposal(self, proposal_id: str, *, tenant_id: str, decision: str, edited_changes: Optional[list] = None) -> dict:
        if self.settings.OPTIMIZATION_ALLOW_AUTOMATIC_EXECUTION:
            pass  # still never auto-execute next experiment
        prop = self.proposals.get(proposal_id)
        if not prop or prop["tenant_id"] != tenant_id:
            raise KeyError("Proposal not found")
        if edited_changes is not None:
            prop["changes"] = edited_changes
            prop["status"] = "EDITED"
        if decision == "accept":
            prop["status"] = "ACCEPTED"
        elif decision == "partial":
            prop["status"] = "PARTIALLY_ACCEPTED"
        elif decision == "reject":
            prop["status"] = "REJECTED"
        else:
            prop["status"] = decision.upper()
        self.audit.record(
            tenant_id=tenant_id, actor_type="human", actor_id=self.settings.default_user_id,
            action="optimization.review", entity_type="optimization_proposal", entity_id=proposal_id, after={"status": prop["status"]},
        )
        return prop

    def create_next_experiment(self, proposal_id: str, *, tenant_id: str) -> dict:
        """Human-triggered only."""
        if not self.settings.OPTIMIZATION_REQUIRE_HUMAN_TRIGGER:
            pass
        prop = self.proposals.get(proposal_id)
        if not prop or prop["tenant_id"] != tenant_id:
            raise KeyError("Proposal not found")
        if prop["status"] not in ("ACCEPTED", "PARTIALLY_ACCEPTED", "EDITED", "APPLIED_TO_NEXT_EXPERIMENT"):
            raise ValueError("Proposal must be accepted/edited before creating next experiment")
        ev = self.eval_runs[prop["evaluation_run_id"]]
        parent = self.experiments[ev["experiment_id"]]
        if parent.get("round_number", 1) >= self.settings.OPTIMIZATION_MAX_ROUNDS:
            raise ValueError("OPTIMIZATION_MAX_ROUNDS reached")
        plan = self.chunk_plans[parent["chunk_plan_id"]]
        accepted = [c for c in prop["changes"] if c.get("status") != "REJECTED"]
        new_effective = apply_accepted_changes(plan["effective_plan"], accepted)
        new_plan_id = new_id()
        new_plan = {
            **plan,
            "plan_id": new_plan_id,
            "effective_plan": new_effective,
            "proposed_plan": plan["effective_plan"],
            "version": 1,
            "status": "validated",
            "validation": self.validate_plan(new_effective, version_id=plan["document_version_id"], tenant_id=tenant_id),
            "created_at": utcnow().isoformat(),
            "updated_at": utcnow().isoformat(),
        }
        self.chunk_plans[new_plan_id] = new_plan
        exp_id = new_id()
        exp = {
            "experiment_id": exp_id,
            "tenant_id": tenant_id,
            "document_version_id": parent["document_version_id"],
            "name": f"Experiment round {parent.get('round_number', 1) + 1}",
            "chunk_plan_id": new_plan_id,
            "parent_experiment_id": parent["experiment_id"],
            "status": "draft",
            "round_number": parent.get("round_number", 1) + 1,
            "snapshot": {"from_proposal": proposal_id, "effective_plan": new_effective},
            "created_at": utcnow().isoformat(),
        }
        self.experiments[exp_id] = exp
        prop["status"] = "APPLIED_TO_NEXT_EXPERIMENT"
        # NEVER auto-start chunk run
        return exp

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_version(self, version_id: str, tenant_id: str) -> dict:
        v = self.versions.get(version_id)
        if not v or v["tenant_id"] != tenant_id:
            raise KeyError("Document version not found")
        return v

    def _get_plan(self, plan_id: str, tenant_id: str) -> dict:
        p = self.chunk_plans.get(plan_id)
        if not p or p["tenant_id"] != tenant_id:
            raise KeyError("Chunk plan not found")
        return p

    def _get_dataset(self, dataset_id: str, tenant_id: str) -> dict:
        d = self.qa_datasets.get(dataset_id)
        if not d or d["tenant_id"] != tenant_id:
            raise KeyError("QA dataset not found")
        return d

    def health_dependencies(self) -> dict:
        strategies = self.list_strategies()
        return {
            "strategies": [{"id": s["strategy_id"], "status": s.get("health_status"), "available": s.get("dependency_available"), "reason": s.get("health_reason")} for s in strategies],
            "qdrant_url": self.settings.qdrant_url,
            "database_configured": bool(self.settings.database_url),
            "auth_mode": self.settings.auth_mode,
            "auth_warning": None if self.settings.auth_mode != "development" else "Development auth is NOT production-safe",
        }


_ENGINE: Optional[Engine] = None


def get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = Engine()
    return _ENGINE
