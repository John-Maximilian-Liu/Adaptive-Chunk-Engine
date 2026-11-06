"""Indexing queue + outbox consumer."""
from __future__ import annotations

from workers.common.celery_app import celery_app


@celery_app.task(name="workers.indexing.process_outbox_task")
def process_outbox_task():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "python"))
    from app.services.engine import get_engine
    return get_engine().process_outbox()


@celery_app.task(name="workers.indexing.indexing_run_task", bind=True, max_retries=5)
def indexing_run_task(self, indexing_run_id: str):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "python"))
    from app.services.engine import get_engine
    try:
        return get_engine().execute_indexing_run(indexing_run_id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=min(2 ** self.request.retries, 60))
