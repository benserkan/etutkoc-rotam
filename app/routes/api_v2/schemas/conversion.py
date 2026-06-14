"""API v2 şemaları — Dönüşüm (conversion) hunisi."""

from __future__ import annotations

from pydantic import BaseModel


class ConversionFunnel(BaseModel):
    visitors: int
    engaged: int
    clicked: int
    demo: int
    signups_landing: int
    signups_direct: int
    signups_total: int
    paid_total: int
    paid_landing: int
    rate_visitor_engaged: float
    rate_engaged_demo: float
    rate_visitor_signup: float
    rate_signup_paid: float
    rate_visitor_paid: float


class ConversionVariantRow(BaseModel):
    slug: str
    sessions: int
    signups: int
    conversion_pct: float
    paid: int
    paid_pct: float


class ConversionResponse(BaseModel):
    days: int
    funnel: ConversionFunnel
    variants: list[ConversionVariantRow]
    has_experiment: bool
    experiment_name: str | None = None
