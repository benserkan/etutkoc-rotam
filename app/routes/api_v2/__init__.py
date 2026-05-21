"""API v2 — Next.js BFF için JSON-only endpoint'ler.

Mevcut /api/v1 (native mobile, 47/47 smoke PASS) DOKUNULMAZ; v2 ayrı namespace.

Auth: dual-channel (session cookie + Bearer JWT). BFF __Host-access cookie
desteği Dalga 0 sonunda dependencies.py'a eklenir; endpoint'ler değişmez.

Hata zarfı (tüm 4xx/5xx):
    {"error": "...", "code": "...", "message": "...", "details": {...}?}

Mutation response zarfı (HTMX OOB swap karşılığı):
    {"data": {...}, "invalidate": ["queryKeyPrefix", ...]}

İlk dalgalar:
  - Dalga 1: /me (profil + KVKK self-serve)
  - Dalga 2: /student/*
  - Dalga 3: /teacher/*
  - Dalga 4: /institution/* (Paket 1: dashboard + teachers + roster + goals)
"""
from fastapi import APIRouter

from app.routes.api_v2 import academic as v2_academic
from app.routes.api_v2 import admin as v2_admin
from app.routes.api_v2 import auth as v2_auth
from app.routes.api_v2 import csv_ops as v2_csv
from app.routes.api_v2 import grade_advance as v2_grade
from app.routes.api_v2 import insights as v2_insights
from app.routes.api_v2 import institution as v2_institution
from app.routes.api_v2 import landing_public as v2_landing_public
from app.routes.api_v2 import library as v2_library
from app.routes.api_v2 import me as v2_me
from app.routes.api_v2 import offers_public as v2_offers_public
from app.routes.api_v2 import parent as v2_parent
from app.routes.api_v2 import settings as v2_settings
from app.routes.api_v2 import student as v2_student
from app.routes.api_v2 import teacher as v2_teacher
from app.routes.api_v2 import weekly_plan as v2_weekly_plan


router = APIRouter(prefix="/api/v2", tags=["api-v2"])
router.include_router(v2_auth.router)
router.include_router(v2_me.router)
router.include_router(v2_admin.router)
router.include_router(v2_student.router)
router.include_router(v2_teacher.router)
router.include_router(v2_institution.router)
router.include_router(v2_parent.router)
router.include_router(v2_offers_public.router)
router.include_router(v2_landing_public.router)
router.include_router(v2_library.router)
router.include_router(v2_insights.router)
router.include_router(v2_settings.router)
router.include_router(v2_academic.router)
router.include_router(v2_grade.router)
router.include_router(v2_csv.router)
router.include_router(v2_weekly_plan.router)


@router.get("/ping", include_in_schema=False)
def api_v2_ping():
    """Health probe — auth gerektirmez. CI smoke için."""
    return {"ok": True, "service": "lgs-api-v2"}
