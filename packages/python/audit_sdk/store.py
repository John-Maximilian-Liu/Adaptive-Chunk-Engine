"""In-memory + DB-backed audit store interface."""
from __future__ import annotations

from typing import Any, Optional

from canonical_schemas.audit import AuditEvent, ProviderManifest, ReproductionManifest
from shared.ids import new_id


class AuditStore:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._providers: list[ProviderManifest] = []
        self._reproductions: dict[str, ReproductionManifest] = {}

    def record(
        self,
        *,
        tenant_id: str,
        actor_type: str,
        actor_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        before: Optional[dict[str, Any]] = None,
        after: Optional[dict[str, Any]] = None,
        patch: Optional[list[dict[str, Any]]] = None,
        correlation_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        origin: str = "system",
        metadata: Optional[dict[str, Any]] = None,
    ) -> AuditEvent:
        # Never store secrets
        before = _redact(before)
        after = _redact(after)
        event = AuditEvent(
            tenant_id=tenant_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            patch=patch,
            correlation_id=correlation_id,
            source_ip=source_ip,
            origin=origin,
            metadata=metadata or {},
        )
        self._events.append(event)
        return event

    def list_events(
        self,
        *,
        tenant_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        items = self._events
        if tenant_id:
            items = [e for e in items if e.tenant_id == tenant_id]
        if entity_type:
            items = [e for e in items if e.entity_type == entity_type]
        if entity_id:
            items = [e for e in items if e.entity_id == entity_id]
        return list(reversed(items[-limit:]))

    def add_provider_manifest(self, manifest: ProviderManifest) -> ProviderManifest:
        self._providers.append(manifest)
        return manifest

    def put_reproduction(self, manifest: ReproductionManifest) -> ReproductionManifest:
        manifest.mark_complete()
        self._reproductions[manifest.experiment_id] = manifest
        return manifest

    def get_reproduction(self, experiment_id: str) -> Optional[ReproductionManifest]:
        return self._reproductions.get(experiment_id)


def _redact(obj: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if obj is None:
        return None
    SENSITIVE = {"api_key", "secret", "password", "token", "credential", "authorization"}
    out = {}
    for k, v in obj.items():
        if any(s in k.lower() for s in SENSITIVE):
            out[k] = "***REDACTED***"
        elif isinstance(v, dict):
            out[k] = _redact(v)
        else:
            out[k] = v
    return out


_STORE: Optional[AuditStore] = None


def get_audit_store() -> AuditStore:
    global _STORE
    if _STORE is None:
        _STORE = AuditStore()
    return _STORE
