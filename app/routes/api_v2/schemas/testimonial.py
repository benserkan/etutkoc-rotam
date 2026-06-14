"""API v2 şemaları — Testimonial (sosyal kanıt)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- public (anasayfa)

class TestimonialPublicItem(BaseModel):
    id: int
    kind: str
    author_name: str
    author_role: str | None = None
    author_role_label: str | None = None
    author_title: str | None = None
    institution_name: str | None = None
    rating: int | None = None
    content: str
    featured: bool


class TestimonialPublicResponse(BaseModel):
    items: list[TestimonialPublicItem]
    counts: dict[str, int]


# ---------------------------------------------------------------- uygulama-içi gönderim

class TestimonialSubmitBody(BaseModel):
    content: str = Field(..., min_length=10, max_length=2000)
    rating: int | None = Field(default=None, ge=1, le=5)
    author_name: str = Field(..., min_length=2, max_length=160)
    consent_public: bool = False


class TestimonialSubmitOut(BaseModel):
    ok: bool = True
    message: str
    already_pending: bool = False


class TestimonialPromptOut(BaseModel):
    eligible: bool
    default_name: str | None = None


# ---------------------------------------------------------------- süper admin

class TestimonialAdminItem(BaseModel):
    id: int
    kind: str
    kind_label: str
    author_name: str
    author_role: str | None = None
    author_role_label: str | None = None
    author_title: str | None = None
    institution_name: str | None = None
    rating: int | None = None
    content: str
    status: str
    status_label: str
    source: str
    source_label: str
    submitted_by_id: int | None = None
    consent_public: bool
    featured: bool
    sort_order: int
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TestimonialAdminListResponse(BaseModel):
    items: list[TestimonialAdminItem]
    counts: dict[str, int]
    kinds: dict[str, str]
    statuses: dict[str, str]
    roles: dict[str, str]


class TestimonialCreateBody(BaseModel):
    kind: str = "review"
    author_name: str = Field(..., min_length=2, max_length=160)
    author_role: str | None = Field(default=None, max_length=30)
    author_title: str | None = Field(default=None, max_length=200)
    institution_name: str | None = Field(default=None, max_length=200)
    rating: int | None = Field(default=None, ge=1, le=5)
    content: str = Field(..., min_length=5, max_length=2000)
    status: str = "published"
    consent_public: bool = True
    featured: bool = False
    sort_order: int = 0


class TestimonialUpdateBody(BaseModel):
    kind: str | None = None
    author_name: str | None = Field(default=None, max_length=160)
    author_role: str | None = Field(default=None, max_length=30)
    author_title: str | None = Field(default=None, max_length=200)
    institution_name: str | None = Field(default=None, max_length=200)
    rating: int | None = Field(default=None, ge=1, le=5)
    content: str | None = Field(default=None, max_length=2000)
    consent_public: bool | None = None
    featured: bool | None = None
    sort_order: int | None = None


class TestimonialStatusBody(BaseModel):
    status: str = Field(..., pattern="^(pending|published|hidden)$")
