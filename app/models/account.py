"""Account model for connected social media accounts."""

import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Platform(str, enum.Enum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    page_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    page_name: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[str] = mapped_column(String(1024), nullable=False)
    token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Account {self.platform.value}:{self.page_name}>"

    @property
    def is_token_expired(self) -> bool:
        if self.token_expiry is None:
            return False
        from datetime import timezone
        return datetime.now(timezone.utc) > self.token_expiry
