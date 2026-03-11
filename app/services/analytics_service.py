"""Analytics and logging service for tracking post performance."""

from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.post import Post, PostStatus, PostType
from app.models.post_log import PostLog


class AnalyticsService:
    """Tracks and reports on posting activity and success rates."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self) -> dict:
        """Get overall posting analytics summary."""
        total = await self.db.scalar(select(func.count(Post.id))) or 0
        posted = await self.db.scalar(
            select(func.count(Post.id)).where(Post.status == PostStatus.POSTED)
        ) or 0
        failed = await self.db.scalar(
            select(func.count(Post.id)).where(Post.status == PostStatus.FAILED)
        ) or 0

        success_rate = (posted / total * 100) if total > 0 else 0

        return {
            "total_posts": total,
            "posted": posted,
            "failed": failed,
            "success_rate": round(success_rate, 1),
        }

    async def get_platform_breakdown(self) -> list[dict]:
        """Get post counts broken down by platform."""
        result = await self.db.execute(
            select(Post.platform, func.count(Post.id))
            .group_by(Post.platform)
        )
        return [{"platform": row[0], "count": row[1]} for row in result.all()]

    async def get_type_breakdown(self) -> list[dict]:
        """Get post counts broken down by post type."""
        result = await self.db.execute(
            select(Post.post_type, func.count(Post.id))
            .group_by(Post.post_type)
        )
        return [{"post_type": row[0], "count": row[1]} for row in result.all()]

    async def log_publish_result(
        self, post_id: int, platform_response: str, success: bool
    ) -> PostLog:
        """Log a publish attempt result."""
        log = PostLog(
            post_id=post_id,
            platform_response=platform_response,
            success=success,
        )
        self.db.add(log)
        await self.db.flush()
        logger.info(f"Logged publish result for post {post_id}: {'success' if success else 'failed'}")
        return log
