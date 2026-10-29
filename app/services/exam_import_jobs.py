"""Deneme karnesi okuma — arka plan işi (2026-10-29).

Akış: yükle (hızlı kapılar: koç/rıza/kredi/aynı PDF) → `ai_jobs` satırı →
aynı süreçte arka plan iş parçacığı okur → taslak satırda → kullanıcı
önizler ve kaydeder (`import-confirm` + job_id; PDF yeniden yüklenmez).

Okuma çekirdeği (`analyze_core`) hem bu yürütücü hem eski tek-istekli uç
tarafından kullanılır → iki yol aynı sonucu üretir.

Sağlamlık:
- Süreç başına en çok MAX_PARALLEL okuma (Gemini kotası + bellek); fazlası
  sırada bekler. Koç birden çok öğrencinin karnesini art arda yükleyebilir.
- Nabız: bu süreçteki işler HEARTBEAT_EVERY'de bir damgalanır. Nabzı
  STALE_AFTER'dan eski iş (sunucu yeniden başladı / süreç öldü) bir sonraki
  sorguda başka süreç tarafından devralınır; MAX_ATTEMPTS'ten sonra başarısız.
- Kredi/ücretsiz hak YALNIZ okuma başarıyla bitince düşer → yarıda kalan iş
  ikinci kez ücretlendirilmez.
- Kaydedilmeyen taslak DRAFT_TTL sonra silinir.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.models import EXAM_SECTION_LABELS, ExamSection, UsageKind, User
from app.models.ai_job import (
    ACTIVE_STATUSES,
    JOB_CONSUMED,
    JOB_DISMISSED,
    JOB_DONE,
    JOB_FAILED,
    JOB_QUEUED,
    JOB_RUNNING,
    KIND_EXAM_IMPORT,
    OPEN_STATUSES,
    AiJob,
)
from app.services import exam_duplicate, free_exam_quota
from app.services import exam_import_service as svc
from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable
from app.services.credits import (
    CreditBlocked,
    CreditOwner,
    KIND_CREDITS,
    check_credit_available,
    consume_credits,
)

logger = logging.getLogger(__name__)

MAX_PARALLEL = 3
MAX_ATTEMPTS = 2
HEARTBEAT_EVERY = 20       # sn
STALE_AFTER = timedelta(seconds=90)
DRAFT_TTL = timedelta(days=7)
# Kullanıcının kendi tekrar deneyebileceği hata kodları (belge sorunu değil)
RETRYABLE_CODES = {"ai_unavailable", "server_restarted", "internal_error", "ai_credit_exhausted"}

# Testler yürütücüyü kendi iş parçacığında beklemek yerine senkron koşturabilir
RUN_INLINE = False


class JobError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Okuma çekirdeği (eski tek-istekli uç da bunu kullanır)
# ---------------------------------------------------------------------------


def section_choices() -> list[dict]:
    return [{"value": s.value, "label": EXAM_SECTION_LABELS[s]} for s in ExamSection]


def check_pdf_duplicate(db: Session, student: User, pdf_bytes: bytes) -> None:
    """Aynı PDF bu öğrenciye daha önce kaydedildiyse Gemini'ye gitmeden dur."""
    prior = exam_duplicate.find_by_pdf(db, student.id, exam_duplicate.pdf_sha256(pdf_bytes))
    if prior is not None:
        m = exam_duplicate.DuplicateMatch(
            exam_duplicate.LEVEL_EXACT, "same_file", prior.id, prior.title,
            prior.exam_date.isoformat(), 1.0,
        )
        raise JobError(409, "duplicate_exam", m.message(), m.as_details())


def analyze_core(
    db: Session,
    *,
    student: User,
    coach: User,
    actor: User,
    pdf_bytes: bytes,
    declared_section: str | None = None,
    declared_grade: int | None = None,
    filename: str | None = None,
) -> dict:
    """Çift okuma + normalizasyon + kredi. Döner: taslak sözlüğü (credits_charged,
    free_quota_left, section_choices dahil). Hata → JobError (db geri alınmış)."""
    quota = free_exam_quota.status_for(db, coach)
    try:
        if quota.applies:
            draft = svc.analyze(
                db, student, pdf_bytes,
                declared_section=declared_section, declared_grade=declared_grade)
            free_exam_quota.record_free_use(db, coach, actor_id=actor.id, metadata={
                "student_id": student.id,
                "rows": len(draft["rows"]),
                "universe": draft["universe"],
            })
        else:
            with consume_credits(
                db, owner=CreditOwner.for_user(coach), kind=UsageKind.AI_EXAM_IMPORT,
                actor_user_id=actor.id, autocommit=False,
            ) as ctx:
                draft = svc.analyze(
                    db, student, pdf_bytes,
                    declared_section=declared_section, declared_grade=declared_grade)
                ctx.set_metadata({
                    "student_id": student.id,
                    "rows": len(draft["rows"]),
                    "universe": draft["universe"],
                    "suspects": draft["suspect_count"],
                })
    except CreditBlocked:
        db.rollback()
        raise JobError(402, "ai_credit_exhausted", "Koçun yapay zekâ kredisi bu ay için doldu.")
    except svc.ExamImportError as e:
        db.rollback()
        raise JobError(e.status, e.code, e.message, getattr(e, "details", None))
    except AIInvalidResponse as e:
        db.rollback()
        raise JobError(422, "pdf_unreadable", str(e) or (
            "Belge okunamadı — konu analizi içeren bir deneme sonuç PDF'i yükleyin."))
    except AIServiceUnavailable as e:
        db.rollback()
        raise JobError(502, "ai_unavailable", f"Yapay zekâ servisi şu an kullanılamıyor: {e}")
    db.commit()  # kullanım kaydı + sözlük hit sayaçları
    # Karnede tarih yoksa dosya adındaki tarih önerilir (2026-10-06).
    if not draft.get("exam_date"):
        fd = svc.date_from_filename(filename)
        if fd:
            draft["exam_date"] = fd.isoformat()
            draft["checks"] = list(draft.get("checks") or []) + [{
                "code": "date_from_filename", "label": "Tarih dosya adından",
                "ok": True,
                "detail": f"Karnede tarih yazmıyor; dosya adından {fd.strftime('%d.%m.%Y')} "
                          "alındı — doğru değilse değiştir.",
            }]
    draft["section_choices"] = section_choices()
    draft["credits_charged"] = 0 if quota.applies else KIND_CREDITS[UsageKind.AI_EXAM_IMPORT]
    draft["free_quota_left"] = (quota.left - 1) if quota.applies else None
    return draft


# ---------------------------------------------------------------------------
# İş oluşturma
# ---------------------------------------------------------------------------


def create_exam_job(
    db: Session,
    *,
    owner: User,
    student: User,
    coach: User,
    pdf_bytes: bytes,
    filename: str | None,
    content_type: str | None,
    declared_section: str | None = None,
    declared_grade: int | None = None,
) -> AiJob:
    """Hızlı kontrolleri yap, işi aç ve başlat (yanıt beklemeden döner)."""
    check_pdf_duplicate(db, student, pdf_bytes)
    sha = exam_duplicate.pdf_sha256(pdf_bytes)
    open_same = (
        db.query(AiJob)
        .filter(
            AiJob.kind == KIND_EXAM_IMPORT,
            AiJob.student_id == student.id,
            AiJob.input_sha256 == sha,
            AiJob.status.in_((JOB_QUEUED, JOB_RUNNING, JOB_DONE)),
        )
        .first()
    )
    if open_same is not None:
        raise JobError(409, "job_exists", (
            "Bu karne zaten okunuyor ya da önizleme bekliyor."
            if open_same.status != JOB_DONE else
            "Bu karne okundu ve önizleme bekliyor — oradan kaydedebilirsin."),
            {"job_id": open_same.id, "status": open_same.status})
    # Ön kredi kontrolü: kredisi bitmiş koç 3 dk beklemeden öğrensin
    quota = free_exam_quota.status_for(db, coach)
    if not quota.applies:
        chk = check_credit_available(
            db, owner=CreditOwner.for_user(coach), kind=UsageKind.AI_EXAM_IMPORT)
        if not chk.ok:
            raise JobError(402, "ai_credit_exhausted", "Koçun yapay zekâ kredisi bu ay için doldu.")

    now = _now()
    job = AiJob(
        kind=KIND_EXAM_IMPORT,
        owner_id=owner.id,
        student_id=student.id,
        coach_id=coach.id,
        status=JOB_QUEUED,
        stage="Sırada",
        params_json=json.dumps({
            "declared_section": declared_section,
            "declared_grade": declared_grade,
        }),
        input_data=pdf_bytes,
        input_filename=(filename or "")[:255] or None,
        input_content_type=(content_type or "application/pdf")[:100],
        input_sha256=sha,
        heartbeat_at=now,
        expires_at=now + DRAFT_TTL,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    start(job.id)
    return job



# ---------------------------------------------------------------------------
# Yürütücü
# ---------------------------------------------------------------------------

_SEM = threading.Semaphore(MAX_PARALLEL)
_LOCAL_JOBS: set[int] = set()
_LOCAL_LOCK = threading.Lock()
_HB_STARTED = False


def _heartbeat_loop() -> None:
    import time

    from app.database import SessionLocal

    while True:
        time.sleep(HEARTBEAT_EVERY)
        with _LOCAL_LOCK:
            ids = list(_LOCAL_JOBS)
        if not ids:
            continue
        try:
            with SessionLocal() as db:
                db.execute(
                    update(AiJob)
                    .where(AiJob.id.in_(ids), AiJob.status.in_(ACTIVE_STATUSES))
                    .values(heartbeat_at=_now())
                )
                db.commit()
        except Exception as e:  # noqa: BLE001
            logger.warning("ai_jobs heartbeat hatası: %s", e)


def _ensure_heartbeat() -> None:
    global _HB_STARTED
    with _LOCAL_LOCK:
        if _HB_STARTED:
            return
        _HB_STARTED = True
    threading.Thread(target=_heartbeat_loop, name="ai-jobs-heartbeat", daemon=True).start()


def start(job_id: int) -> None:
    if RUN_INLINE:
        _run(job_id)
        return
    _ensure_heartbeat()
    with _LOCAL_LOCK:
        _LOCAL_JOBS.add(job_id)
    threading.Thread(target=_run, args=(job_id,), name=f"ai-job-{job_id}", daemon=True).start()


def _set(db: Session, job: AiJob, **fields: Any) -> None:
    for k, v in fields.items():
        setattr(job, k, v)
    job.heartbeat_at = _now()
    db.commit()


def _run(job_id: int) -> None:
    from app.database import SessionLocal

    with _LOCAL_LOCK:
        _LOCAL_JOBS.add(job_id)
    try:
        with _SEM:
            with SessionLocal() as db:
                job = db.get(AiJob, job_id)
                if job is None or job.status not in ACTIVE_STATUSES:
                    return
                _set(db, job, status=JOB_RUNNING, stage="Karne iki kez okunup karşılaştırılıyor",
                     started_at=_now(), attempts=(job.attempts or 0) + 1)
                try:
                    _execute(db, job)
                except Exception as e:  # noqa: BLE001 — iş asla askıda kalmasın
                    logger.exception("ai_job %s beklenmeyen hata", job_id)
                    db.rollback()
                    job = db.get(AiJob, job_id)
                    if job is not None and job.status in ACTIVE_STATUSES:
                        _finish_failed(db, job, JobError(
                            500, "internal_error",
                            f"Okuma sırasında beklenmeyen bir hata oluştu ({type(e).__name__})."))
    finally:
        with _LOCAL_LOCK:
            _LOCAL_JOBS.discard(job_id)


def _execute(db: Session, job: AiJob) -> None:
    student = db.get(User, job.student_id) if job.student_id else None
    coach = db.get(User, job.coach_id) if job.coach_id else None
    owner = db.get(User, job.owner_id)
    if student is None or coach is None or owner is None:
        _finish_failed(db, job, JobError(404, "not_found", "Öğrenci ya da koç artık bulunamıyor."))
        return
    params = json.loads(job.params_json or "{}")
    pdf = job.input_data or b""
    job_id, student_id = job.id, student.id
    # Okuma uzun sürer; bu arada başka istekler aynı satırı güncelleyebilir
    # (nabız). Satırı bırak, okumadan sonra taze oku.
    db.commit()
    try:
        draft = analyze_core(
            db, student=student, coach=coach, actor=owner, pdf_bytes=pdf,
            declared_section=params.get("declared_section"),
            declared_grade=params.get("declared_grade"),
            filename=job.input_filename,
        )
    except JobError as e:
        job = db.get(AiJob, job_id)
        if job is not None:
            _finish_failed(db, job, e)
        return
    job = db.get(AiJob, job_id)
    if job is None:
        return
    job.result_json = json.dumps(draft, ensure_ascii=False, default=str)
    _set(db, job, status=JOB_DONE, stage="Okundu — önizleme bekliyor",
         finished_at=_now(), credits_charged=draft.get("credits_charged"),
         error_status=None, error_code=None, error_message=None, error_details_json=None)
    _notify(db, job, student_id=student_id, ok=True)


def _finish_failed(db: Session, job: AiJob, e: JobError) -> None:
    _set(db, job, status=JOB_FAILED, stage="Okunamadı", finished_at=_now(),
         error_status=e.status, error_code=e.code, error_message=e.message,
         error_details_json=json.dumps(e.details, ensure_ascii=False, default=str) if e.details else None)
    _notify(db, job, student_id=job.student_id, ok=False)


def _notify(db: Session, job: AiJob, *, student_id: int | None, ok: bool) -> None:
    """Mobil bildirim: yükleyene; öğrenci yüklediyse ve okunduysa koça da."""
    from app.services.push_notifications import safe_push

    try:
        student = db.get(User, student_id) if student_id else None
        name = student.full_name if student else "Öğrenci"
        own_upload = student is not None and job.owner_id == student.id
        if ok:
            title = "Karne okundu"
            body = ("Deneme karnen okundu — kontrol edip kaydet." if own_upload
                    else f"{name} adlı öğrencinin karnesi okundu — kontrol edip kaydet.")
        else:
            title = "Karne okunamadı"
            body = job.error_message or "Karne okunamadı."
        data = ({"type": "student", "screen": "exams", "job_id": job.id} if own_upload
                else {"type": "coach_student", "student_id": student_id, "tab": "exams", "job_id": job.id})
        safe_push(db, user_id=job.owner_id, title=title, body=body, data=data)
        if ok and own_upload and job.coach_id and job.coach_id != job.owner_id:
            safe_push(
                db, user_id=job.coach_id, title="Öğrencin karne yükledi",
                body=f"{name} deneme karnesini yükledi; okundu, kaydetmesi bekleniyor.",
                data={"type": "coach_student", "student_id": student_id, "tab": "exams"},
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("ai_job bildirim hatası: %s", e)


# ---------------------------------------------------------------------------
# Kurtarma + temizlik (sorgu anında, tembel)
# ---------------------------------------------------------------------------


def recover_stale(db: Session) -> int:
    """Nabzı kesilmiş işleri devral (sunucu yeniden başladıysa)."""
    cutoff = _now() - STALE_AFTER
    stale = (
        db.query(AiJob)
        .filter(
            AiJob.status.in_(ACTIVE_STATUSES),
            or_(AiJob.heartbeat_at.is_(None), AiJob.heartbeat_at < cutoff),
        )
        .all()
    )
    taken = 0
    for job in stale:
        with _LOCAL_LOCK:
            if job.id in _LOCAL_JOBS:
                continue
        old_hb = job.heartbeat_at
        if (job.attempts or 0) >= MAX_ATTEMPTS:
            _finish_failed(db, job, JobError(
                503, "server_restarted",
                "Okuma sunucu yeniden başlarken yarıda kaldı. Ücret düşmedi — tekrar dene."))
            continue
        # Yarış koruması: yalnız nabız hâlâ eskiyse devral
        q = update(AiJob).where(AiJob.id == job.id, AiJob.status.in_(ACTIVE_STATUSES))
        q = q.where(AiJob.heartbeat_at.is_(None)) if old_hb is None else q.where(AiJob.heartbeat_at == old_hb)
        res = db.execute(q.values(status=JOB_QUEUED, stage="Yeniden sıraya alındı", heartbeat_at=_now()))
        db.commit()
        if res.rowcount:
            taken += 1
            start(job.id)
    return taken


def purge_expired(db: Session) -> int:
    now = _now()
    n = (
        db.query(AiJob)
        .filter(AiJob.expires_at.is_not(None), AiJob.expires_at < now,
                AiJob.status.not_in(ACTIVE_STATUSES))
        .delete(synchronize_session=False)
    )
    if n:
        db.commit()
    return n


def housekeeping(db: Session) -> None:
    try:
        purge_expired(db)
        recover_stale(db)
    except Exception as e:  # noqa: BLE001 — sorgu yanıtını bozmasın
        db.rollback()
        logger.warning("ai_jobs bakım hatası: %s", e)


# ---------------------------------------------------------------------------
# Okuma / durum geçişleri
# ---------------------------------------------------------------------------


def get_owned(db: Session, user: User, job_id: int) -> AiJob:
    job = db.get(AiJob, job_id)
    if job is None or job.owner_id != user.id:
        raise JobError(404, "not_found", "İş bulunamadı.")
    return job


def list_for_owner(db: Session, user: User, *, student_id: int | None = None) -> list[AiJob]:
    q = db.query(AiJob).filter(AiJob.owner_id == user.id, AiJob.status.in_(OPEN_STATUSES))
    if student_id is not None:
        q = q.filter(AiJob.student_id == student_id)
    return q.order_by(AiJob.created_at.desc(), AiJob.id.desc()).limit(50).all()


def draft_of(job: AiJob) -> dict | None:
    if job.status != JOB_DONE or not job.result_json:
        return None
    try:
        return json.loads(job.result_json)
    except (ValueError, TypeError):
        return None


def acknowledge(db: Session, job: AiJob) -> None:
    if job.acknowledged_at is None:
        job.acknowledged_at = _now()
        db.commit()


def dismiss(db: Session, job: AiJob) -> None:
    if job.status in ACTIVE_STATUSES:
        raise JobError(409, "job_running", "Okuma sürerken vazgeçilemez; bitmesini bekle.")
    job.status = JOB_DISMISSED
    job.input_data = None
    job.acknowledged_at = job.acknowledged_at or _now()
    db.commit()


def retry(db: Session, job: AiJob) -> None:
    if job.status != JOB_FAILED or job.error_code not in RETRYABLE_CODES:
        raise JobError(409, "not_retryable", "Bu iş yeniden denenemez — yeni bir yükleme yap.")
    if not job.input_data:
        raise JobError(409, "not_retryable", "PDF artık saklanmıyor — yeniden yükle.")
    job.status = JOB_QUEUED
    job.stage = "Yeniden sıraya alındı"
    job.attempts = 0
    job.error_status = job.error_code = job.error_message = job.error_details_json = None
    job.acknowledged_at = None
    job.finished_at = None
    job.heartbeat_at = _now()
    job.expires_at = _now() + DRAFT_TTL
    db.commit()
    start(job.id)


def take_for_confirm(db: Session, user: User, job_id: int, student: User) -> AiJob:
    job = get_owned(db, user, job_id)
    if job.kind != KIND_EXAM_IMPORT or job.student_id != student.id:
        raise JobError(404, "not_found", "İş bulunamadı.")
    if job.status != JOB_DONE:
        raise JobError(409, "job_not_ready", "Bu karne henüz kaydedilmeye hazır değil.")
    return job


def mark_consumed(db: Session, job: AiJob, exam_id: int) -> None:
    job.status = JOB_CONSUMED
    job.consumed_exam_id = exam_id
    job.input_data = None
    job.result_json = None
    job.acknowledged_at = job.acknowledged_at or _now()
    db.commit()


def brief(db: Session, job: AiJob) -> dict:
    student = db.get(User, job.student_id) if job.student_id else None
    details = None
    if job.error_details_json:
        try:
            details = json.loads(job.error_details_json)
        except (ValueError, TypeError):
            details = None
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "status_label": job.status_label,
        "stage": job.stage,
        "student_id": job.student_id,
        "student_name": student.full_name if student else None,
        "own_upload": bool(student and job.owner_id == student.id),
        "filename": job.input_filename,
        "created_at": _aware(job.created_at).isoformat() if job.created_at else None,
        "finished_at": _aware(job.finished_at).isoformat() if job.finished_at else None,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "error_details": details,
        "retryable": job.status == JOB_FAILED and job.error_code in RETRYABLE_CODES,
        "credits_charged": job.credits_charged,
        "acknowledged": job.acknowledged_at is not None,
    }
