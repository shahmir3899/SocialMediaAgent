"""Celery tasks for content generation and scheduling."""

import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import async_session_factory
from app.core.logging import logger
from app.scheduler.content_scheduler import ContentScheduler
from app.models.account import Account
from app.integrations.meta_client import MetaClient


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


@celery_app.task(name="app.tasks.content_tasks.refresh_expiring_tokens", bind=True)
def refresh_expiring_tokens(self):
    """Refresh Meta access tokens that will expire within 7 days."""
    logger.info("Task: refresh_expiring_tokens started")

    async def _refresh():
        async with async_session_factory() as db:
            threshold = datetime.now(timezone.utc) + timedelta(days=7)
            result = await db.execute(
                select(Account).where(
                    Account.token_expiry.isnot(None),
                    Account.token_expiry <= threshold,
                )
            )
            accounts = list(result.scalars().all())
            logger.info(f"Found {len(accounts)} accounts with expiring tokens")

            meta = MetaClient()
            refreshed = 0
            for account in accounts:
                data = await meta.refresh_long_lived_token(account.access_token)
                new_token = data.get("access_token")
                if new_token:
                    account.access_token = new_token
                    expires_in = data.get("expires_in", 5184000)
                    account.token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                    refreshed += 1
                    logger.info(f"Refreshed token for {account.page_name}")
                else:
                    logger.warning(f"Failed to refresh token for {account.page_name}")

            await db.commit()
            return refreshed

    try:
        count = run_async(_refresh())
        logger.info(f"Task: refresh_expiring_tokens completed — {count} refreshed")
        return {"status": "success", "refreshed": count}
    except Exception as e:
        logger.error(f"Task: refresh_expiring_tokens failed — {e}")
