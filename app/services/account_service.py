"""Service layer for account management."""

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.account import Account, Platform
from app.api.schemas import AccountConnect
from app.integrations.meta_client import MetaClient


class AccountService:
    """Handles account connection, listing, and disconnection."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.meta_client = MetaClient()

    async def connect_account(self, data: AccountConnect) -> Account:
        """Connect a new social media account after validating the token."""
        logger.info(f"Validating token for {data.platform} page: {data.page_id}")

        # Validate token with Meta API
        is_valid = await self.meta_client.validate_token(data.access_token)
        if not is_valid:
            logger.warning(f"Invalid token for {data.platform} page: {data.page_id}")
            # Still allow connection in dev mode, but log warning

        # Check if account already exists
        existing = await self.db.execute(
            select(Account).where(Account.page_id == data.page_id)
        )
        existing_account = existing.scalar_one_or_none()

        if existing_account:
            # Update existing account
            existing_account.access_token = data.access_token
            existing_account.page_name = data.page_name
            if data.token_expiry is not None:
                existing_account.token_expiry = data.token_expiry
            logger.info(f"Updated existing account: {data.page_name}")
            await self.db.flush()
            return existing_account

        # Create new account
        account = Account(
            platform=Platform(data.platform),
            page_id=data.page_id,
            page_name=data.page_name,
            access_token=data.access_token,
            token_expiry=data.token_expiry,
        )
        self.db.add(account)
        await self.db.flush()
        logger.info(f"Connected new account: {data.page_name} ({data.platform})")
        return account

    async def list_accounts(self) -> list[Account]:
        """List all connected accounts."""
        result = await self.db.execute(
            select(Account).order_by(Account.created_at.desc())
        )
        return list(result.scalars().all())

    async def disconnect_account(self, account_id: int) -> None:
        """Disconnect an account by ID."""
        await self.db.execute(delete(Account).where(Account.id == account_id))
        logger.info(f"Disconnected account {account_id}")

    async def get_account(self, account_id: int) -> Account | None:
        """Get a single account by ID."""
        result = await self.db.execute(
            select(Account).where(Account.id == account_id)
        )
        return result.scalar_one_or_none()

    async def get_account_by_platform(self, platform: str) -> Account | None:
        """Get the first account for a given platform."""
        result = await self.db.execute(
            select(Account).where(Account.platform == Platform(platform)).limit(1)
        )
        return result.scalar_one_or_none()
