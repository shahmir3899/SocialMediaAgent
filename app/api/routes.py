"""API route definitions."""

import secrets
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import logger
from app.models.account import Account, Platform
from app.models.post import Post, PostStatus, PostMode, PostType
from app.models.post_log import PostLog
from app.models.approval import ApprovalQueue, ApprovalStatus
from app.api.schemas import (
    AccountConnect, AccountResponse,
    PostCreate, PostEdit, PostResponse,
    ApprovalAction, ApprovalResponse,
    GeneratePostRequest, GeneratedPostResponse,
    PostLogResponse,
)
from app.services.account_service import AccountService
from app.services.post_service import PostService
from app.services.approval_service import ApprovalService
from app.agents.content_agent import ContentAgent
from app.integrations.meta_client import MetaClient

router = APIRouter()
settings = get_settings()


def _compose_topic(topic: str | None, additional_keywords: str | None) -> str | None:
    """Build a single topic string from a preset topic and optional extra keywords."""
    clean_topic = (topic or "").strip()
    clean_keywords = (additional_keywords or "").strip()

    if clean_topic and clean_keywords:
        return f"{clean_topic}. Include these keywords naturally: {clean_keywords}"
    if clean_topic:
        return clean_topic
    if clean_keywords:
        return f"Focus on these keywords: {clean_keywords}"
    return None


# ─── Account Endpoints ───

@router.post("/accounts/connect", response_model=AccountResponse)
async def connect_account(data: AccountConnect, db: AsyncSession = Depends(get_db)):
    """Connect a new social media account."""
    logger.info(f"Connecting {data.platform} account: {data.page_name}")
    service = AccountService(db)
    account = await service.connect_account(data)
    return account


@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    """List all connected accounts."""
    service = AccountService(db)
    return await service.list_accounts()


@router.delete("/accounts/{account_id}")
async def disconnect_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """Disconnect a social media account."""
    service = AccountService(db)
    await service.disconnect_account(account_id)
    return {"message": "Account disconnected"}


@router.post("/accounts/{account_id}/test")
async def test_account_connection(account_id: int, db: AsyncSession = Depends(get_db)):
    """Test whether an account's access token is still valid."""
    service = AccountService(db)
    account = await service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    meta = MetaClient()
    is_valid = await meta.validate_token(account.access_token)
    return {"valid": is_valid, "account_id": account_id}


@router.get("/auth/meta")
async def meta_oauth_start():
    """Begin Facebook OAuth: redirect browser to Facebook authorization dialog."""
    state = secrets.token_urlsafe(32)
    params = urlencode({
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.meta_redirect_uri,
        "scope": "pages_show_list,pages_manage_posts,pages_read_engagement,instagram_basic,instagram_content_publish",
        "response_type": "code",
        "state": state,
    })
    response = RedirectResponse(
        url=f"https://www.facebook.com/dialog/oauth?{params}",
        status_code=302,
    )
    response.set_cookie(key="oauth_state", value=state, max_age=600, httponly=True, samesite="lax")
    return response


@router.get("/auth/meta/callback")
async def meta_oauth_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Handle Facebook OAuth callback: exchange tokens, discover pages, save accounts."""
    def _popup_result(status: str, message: str) -> HTMLResponse:
        """Return a small HTML page that notifies the opener window and closes."""
        return HTMLResponse(f"""
        <!DOCTYPE html><html><head><title>Connecting...</title></head>
        <body>
        <script>
            if (window.opener) {{
                window.opener.postMessage({{ type: 'oauth_result', status: '{status}', message: '{message}' }}, '*');
                window.close();
            }} else {{
                window.location.href = '/accounts?{"success=1" if status == "success" else "error=" + message}';
            }}
        </script>
        <p>Redirecting&hellip;</p>
        </body></html>
        """)

    if error:
        logger.warning(f"Facebook OAuth error: {error}")
        return _popup_result("error", error)

    if not code:
        return _popup_result("error", "missing_code")

    # CSRF check via state cookie
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or stored_state != state:
        logger.warning("OAuth state mismatch")
        return _popup_result("error", "state_mismatch")

    meta = MetaClient()

    # Exchange code for short-lived user token
    token_data = await meta.exchange_code_for_token(code)
    if not token_data.get("access_token"):
        return _popup_result("error", "token_exchange_failed")

    # Exchange short-lived token for 60-day long-lived token
    long_lived_data = await meta.exchange_for_long_lived_token(token_data["access_token"])
    if not long_lived_data.get("access_token"):
        return _popup_result("error", "long_lived_token_failed")

    long_lived_token = long_lived_data["access_token"]
    expires_in = long_lived_data.get("expires_in", 5184000)
    token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # Discover all managed Facebook Pages
    pages = await meta.get_managed_pages(long_lived_token)
    if not pages:
        return _popup_result("error", "no_pages_found")

    # Save each Page and any linked Instagram account
    service = AccountService(db)
    for page in pages:
        page_id = page.get("id")
        page_name = page.get("name")
        page_token = page.get("access_token")
        if not all([page_id, page_name, page_token]):
            continue

        await service.connect_account(AccountConnect(
            platform="facebook",
            page_id=page_id,
            page_name=page_name,
            access_token=page_token,
            token_expiry=token_expiry,
        ))

        ig = await meta.get_instagram_account(page_id, page_token)
        if ig and ig.get("id"):
            await service.connect_account(AccountConnect(
                platform="instagram",
                page_id=ig["id"],
                page_name=f"{page_name} (Instagram)",
                access_token=page_token,
                token_expiry=token_expiry,
            ))

    response = _popup_result("success", "accounts_connected")
    response.delete_cookie("oauth_state")
    return response


# ─── Post Generation Endpoints ───

@router.post("/posts/generate", response_model=GeneratedPostResponse)
async def generate_post(data: GeneratePostRequest):
    """Generate a post using AI."""
    logger.info(f"Generating {data.post_type} post for {data.platform}")
    agent = ContentAgent()
    topic = _compose_topic(data.topic, data.additional_keywords)
    result = await agent.generate_post(
        post_type=data.post_type,
        platform=data.platform,
        topic=topic,
    )
    return result


@router.post("/posts/generate-and-save", response_model=PostResponse)
async def generate_and_save_post(
    data: GeneratePostRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a post with AI and save it to the database."""
    import random
    from app.scheduler.content_scheduler import TOPIC_POOLS

    topic = _compose_topic(data.topic, data.additional_keywords)
    if not topic:
        pool = TOPIC_POOLS.get(data.post_type, TOPIC_POOLS.get("educational", []))
        if pool:
            topic = random.choice(pool)

    logger.info(f"Generating and saving {data.post_type} post for {data.platform} topic='{topic}'")
    agent = ContentAgent()
    generated = await agent.generate_post(
        post_type=data.post_type,
        platform=data.platform,
        topic=topic,
    )

    service = PostService(db)
    post = await service.create_post_from_generated(generated, data)
    return post


# ─── Post CRUD Endpoints ───

@router.post("/posts", response_model=PostResponse)
async def create_post(data: PostCreate, db: AsyncSession = Depends(get_db)):
    """Create a new post manually."""
    service = PostService(db)
    post = await service.create_post(data)
    return post


@router.get("/posts", response_model=list[PostResponse])
async def list_posts(
    status: str | None = None,
    platform: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List posts with optional filtering."""
    service = PostService(db)
    return await service.list_posts(status=status, platform=platform)


@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single post by ID."""
    service = PostService(db)
    post = await service.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.put("/posts/{post_id}", response_model=PostResponse)
async def update_post(post_id: int, data: PostEdit, db: AsyncSession = Depends(get_db)):
    """Edit an existing post."""
    service = PostService(db)
    post = await service.update_post(post_id, data)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


# ─── Approval Endpoints ───

@router.get("/posts/pending/list", response_model=list[PostResponse])
async def list_pending_posts(db: AsyncSession = Depends(get_db)):
    """List all posts pending approval."""
    service = ApprovalService(db)
    return await service.list_pending_posts()


@router.post("/posts/{post_id}/approve", response_model=PostResponse)
async def approve_post(
    post_id: int,
    data: ApprovalAction | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending post."""
    logger.info(f"Approving post {post_id}")
    service = ApprovalService(db)
    post = await service.approve_post(post_id, data)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.post("/posts/{post_id}/reject", response_model=PostResponse)
async def reject_post(
    post_id: int,
    data: ApprovalAction | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending post."""
    logger.info(f"Rejecting post {post_id}")
    service = ApprovalService(db)
    post = await service.reject_post(post_id, data)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


# ─── Schedule Endpoints ───

@router.get("/posts/scheduled/list", response_model=list[PostResponse])
async def list_scheduled_posts(db: AsyncSession = Depends(get_db)):
    """List all scheduled posts."""
    service = PostService(db)
    return await service.list_posts(status="scheduled")


# ─── Publish Endpoints ───

@router.post("/posts/{post_id}/publish")
async def publish_post_now(post_id: int, db: AsyncSession = Depends(get_db)):
    """Immediately publish a post to the connected social media account."""
    # Get the post
    post_service = PostService(db)
    post = await post_service.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.status == PostStatus.POSTED:
        raise HTTPException(status_code=400, detail="Post already published")

    # Get the account for this platform
    account_service = AccountService(db)
    account = await account_service.get_account_by_platform(post.platform)
    if not account:
        raise HTTPException(status_code=400, detail=f"No {post.platform} account connected")

    # Publish to the platform
    meta = MetaClient()
    if post.platform == "facebook":
        result = await meta.publish_facebook_post(
            page_id=account.page_id,
            access_token=account.access_token,
            message=post.content,
            image_url=post.image_url,
        )
    elif post.platform == "instagram":
        if not post.image_url:
            raise HTTPException(status_code=400, detail="Instagram posts require an image")
        result = await meta.publish_instagram_post(
            ig_user_id=account.page_id,
            access_token=account.access_token,
            caption=post.content,
            image_url=post.image_url,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {post.platform}")

    # Log the result
    log_entry = PostLog(
        post_id=post.id,
        success=result.get("success", False),
        platform_response=str(result.get("response") or result.get("error", "")),
    )
    db.add(log_entry)

    if result.get("success"):
        post.status = PostStatus.POSTED
        logger.info(f"Published post {post_id} to {post.platform}")
        await db.flush()
        return {"success": True, "message": "Post published successfully", "post_id": result.get("post_id")}
    else:
        post.status = PostStatus.FAILED
        await db.flush()
        error_msg = result.get("error", "Unknown error")
        logger.error(f"Failed to publish post {post_id}: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Publish failed: {error_msg}")


# ─── Post Log Endpoints ───

@router.get("/posts/{post_id}/logs", response_model=list[PostLogResponse])
async def get_post_logs(post_id: int, db: AsyncSession = Depends(get_db)):
    """Get publishing logs for a post."""
    result = await db.execute(
        select(PostLog).where(PostLog.post_id == post_id).order_by(PostLog.posted_at.desc())
    )
    return result.scalars().all()


# ─── Analytics Endpoints ───

@router.get("/analytics/summary")
async def get_analytics_summary(db: AsyncSession = Depends(get_db)):
    """Get a summary of posting analytics."""
    from sqlalchemy import func

    total_posts = await db.scalar(select(func.count(Post.id)))
    posted = await db.scalar(
        select(func.count(Post.id)).where(Post.status == PostStatus.POSTED)
    )
    failed = await db.scalar(
        select(func.count(Post.id)).where(Post.status == PostStatus.FAILED)
    )
    pending = await db.scalar(
        select(func.count(Post.id)).where(Post.status == PostStatus.PENDING)
    )
    scheduled = await db.scalar(
        select(func.count(Post.id)).where(Post.status == PostStatus.SCHEDULED)
    )

    return {
        "total_posts": total_posts or 0,
        "posted": posted or 0,
        "failed": failed or 0,
        "pending_approval": pending or 0,
        "scheduled": scheduled or 0,
    }
