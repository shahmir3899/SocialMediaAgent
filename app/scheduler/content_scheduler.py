"""Content scheduling service for daily post generation and scheduling."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.config import get_settings
from app.models.post import Post, PostStatus, PostMode, PostType
from app.models.approval import ApprovalQueue, ApprovalStatus
from app.services.website_source_service import WebsiteSourceService
from app.agents.content_agent import ContentAgent
from app.agents.image_agent import ImageAgent
from app.services.workflow_engine import WorkflowEngine
from app.utils.image_cache import download_and_cache

settings = get_settings()

# Daily content strategy: type -> count
DAILY_STRATEGY = {
    "educational": 3,
    "engagement": 2,
    "promotional": 1,
}

# Topic pools per post type — shuffled daily to ensure variety
TOPIC_POOLS = {
    "educational": [
        "productivity tips for remote workers",
        "the science of habit building",
        "how AI is transforming everyday tasks",
        "financial literacy basics everyone should know",
        "effective communication in the digital age",
        "the psychology behind decision making",
        "sustainable living tips for beginners",
        "the future of renewable energy",
        "how to build a personal brand online",
        "nutrition myths debunked by science",
        "time management strategies that actually work",
        "the impact of technology on mental health",
        "understanding data privacy in social media",
        "creative problem-solving techniques",
        "benefits of continuous learning and upskilling",
    ],
    "engagement": [
        "what is one skill you wish you learned earlier",
        "morning routines vs night routines — which team are you on",
        "share your biggest lesson from this year so far",
        "what book or podcast changed your perspective",
        "if you could master one thing overnight what would it be",
        "unpopular opinion about your industry — go",
        "what does work-life balance look like for you",
        "best advice you ever received from a mentor",
        "what motivates you to keep going on tough days",
        "describe your dream project in three words",
    ],
    "promotional": [
        "how our service helps small businesses grow",
        "why automation saves you hours every week",
        "client success stories that inspire us",
        "special offer for new followers this month",
        "behind the scenes of how we built our platform",
        "top features our users love most",
        "join our community of forward-thinking creators",
    ],
    "quote": [
        "an inspiring quote about perseverance",
        "a thought-provoking quote about innovation",
        "a motivational quote about growth mindset",
        "an insightful quote about leadership",
        "a powerful quote about creativity and imagination",
    ],
    "announcement": [
        "exciting new feature we just launched",
        "upcoming event you will not want to miss",
        "milestone we just reached as a community",
        "partnership announcement that benefits our users",
    ],
}


class ContentScheduler:
    """Generates and schedules daily content based on the content strategy."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.agent = ContentAgent()
        self.image_agent = ImageAgent()
        self.workflow = WorkflowEngine()

    async def generate_daily_posts(self, platform: str = "facebook") -> list[Post]:
        """Generate the full set of daily posts according to strategy.

        Auto-generation is website-grounded only. If no website sources are
        available, generation is skipped to avoid random unattended posts.
        """
        logger.info("Starting daily post generation")
        posts = []
        service = WebsiteSourceService(self.db)
        enabled_sources = await service.list_enabled_sources()
        source_contexts: list[tuple[object, str]] = []

        for source in enabled_sources:
            context = await service.build_context_for_source(source.id)
            if context:
                source_contexts.append((source, context))

        if not source_contexts:
            logger.warning(
                "Daily generation skipped: no enabled website source content available"
            )
            return posts

        weighted_source_contexts: list[tuple[object, str]] = []
        for source, context in source_contexts:
            quota = max(1, int(getattr(source, "daily_quota", 1) or 1))
            weighted_source_contexts.extend([(source, context)] * quota)

        source_cursor = 0
        for post_type, count in DAILY_STRATEGY.items():
            for i in range(count):
                source, website_context = weighted_source_contexts[
                    source_cursor % len(weighted_source_contexts)
                ]
                source_cursor += 1
                topic = (
                    f"Create a {post_type} post grounded only in the following website content. "
                    f"Angle #{i + 1} should be meaningfully different from other posts. "
                    f"Center the post on this source: {source.name} ({source.base_url}).\\n\\n"
                    f"{website_context}"
                )
                try:
                    generated = await self.agent.generate_post(
                        post_type=post_type,
                        platform=platform,
                        topic=topic,
                    )
                    post = await self._save_generated_post(generated, platform, source_id=source.id)
                    posts.append(post)
                    logger.info(
                        f"Generated website-grounded {post_type} post {i+1}/{count} for source={source.name}"
                    )
                except Exception as e:
                    logger.error(f"Failed to generate {post_type} post: {e}")

        logger.info(f"Daily generation complete: {len(posts)} posts created")
        return posts

    async def _save_generated_post(
        self,
        generated: dict,
        platform: str,
        source_id: int | None = None,
    ) -> Post:
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
            website_source_id=source_id,
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

        # Eagerly cache image to disk so dashboard thumbnails load instantly
        if image_url:
            await download_and_cache(post.id, image_url)

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
