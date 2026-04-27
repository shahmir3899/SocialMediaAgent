"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from pydantic import BaseModel, Field


# ─── Account Schemas ───

class AccountConnect(BaseModel):
    platform: str = Field(..., description="Platform: facebook or instagram")
    page_id: str
    page_name: str
    access_token: str
    token_expiry: datetime | None = None


class AccountResponse(BaseModel):
    id: int
    platform: str
    page_id: str
    page_name: str
    token_expiry: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Post Schemas ───

class PostCreate(BaseModel):
    content: str
    image_url: str | None = None
    platform: str
    post_type: str = "educational"
    account_id: int | None = None
    scheduled_time: datetime | None = None


class PostEdit(BaseModel):
    content: str | None = None
    image_url: str | None = None
    scheduled_time: datetime | None = None


class PostResponse(BaseModel):
    id: int
    content: str
    image_url: str | None
    platform: str
    status: str
    mode: str
    post_type: str
    hashtags: str | None
    scheduled_time: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Approval Schemas ───

class ApprovalAction(BaseModel):
    reviewer_notes: str | None = None


class ApprovalResponse(BaseModel):
    id: int
    post_id: int
    status: str
    reviewer_notes: str | None
    reviewed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Generation Schemas ───

class GeneratePostRequest(BaseModel):
    post_type: str = "educational"
    platform: str = "facebook"
    topic: str | None = None
    additional_keywords: str | None = None
    account_id: int | None = None
    generation_mode: str = "direct_topic"  # direct_topic | website | random
    website_source_ids: list[int] | None = None
    website_urls: list[str] | None = None


class GeneratedPostResponse(BaseModel):
    caption: str
    hashtags: list[str]
    image_prompt: str
    post_type: str


# ─── Post Log Schemas ───

class PostLogResponse(BaseModel):
    id: int
    post_id: int
    platform_response: str | None
    posted_at: datetime
    success: bool

    model_config = {"from_attributes": True}


# ─── Website Source Schemas ───

class WebsiteSourceCreate(BaseModel):
    name: str
    base_url: str
    is_enabled: bool = True
    priority: int = 100
    notes: str | None = None
    max_pages: int = 20


class WebsiteSourceUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    is_enabled: bool | None = None
    priority: int | None = None
    notes: str | None = None
    max_pages: int | None = None


class WebsiteSourceResponse(BaseModel):
    id: int
    name: str
    base_url: str
    is_enabled: bool
    priority: int
    notes: str | None
    max_pages: int
    last_crawled_at: datetime | None
    last_status: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
