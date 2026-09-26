"""Video Sepeti şemaları (koç)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class VideoItemOut(BaseModel):
    id: int
    youtube_id: str
    title: str
    url: str
    channel_title: str | None = None
    duration_min: int | None = None
    role: str
    role_label: str
    order: int
    #: waiting (sepette) | planned (programda) | watched (görev tamamlandı)
    status: str
    task_id: int | None = None
    task_date: str | None = None


class VideoGroupOut(BaseModel):
    group_key: str
    label: str
    topic_id: int | None = None
    topic_name: str | None = None
    subject_id: int | None = None
    subject_name: str | None = None
    playlist_title: str | None = None
    #: geldiği kayıtlı liste (sepet liste liste gösterilir)
    source_id: int | None = None
    total_min: int = 0
    waiting_count: int = 0
    items: list[VideoItemOut]


class VideoSourceOut(BaseModel):
    """Koçun kayıtlı listesi (daha önce getirdiği oynatma listesi / video)."""
    id: int
    name: str
    title: str | None = None
    label: str | None = None
    url: str
    subject_id: int | None = None
    subject_name: str | None = None
    video_count: int = 0
    created_at: str | None = None
    last_used_at: str | None = None
    #: bu öğrencinin sepetindeki video sayısı / bekleyen
    in_basket: int = 0
    waiting: int = 0


class VideoBasketResponse(BaseModel):
    youtube_configured: bool
    groups: list[VideoGroupOut]
    #: koçun tüm kayıtlı listeleri (son kullanılan önce)
    sources: list[VideoSourceOut] = []
    waiting_count: int
    #: Günlük video toplamı bu dakikayı geçince uyarı verilir (sınır değil).
    day_warn_minutes: int = 60


class VideoImportBody(BaseModel):
    #: yeni link; ya da kayıtlı liste için source_id
    url: str | None = Field(default=None, max_length=500)
    source_id: int | None = None
    subject_id: int | None = None


class VideoImportResult(BaseModel):
    added: int
    skipped_existing: int
    groups: int
    playlist_title: str | None = None
    truncated: bool = False
    unmatched_groups: int = 0
    source_id: int | None = None


class VideoItemPatchBody(BaseModel):
    role: str | None = None
    #: başka gruba taşı; "new" → tek başına yeni grup
    group_key: str | None = None


class VideoGroupPatchBody(BaseModel):
    group_key: str
    label: str | None = Field(default=None, max_length=255)
    #: 0 → konu bağını kaldır
    topic_id: int | None = None
    subject_id: int | None = None


class VideoGroupKeyBody(BaseModel):
    group_key: str


class VideoReorderBody(BaseModel):
    item_ids: list[int] = Field(min_length=1, max_length=500)


class VideoPlaceBody(BaseModel):
    item_ids: list[int] = Field(min_length=1, max_length=100)
    date: str
    period: str | None = None
    is_draft: bool | None = None


class VideoPlaceResult(BaseModel):
    task_ids: list[int]
    day_minutes: int


class VideoCopyBody(BaseModel):
    target_student_id: int
    group_keys: list[str] | None = None


class VideoCopyResult(BaseModel):
    added: int
    skipped_existing: int


class VideoSourcePatchBody(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    #: 0 → dersi kaldır
    subject_id: int | None = None


class VideoSourceDeleteBody(BaseModel):
    #: verilirse bu öğrencinin sepetindeki BEKLEYEN videoları da silinir
    student_id: int | None = None
    remove_waiting: bool = False
