"""API v2 — Herkese açık araçlar (giriş gerektirmez).

POST /api/v2/tools/yks-simulate — YKS net → puan → Türkiye sırası + sınav günü tahmini
(app/services/yks_public_sim.py; Etütkoç deneme analiz sistemindeki YKS Simülasyonu v4).
Kişisel veri saklanmaz; istek yalnız hesaplanır. IP başına dakikada 30 istek.
"""
from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.services import yks_public_sim as sim
from app.services.rate_limit import SlidingWindowLimiter, _client_ip

router = APIRouter(prefix="/tools", tags=["v2-tools-public"])

_limiter = SlidingWindowLimiter(window_seconds=60, max_hits=30)


class DenemeIn(BaseModel):
    date: Date | None = None
    nets: dict[str, float] = Field(default_factory=dict)


class YksSimulateIn(BaseModel):
    denemeler: list[DenemeIn] = Field(..., min_length=1, max_length=sim.MAX_DENEMES)
    score_type: str | None = Field(default=None, pattern="^(SAY|EA|SÖZ)$")
    diploma: float | None = Field(default=None, ge=50, le=100)


@router.get("/yks-meta")
def yks_meta() -> dict:
    """Form için test listesi + sınav tarihi (önbelleklenebilir)."""
    exam = sim.next_exam(Date.today())
    return {
        "tests": [{"key": k, "label": v[0], "questions": v[1], "session": v[2]} for k, v in sim.TESTS.items()],
        "field_tests": {st: list(atoms) for st, atoms in sim.FIELD_ATOMS.items()},
        "exam_date": exam["date"].isoformat(),
        "exam_official": bool(exam.get("official")),
        "rank_year": sim._rank_tables()["rank_year"],
    }


@router.post("/yks-simulate")
def yks_simulate(body: YksSimulateIn, request: Request) -> dict:
    allowed, retry = _limiter.hit(_client_ip(request))
    if not allowed:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            detail={"code": "rate_limited", "message": "Çok fazla deneme yaptın, biraz sonra tekrar dene."},
                            headers={"Retry-After": str(retry)})
    try:
        return sim.simulate([d.model_dump() for d in body.denemeler], body.score_type, body.diploma)
    except sim.SimulationInputError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"code": "invalid_input", "message": str(e)})
