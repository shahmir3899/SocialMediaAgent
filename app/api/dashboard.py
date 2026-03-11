"""Dashboard routes serving HTML templates."""

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.post import Post, PostStatus
from app.models.account import Account

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
