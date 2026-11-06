from __future__ import annotations
from workers.common.celery_app import celery_app


@celery_app.task(name="workers.optimization.propose_task")
def propose_task(evaluation_run_id: str, tenant_id: str):
    """Generate proposal only — never auto-execute next experiment."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "python"))
    from app.services.engine import get_engine
    return get_engine().create_optimization_proposal(evaluation_run_id, tenant_id=tenant_id)
