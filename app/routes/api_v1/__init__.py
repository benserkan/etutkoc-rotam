"""Native mobile + external API katmanı (v1).

/api/v1 prefix altında JSON-only endpoint'ler. Web sürümü (HTML) `/teacher`,
`/student`, `/institution` route'larında olduğu gibi devam eder; mobile
client'lar `/api/v1/...` kullanır.

Auth:
  - POST /api/v1/auth/login           → JWT access + refresh
  - POST /api/v1/auth/refresh         → access token yenile
  - POST /api/v1/auth/logout          → no-op (stateless; client token siler)
  - GET  /api/v1/me                   → kullanıcı profili

Student:
  - GET  /api/v1/student/today
  - POST /api/v1/student/tasks/{id}/complete
  - GET  /api/v1/student/review       → due cards
  - POST /api/v1/student/review/{id}  → rating
  - GET  /api/v1/student/focus        → bugün özet + aktif session
  - POST /api/v1/student/focus/start
  - POST /api/v1/student/focus/{id}/end

Teacher:
  - GET  /api/v1/teacher/students     → öğrenci listesi
  - GET  /api/v1/teacher/students/{id} → detay özet
"""
from fastapi import APIRouter, Depends

from app.models import User
from app.routes.api_v1 import auth as api_auth
from app.routes.api_v1 import student as api_student
from app.routes.api_v1 import teacher as api_teacher
from app.routes.api_v1.auth import UserOut
from app.routes.api_v1.dependencies import get_current_api_user


router = APIRouter(prefix="/api/v1", tags=["api-v1"])
router.include_router(api_auth.router)
router.include_router(api_student.router)
router.include_router(api_teacher.router)


@router.get("/me", response_model=UserOut)
def api_v1_me(user: User = Depends(get_current_api_user)):
    """Mevcut kullanıcı profili (top-level)."""
    return UserOut.from_orm_user(user)


@router.get("/ping")
def api_v1_ping():
    """Health probe (auth gerektirmez) — mobile build smoke için."""
    return {"ok": True, "service": "lgs-api-v1"}
