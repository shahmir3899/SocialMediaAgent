"""Service layer for post management."""

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.post import Post, PostStatus, PostMode, PostType
from app.models.approval import ApprovalQueue, ApprovalStatus
from app.api.schemas import PostCreate, PostEdit, GeneratePostRequest, GeneratedPostResponse
from app.services.workflow_engine import WorkflowEngine
from app.agents.image_agent import ImageAgent


class PostService:
    """Handles post CRUD operations and workflow routing."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.workflow = WorkflowEngine()

    async def create_post(self, data: PostCreate) -> Post:
        """Create a new post and route it through the workflow."""
        post_type = PostType(data.post_type)
        mode = self.workflow.determine_mode(post_type)

        post = Post(
            content=data.content,
            image_url=data.image_url,
            platform=data.platform,
            post_type=post_type,
            mode=mode,
            account_id=data.account_id,
            scheduled_time=data.scheduled_time,
        )

        if mode == PostMode.MANUAL:
            post.status = PostStatus.PENDING
        elif data.scheduled_time:
            post.status = PostStatus.SCHEDULED
        else:
            post.status = PostStatus.DRAFT

        self.db.add(post)
        await self.db.flush()

        # If manual mode, add to approval queue
        if mode == PostMode.MANUAL:
            approval = ApprovalQueue(post_id=post.id, status=ApprovalStatus.PENDING)
            self.db.add(approval)
            await self.db.flush()
            logger.info(f"Post {post.id} sent to approval queue (manual mode)")

        logger.info(f"Created post {post.id} [{mode.value}] for {data.platform}")
        return post

    async def create_post_from_generated(
        self, generated: dict, request: GeneratePostRequest
    ) -> Post:
        """Create a post from AI-generated content with an auto-generated image."""
        hashtags = generated.get("hashtags", [])
        caption = generated.get("caption", "")
        image_prompt = generated.get("image_prompt", "")
        post_type_str = generated.get("post_type", "educational")

        hashtag_str = " ".join(f"#{h}" for h in hashtags)
        full_content = f"{caption}\n\n{hashtag_str}"

        post_type = PostType(post_type_str)
        mode = self.workflow.determine_mode(post_type)

        # Generate image from prompt using Pollinations.ai
        image_url = None
        if image_prompt:
            image_agent = ImageAgent()
            image_url = image_agent.generate_for_post_type(
                image_prompt, post_type_str
            )

        post = Post(
            content=full_content,
            platform=request.platform,
            post_type=post_type,
            mode=mode,
            hashtags=hashtag_str,
            image_prompt=image_prompt,
            image_url=image_url,
            account_id=request.account_id,
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
            f"Created AI-generated post {post.id} [{mode.value}] "
            f"image={'yes' if image_url else 'no'}"
        )
        return post

    async def get_post(self, post_id: int) -> Post | None:
        """Get a single post by ID."""
        result = await self.db.execute(select(Post).where(Post.id == post_id))
        return result.scalar_one_or_none()

    async def list_posts(
        self, status: str | None = None, platform: str | None = None
    ) -> list[Post]:
        """List posts with optional filtering."""
        query = select(Post).order_by(Post.created_at.desc())

        if status:
            query = query.where(Post.status == PostStatus(status))
        if platform:
            query = query.where(Post.platform == platform)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_post(self, post_id: int, data: PostEdit) -> Post | None:
        """Update an existing post."""
        post = await self.get_post(post_id)
        if not post:
            return None

        if data.content is not None:
            post.content = data.content
        if data.image_url is not None:
            post.image_url = data.image_url
        if data.scheduled_time is not None:
            post.scheduled_time = data.scheduled_time

        await self.db.flush()
        logger.info(f"Updated post {post_id}")
        return post

    async def mark_post_scheduled(self, post_id: int, scheduled_time: datetime) -> Post | None:
        """Mark a post as scheduled."""
        post = await self.get_post(post_id)
        if not post:
            return None
        post.status = PostStatus.SCHEDULED
        post.scheduled_time = scheduled_time
        await self.db.flush()
        return post

    async def mark_post_posted(self, post_id: int) -> Post | None:
        """Mark a post as successfully posted."""
        post = await self.get_post(post_id)
        if not post:
            return None
        post.status = PostStatus.POSTED
        await self.db.flush()
        return post

    async def mark_post_failed(self, post_id: int) -> Post | None:
        """Mark a post as failed."""
        post = await self.get_post(post_id)
        if not post:
            return None
        post.status = PostStatus.FAILED
        await self.db.flush()
        return post
