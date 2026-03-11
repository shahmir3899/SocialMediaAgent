"""Celery tasks package. Import submodules so tasks are registered on startup."""

from app.tasks import content_tasks, post_publisher  # noqa: F401
