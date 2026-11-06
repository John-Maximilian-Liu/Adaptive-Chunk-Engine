from __future__ import annotations
import asyncio
from workers.common.celery_app import celery_app


@celery_app.task(name="workers.qa.generate_qa_task")
def generate_qa_task(dataset_id: str, tenant_id: str):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "python"))
    from app.services.engine import get_engine
    return asyncio.run(get_engine().generate_qa(dataset_id, tenant_id=tenant_id))
