"""Celery tasks for publishing posts to social media platforms."""

import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import async_session_factory
from app.core.logging import logger
from app.models.post import Post, PostStatus
from app.models.post_log import PostLog
from app.models.account import Account, Platform
from app.integrations.meta_client import MetaClient


def run_async(coro):
    """Helper to run async code in a Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.tasks.post_publisher.publish_scheduled_posts", bind=True)
def publish_scheduled_posts(self):
    """Find and publish all posts that are due."""
    logger.info("Task: publish_scheduled_posts started")

    async def _publish_all():
        async with async_session_factory() as db:
            now = datetime.now(timezone.utc)

            result = await db.execute(
                select(Post).where(
                    Post.status == PostStatus.SCHEDULED,
                    Post.scheduled_time <= now,
                )
            )
            posts = list(result.scalars().all())
            logger.info(f"Found {len(posts)} posts due for publishing")

            published = 0
            for post in posts:
                success = await _publish_single_post(db, post)
                if success:
                    published += 1

            await db.commit()
            return published

    try:
        count = run_async(_publish_all())
        logger.info(f"Task: publish_scheduled_posts completed — {count} published")
        return {"status": "success", "published": count}
    except Exception as e:
        logger.error(f"Task: publish_scheduled_posts failed — {e}")


@celery_app.task(name="app.tasks.post_publisher.publish_single_post", bind=True, max_retries=3)
def publish_single_post(self, post_id: int):
    """Publish a single post by ID."""
    logger.info(f"Task: publish_single_post started for post {post_id}")

    async def _publish():
        async with async_session_factory() as db:
            result = await db.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()

            if not post:
                logger.error(f"Post {post_id} not found")
                return False

            success = await _publish_single_post(db, post)
            await db.commit()
            return success

    try:
        success = run_async(_publish())
        return {"status": "success" if success else "failed", "post_id": post_id}
    except Exception as e:
        logger.error(f"Task: publish_single_post failed — {e}")
        self.retry(countdown=60)


@celery_app.task(name="app.tasks.post_publisher.retry_failed_posts", bind=True)
def retry_failed_posts(self):
    """Retry publishing failed posts (max 3 attempts tracked via logs)."""
    logger.info("Task: retry_failed_posts started")

    async def _retry():
        async with async_session_factory() as db:
            result = await db.execute(
                select(Post).where(Post.status == PostStatus.FAILED)
            )
            failed_posts = list(result.scalars().all())
            logger.info(f"Found {len(failed_posts)} failed posts to retry")

            retried = 0
            for post in failed_posts:
                # Check retry count from logs
                log_result = await db.execute(
                    select(PostLog).where(PostLog.post_id == post.id)
                )
                logs = list(log_result.scalars().all())

                if len(logs) >= 3:
                    logger.warning(f"Post {post.id} exceeded max retries, skipping")
                    continue

                post.status = PostStatus.SCHEDULED
                retried += 1

            await db.commit()
            return retried

    try:
        count = run_async(_retry())
        logger.info(f"Task: retry_failed_posts completed — {count} posts requeued")
        return {"status": "success", "retried": count}
    except Exception as e:
        logger.error(f"Task: retry_failed_posts failed — {e}")


async def _publish_single_post(db, post: Post) -> bool:
    """Core publishing logic for a single post."""
    meta_client = MetaClient()

    # Get the account for this post
    account = None
    if post.account_id:
        result = await db.execute(
            select(Account).where(Account.id == post.account_id)
        )
        account = result.scalar_one_or_none()

    if not account:
        # Try to find any account for this platform
        result = await db.execute(
            select(Account).where(
                Account.platform == Platform(post.platform)
            ).limit(1)
        )
        account = result.scalar_one_or_none()

    if not account:
        logger.error(f"No account found for platform {post.platform}, post {post.id}")
        post.status = PostStatus.FAILED
        log = PostLog(
            post_id=post.id,
            platform_response=json.dumps({"error": "No account connected"}),
            success=False,
        )
        db.add(log)
        return False

    # Publish based on platform
    if post.platform == "facebook":
        result = await meta_client.publish_facebook_post(
            page_id=account.page_id,
            access_token=account.access_token,
            message=post.content,
            image_url=post.image_url,
            post_id=post.id,
        )
    elif post.platform == "instagram":
        if not post.image_url:
            logger.error(f"Instagram post {post.id} requires an image")
            post.status = PostStatus.FAILED
            log = PostLog(
                post_id=post.id,
                platform_response=json.dumps({"error": "Instagram requires an image"}),
                success=False,
            )
            db.add(log)
            return False

        result = await meta_client.publish_instagram_post(
            ig_user_id=account.page_id,
            access_token=account.access_token,
            caption=post.content,
            image_url=post.image_url,
            post_id=post.id,
        )
    else:
        logger.error(f"Unsupported platform: {post.platform}")
        post.status = PostStatus.FAILED
        return False

    # Log the result
    success = result.get("success", False)
    log = PostLog(
        post_id=post.id,
        platform_response=json.dumps(result),
        success=success,
    )
    db.add(log)

    if success:
        post.status = PostStatus.POSTED
        logger.info(f"Post {post.id} published successfully to {post.platform}")
    else:
        post.status = PostStatus.FAILED
        logger.error(f"Post {post.id} failed to publish: {result}")

    return success
