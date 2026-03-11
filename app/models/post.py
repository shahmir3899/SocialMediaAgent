"""Post model for social media content."""

import enum
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    POSTED = "posted"
    FAILED = "failed"


class PostMode(str, enum.Enum):
    AUTO = "auto"
    MANUAL = "manual"


class PostType(str, enum.Enum):
    EDUCATIONAL = "educational"
    ENGAGEMENT = "engagement"
    PROMOTIONAL = "promotional"
    QUOTE = "quote"
    ANNOUNCEMENT = "announcement"


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus), default=PostStatus.DRAFT, nullable=False
    )
    mode: Mapped[PostMode] = mapped_column(
        Enum(PostMode), default=PostMode.AUTO, nullable=False
    )
    post_type: Mapped[PostType] = mapped_column(
        Enum(PostType), default=PostType.EDUCATIONAL, nullable=False
    )
    hashtags: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    scheduled_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account", lazy="selectin")
    logs: Mapped[list["PostLog"]] = relationship("PostLog", back_populates="post", lazy="selectin")
    approval: Mapped["ApprovalQueue | None"] = relationship(
        "ApprovalQueue", back_populates="post", uselist=False, lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Post {self.id} [{self.status.value}] {self.platform}>"


from app.models.post_log import PostLog
from app.models.approval import ApprovalQueue
