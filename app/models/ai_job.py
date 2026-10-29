"""Arka plan yapay zekâ işi — deneme karnesi okuma vb. (2026-10-29).

Neden: karne PDF'i okuma 2–5 dk sürüyor (canlı ölçüm: ortanca 130 sn). Tek
istekte beklemek (a) bağlantı koparsa sonucu kaybettiriyor, (b) Cloudflare
proxy'nin 100 sn sınırına takılıyor. Akış: yükle (1-2 sn) → iş satırı → aynı
süreçte arka plan iş parçacığı okur → taslak burada saklanır → kullanıcı
önizleyip kaydeder. PDF satırda tutulur (≤10 MB), kayıtta deneme kaydına geçer,
kaydedilmeyen taslak 7 gün sonra silinir.

Kredi/ücretsiz hak YALNIZ okuma başarıyla bitince düşer (credits_charged).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

KIND_EXAM_IMPORT = "exam_import"

JOB_QUEUED = "queued"        # sırada (süreç içi semafor bekliyor)
JOB_RUNNING = "running"      # okunuyor
JOB_DONE = "done"            # taslak hazır — önizleme bekliyor
JOB_FAILED = "failed"        # okunamadı / servis hatası (ücret düşmedi)
JOB_CONSUMED = "consumed"    # taslak deneme olarak kaydedildi
JOB_DISMISSED = "dismissed"  # kullanıcı vazgeçti

ACTIVE_STATUSES = (JOB_QUEUED, JOB_RUNNING)
OPEN_STATUSES = (JOB_QUEUED, JOB_RUNNING, JOB_DONE, JOB_FAILED)

STATUS_LABELS_TR = {
    JOB_QUEUED: "Sırada",
    JOB_RUNNING: "Okunuyor",
    JOB_DONE: "Okundu — önizleme bekliyor",
    JOB_FAILED: "Okunamadı",
    JOB_CONSUMED: "Kaydedildi",
    JOB_DISMISSED: "Vazgeçildi",
}


class AiJob(Base):
    __tablename__ = "ai_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Yükleyen kişi (koç ya da öğrenci) — ekran bilgilendirmesi ona gider
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Kredi/kapı sahibi koç (öğrenci yüklediğinde de koçun havuzu)
    coach_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=JOB_QUEUED, index=True)
    stage: Mapped[str | None] = mapped_column(String(255), nullable=True)
    params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    input_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)
    error_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    credits_charged: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consumed_exam_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Kullanıcı "okundu" bilgisini gördü/kapattı → ekran kutusu bir daha çıkmaz
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def status_label(self) -> str:
        return STATUS_LABELS_TR.get(self.status, self.status)
