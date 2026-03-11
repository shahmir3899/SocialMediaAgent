"""Content scheduling service for daily post generation and scheduling."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.config import get_settings
from app.models.post import Post, PostStatus, PostMode, PostType
from app.models.approval import ApprovalQueue, ApprovalStatus
from app.agents.content_agent import ContentAgent
from app.agents.image_agent import ImageAgent
from app.services.workflow_engine import WorkflowEngine

settings = get_settings()

# Daily content strategy: type -> count
DAILY_STRATEGY = {
    "educational": 3,
    "engagement": 2,
    "promotional": 1,
}


class ContentScheduler:
    """Generates and schedules daily content based on the content strategy."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.agent = ContentAgent()
        self.image_agent = ImageAgent()
        self.workflow = WorkflowEngine()

    async def generate_daily_posts(self, platform: str = "facebook") -> list[Post]:
        """Generate the full set of daily posts according to strategy."""
        logger.info("Starting daily post generation")
        posts = []

        for post_type, count in DAILY_STRATEGY.items():
            for i in range(count):
                try:
                    generated = await self.agent.generate_post(
                        post_type=post_type,
                        platform=platform,
                    )
                    post = await self._save_generated_post(generated, platform)
                    posts.append(post)
                    logger.info(f"Generated {post_type} post {i+1}/{count}")
                except Exception as e:
                    logger.error(f"Failed to generate {post_type} post: {e}")

        logger.info(f"Daily generation complete: {len(posts)} posts created")
        return posts

    async def _save_generated_post(self, generated: dict, platform: str) -> Post:
        """Save a generated post to the database with an auto-generated image."""
        post_type = PostType(generated["post_type"])
        mode = self.workflow.determine_mode(post_type)
        hashtag_str = " ".join(f"#{h}" for h in generated.get("hashtags", []))
        full_content = f"{generated['caption']}\n\n{hashtag_str}"
        image_prompt = generated.get("image_prompt", "")

        # Generate image URL from prompt (Pollinations.ai — free, no key)
        image_url = None
        if image_prompt:
            image_url = self.image_agent.generate_for_post_type(
                image_prompt, generated["post_type"]
            )

        post = Post(
            content=full_content,
            platform=platform,
            post_type=post_type,
            mode=mode,
            hashtags=hashtag_str,
            image_prompt=image_prompt,
            image_url=image_url,
        )

        if mode == PostMode.MANUAL:
            post.status = PostStatus.PENDING
        else:
            post.status = PostStatus.DRAFT

        self.db.add(post)
        await self.db.flush()

        if mode == PostMode.MANUAL:
            approval = ApprovalQueue(post_id=post.id, status=ApprovalStatus.PENDING)
            self.db.add(approval)
            await self.db.flush()

        logger.info(
            f"Saved {post_type.value} post {post.id} [{mode.value}] "
            f"image={'yes' if image_url else 'no'}"
        )
        return post

    async def assign_schedule_times(self, date: datetime | None = None) -> list[Post]:
        """Assign posting times to draft/approved posts for a given day.

        Default schedule slots (UTC):
            09:00, 12:00, 15:00, 17:00, 19:00, 21:00
        """
        if date is None:
            date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            date += timedelta(days=1)  # Schedule for tomorrow

        schedule_hours = [9, 12, 15, 17, 19, 21]

        # Get posts ready to schedule (auto=draft, manual=approved)
        result = await self.db.execute(
            select(Post).where(
                Post.status.in_([PostStatus.DRAFT, PostStatus.APPROVED]),
                Post.scheduled_time.is_(None),
            ).order_by(Post.created_at)
        )
        posts = list(result.scalars().all())

        scheduled = []
        for i, post in enumerate(posts):
            if i >= len(schedule_hours):
                break

            schedule_time = date.replace(hour=schedule_hours[i], tzinfo=timezone.utc)
            post.scheduled_time = schedule_time
            post.status = PostStatus.SCHEDULED
            scheduled.append(post)
            logger.info(f"Scheduled post {post.id} for {schedule_time}")

        await self.db.flush()
        logger.info(f"Scheduled {len(scheduled)} posts")
        return scheduled
