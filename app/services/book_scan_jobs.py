"""Tam kitap tarama işleri — süper admin arka plan işi (2026-09-29).

Akış: admin PDF yükler → dosya geçici klasöre AKIŞLA yazılır (bellekte
tutulmaz) → iş satırı açılır → aynı süreçte arka plan iş parçacığı
`book_pipeline.run_pipeline`'ı koşar ve ilerlemeyi satıra yazar → sonuç
TASLAK (result_json) olarak saklanır, PDF silinir. Admin taslağı katalog
formuna aktarıp düzeltir ve kaydeder — tarama hiçbir zaman doğrudan yayına
çıkmaz.

Süreç başına aynı anda TEK iş koşar (Gemini kotası + bellek); diğerleri
sırada bekler. Sunucu yeniden başlarsa yarım kalan iş, nabız 20 dakikadır
gelmiyorsa listelemede "başarısız" işaretlenir.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.book_scan_job import (
    JOB_DONE,
    JOB_FAILED,
    JOB_QUEUED,
    JOB_RUNNING,
    BookScanJob,
)

logger = logging.getLogger(__name__)

MAX_SCAN_BYTES = 450 * 1024 * 1024
STALE_AFTER = timedelta(minutes=20)          # koşan işin nabzı
QUEUED_STALE_AFTER = timedelta(hours=3)      # sırada bekleyen (önünde uzun iş olabilir)
_CHUNK = 4 * 1024 * 1024
_RUN_LOCK = threading.Semaphore(1)


class ScanJobError(ValueError):
    def __init__(self, code: str, message: str, http: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http = http


def scan_dir() -> str:
    d = os.environ.get("BOOK_SCAN_DIR") or os.path.join(tempfile.gettempdir(), "etutkoc_book_scans")
    os.makedirs(d, exist_ok=True)
    return d


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _remove_file(path: str | None) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            logger.warning("tarama dosyası silinemedi: %s", path)


def save_upload(fileobj: Any, filename: str) -> tuple[str, int]:
    """Yüklenen dosyayı parça parça diske yazar. Döner: (yol, boyut)."""
    fd, path = tempfile.mkstemp(suffix=".pdf", dir=scan_dir())
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            head = b""
            while True:
                chunk = fileobj.read(_CHUNK)
                if not chunk:
                    break
                if not head:
                    head = chunk[:5]
                size += len(chunk)
                if size > MAX_SCAN_BYTES:
                    raise ScanJobError("file_too_large", "PDF en fazla 450 MB olabilir.")
                out.write(chunk)
        if size == 0:
            raise ScanJobError("empty_file", "Dosya boş.")
        if head != b"%PDF-":
            raise ScanJobError("not_pdf", "Yalnız PDF yüklenebilir.")
    except ScanJobError:
        _remove_file(path)
        raise
    return path, size


def create_job(
    db: Session,
    admin_id: int,
    *,
    fileobj: Any,
    filename: str,
    toc_pages: int = 12,
    page_offset: int | None = None,
    start: bool = True,
) -> BookScanJob:
    path, size = save_upload(fileobj, filename)
    try:
        from app.services.book_pipeline import fitz

        with fitz.open(path) as doc:
            page_count = doc.page_count
    except Exception:  # noqa: BLE001
        _remove_file(path)
        raise ScanJobError("pdf_unreadable", "PDF açılamadı — dosya bozuk ya da şifreli olabilir.")
    if page_count < 2:
        _remove_file(path)
        raise ScanJobError("pdf_too_short", "PDF'te en az 2 sayfa olmalı (kapak + içindekiler + gövde).")
    job = BookScanJob(
        created_by_id=admin_id,
        filename=(filename or "kitap.pdf")[:255],
        file_size=size,
        file_path=path,
        page_count=page_count,
        toc_pages=max(2, min(int(toc_pages or 12), 40)),
        page_offset=page_offset,
        status=JOB_QUEUED,
        progress=0,
        stage="Sırada — tarama birazdan başlayacak",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    if start:
        threading.Thread(target=run_job, args=(job.id, path), daemon=True,
                         name=f"book-scan-{job.id}").start()
    return job


def run_job(job_id: int, expected_path: str | None = None) -> None:
    """İşi koşar (arka plan iş parçacığı; kendi oturumunu açar)."""
    from app.database import SessionLocal
    from app.services import book_pipeline

    with _RUN_LOCK:
        db = SessionLocal()
        path: str | None = None
        try:
            job = db.get(BookScanJob, job_id)
            if job is None or job.status != JOB_QUEUED:
                return
            if expected_path is not None and job.file_path != expected_path:
                return  # satır silinmiş, kimlik başka bir işe geçmiş
            job.status = JOB_RUNNING
            job.started_at = job.heartbeat_at = _now()
            job.stage = "Başladı"
            db.commit()
            path = job.file_path
            last = {"at": 0.0, "stage": ""}

            def progress(pct: int, stage: str) -> None:
                import time

                t = time.monotonic()
                if stage == last["stage"] and t - last["at"] < 3 and pct < 100:
                    return
                last["at"], last["stage"] = t, stage
                try:
                    j = db.get(BookScanJob, job_id)
                    db.refresh(j) if j is not None else None
                    # Kimlik yeniden kullanımına karşı: yalnız KENDİ dosyamızın satırı
                    if j is not None and j.file_path == path:
                        j.progress = pct
                        j.stage = stage[:255]
                        j.heartbeat_at = _now()
                        db.commit()
                except Exception:  # noqa: BLE001 — ilerleme yazımı işi düşürmez
                    db.rollback()

            try:
                result = book_pipeline.run_pipeline(
                    path, toc_pages=job.toc_pages, offset=job.page_offset, progress=progress,
                )
            except book_pipeline.PipelineError as e:
                _finish(db, job_id, path, error=e.message)
                return
            except Exception as e:  # noqa: BLE001
                logger.exception("kitap taraması düştü (iş %s)", job_id)
                _finish(db, job_id, path, error=f"Tarama beklenmedik şekilde durdu: {e}")
                return
            _finish(db, job_id, path, result=result)
        finally:
            try:
                _remove_file(path)
                j = db.get(BookScanJob, job_id)
                if j is not None:
                    db.refresh(j)
                    if j.file_path == path:
                        j.file_path = None
                        db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
            db.close()


def _finish(
    db: Session, job_id: int, path: str | None, *, result: dict | None = None,
    error: str | None = None,
) -> None:
    job = db.get(BookScanJob, job_id)
    if job is None:
        return
    db.refresh(job)
    if job.file_path != path:  # satır silinmiş / kimlik başka işe geçmiş
        return
    job.finished_at = job.heartbeat_at = _now()
    if error is not None:
        job.status = JOB_FAILED
        job.error = error[:4000]
        job.stage = "Başarısız"
    else:
        job.status = JOB_DONE
        job.progress = 100
        job.result_json = json.dumps(result, ensure_ascii=False)
        job.stage = (
            "Bitti — kapılardan geçemeyenleri elle incele"
            if result and result.get("needs_review") else "Bitti"
        )
    db.commit()


def reap_stale(db: Session) -> int:
    """Nabzı kesilen (sunucu yeniden başladı) işleri başarısız işaretler."""
    now = _now()
    n = 0
    for job in db.query(BookScanJob).filter(BookScanJob.status.in_([JOB_QUEUED, JOB_RUNNING])).all():
        if job.status == JOB_RUNNING:
            beat = _aware(job.heartbeat_at) or _aware(job.started_at)
            stale = beat is not None and beat < now - STALE_AFTER
        else:
            made = _aware(job.created_at)
            stale = made is not None and made < now - QUEUED_STALE_AFTER
        if stale:
            job.status = JOB_FAILED
            job.error = "İş yarıda kaldı (sunucu yeniden başlamış olabilir) — PDF'i yeniden yükle."
            job.stage = "Başarısız"
            job.finished_at = _now()
            _remove_file(job.file_path)
            job.file_path = None
            n += 1
    if n:
        db.commit()
    return n


def list_jobs(db: Session, limit: int = 20) -> list[BookScanJob]:
    reap_stale(db)
    return db.query(BookScanJob).order_by(BookScanJob.id.desc()).limit(limit).all()


def delete_job(db: Session, job: BookScanJob) -> None:
    if job.status == JOB_RUNNING:
        raise ScanJobError("job_running", "Taranan iş silinemez — bitmesini bekle.", http=409)
    _remove_file(job.file_path)
    db.delete(job)
    db.commit()


def job_result(job: BookScanJob) -> dict | None:
    if not job.result_json:
        return None
    try:
        return json.loads(job.result_json)
    except ValueError:
        return None
