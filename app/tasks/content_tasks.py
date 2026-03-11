"""Celery tasks for content generation and scheduling."""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import async_session_factory
from app.core.logging import logger
from app.scheduler.content_scheduler import ContentScheduler


def run_async(coro):
    """Helper to run async code in a Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.tasks.content_tasks.generate_daily_posts", bind=True, max_retries=3)
def generate_daily_posts(self):
    """Generate daily posts according to the content strategy."""
    logger.info("Task: generate_daily_posts started")

    async def _generate():
        async with async_session_factory() as db:
            try:
                scheduler = ContentScheduler(db)
                posts = await scheduler.generate_daily_posts(platform="facebook")
                await db.commit()
                return len(posts)
            except Exception as e:
                await db.rollback()
                raise e

    try:
        count = run_async(_generate())
        logger.info(f"Task: generate_daily_posts completed — {count} posts created")
        return {"status": "success", "posts_created": count}
    except Exception as e:
        logger.error(f"Task: generate_daily_posts failed — {e}")
        self.retry(countdown=60 * 5)


@celery_app.task(name="app.tasks.content_tasks.schedule_posts", bind=True, max_retries=3)
def schedule_posts(self):
    """Assign schedule times to ready posts."""
    logger.info("Task: schedule_posts started")

    async def _schedule():
        async with async_session_factory() as db:
            try:
                scheduler = ContentScheduler(db)
                posts = await scheduler.assign_schedule_times()
                await db.commit()
                return len(posts)
            except Exception as e:
                await db.rollback()
                raise e

    try:
        count = run_async(_schedule())
        logger.info(f"Task: schedule_posts completed — {count} posts scheduled")
        return {"status": "success", "posts_scheduled": count}
    except Exception as e:
        logger.error(f"Task: schedule_posts failed — {e}")
        self.retry(countdown=60)
