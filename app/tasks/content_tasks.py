"""Celery tasks for content generation and scheduling."""

import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import async_session_factory
from app.core.logging import logger
from app.scheduler.content_scheduler import ContentScheduler
from app.models.account import Account
from app.models.post import Post, PostStatus
from app.integrations.meta_client import MetaClient
from app.utils.image_cache import download_and_cache, is_cached


def run_async(coro):
    """Helper to run async code in a Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.tasks.content_tasks.generate_daily_posts", bind=True, max_retries=3)
def generate_daily_posts(self):
    """Ensure a minimum number of posts are generated each day."""
    logger.info("Task: generate_daily_posts started")

    async def _generate():
        async with async_session_factory() as db:
            try:
                day_start = datetime.now(timezone.utc).replace(
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                min_posts_per_day = 5
                existing_today = await db.scalar(
                    select(func.count(Post.id)).where(
                        Post.created_at >= day_start,
                        Post.platform == "facebook",
                        Post.image_prompt.isnot(None),
                    )
                ) or 0

                if existing_today >= min_posts_per_day:
                    logger.info(
                        "Task: generate_daily_posts skipped — "
                        f"{existing_today} posts already created today"
                    )
                    return 0

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
        logger.error(f"Task: generate_daily_posts failed — {e!r}", exc_info=True)
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
        logger.error(f"Task: schedule_posts failed — {e!r}", exc_info=True)
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
        logger.error(f"Task: refresh_expiring_tokens failed — {e!r}", exc_info=True)


@celery_app.task(name="app.tasks.content_tasks.backfill_image_cache")
def backfill_image_cache():
    """Download and cache images for all posts that have a Pollinations URL but no local cache."""
    logger.info("Task: backfill_image_cache started")

    async def _get_urls():
        """Quickly fetch all post IDs and image URLs, then close the DB session."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(Post.id, Post.image_url).where(
                    Post.image_url.isnot(None),
                    Post.image_url.like("%pollinations.ai%"),
                )
            )
            return [(r[0], r[1]) for r in result.all()]

    async def _download_all(rows):
        cached = 0
        for post_id, image_url in rows:
            if is_cached(post_id):
                continue
            # Retry up to 2 times for transient Pollinations errors
            for attempt in range(3):
                ok = await download_and_cache(post_id, image_url)
                if ok:
                    cached += 1
                    break
                if attempt < 2:
                    logger.info(f"[backfill] Retrying post {post_id} (attempt {attempt + 2}/3)")
                    import asyncio
                    await asyncio.sleep(5)
        return cached

    try:
        rows = run_async(_get_urls())
        logger.info(f"Task: backfill_image_cache — {len(rows)} posts to check")
        count = run_async(_download_all(rows))
        logger.info(f"Task: backfill_image_cache completed — {count} images cached")
        return {"status": "success", "cached": count}
    except Exception as e:
        logger.error(f"Task: backfill_image_cache failed — {e!r}", exc_info=True)


@celery_app.task(
    name="app.tasks.content_tasks.retry_cache_post_image",
    bind=True,
    max_retries=6,
)
def retry_cache_post_image(self, post_id: int):
    """Retry caching image for a single post ID with exponential backoff."""
    logger.info(f"Task: retry_cache_post_image started for post {post_id}")

    async def _retry_one():
        async with async_session_factory() as db:
            post = await db.get(Post, post_id)
            if not post or not post.image_url:
                logger.warning(f"retry_cache_post_image: post {post_id} has no image_url")
                return {"status": "missing", "post_id": post_id}

            if is_cached(post_id):
                logger.info(f"retry_cache_post_image: post {post_id} already cached")
                return {"status": "already_cached", "post_id": post_id}

            ok = await download_and_cache(post_id, post.image_url)
            return {"status": "cached" if ok else "failed", "post_id": post_id}

    try:
        result = run_async(_retry_one())
        if result["status"] == "failed":
            retries = self.request.retries + 1
            countdown = min(60 * (2 ** retries), 900)
            logger.warning(
                f"Task: retry_cache_post_image failed for post {post_id}; "
                f"retrying in {countdown}s ({retries}/{self.max_retries})"
            )
            raise self.retry(countdown=countdown)

        logger.info(
            f"Task: retry_cache_post_image completed for post {post_id} "
            f"status={result['status']}"
        )
        return result
    except Exception as e:
        logger.error(f"Task: retry_cache_post_image failed — {e!r}", exc_info=True)
        raise


@celery_app.task(name="app.tasks.content_tasks.warmup_images_before_publish", bind=True)
def warmup_images_before_publish(self):
    """Pre-warm images for posts scheduled to publish within the next 30-90 minutes.
    
    This task runs every 30 minutes to ensure images are cached before publishing,
    reducing the chance of Pollinations.ai failures during the actual publish process.
    """
    logger.info("Task: warmup_images_before_publish started")

    async def _warmup():
        async with async_session_factory() as db:
            now = datetime.now(timezone.utc)
            # Look for posts scheduled 30-90 minutes from now
            window_start = now + timedelta(minutes=30)
            window_end = now + timedelta(minutes=90)
            
            result = await db.execute(
                select(Post.id, Post.image_url).where(
                    Post.status == PostStatus.SCHEDULED,
                    Post.scheduled_time >= window_start,
                    Post.scheduled_time <= window_end,
                    Post.image_url.isnot(None),
                )
            )
            posts_to_warmup = result.all()
            
            if not posts_to_warmup:
                logger.info("Task: warmup_images_before_publish — no posts need warming up")
                return 0
            
            logger.info(f"Task: warmup_images_before_publish — warming up {len(posts_to_warmup)} posts")
            
            warmed_up = 0
            for post_id, image_url in posts_to_warmup:
                if is_cached(post_id):
                    logger.debug(f"Post {post_id} already cached, skipping")
                    continue
                
                # Use the same retry logic as publishing (3 attempts with exponential backoff)
                meta_client = MetaClient()
                image_bytes = await meta_client._download_image(image_url, max_retries=3)
                
                if image_bytes:
                    # Cache the image locally
                    from app.utils.image_cache import download_and_cache
                    try:
                        # Use the existing download_and_cache function but with pre-downloaded bytes
                        # Since we already have the bytes, we'll save them directly
                        from app.utils.image_cache import cached_path, _ensure_cache_dir
                        _ensure_cache_dir()
                        dest = cached_path(post_id)
                        dest.write_bytes(image_bytes)
                        warmed_up += 1
                        logger.info(f"Warmed up image for post {post_id}")
                    except Exception as e:
                        logger.error(f"Failed to cache image for post {post_id}: {e}")
                else:
                    logger.warning(f"Failed to download image for post {post_id} after retries")
            
            return warmed_up

    try:
        count = run_async(_warmup())
        logger.info(f"Task: warmup_images_before_publish completed — {count} images warmed up")
        return {"status": "success", "warmed_up": count}
    except Exception as e:
        logger.error(f"Task: warmup_images_before_publish failed — {e!r}", exc_info=True)
        raise
