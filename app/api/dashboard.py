"""Dashboard routes serving HTML templates."""

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.post import Post, PostStatus
from app.models.account import Account
from app.models.website_source import WebsiteSource

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/")
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Dashboard home page with stats and recent posts."""
    total = await db.scalar(select(func.count(Post.id))) or 0
    posted = await db.scalar(select(func.count(Post.id)).where(Post.status == PostStatus.POSTED)) or 0
    failed = await db.scalar(select(func.count(Post.id)).where(Post.status == PostStatus.FAILED)) or 0
    pending = await db.scalar(select(func.count(Post.id)).where(Post.status == PostStatus.PENDING)) or 0
    scheduled = await db.scalar(select(func.count(Post.id)).where(Post.status == PostStatus.SCHEDULED)) or 0

    result = await db.execute(select(Post).order_by(Post.created_at.desc()).limit(20))
    recent_posts = result.scalars().all()

    source_stats_result = await db.execute(
        select(
            WebsiteSource.id,
            WebsiteSource.name,
            func.count(Post.id).label("generated"),
            func.coalesce(
                func.sum(case((Post.status == PostStatus.POSTED, 1), else_=0)),
                0,
            ).label("posted"),
            func.coalesce(
                func.sum(case((Post.status == PostStatus.FAILED, 1), else_=0)),
                0,
            ).label("failed"),
        )
        .outerjoin(Post, Post.website_source_id == WebsiteSource.id)
        .group_by(WebsiteSource.id, WebsiteSource.name, WebsiteSource.priority)
        .order_by(WebsiteSource.priority.asc(), WebsiteSource.name.asc())
    )
    source_stats = [
        {
            "id": row.id,
            "name": row.name,
            "generated": int(row.generated or 0),
            "posted": int(row.posted or 0),
            "failed": int(row.failed or 0),
        }
        for row in source_stats_result
    ]

    return templates.TemplateResponse("pages/dashboard.html", {
        "request": request,
        "stats": {
            "total_posts": total,
            "posted": posted,
            "failed": failed,
            "pending_approval": pending,
            "scheduled": scheduled,
        },
        "recent_posts": recent_posts,
        "source_stats": source_stats,
    })


@router.get("/accounts")
async def accounts_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Accounts management page."""
    result = await db.execute(select(Account).order_by(Account.created_at.desc()))
    accounts = result.scalars().all()

    return templates.TemplateResponse("pages/accounts.html", {
        "request": request,
        "accounts": accounts,
    })


@router.get("/pending")
async def pending_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Pending approvals page."""
    result = await db.execute(
        select(Post).where(Post.status == PostStatus.PENDING).order_by(Post.created_at.desc())
    )
    posts = result.scalars().all()

    return templates.TemplateResponse("pages/pending.html", {
        "request": request,
        "posts": posts,
    })


@router.get("/scheduled")
async def scheduled_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Scheduled posts page."""
    result = await db.execute(
        select(Post).where(Post.status == PostStatus.SCHEDULED).order_by(Post.scheduled_time)
    )
    posts = result.scalars().all()

    return templates.TemplateResponse("pages/scheduled.html", {
        "request": request,
        "posts": posts,
    })


@router.get("/history")
async def history_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Post history page."""
    result = await db.execute(select(Post).order_by(Post.created_at.desc()).limit(50))
    posts = result.scalars().all()

    return templates.TemplateResponse("pages/history.html", {
        "request": request,
        "posts": posts,
    })
