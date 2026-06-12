"""Anket sistemi API'si — koç (ata/sonuç) + öğrenci (doldur) yüzeyleri.

Endpoint'ler:
  Koç:
    - GET  /teacher/surveys/catalog                      — aktif anket kataloğu
    - GET  /teacher/students/{sid}/surveys               — öğrencinin atamaları + katalog
    - POST /teacher/students/{sid}/surveys               — anket ata (mükerrer → 409)
    - GET  /teacher/surveys/assignments/{aid}            — atama detayı + sonuç
    - POST /teacher/surveys/assignments/{aid}/cancel     — iptal (tamamlanmamışsa)
  Öğrenci:
    - GET  /student/surveys                              — bekleyen + tamamlanan
    - GET  /student/surveys/{aid}                        — doldurma görünümü (+sonuç)
    - POST /student/surveys/{aid}/answers                — kaydet / tamamla

Sahiplik: koç yalnız kendi öğrencisinin atamasını görür (404 — sızıntı yok);
öğrenci yalnız kendi atamasını doldurur. Tamamlanınca koça push bildirimi.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import User, UserRole
from app.models.survey import (
    ASSIGNMENT_CANCELLED,
    ASSIGNMENT_COMPLETED,
    ASSIGNMENT_IN_PROGRESS,
    ASSIGNMENT_PENDING,
    CAREER_REQUIRED_CODES,
    CAREER_SURVEY_CODES,
    SURVEY_ASSIGNMENT_STATUS_LABELS_TR,
    SURVEY_CATEGORY_LABELS_TR,
    SURVEY_DISCLAIMER_TR,
    CareerInsight,
    SurveyAssignment,
    SurveyQuestion,
    SurveyTemplate,
)
from app.routes.api_v2.dependencies import _auth_error, get_current_user_v2
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.survey import (
    CareerSuggestionModel,
    CareerSynthesisCacheResponse,
    CareerSynthesisModel,
    StudentSurveyAnswersBody,
    StudentSurveyFillResponse,
    StudentSurveysResponse,
    StudentSurveySaveResult,
    SurveyAssignBody,
    SurveyAssignmentDetail,
    SurveyAssignmentRow,
    SurveyAssignResult,
    SurveyCancelResult,
    SurveyCatalogResponse,
    SurveyQuestionModel,
    SurveyResultModel,
    SurveyTemplateBrief,
    TeacherStudentSurveysResponse,
)
from app.services import survey_service
from app.services.push_notifications import safe_push

router = APIRouter(tags=["v2-surveys"])


# =============================================================================
# Rol kapıları + yardımcılar
# =============================================================================


def _require_teacher(user: User = Depends(get_current_user_v2)) -> User:
    if user.role != UserRole.TEACHER:
        raise _auth_error(
            "Bu uç nokta öğretmen hesabı bekler", "role_required",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    return user


def _require_student(user: User = Depends(get_current_user_v2)) -> User:
    if user.role != UserRole.STUDENT:
        raise _auth_error(
            "Bu uç nokta öğrenci hesabı bekler", "role_required",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    return user


def _not_found(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "not_found", "code": code, "message": message},
    )


def _get_owned_student(db: Session, student_id: int, teacher_id: int) -> User:
    student = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.teacher_id == teacher_id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if not student:
        raise _not_found("student_not_found", "Öğrenci bulunamadı.")
    return student


def _template_brief(t: SurveyTemplate, question_count: int) -> SurveyTemplateBrief:
    return SurveyTemplateBrief(
        id=t.id,
        code=t.code,
        title=t.title,
        description=t.description or "",
        category=t.category,
        category_label=SURVEY_CATEGORY_LABELS_TR.get(t.category, t.category),
        scoring_type=t.scoring_type,
        question_count=question_count,
        estimated_minutes=t.estimated_minutes,
        source_attribution=t.source_attribution or "",
    )


def _question_counts(db: Session, template_ids: list[int]) -> dict[int, int]:
    if not template_ids:
        return {}
    from sqlalchemy import func as sa_func

    rows = (
        db.query(SurveyQuestion.template_id, sa_func.count(SurveyQuestion.id))
        .filter(SurveyQuestion.template_id.in_(template_ids))
        .group_by(SurveyQuestion.template_id)
        .all()
    )
    return {tid: cnt for tid, cnt in rows}


def _assignment_row(
    a: SurveyAssignment, qcounts: dict[int, int]
) -> SurveyAssignmentRow:
    answered = len(survey_service.parse_answers(a))
    return SurveyAssignmentRow(
        id=a.id,
        template=_template_brief(a.template, qcounts.get(a.template_id, 0)),
        status=a.status,
        status_label=SURVEY_ASSIGNMENT_STATUS_LABELS_TR.get(a.status, a.status),
        note=a.note or "",
        assigned_at=a.assigned_at,
        started_at=a.started_at,
        completed_at=a.completed_at,
        teacher_name=a.teacher.full_name if a.teacher else None,
        student_name=a.student.full_name if a.student else None,
        answered_count=answered,
    )


def _active_catalog(db: Session) -> tuple[list[SurveyTemplate], dict[int, int]]:
    templates = (
        db.query(SurveyTemplate)
        .filter(SurveyTemplate.is_active.is_(True))
        .order_by(SurveyTemplate.category, SurveyTemplate.sort_order)
        .all()
    )
    qcounts = _question_counts(db, [t.id for t in templates])
    return templates, qcounts


# =============================================================================
# Koç yüzeyi
# =============================================================================


@router.get("/teacher/surveys/catalog", response_model=SurveyCatalogResponse)
def teacher_survey_catalog(
    db: Session = Depends(get_db),
    teacher: User = Depends(_require_teacher),
) -> SurveyCatalogResponse:
    templates, qcounts = _active_catalog(db)
    return SurveyCatalogResponse(
        items=[_template_brief(t, qcounts.get(t.id, 0)) for t in templates],
        categories=SURVEY_CATEGORY_LABELS_TR,
    )


@router.get(
    "/teacher/students/{student_id}/surveys",
    response_model=TeacherStudentSurveysResponse,
)
def teacher_student_surveys(
    student_id: int,
    db: Session = Depends(get_db),
    teacher: User = Depends(_require_teacher),
) -> TeacherStudentSurveysResponse:
    _get_owned_student(db, student_id, teacher.id)
    templates, qcounts = _active_catalog(db)
    assignments = (
        db.query(SurveyAssignment)
        .options(
            joinedload(SurveyAssignment.template),
            joinedload(SurveyAssignment.teacher),
            joinedload(SurveyAssignment.student),
        )
        .filter(SurveyAssignment.student_id == student_id)
        .order_by(SurveyAssignment.assigned_at.desc())
        .all()
    )
    all_qcounts = dict(qcounts)
    missing_tids = [
        a.template_id for a in assignments if a.template_id not in all_qcounts
    ]
    all_qcounts.update(_question_counts(db, missing_tids))
    return TeacherStudentSurveysResponse(
        assignments=[_assignment_row(a, all_qcounts) for a in assignments],
        catalog=[_template_brief(t, qcounts.get(t.id, 0)) for t in templates],
        categories=SURVEY_CATEGORY_LABELS_TR,
    )


@router.post(
    "/teacher/students/{student_id}/surveys",
    response_model=MutationResponse[SurveyAssignResult],
)
def teacher_assign_survey(
    student_id: int,
    body: SurveyAssignBody,
    db: Session = Depends(get_db),
    teacher: User = Depends(_require_teacher),
) -> MutationResponse[SurveyAssignResult]:
    student = _get_owned_student(db, student_id, teacher.id)
    template = (
        db.query(SurveyTemplate)
        .filter(
            SurveyTemplate.id == body.template_id,
            SurveyTemplate.is_active.is_(True),
        )
        .first()
    )
    if not template:
        raise _not_found("survey_not_found", "Anket bulunamadı.")
    if survey_service.has_open_assignment(db, student_id, template.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "survey_already_assigned",
                "message": "Bu anket öğrencide zaten bekliyor — önce mevcut atama tamamlanmalı veya iptal edilmeli.",
            },
        )
    assignment = SurveyAssignment(
        template_id=template.id,
        teacher_id=teacher.id,
        student_id=student.id,
        note=(body.note or "").strip(),
    )
    db.add(assignment)
    db.commit()
    # Öğrenciye push — anket bekliyor
    safe_push(
        db,
        user_id=student.id,
        title="Yeni anket",
        body=f"Koçun senden bir anket doldurmanı istiyor: {template.title}",
        data={"type": "student", "screen": "surveys"},
    )
    return MutationResponse(
        data=SurveyAssignResult(assignment_id=assignment.id),
        invalidate=[
            f"teacher:{teacher.id}:students:{student_id}:surveys",
        ],
    )


def _get_teacher_assignment(
    db: Session, assignment_id: int, teacher_id: int
) -> SurveyAssignment:
    a = (
        db.query(SurveyAssignment)
        .options(
            joinedload(SurveyAssignment.template),
            joinedload(SurveyAssignment.teacher),
            joinedload(SurveyAssignment.student),
        )
        .filter(SurveyAssignment.id == assignment_id)
        .first()
    )
    # Sahiplik: atayan koç VEYA öğrencinin güncel koçu (koç değişimi durumu)
    if not a or not (
        a.teacher_id == teacher_id
        or (a.student and a.student.teacher_id == teacher_id)
    ):
        raise _not_found("assignment_not_found", "Anket ataması bulunamadı.")
    return a


@router.get(
    "/teacher/surveys/assignments/{assignment_id}",
    response_model=SurveyAssignmentDetail,
)
def teacher_assignment_detail(
    assignment_id: int,
    db: Session = Depends(get_db),
    teacher: User = Depends(_require_teacher),
) -> SurveyAssignmentDetail:
    a = _get_teacher_assignment(db, assignment_id, teacher.id)
    qcounts = _question_counts(db, [a.template_id])
    result = survey_service.build_result(a.template, a)
    return SurveyAssignmentDetail(
        assignment=_assignment_row(a, qcounts),
        result=SurveyResultModel(**result) if result else None,
    )


@router.post(
    "/teacher/surveys/assignments/{assignment_id}/cancel",
    response_model=MutationResponse[SurveyCancelResult],
)
def teacher_cancel_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    teacher: User = Depends(_require_teacher),
) -> MutationResponse[SurveyCancelResult]:
    a = _get_teacher_assignment(db, assignment_id, teacher.id)
    if a.status == ASSIGNMENT_COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_state",
                "code": "survey_completed",
                "message": "Tamamlanmış anket iptal edilemez.",
            },
        )
    a.status = ASSIGNMENT_CANCELLED
    db.commit()
    return MutationResponse(
        data=SurveyCancelResult(),
        invalidate=[
            f"teacher:{teacher.id}:students:{a.student_id}:surveys",
        ],
    )


# =============================================================================
# AI Kariyer Sentezi — anketler ölçer, AI sentezler (KS4 kredi deseni)
# =============================================================================


def _latest_completed_by_code(
    db: Session, student_id: int
) -> dict[str, SurveyAssignment]:
    """Kariyer setindeki her anket kodu için en güncel TAMAMLANMIŞ atama."""
    rows = (
        db.query(SurveyAssignment)
        .join(SurveyTemplate, SurveyAssignment.template_id == SurveyTemplate.id)
        .options(joinedload(SurveyAssignment.template))
        .filter(
            SurveyAssignment.student_id == student_id,
            SurveyAssignment.status == ASSIGNMENT_COMPLETED,
            SurveyTemplate.code.in_(CAREER_SURVEY_CODES),
        )
        .order_by(SurveyAssignment.completed_at.desc())
        .all()
    )
    by_code: dict[str, SurveyAssignment] = {}
    for a in rows:
        code = a.template.code
        if code not in by_code:
            by_code[code] = a
    return by_code


def _career_readiness(
    db: Session, student_id: int
) -> tuple[bool, list[str], dict[str, SurveyAssignment]]:
    """(ready, eksik anket başlıkları, kod→tamamlanmış atama)."""
    by_code = _latest_completed_by_code(db, student_id)
    missing_codes = [c for c in CAREER_REQUIRED_CODES if c not in by_code]
    if not missing_codes:
        return True, [], by_code
    titles = dict(
        db.query(SurveyTemplate.code, SurveyTemplate.title)
        .filter(SurveyTemplate.code.in_(missing_codes))
        .all()
    )
    return False, [titles.get(c, c) for c in missing_codes], by_code


def _mark_career_stale(db: Session, student_id: int) -> None:
    """Kariyer setinden bir anket yeniden tamamlandı → cache bayatlar (AI çağrısı YOK)."""
    ci = (
        db.query(CareerInsight)
        .filter(CareerInsight.student_id == student_id)
        .first()
    )
    if ci is not None and not ci.is_stale:
        ci.is_stale = True


def _career_insight_to_model(ci: CareerInsight) -> CareerSynthesisModel:
    import json as _json

    def _loads(v, default):
        if not v:
            return default
        try:
            out = _json.loads(v)
            return out if isinstance(out, (list, dict)) else default
        except Exception:
            return default

    based = _loads(ci.based_on, {})
    return CareerSynthesisModel(
        summary=ci.summary or "",
        career_suggestions=[
            CareerSuggestionModel(**s)
            for s in _loads(ci.career_suggestions, [])
            if isinstance(s, dict) and s.get("title")
        ],
        strengths=_loads(ci.strengths, []),
        agenda=_loads(ci.agenda, []),
        watch_outs=_loads(ci.watch_outs, []),
        based_on_surveys=(based.get("survey_titles") or []) if isinstance(based, dict) else [],
        exam_count=int(based.get("exam_count") or 0) if isinstance(based, dict) else 0,
        generated_at=ci.generated_at,
    )


_CAREER_DISCLAIMER = (
    "Bu sentez bir öneri/taslaktır; kesin yönlendirme değildir. Karar koç, "
    "öğrenci ve ailenindir. " + SURVEY_DISCLAIMER_TR
)


@router.get(
    "/teacher/students/{student_id}/career-synthesis",
    response_model=CareerSynthesisCacheResponse,
)
def teacher_career_synthesis_get(
    student_id: int,
    db: Session = Depends(get_db),
    teacher: User = Depends(_require_teacher),
) -> CareerSynthesisCacheResponse:
    """Cache'lenmiş Kariyer Sentezi'ni oku — KREDİ DÜŞMEZ.

    `ready=False` ise zorunlu anketler (Mesleki İlgi + Beceri Seti) henüz
    tamamlanmamış — `missing_surveys` koça hangilerini uygulayacağını söyler.
    """
    _get_owned_student(db, student_id, teacher.id)
    ready, missing, _ = _career_readiness(db, student_id)
    ci = (
        db.query(CareerInsight)
        .filter(CareerInsight.student_id == student_id)
        .first()
    )
    return CareerSynthesisCacheResponse(
        insight=_career_insight_to_model(ci) if ci else None,
        is_stale=bool(ci.is_stale) if ci else False,
        ready=ready,
        missing_surveys=missing,
        disclaimer=_CAREER_DISCLAIMER,
    )


@router.post(
    "/teacher/students/{student_id}/career-synthesis",
    response_model=CareerSynthesisCacheResponse,
)
def teacher_career_synthesis_generate(
    student_id: int,
    db: Session = Depends(get_db),
    teacher: User = Depends(_require_teacher),
) -> CareerSynthesisCacheResponse:
    """Kariyer Sentezi ÜRET/YENİLE — KREDİ DÜŞER (AI_CAREER_SYNTHESIS).

    Zorunlu: ücretli paket + AI rızası + Mesleki İlgi ve Beceri Seti anketleri
    tamamlanmış. Sonuç cache'lenir; sonraki görüntülemeler GET ile ücretsiz.
    """
    import json as _json
    from datetime import datetime, timezone

    from app.models import ExamResult, UsageKind
    from app.models.curriculum import EXAM_SECTION_LABELS
    from app.routes.api_v2.dependencies import assert_ai_premium
    from app.routes.api_v2.teacher import (
        _ai_credit_exhausted_error,
        _compute_session_prefill,
    )
    from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable
    from app.services.ai_career_synthesis import generate_career_synthesis
    from app.services.credits import CreditBlocked, CreditOwner, consume_credits

    student = _get_owned_student(db, student_id, teacher.id)
    assert_ai_premium(db, teacher)  # ücretli paket kapısı (tek kaynak)
    if teacher.ai_capture_consent_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "code": "consent_required",
                    "message": "AI özellikleri için önce açık rıza vermelisiniz."},
        )

    ready, missing, by_code = _career_readiness(db, student_id)
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "not_enough_data",
                "message": "Kariyer sentezi için önce şu anketler tamamlanmalı: "
                + ", ".join(missing),
                "details": {"missing_surveys": missing},
            },
        )

    # Anket sonuçlarını AI girdisine çevir (deterministik skorlar)
    surveys_data: list[dict] = []
    survey_titles: list[str] = []
    for code in CAREER_SURVEY_CODES:
        a = by_code.get(code)
        if not a:
            continue
        result = survey_service.build_result(a.template, a)
        if not result:
            continue
        survey_titles.append(a.template.title)
        surveys_data.append({
            "title": a.template.title,
            "completed_at": a.completed_at.date().isoformat() if a.completed_at else "?",
            "dimensions": [
                {
                    "label": d["label"],
                    "score_pct": d["score_pct"],
                    "level_label": d["level_label"],
                }
                for d in result.get("dimensions", [])
            ],
        })

    academic = _compute_session_prefill(db, student)
    exam_rows = (
        db.query(ExamResult)
        .filter(ExamResult.student_id == student.id)
        .order_by(ExamResult.exam_date.desc(), ExamResult.id.desc())
        .limit(5)
        .all()
    )
    exams = []
    for e in exam_rows:
        total_q = e.total_correct + e.total_wrong + e.total_blank
        exams.append({
            "title": e.title,
            "section_label": EXAM_SECTION_LABELS[e.section],
            "net": e.net,
            "net_pct": int(round(100 * e.net / total_q)) if total_q > 0 else None,
        })

    grade_label = (
        "Mezun" if getattr(student, "is_graduate", False)
        else f"{student.grade_level}. sınıf" if student.grade_level
        else "sınıf bilinmiyor"
    )

    owner = CreditOwner.for_user(teacher)
    synthesis: dict | None = None
    try:
        with consume_credits(
            db, owner=owner, kind=UsageKind.AI_CAREER_SYNTHESIS,
            actor_user_id=teacher.id, autocommit=False,
        ) as cctx:
            synthesis = generate_career_synthesis(
                student.full_name, grade_label, surveys_data, academic, exams,
            )
            cctx.set_metadata({
                "student_id": student_id, "surveys": len(surveys_data),
            })
    except CreditBlocked as e:
        db.rollback()
        raise _ai_credit_exhausted_error(teacher, e.message)
    except AIInvalidResponse as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "synthesis_unreadable",
                    "message": f"Kariyer sentezi üretilemedi: {e}"},
        )
    except AIServiceUnavailable as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "upstream_unavailable", "code": "ai_unavailable",
                    "message": f"AI servisi şu an kullanılamıyor: {e}"},
        )

    ci = (
        db.query(CareerInsight)
        .filter(CareerInsight.student_id == student.id)
        .first()
    )
    if ci is None:
        ci = CareerInsight(student_id=student.id)
        db.add(ci)
    ci.generated_by_id = teacher.id
    ci.summary = synthesis["summary"]
    ci.career_suggestions = _json.dumps(
        synthesis["career_suggestions"], ensure_ascii=False
    )
    ci.strengths = _json.dumps(synthesis["strengths"], ensure_ascii=False)
    ci.agenda = _json.dumps(synthesis["agenda"], ensure_ascii=False)
    ci.watch_outs = _json.dumps(synthesis["watch_outs"], ensure_ascii=False)
    ci.based_on = _json.dumps(
        {"survey_titles": survey_titles, "exam_count": len(exams)},
        ensure_ascii=False,
    )
    ci.is_stale = False
    ci.generated_at = datetime.now(timezone.utc)
    db.commit()  # kredi kaydı + cache birlikte sabitlenir
    db.refresh(ci)
    return CareerSynthesisCacheResponse(
        insight=_career_insight_to_model(ci),
        is_stale=False,
        ready=True,
        missing_surveys=[],
        disclaimer=_CAREER_DISCLAIMER,
    )


# =============================================================================
# Öğrenci yüzeyi
# =============================================================================


@router.get("/student/surveys", response_model=StudentSurveysResponse)
def student_surveys(
    db: Session = Depends(get_db),
    student: User = Depends(_require_student),
) -> StudentSurveysResponse:
    assignments = (
        db.query(SurveyAssignment)
        .options(
            joinedload(SurveyAssignment.template),
            joinedload(SurveyAssignment.teacher),
            joinedload(SurveyAssignment.student),
        )
        .filter(SurveyAssignment.student_id == student.id)
        .order_by(SurveyAssignment.assigned_at.desc())
        .all()
    )
    qcounts = _question_counts(db, list({a.template_id for a in assignments}))
    pending: list = []
    completed: list = []
    for a in assignments:
        if a.status in (ASSIGNMENT_PENDING, ASSIGNMENT_IN_PROGRESS):
            pending.append(_assignment_row(a, qcounts))
        elif a.status == ASSIGNMENT_COMPLETED:
            completed.append(_assignment_row(a, qcounts))
        # cancelled öğrenciye gösterilmez
    return StudentSurveysResponse(pending=pending, completed=completed)


def _get_student_assignment(
    db: Session, assignment_id: int, student_id: int
) -> SurveyAssignment:
    a = (
        db.query(SurveyAssignment)
        .options(
            joinedload(SurveyAssignment.template),
            joinedload(SurveyAssignment.teacher),
            joinedload(SurveyAssignment.student),
        )
        .filter(
            SurveyAssignment.id == assignment_id,
            SurveyAssignment.student_id == student_id,
        )
        .first()
    )
    if not a or a.status == ASSIGNMENT_CANCELLED:
        raise _not_found("assignment_not_found", "Anket bulunamadı.")
    return a


@router.get(
    "/student/surveys/{assignment_id}",
    response_model=StudentSurveyFillResponse,
)
def student_survey_fill_view(
    assignment_id: int,
    db: Session = Depends(get_db),
    student: User = Depends(_require_student),
) -> StudentSurveyFillResponse:
    a = _get_student_assignment(db, assignment_id, student.id)
    questions = (
        db.query(SurveyQuestion)
        .filter(SurveyQuestion.template_id == a.template_id)
        .order_by(SurveyQuestion.order_no)
        .all()
    )
    result = survey_service.build_result(a.template, a)
    return StudentSurveyFillResponse(
        assignment=_assignment_row(a, {a.template_id: len(questions)}),
        questions=[
            SurveyQuestionModel(
                id=q.id,
                order_no=q.order_no,
                text=q.text,
                qtype=q.qtype,
                dimension_key=q.dimension_key,
                options=survey_service.parse_options(q),
            )
            for q in questions
        ],
        answers=survey_service.parse_answers(a),
        result=SurveyResultModel(**result) if result else None,
        disclaimer=SURVEY_DISCLAIMER_TR,
    )


@router.post(
    "/student/surveys/{assignment_id}/answers",
    response_model=MutationResponse[StudentSurveySaveResult],
)
def student_survey_save(
    assignment_id: int,
    body: StudentSurveyAnswersBody,
    db: Session = Depends(get_db),
    student: User = Depends(_require_student),
) -> MutationResponse[StudentSurveySaveResult]:
    a = _get_student_assignment(db, assignment_id, student.id)
    if a.status == ASSIGNMENT_COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_state",
                "code": "survey_completed",
                "message": "Bu anket zaten tamamlandı.",
            },
        )
    questions = (
        db.query(SurveyQuestion)
        .filter(SurveyQuestion.template_id == a.template_id)
        .order_by(SurveyQuestion.order_no)
        .all()
    )
    completed_now, missing = survey_service.save_answers(
        db, a, a.template, questions, body.answers or {}, body.complete
    )
    if completed_now and a.template.code in CAREER_SURVEY_CODES:
        # Kariyer setinden anket tamamlandı → AI sentez cache'i bayatlar
        _mark_career_stale(db, a.student_id)
    if body.complete and missing:
        db.commit()  # kısmi cevaplar yine de kaybolmasın
        return MutationResponse(
            data=StudentSurveySaveResult(
                ok=False,
                status=a.status,
                completed=False,
                missing_question_ids=missing,
            ),
            invalidate=["student:surveys"],
        )
    db.commit()
    if completed_now and a.teacher_id:
        safe_push(
            db,
            user_id=a.teacher_id,
            title="Anket tamamlandı",
            body=f"{student.full_name} · {a.template.title}",
            data={
                "type": "coach_student",
                "student_id": str(a.student_id),
                "screen": "surveys",
            },
        )
    return MutationResponse(
        data=StudentSurveySaveResult(
            ok=True, status=a.status, completed=completed_now
        ),
        invalidate=["student:surveys"],
    )
