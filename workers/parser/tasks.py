"""Parse queue tasks."""
from __future__ import annotations

from workers.common.celery_app import celery_app


@celery_app.task(name="workers.parser.parse_document_task", bind=True, max_retries=3)
def parse_document_task(self, version_id: str, tenant_id: str, correlation_id: str | None = None):
    """Non-retryable for unsupported formats; retryable for transient IO."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "python"))
    from app.services.engine import get_engine

    engine = get_engine()
    try:
        return engine.parse_document_version(version_id, tenant_id=tenant_id, correlation_id=correlation_id)
    except ValueError as exc:
        # unsupported / schema — do not retry
        raise exc
    except Exception as exc:
        raise self.retry(exc=exc, countdown=min(2 ** self.request.retries, 30))
