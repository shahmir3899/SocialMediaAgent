"""Celery application configuration."""

import ssl
from celery import Celery
from celery.schedules import crontab
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "social_media_agent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.timezone,
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "generate-daily-posts": {
            "task": "app.tasks.content_tasks.generate_daily_posts",
            # Run every 4 hours; task itself enforces daily minimum guard.
            "schedule": crontab(minute=0, hour="*/4"),
        },
        "schedule-ready-posts": {
            "task": "app.tasks.content_tasks.schedule_posts",
            "schedule": 300.0,  # every 5 minutes
        },
        "publish-scheduled-posts": {
            "task": "app.tasks.post_publisher.publish_scheduled_posts",
            "schedule": 60.0,  # every minute
        },
        "retry-failed-posts": {
            "task": "app.tasks.post_publisher.retry_failed_posts",
            "schedule": 300.0,  # every 5 minutes
        },
        "refresh-expiring-tokens": {
            "task": "app.tasks.content_tasks.refresh_expiring_tokens",
            "schedule": 3600.0 * 12,  # every 12 hours
        },
        "refresh-website-sources": {
            "task": "app.tasks.content_tasks.refresh_website_sources",
            "schedule": 3600.0 * 6,  # every 6 hours
        },
        "warmup-images-before-publish": {
            "task": "app.tasks.content_tasks.warmup_images_before_publish",
            "schedule": 1800.0,  # every 30 minutes
        },
    },
)

# Upstash Redis uses rediss:// (SSL). Celery requires explicit ssl_cert_reqs.
if settings.celery_broker_url.startswith("rediss://"):
    _ssl_config = {"ssl_cert_reqs": ssl.CERT_NONE}
    celery_app.conf.broker_use_ssl = _ssl_config
    celery_app.conf.redis_backend_use_ssl = _ssl_config

celery_app.autodiscover_tasks([
    "app.tasks",
])
