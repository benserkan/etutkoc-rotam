"""Deneme PDF içe aktarma — API v2 router (koç + öğrenci yüzleri tek dosyada;
wrong_questions.py deseni).

Akış (iki aşama, sunucu tarafında taslak durumu YOK):
  1. import-analyze (multipart PDF) → Gemini çift okuma + normalizasyon →
     önizleme taslağı JSON (KREDİ BURADA düşer: AI_EXAM_IMPORT=6, koç havuzu).
  2. import-confirm (JSON) → düzeltilmiş satırlar + aynı PDF (kanıt) →
     ExamResult + soru satırları + öğrenen sözlük. Kredi DÜŞMEZ.

Kapılar (YSA deseniyle birebir): öğrenci yolunda ai_gate_status (koç yok /
paket / rıza) → 403; koç yolunda koçun kendisi aynı kapılardan geçer.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import (
    EXAM_SECTION_LABELS,
    ExamResult,
    ExamSection,
    UsageKind,
    User,
    UserRole,
)
from app.routes.api_v2.dependencies import get_current_user_v2
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.exam_import import (
    AiJobBrief,
    AiJobDetail,
    AiJobListResponse,
    ExamImportConfirmBody,
    ExamImportConfirmResult,
    ExamImportDraft,
    ExamImportQuotaResponse,
    ExamTopicAnalysisResponse,
    ExamWrongRowsResponse,
    SectionChoice,
    WrongBridgeBody,
    WrongBridgeResult,
)
from app.services import exam_import_service as svc
from app.services import exam_topic_analysis
from app.services import wrong_question_service
from app.services import free_exam_quota
from app.services import exam_import_jobs as jobs
from app.services.credits import KIND_CREDITS

router = APIRouter(tags=["v2-exam-import"])


# ============================================================================
# Yardımcılar
# ============================================================================


def _require_student(user: User = Depends(get_current_user_v2)) -> User:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "role_required",
            "message": "Bu uç yalnız öğrenci hesabıyla kullanılabilir."})
    return user


def _require_teacher(user: User = Depends(get_current_user_v2)) -> User:
    if user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "role_required",
            "message": "Bu uç yalnız koç hesabıyla kullanılabilir."})
    return user


def _get_owned_student(db: Session, coach: User, student_id: int) -> User:
    student = db.get(User, student_id)
    if (
        student is None
        or student.role != UserRole.STUDENT
        or student.teacher_id != coach.id
    ):
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "code": "student_not_found",
            "message": "Öğrenci bulunamadı."})
    return student


def _get_owned_exam(db: Session, coach: User, exam_id: int) -> tuple[ExamResult, User]:
    """Deneme + öğrencisi — koç öğrencinin GÜNCEL koçu değilse 404 (sızıntı yok)."""
    exam = db.get(ExamResult, exam_id)
    student = db.get(User, exam.student_id) if exam is not None else None
    if (
        exam is None
        or student is None
        or student.role != UserRole.STUDENT
        or student.teacher_id != coach.id
    ):
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "code": "exam_not_found",
            "message": "Deneme bulunamadı."})
    return exam, student


def _paying_coach(db: Session, student: User, *, actor: User | None = None) -> User:
    """Kredi + kapı sahibi koç (YSA deseni) — yoksa/kapalıysa 403.

    actor verilirse ve öğrenci kendisi tetikliyorsa öğrencinin AI anahtarı
    da yoklanır (koç kapatmışsa 403; koçun kendi tetiklemesi serbest).
    """
    coach = db.get(User, student.teacher_id) if student.teacher_id else None
    if coach is None:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "no_coach",
            "message": "PDF analizi için bağlı bir koç gerekir."})
    if (actor is not None and actor.id == student.id
            and student.ai_self_disabled_at is not None):
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "ai_disabled_by_coach",
            "message": "Koçun, yapay zekâ PDF okumayı senin için kapatmış. "
                       "Açtırmak için koçunla görüşebilirsin."})
    if coach.ai_self_disabled_at is not None:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "ai_disabled_by_institution",
            "message": "Yapay zekâ kullanımı kurum tarafından kapatılmış."})
    quota = free_exam_quota.status_for(db, coach)
    if quota.applies and quota.left <= 0:
        # Ücretsiz paket: tek seferlik hak bitti → yükseltme (2026-10-28).
        own = actor is None or actor.id == coach.id
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "free_exam_quota_exhausted",
            "message": (
                f"Ücretsiz paketteki {quota.quota} deneme PDF analizi hakkının "
                "tamamını kullandın. Analizlere devam etmek için paketini yükselt."
                if own else
                f"Koçunun ücretsiz paketindeki {quota.quota} PDF analizi hakkı doldu. "
                "Deneme sonucunu elle girebilir ya da koçunla görüşebilirsin."),
            "details": {"quota": quota.quota, "used": quota.used,
                        "upgrade_url": "/teacher/plan"}})
    if coach.ai_capture_consent_at is None:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "consent_required",
            "message": "Koç henüz yapay zekâ onayını vermemiş."})
    return coach


def _read_pdf_upload(file: UploadFile | None) -> bytes:
    """Senkron okuma (file.file = SpooledTemporaryFile) — uçlar bilinçli olarak
    SENKRON def: FastAPI onları threadpool'da çalıştırır. async def + senkron
    Gemini çağrısı event loop'u kilitleyip gunicorn'un 60 sn worker heartbeat
    timeout'una takılıyordu (code 134 — canlıda 2026-07-16 yaşandı)."""
    if file is None or not (file.filename or "").strip():
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "pdf_required",
            "message": "Deneme sonuç PDF'i gerekir."})
    ct = (file.content_type or "").lower()
    if "pdf" not in ct:
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "invalid_file_type",
            "message": "Yalnız PDF kabul edilir."})
    file.file.seek(0)
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "pdf_required",
            "message": "Dosya boş."})
    if len(data) > svc.MAX_PDF_BYTES:
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "pdf_too_large",
            "message": "PDF 10 MB'ı aşamaz."})
    return data


def _svc_error(e: svc.ExamImportError) -> HTTPException:
    kind = {404: "not_found", 409: "conflict", 422: "validation"}.get(e.status, "error")
    detail: dict = {"error": kind, "code": e.code, "message": e.message}
    if getattr(e, "details", None):
        detail["details"] = e.details
    return HTTPException(status_code=e.status, detail=detail)


def _section_choices() -> list[SectionChoice]:
    return [SectionChoice(value=s.value, label=EXAM_SECTION_LABELS[s])
            for s in ExamSection]


def _job_http(e: jobs.JobError) -> HTTPException:
    kind = {402: "payment_required", 404: "not_found", 409: "conflict",
            422: "validation", 502: "upstream_unavailable"}.get(e.status, "error")
    detail: dict = {"error": kind, "code": e.code, "message": e.message}
    if e.details:
        detail["details"] = e.details
    return HTTPException(status_code=e.status, detail=detail)


def _run_analyze(
    db: Session, *, student: User, coach: User, actor: User, pdf_bytes: bytes,
    declared_section: str | None = None, declared_grade: int | None = None,
    filename: str | None = None,
) -> ExamImportDraft:
    """Tek istekte okuma (eski istemciler). Çekirdek arka plan işiyle ortak."""
    try:
        jobs.check_pdf_duplicate(db, student, pdf_bytes)
        draft = jobs.analyze_core(
            db, student=student, coach=coach, actor=actor, pdf_bytes=pdf_bytes,
            declared_section=declared_section, declared_grade=declared_grade,
            filename=filename)
    except jobs.JobError as e:
        raise _job_http(e)
    return ExamImportDraft(**draft)


def _parse_confirm_payload(payload: str) -> ExamImportConfirmBody:
    """Multipart form alanındaki JSON gövdeyi doğrula (dosya + veri tek istekte)."""
    try:
        return ExamImportConfirmBody.model_validate(json.loads(payload))
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "invalid_payload",
            "message": f"Onay verisi çözümlenemedi: {e}"})


def _confirm_result(exam: ExamResult) -> ExamImportConfirmResult:
    matched = [q for q in exam.questions if q.topic_id is not None]
    wrong_topic_ids = sorted({
        q.topic_id for q in matched if q.result == "yanlis" and q.topic_id
    })
    return ExamImportConfirmResult(
        exam_id=exam.id,
        title=exam.title,
        exam_date=exam.exam_date.isoformat(),
        section=exam.section.value,
        section_label=EXAM_SECTION_LABELS[exam.section],
        net=exam.net,
        total_correct=exam.total_correct,
        total_wrong=exam.total_wrong,
        total_blank=exam.total_blank,
        question_count=len(exam.questions),
        matched_topic_count=len(matched),
        wrong_topic_ids=wrong_topic_ids,
    )


def _run_confirm(
    db: Session, *, student: User, actor: User,
    body: ExamImportConfirmBody, pdf_bytes: bytes | None, content_type: str | None,
    job_id: int | None = None,
) -> ExamImportConfirmResult:
    job = None
    if job_id is not None:
        try:
            job = jobs.take_for_confirm(db, actor, job_id, student)
        except jobs.JobError as e:
            raise _job_http(e)
        if pdf_bytes is None:
            pdf_bytes = job.input_data
            content_type = job.input_content_type or "application/pdf"
    try:
        exam = svc.confirm(
            db, student, body.model_dump(),
            pdf_bytes=pdf_bytes, content_type=content_type, actor=actor,
        )
    except svc.ExamImportError as e:
        db.rollback()
        raise _svc_error(e)
    if job is not None:
        jobs.mark_consumed(db, job, exam.id)
    return _confirm_result(exam)


# ============================================================================
# KOÇ uçları
# ============================================================================


@router.post(
    "/teacher/students/{student_id}/exams/import-analyze",
    response_model=ExamImportDraft,
)
def teacher_exam_import_analyze(
    student_id: int,
    file: UploadFile = File(...),
    declared_section: str | None = Form(default=None),
    declared_grade: int | None = Form(default=None),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """PDF'i analiz et → önizleme taslağı (kayıt YAPMAZ; kredi burada düşer).

    declared_section/declared_grade: kullanıcı beyanı (BEYAN ESAS — tespit
    bekçiye döner, çelişkide uyarı üretir). Bilinçli SENKRON uç (threadpool) —
    Gemini çağrıları dakikalar sürebilir.
    """
    student = _get_owned_student(db, user, student_id)
    # koç kendi kapılarından geçer (paket + rıza) — _paying_coach öğrencinin
    # koçunu döndürür; koç yolu için bu zaten user'ın kendisidir.
    coach = _paying_coach(db, student)
    pdf = _read_pdf_upload(file)
    return _run_analyze(db, student=student, coach=coach, actor=user, pdf_bytes=pdf,
                        filename=file.filename if file else None,
                        declared_section=declared_section,
                        declared_grade=declared_grade)


@router.post(
    "/teacher/students/{student_id}/exams/import-confirm",
    response_model=MutationResponse[ExamImportConfirmResult],
)
def teacher_exam_import_confirm(
    student_id: int,
    background_tasks: BackgroundTasks,
    payload: str = Form(...),
    file: UploadFile | None = File(default=None),
    job_id: int | None = Form(default=None),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Önizlemede düzeltilen taslağı kaydet (kredi düşmez; PDF kanıt olarak saklanır)."""
    student = _get_owned_student(db, user, student_id)
    body = _parse_confirm_payload(payload)
    pdf = _read_pdf_upload(file) if file and (file.filename or "").strip() else None
    result = _run_confirm(
        db, student=student, actor=user, body=body,
        pdf_bytes=pdf, content_type=(file.content_type if pdf and file else None),
        job_id=job_id,
    )
    # P4: yeni deneme → veliye "Rota yorumlamaya hazır" push'u (yanıt sonrası,
    # taze session; throttle + mute + Rota-kapısı fonksiyonun içinde).
    from app.services.push_notifications import notify_parents_rota_exam_ready_bg
    background_tasks.add_task(
        notify_parents_rota_exam_ready_bg, student.id, student.full_name)
    from app.routes.api_v2.teacher import _pool_exam_cross
    _pool_exam_cross(db, student=student, exam_id=result.exam_id, actor=user)
    return MutationResponse[ExamImportConfirmResult](
        data=result,
        invalidate=[
            f"teacher:{user.id}:students:{student.id}:exams",
            f"teacher:{user.id}:students:{student.id}",
        ],
    )


@router.get(
    "/teacher/exams/{exam_id}/import-rows",
    response_model=ExamImportDraft,
)
def teacher_exam_import_rows(
    exam_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Kayıtlı (PDF'ten aktarılmış) denemeyi satır-düzeyi düzenleme için aç.

    Yeni Gemini OKUMASI yapılmaz → KREDİ DÜŞMEZ. Eşleşmemiş konular güncel
    taksonomi + öğrenen sözlük + kapalı-küme AI (ücretsiz anahtar) ile yeniden
    denenir. Bilinçli SENKRON uç (best-effort AI çağrısı threadpool'da).
    """
    exam, student = _get_owned_exam(db, user, exam_id)
    try:
        draft = svc.build_edit_draft(db, student, exam)
    except svc.ExamImportError as e:
        db.rollback()
        raise _svc_error(e)
    db.commit()  # sözlük hit sayaçları (normalize alias katmanı)
    return ExamImportDraft(
        **draft,
        section_choices=_section_choices(),
        credits_charged=0,
    )


@router.post(
    "/teacher/exams/{exam_id}/import-rows",
    response_model=MutationResponse[ExamImportConfirmResult],
)
def teacher_exam_import_rows_update(
    exam_id: int,
    body: ExamImportConfirmBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Düzeltilen satırlarla denemeyi YENİDEN kaydet (kredi düşmez).

    Toplamlar/net/ders kırılımı satırlardan yeniden hesaplanır; konu bazlı
    birikim + net trendi + veli/kurum panoları otomatik güncellenir.
    """
    exam, student = _get_owned_exam(db, user, exam_id)
    try:
        exam = svc.update_imported(db, student, exam, body.model_dump(), actor=user)
    except svc.ExamImportError as e:
        db.rollback()
        raise _svc_error(e)
    return MutationResponse[ExamImportConfirmResult](
        data=_confirm_result(exam),
        invalidate=[
            f"teacher:{user.id}:students:{student.id}:exams",
            f"teacher:{user.id}:students:{student.id}",
        ],
    )


def _wrong_rows_response(db: Session, student: User, exam) -> ExamWrongRowsResponse:
    from app.models import WQ_ERROR_LABELS_TR
    return ExamWrongRowsResponse(
        exam_id=exam.id,
        title=exam.title,
        rows=wrong_question_service.exam_wrong_rows(db, student, exam),
        error_types=[{"value": k, "label": v}
                     for k, v in WQ_ERROR_LABELS_TR.items()],
    )


@router.get(
    "/teacher/exams/{exam_id}/wrong-rows",
    response_model=ExamWrongRowsResponse,
)
def teacher_exam_wrong_rows(
    exam_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Seçici köprü: denemenin yanlış soruları (arşiv durumu işaretli) —
    koç hangilerinin arşive değer olduğunu buradan seçer."""
    exam, student = _get_owned_exam(db, user, exam_id)
    return _wrong_rows_response(db, student, exam)


@router.post(
    "/teacher/exams/{exam_id}/wrong-to-archive",
    response_model=MutationResponse[WrongBridgeResult],
)
def teacher_exam_wrongs_to_archive(
    exam_id: int,
    body: WrongBridgeBody | None = None,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Denemenin SEÇİLEN yanlışlarını Yanlış Soru Arşivine aktar (Faz 3
    köprüsü). body.items yoksa tümü (geriye uyum). İdempotent."""
    exam, student = _get_owned_exam(db, user, exam_id)
    result = wrong_question_service.bulk_from_exam(
        db, student, exam=exam, created_by=user,
        selected=([i.model_dump() for i in body.items]
                  if body and body.items is not None else None))
    return MutationResponse[WrongBridgeResult](
        data=WrongBridgeResult(**result),
        invalidate=[
            f"teacher:{user.id}:students:{student.id}:wrong-questions",
            "student:wrong-questions",
        ],
    )


@router.get(
    "/teacher/students/{student_id}/exam-topic-analysis",
    response_model=ExamTopicAnalysisResponse,
)
def teacher_exam_topic_analysis(
    student_id: int,
    section: str | None = None,
    period: str | None = None,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Konu × deneme analizi (Faz 2): ısı haritası + net fırsat + unutulan/
    gelişen. Salt-okuma, AI YOK, kredi düşmez.

    P3: varsayılan güncel sınıf dönemi (`?period=all` tüm geçmiş)."""
    student = _get_owned_student(db, user, student_id)
    return ExamTopicAnalysisResponse(
        **exam_topic_analysis.build_exam_topic_analysis(
            db, student, section=section, period=period))


# ============================================================================
# ÖĞRENCİ uçları (kredi + kapılar yine KOÇUN — YSA deseni)
# ============================================================================


@router.get(
    "/student/exams/{exam_id}/wrong-rows",
    response_model=ExamWrongRowsResponse,
)
def student_exam_wrong_rows(
    exam_id: int,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    exam = db.get(ExamResult, exam_id)
    if exam is None or exam.student_id != user.id:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "code": "exam_not_found",
            "message": "Deneme bulunamadı."})
    return _wrong_rows_response(db, user, exam)


@router.post(
    "/student/exams/{exam_id}/wrong-to-archive",
    response_model=MutationResponse[WrongBridgeResult],
)
def student_exam_wrongs_to_archive(
    exam_id: int,
    body: WrongBridgeBody | None = None,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Öğrenci kendi denemesinin SEÇTİĞİ yanlışlarını arşive aktarır."""
    exam = db.get(ExamResult, exam_id)
    if exam is None or exam.student_id != user.id:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "code": "exam_not_found",
            "message": "Deneme bulunamadı."})
    result = wrong_question_service.bulk_from_exam(
        db, user, exam=exam, created_by=user,
        selected=([i.model_dump() for i in body.items]
                  if body and body.items is not None else None))
    invalidate = ["student:wrong-questions"]
    if user.teacher_id:
        invalidate.append(
            f"teacher:{user.teacher_id}:students:{user.id}:wrong-questions")
    return MutationResponse[WrongBridgeResult](
        data=WrongBridgeResult(**result), invalidate=invalidate)


@router.get("/student/exam-topic-analysis", response_model=ExamTopicAnalysisResponse)
def student_exam_topic_analysis(
    section: str | None = None,
    period: str | None = None,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Öğrenci kendi konu × deneme analizini görür (Faz 2b UI için hazır uç).

    P3: varsayılan güncel sınıf dönemi (`?period=all` tüm geçmiş)."""
    return ExamTopicAnalysisResponse(
        **exam_topic_analysis.build_exam_topic_analysis(
            db, user, section=section, period=period))


@router.post("/student/exams/import-analyze", response_model=ExamImportDraft)
def student_exam_import_analyze(
    file: UploadFile = File(...),
    declared_section: str | None = Form(default=None),
    declared_grade: int | None = Form(default=None),
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    coach = _paying_coach(db, user, actor=user)
    pdf = _read_pdf_upload(file)
    return _run_analyze(db, student=user, coach=coach, actor=user, pdf_bytes=pdf,
                        filename=file.filename if file else None,
                        declared_section=declared_section,
                        declared_grade=declared_grade)


@router.post(
    "/student/exams/import-confirm",
    response_model=MutationResponse[ExamImportConfirmResult],
)
def student_exam_import_confirm(
    background_tasks: BackgroundTasks,
    payload: str = Form(...),
    file: UploadFile | None = File(default=None),
    job_id: int | None = Form(default=None),
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    body = _parse_confirm_payload(payload)
    pdf = _read_pdf_upload(file) if file and (file.filename or "").strip() else None
    result = _run_confirm(
        db, student=user, actor=user, body=body,
        pdf_bytes=pdf, content_type=(file.content_type if pdf and file else None),
        job_id=job_id,
    )
    # P4: yeni deneme → veliye "Rota yorumlamaya hazır" push'u (yanıt sonrası).
    from app.services.push_notifications import notify_parents_rota_exam_ready_bg
    background_tasks.add_task(
        notify_parents_rota_exam_ready_bg, user.id, user.full_name)
    from app.routes.api_v2.teacher import _pool_exam_cross
    _pool_exam_cross(db, student=user, exam_id=result.exam_id, actor=user)
    invalidate = ["student:exams"]
    if user.teacher_id:
        invalidate.append(f"teacher:{user.teacher_id}:students:{user.id}:exams")
        invalidate.append(f"teacher:{user.teacher_id}:students:{user.id}")
    return MutationResponse[ExamImportConfirmResult](data=result, invalidate=invalidate)


# ============================================================================
# PDF analizi hakkı durumu (ücretsiz paket tek seferlik hak — 2026-10-28)
# ============================================================================


def _quota_payload(db: Session, coach: User | None) -> ExamImportQuotaResponse:
    if coach is None:
        return ExamImportQuotaResponse(available=False, free_mode=False,
                                       quota=free_exam_quota.FREE_EXAM_IMPORT_QUOTA,
                                       used=0, left=0, credits_per_import=0)
    q = free_exam_quota.status_for(db, coach)
    return ExamImportQuotaResponse(
        available=(not q.applies) or q.left > 0,
        free_mode=q.applies,
        quota=q.quota, used=q.used if q.applies else 0,
        left=q.left if q.applies else 0,
        credits_per_import=0 if q.applies else KIND_CREDITS[UsageKind.AI_EXAM_IMPORT],
    )


@router.get("/teacher/exam-import-quota", response_model=ExamImportQuotaResponse)
def teacher_exam_import_quota(
    user: User = Depends(_require_teacher), db: Session = Depends(get_db),
):
    return _quota_payload(db, user)


@router.get("/student/exam-import-quota", response_model=ExamImportQuotaResponse)
def student_exam_import_quota(
    user: User = Depends(_require_student), db: Session = Depends(get_db),
):
    coach = db.get(User, user.teacher_id) if user.teacher_id else None
    return _quota_payload(db, coach)


# ============================================================================
# Arka plan okuma işleri (2026-10-29) — yükle → arkada oku → önizle/kaydet
# ============================================================================


def _list_payload(db: Session, user: User, student_id: int | None = None) -> AiJobListResponse:
    items = jobs.list_for_owner(db, user, student_id=student_id)
    return AiJobListResponse(
        items=[AiJobBrief(**jobs.brief(db, j)) for j in items],
        active_count=sum(1 for j in items if j.status in ("queued", "running")),
        ready_count=sum(1 for j in items if j.status == "done"),
    )


def _create_job_response(db: Session, **kw) -> AiJobBrief:
    try:
        job = jobs.create_exam_job(db, **kw)
    except jobs.JobError as e:
        raise _job_http(e)
    db.refresh(job)
    return AiJobBrief(**jobs.brief(db, job))


@router.post(
    "/teacher/students/{student_id}/exams/import-jobs",
    response_model=AiJobBrief, status_code=202,
)
def teacher_exam_import_job(
    student_id: int,
    file: UploadFile = File(...),
    declared_section: str | None = Form(default=None),
    declared_grade: int | None = Form(default=None),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Karneyi yükle, arka planda oku (1-2 sn'de döner). Kredi okuma bitince düşer."""
    student = _get_owned_student(db, user, student_id)
    coach = _paying_coach(db, student)
    pdf = _read_pdf_upload(file)
    return _create_job_response(
        db, owner=user, student=student, coach=coach, pdf_bytes=pdf,
        filename=file.filename, content_type=file.content_type,
        declared_section=declared_section, declared_grade=declared_grade)


@router.post("/student/exams/import-jobs", response_model=AiJobBrief, status_code=202)
def student_exam_import_job(
    file: UploadFile = File(...),
    declared_section: str | None = Form(default=None),
    declared_grade: int | None = Form(default=None),
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    coach = _paying_coach(db, user, actor=user)
    pdf = _read_pdf_upload(file)
    return _create_job_response(
        db, owner=user, student=user, coach=coach, pdf_bytes=pdf,
        filename=file.filename, content_type=file.content_type,
        declared_section=declared_section, declared_grade=declared_grade)


@router.get("/me/ai-jobs", response_model=AiJobListResponse)
def my_ai_jobs(
    student_id: int | None = None,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Yükleyenin açık işleri — her sayfadaki "okundu" bilgilendirmesini besler."""
    jobs.housekeeping(db)
    return _list_payload(db, user, student_id)


def _owned_or_404(db: Session, user: User, job_id: int):
    try:
        return jobs.get_owned(db, user, job_id)
    except jobs.JobError as e:
        raise _job_http(e)


@router.get("/me/ai-jobs/{job_id}", response_model=AiJobDetail)
def my_ai_job(
    job_id: int,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    jobs.housekeeping(db)
    job = _owned_or_404(db, user, job_id)
    draft = jobs.draft_of(job)
    return AiJobDetail(
        job=AiJobBrief(**jobs.brief(db, job)),
        draft=ExamImportDraft(**draft) if draft else None,
        result=jobs.result_of(job),
    )


@router.post("/me/ai-jobs/{job_id}/ack", response_model=MutationResponse[AiJobBrief])
def my_ai_job_ack(
    job_id: int,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Ekran bilgilendirmesini kapat (iş önizleme bekliyorsa listede kalır)."""
    job = _owned_or_404(db, user, job_id)
    jobs.acknowledge(db, job)
    return MutationResponse[AiJobBrief](data=AiJobBrief(**jobs.brief(db, job)),
                                        invalidate=["me:ai-jobs"])


@router.post("/me/ai-jobs/{job_id}/dismiss", response_model=MutationResponse[AiJobBrief])
def my_ai_job_dismiss(
    job_id: int,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Taslaktan vazgeç (PDF silinir; düşen ücret iade edilmez — okuma yapılmıştı)."""
    job = _owned_or_404(db, user, job_id)
    try:
        jobs.dismiss(db, job)
    except jobs.JobError as e:
        raise _job_http(e)
    return MutationResponse[AiJobBrief](data=AiJobBrief(**jobs.brief(db, job)),
                                        invalidate=["me:ai-jobs"])


@router.post("/me/ai-jobs/{job_id}/retry", response_model=MutationResponse[AiJobBrief])
def my_ai_job_retry(
    job_id: int,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Servis hatası / yeniden başlatma yüzünden kalan işi tekrar dene (ücretsiz)."""
    job = _owned_or_404(db, user, job_id)
    try:
        jobs.retry(db, job)
    except jobs.JobError as e:
        raise _job_http(e)
    db.refresh(job)
    return MutationResponse[AiJobBrief](data=AiJobBrief(**jobs.brief(db, job)),
                                        invalidate=["me:ai-jobs"])
