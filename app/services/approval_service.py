"""Service layer for the approval workflow."""

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.post import Post, PostStatus
from app.models.approval import ApprovalQueue, ApprovalStatus
from app.api.schemas import ApprovalAction


class ApprovalService:
    """Handles post approval and rejection workflow."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_pending_posts(self) -> list[Post]:
        """List all posts awaiting approval."""
        result = await self.db.execute(
            select(Post)
            .where(Post.status == PostStatus.PENDING)
            .order_by(Post.created_at.desc())
        )
        return list(result.scalars().all())

    async def approve_post(self, post_id: int, data: ApprovalAction | None = None) -> Post | None:
        """Approve a post and move it to scheduled status."""
        post = await self._get_post(post_id)
        if not post:
            return None

        if post.status != PostStatus.PENDING:
            logger.warning(f"Post {post_id} is not pending, current status: {post.status}")

        # Update post status
        post.status = PostStatus.SCHEDULED

        # Update approval queue
        approval = await self._get_approval(post_id)
        if approval:
            approval.status = ApprovalStatus.APPROVED
            approval.reviewed_at = datetime.now(timezone.utc)
            if data and data.reviewer_notes:
                approval.reviewer_notes = data.reviewer_notes

        await self.db.flush()
        logger.info(f"Post {post_id} approved and scheduled")
        return post

    async def reject_post(self, post_id: int, data: ApprovalAction | None = None) -> Post | None:
        """Reject a post."""
        post = await self._get_post(post_id)
        if not post:
            return None

        post.status = PostStatus.DRAFT

        approval = await self._get_approval(post_id)
        if approval:
            approval.status = ApprovalStatus.REJECTED
            approval.reviewed_at = datetime.now(timezone.utc)
            if data and data.reviewer_notes:
                approval.reviewer_notes = data.reviewer_notes

        await self.db.flush()
        logger.info(f"Post {post_id} rejected")
        return post

    async def _get_post(self, post_id: int) -> Post | None:
        result = await self.db.execute(select(Post).where(Post.id == post_id))
        return result.scalar_one_or_none()

    async def _get_approval(self, post_id: int) -> ApprovalQueue | None:
        result = await self.db.execute(
            select(ApprovalQueue).where(ApprovalQueue.post_id == post_id)
        )
        return result.scalar_one_or_none()
