from __future__ import annotations
from workers.common.celery_app import celery_app


@celery_app.task(name="workers.embedding.embed_batch_task")
def embed_batch_task(texts: list[str], embedding_profile_id: str | None = None):
    import asyncio, sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "python"))
    from app.services.engine import get_engine
    engine = get_engine()
    return asyncio.run(engine._embed_texts(texts, embedding_profile_id))
