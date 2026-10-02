"""Deneme analizi Faz 2 uçları — gelişim raporu, hedef net, seans gündem kuyruğu,
öğrenciyle paylaşım (koç + öğrenci).

Koç uçları sahiplik dışında 404 (öğrencinin varlığı sızdırılmaz). Öğrenci yalnız
kendi raporunu, hedefini ve kendisiyle paylaşılan denemeleri görür.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import ExamResult, User
from app.routes.api_v2.schemas.exam_progress import (
    AgendaQueueAddBody,
    AgendaQueueIdsBody,
    AgendaQueueItem,
    AgendaQueueResponse,
    DistractorResponse,
    ExamAveragesBody,
    ExamAveragesResult,
    ScoreEstimateResponse,
    ExamProgressResponse,
    ExamShareBody,
    ExamShareInfo,
    ExamShareResult,
    ExamSharesResponse,
    ExamTargetBody,
    ExamTargetsResponse,
    ProgressTarget,
)
from app.routes.api_v2.student import _require_student
from app.routes.api_v2.teacher import _get_owned_exam, _get_owned_student, _require_teacher
from app.services import exam_faz3
from app.services import exam_progress as svc

logger = logging.getLogger(__name__)
router = APIRouter(tags=["v2-exam-progress"])


def _err(e: svc.ProgressError) -> HTTPException:
    return HTTPException(status_code=e.status,
                         detail={"error": "validation", "code": e.code, "message": e.message})


def _k(tid: int, sid: int, leaf: str) -> str:
    return f"teacher:{tid}:students:{sid}:{leaf}"


def _report(db: Session, student: User, section: str | None, period: str | None) -> ExamProgressResponse:
    data = svc.build_progress_report(db, student, section=section, period=period)
    return ExamProgressResponse(**data)


def _targets_out(targets: dict) -> dict[str, ProgressTarget]:
    return {k: ProgressTarget(**v) for k, v in targets.items() if isinstance(v, dict)}


def _shares_for(db: Session, student_id: int) -> dict[str, ExamShareInfo]:
    out: dict[str, ExamShareInfo] = {}
    for e in db.query(ExamResult).filter(ExamResult.student_id == student_id).all():
        s = svc.share_info(e)
        if s:
            out[str(e.id)] = ExamShareInfo(**{k: s.get(k) for k in ExamShareInfo.model_fields})
    return out


# ---------------------------------------------------------------- koç

@router.get("/teacher/students/{student_id}/exam-progress", response_model=ExamProgressResponse)
def teacher_exam_progress(student_id: int, section: str | None = None, period: str | None = None,
                          user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """Gelişim raporu: özet + ders gidişatı + hedef farkı + yorum + aksiyon planı.

    Aksiyonlarda `queued` = seans gündem kuyruğunda zaten var.
    """
    student = _get_owned_student(db, student_id, user.id)
    rep = _report(db, student, section, period)
    qkeys = {q.get("key") for q in svc.get_queue(db, student.id) if q.get("key")}
    for a in rep.actions:
        a.queued = a.key in qkeys
    return rep


@router.get("/teacher/students/{student_id}/exam-targets", response_model=ExamTargetsResponse)
def teacher_exam_targets(student_id: int, user: User = Depends(_require_teacher),
                         db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    return ExamTargetsResponse(targets=_targets_out(svc.get_targets(db, student.id)))


@router.post("/teacher/students/{student_id}/exam-targets", response_model=ExamTargetsResponse)
def teacher_set_exam_target(student_id: int, body: ExamTargetBody,
                            user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """Hedef net kaydet (target_net boş → o türün hedefi kaldırılır)."""
    student = _get_owned_student(db, student_id, user.id)
    try:
        targets = svc.set_target(db, student.id, section=body.section, target_net=body.target_net,
                                 target_date=body.target_date, subjects=body.subjects,
                                 note=body.note, actor=user)
    except svc.ProgressError as e:
        raise _err(e)
    db.commit()
    return ExamTargetsResponse(
        targets=_targets_out(targets),
        invalidate=[_k(user.id, student.id, "exam-targets"), _k(user.id, student.id, "exam-progress")],
    )


@router.get("/teacher/students/{student_id}/agenda-queue", response_model=AgendaQueueResponse)
def teacher_agenda_queue(student_id: int, user: User = Depends(_require_teacher),
                         db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    return AgendaQueueResponse(items=[AgendaQueueItem(**q) for q in svc.get_queue(db, student.id)])


def _queue_inv(tid: int, sid: int) -> list[str]:
    return [_k(tid, sid, "agenda-queue"), _k(tid, sid, "exam-progress"),
            _k(tid, sid, "sessions")]


@router.post("/teacher/students/{student_id}/agenda-queue", response_model=AgendaQueueResponse)
def teacher_agenda_queue_add(student_id: int, body: AgendaQueueAddBody,
                             user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """Seansa ekle — maddeler sıradaki seansın gündemine işaretli gelir."""
    student = _get_owned_student(db, student_id, user.id)
    queue, added = svc.add_to_queue(db, student.id, [i.model_dump() for i in body.items], actor=user)
    db.commit()
    return AgendaQueueResponse(items=[AgendaQueueItem(**q) for q in queue], added=added,
                               invalidate=_queue_inv(user.id, student.id))


@router.post("/teacher/students/{student_id}/agenda-queue/remove", response_model=AgendaQueueResponse)
def teacher_agenda_queue_remove(student_id: int, body: AgendaQueueIdsBody,
                                user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """Kuyruktan çıkar — seans kaydedildiğinde kullanılan maddeler de buradan düşer."""
    student = _get_owned_student(db, student_id, user.id)
    queue = svc.remove_from_queue(db, student.id, body.ids, actor=user)
    db.commit()
    return AgendaQueueResponse(items=[AgendaQueueItem(**q) for q in queue],
                               invalidate=_queue_inv(user.id, student.id))


@router.get("/teacher/students/{student_id}/exam-shares", response_model=ExamSharesResponse)
def teacher_exam_shares(student_id: int, user: User = Depends(_require_teacher),
                        db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    return ExamSharesResponse(shares=_shares_for(db, student.id))


def _notify_student_bg(student_id: int, exam_id: int) -> None:
    """Öğrenciye push (taze oturum; yanıtı bloklamaz, hata yutulur)."""
    from app.services.push_notifications import safe_push
    try:
        with SessionLocal() as db:
            e = db.get(ExamResult, exam_id)
            if e is None:
                return
            safe_push(db, user_id=student_id, title="Koçun denemeni değerlendirdi",
                      body=f"{e.title} — net {e.net:.2f}".replace(".", ","),
                      data={"type": "student", "screen": "exams", "exam_id": exam_id})
    except Exception as ex:  # noqa: BLE001
        logger.warning("exam share push hatası: %s", ex)


@router.post("/teacher/exams/{exam_id}/share-student", response_model=ExamShareResult)
def teacher_share_exam(exam_id: int, body: ExamShareBody, background: BackgroundTasks,
                       user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """Denemeyi öğrenciyle paylaş: koçun ÖĞRENCİYE notu + paylaşım anı (+ push).

    Koça özel `note` öğrenciye gösterilmez; buradaki not ayrıdır.
    """
    exam = _get_owned_exam(db, exam_id, user.id)
    share = svc.set_share(db, exam, note=body.note, actor=user)
    db.commit()
    if body.notify:
        background.add_task(_notify_student_bg, exam.student_id, exam.id)
    return ExamShareResult(
        exam_id=exam.id, share=ExamShareInfo(**share), notified=body.notify,
        invalidate=[_k(user.id, exam.student_id, "exam-shares"), "student:exams"],
    )


@router.post("/teacher/exams/{exam_id}/unshare-student", response_model=ExamShareResult)
def teacher_unshare_exam(exam_id: int, user: User = Depends(_require_teacher),
                         db: Session = Depends(get_db)):
    exam = _get_owned_exam(db, exam_id, user.id)
    svc.clear_share(exam)
    db.commit()
    return ExamShareResult(exam_id=exam.id, share=None,
                           invalidate=[_k(user.id, exam.student_id, "exam-shares"), "student:exams"])


# ---------------------------------------------------------------- öğrenci

@router.get("/student/exam-progress", response_model=ExamProgressResponse)
def student_exam_progress(section: str | None = None, period: str | None = None,
                          user: User = Depends(_require_student), db: Session = Depends(get_db)):
    return _report(db, user, section, period)


@router.get("/student/exam-shares", response_model=ExamSharesResponse)
def student_exam_shares(user: User = Depends(_require_student), db: Session = Depends(get_db)):
    """Koçun öğrenciyle paylaştığı denemeler + öğrenciye yazdığı notlar."""
    return ExamSharesResponse(shares=_shares_for(db, user.id))


# ================================================================ Faz 3

@router.post("/teacher/exams/{exam_id}/averages", response_model=ExamAveragesResult)
def teacher_set_exam_averages(exam_id: int, body: ExamAveragesBody,
                              user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    """Genel ortalamayı elle gir/düzelt (karnede yoksa). Boş gövde → elle girişi kaldırır."""
    exam = _get_owned_exam(db, exam_id, user.id)
    try:
        av = exam_faz3.set_manual_averages(exam, label=body.label, total=body.total, subjects=body.subjects)
    except exam_faz3.Faz3Error as e:
        raise HTTPException(status_code=e.status,
                            detail={"error": "validation", "code": e.code, "message": e.message})
    db.commit()
    return ExamAveragesResult(exam_id=exam.id, averages=av,
                              invalidate=[_k(user.id, exam.student_id, "exams"), "student:exams"])


@router.get("/teacher/exams/{exam_id}/distractors", response_model=DistractorResponse)
def teacher_exam_distractors(exam_id: int, user: User = Depends(_require_teacher),
                             db: Session = Depends(get_db)):
    """Çeldirici analizi: şık eğilimi + koçun aynı denemeye giren öğrencileri."""
    exam = _get_owned_exam(db, exam_id, user.id)
    return DistractorResponse(**exam_faz3.distractor_analysis(db, exam, coach_id=user.id))


@router.get("/student/exams/{exam_id}/distractors", response_model=DistractorResponse)
def student_exam_distractors(exam_id: int, user: User = Depends(_require_student),
                             db: Session = Depends(get_db)):
    """Öğrencinin kendi denemesi — akran verisi yalnız toplu oran olarak (isim yok)."""
    exam = db.query(ExamResult).filter(ExamResult.id == exam_id, ExamResult.student_id == user.id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "exam_not_found",
                                                     "message": "Deneme bulunamadı."})
    return DistractorResponse(**exam_faz3.distractor_analysis(db, exam, coach_id=user.teacher_id))


@router.get("/teacher/students/{student_id}/score-estimate", response_model=ScoreEstimateResponse)
def teacher_score_estimate(student_id: int, user: User = Depends(_require_teacher),
                           db: Session = Depends(get_db)):
    student = _get_owned_student(db, student_id, user.id)
    return ScoreEstimateResponse(**exam_faz3.score_estimate(db, student))


@router.get("/student/score-estimate", response_model=ScoreEstimateResponse)
def student_score_estimate(user: User = Depends(_require_student), db: Session = Depends(get_db)):
    return ScoreEstimateResponse(**exam_faz3.score_estimate(db, user))
