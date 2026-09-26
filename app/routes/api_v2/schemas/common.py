"""API v2 ortak şemalar — hata zarfı, mutation zarfı, sayfalama.

Referans: API_CONTRACTS_DRAFT.md §0.
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Tüm 4xx/5xx yanıtlarında HTTPException.detail içeriği.

    OpenAPI'ye dokümantasyon amaçlı. Gerçek hata zarfı dependencies.py'da
    `_auth_error()` ve route'lardaki `HTTPException(detail={...})` tarafından
    üretilir; bu şema sözleşmenin görünür hâlidir.
    """
    error: str
    code: str | None = None
    message: str
    details: dict | None = None


class MutationResponse(BaseModel, Generic[T]):
    """Başarılı mutasyon zarfı — OOB swap karşılığı.

    `invalidate` listesindeki her string Next.js TanStack Query'de queryKey
    prefix'i olarak yorumlanır; ilgili tüm component'ler otomatik yeniden çeker.
    Bu mekanizma App Router cache bayatlama riskini (R-007) kapatır.

    Örnek:
      {"data": {...}, "invalidate": ["me:kvkk", "me:requests"]}
    """
    data: T
    invalidate: list[str] = []
    # İşlem BAŞARILI ama koçun bilmesi gereken durum (örn. kayıtlı kapasite
    # aşılarak atama). Hata değildir — frontend bilgilendirme olarak gösterir.
    warnings: list[str] = []


class SimpleOk(BaseModel):
    """Yan etkisi olmayan onay response'u."""
    ok: bool = True
    message: str | None = None


class Page(BaseModel, Generic[T]):
    """Listeleme endpoint'lerinde ortak sayfalama."""
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 25
    has_next: bool = False


class TaskVideoRef(BaseModel):
    """Video Sepeti'nden göreve konmuş video (çok linkli video görevi)."""
    id: int
    youtube_id: str
    title: str
    url: str
    duration_min: int | None = None
    role: str = "anlatim"


def task_video_refs(task) -> list[TaskVideoRef]:
    """Görevin sepet videoları (sıra korunur). Sepetsiz görev → []."""
    return [
        TaskVideoRef(id=v.id, youtube_id=v.youtube_id, title=v.title, url=v.url,
                     duration_min=v.duration_min, role=v.role)
        for v in (getattr(task, "basket_videos", None) or [])
    ]
