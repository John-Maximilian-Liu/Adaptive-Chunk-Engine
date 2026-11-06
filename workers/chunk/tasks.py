"""Chunk queue tasks."""
from __future__ import annotations

from workers.common.celery_app import celery_app


@celery_app.task(name="workers.chunk.chunk_run_task", bind=True, max_retries=3)
def chunk_run_task(self, chunk_run_id: str):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "python"))
    from app.services.engine import get_engine

    engine = get_engine()
    try:
        return engine.execute_chunk_run(chunk_run_id)
    except ValueError as exc:
        raise exc  # schema / config — no retry
    except Exception as exc:
        raise self.retry(exc=exc, countdown=min(2 ** self.request.retries, 30))
