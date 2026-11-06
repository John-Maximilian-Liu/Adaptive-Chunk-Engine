"""Celery application — swappable later for Temporal / Azure Service Bus."""
from __future__ import annotations

import os

from celery import Celery

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("ace", broker=redis_url, backend=redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=5,
    task_routes={
        "workers.parser.*": {"queue": "parse"},
        "workers.chunk.*": {"queue": "chunk"},
        "workers.qa.*": {"queue": "qa"},
        "workers.embedding.*": {"queue": "embedding"},
        "workers.indexing.*": {"queue": "indexing"},
        "workers.evaluation.*": {"queue": "evaluation"},
        "workers.optimization.*": {"queue": "optimization"},
    },
)

celery_app.autodiscover_tasks([
    "workers.parser",
    "workers.chunk",
    "workers.qa",
    "workers.embedding",
    "workers.indexing",
    "workers.evaluation",
    "workers.optimization",
])
