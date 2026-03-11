"""Post log model for tracking publishing results."""

from datetime import datetime
from sqlalchemy import Text, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PostLog(Base):
    __tablename__ = "post_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), nullable=False)
    platform_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="logs")

    def __repr__(self) -> str:
        status = "success" if self.success else "failed"
        return f"<PostLog {self.id} post={self.post_id} {status}>"


from app.models.post import Post
