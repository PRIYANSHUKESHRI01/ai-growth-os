"""
app/core/celery_app.py
────────────────────────
Celery application configuration.
Now updated with modular architecture paths.
"""
from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_growth_os",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

import ssl

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

# Handle SSL for Upstash (rediss://)
if settings.REDIS_URL.startswith("rediss://"):
    celery_app.conf.update(
        broker_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE},
        redis_backend_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE},
    )

# IMPORTANT: autodiscover tasks (Automation 1, 2, and 3)
celery_app.autodiscover_tasks([
    "app.modules.lead_scoring",
    "app.modules.lead_discovery.workers",
], related_name="discovery_tasks")

celery_app.autodiscover_tasks([
    "app.modules.lead_scoring.workers",
])

# Explicitly import files that don't match standard Celery naming conventions
celery_app.conf.imports = (
    "app.modules.outreach_engine.workers.outreach_tasks",
)
