"""Sınıf geçişi önizlemesi (P5, 2026-09-05).

8→9 geçişi 9→10'dan FARKLIDIR: müfredat MODELİ değişir (LGS → Maarif Lise).
Bu, öğrencinin tüm konu omurgasının değişmesi demektir — kitapları hâlâ LGS
kaynağıdır, geçen yılın 600+ görevi ve denemeleri "bu yıl" ile karışabilir.

Bu servis YALNIZ ÖNİZLEME üretir — hiçbir şeyi değiştirmez. Uygulama mevcut,
test edilmiş uçlarla yapılır:
    POST /teacher/students/{id}/promote        → profil + DÖNEM DAMGASI (P2)
    POST /teacher/students/{id}/books/archive   → KİTAP ARŞİVİ (P4)

Böylece sihirbaz yeni bir yazma yolu açmaz; yalnız koça "ne olacak"ı önceden
gösterir ve iki adımı tek akışta birleştirir.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models import ExamResult, Task, User
from app.models.curriculum import CurriculumModel, derive_curriculum_model
from app.services import book_archive, grade_period_service

CURRICULUM_LABELS = {
    "lgs": "LGS Müfredatı",
    "maarif_lise": "Maarif Modeli",
    "klasik_lise": "Klasik Lise",
}


def _grade_label(grade: int | None, is_graduate: bool) -> str:
    if is_graduate:
        return "Mezun"
    return f"{grade}. Sınıf" if grade is not None else "—"


def _model_for(
    student: User,
    grade: int | None,
    is_graduate: bool,
    academic_year_start: int | None,
) -> CurriculumModel | None:
    return derive_curriculum_model(
        grade_level=grade,
        is_graduate=is_graduate,
        entry_year_grade9=student.entry_year_grade9,
        academic_year_start=academic_year_start,
    )


def build_preview(
    db: Session,
    student: User,
    *,
    new_grade: int | None,
    new_is_graduate: bool = False,
    academic_year_start: int | None = None,
    today: date | None = None,
) -> dict:
    """Yükseltme uygulanırsa ne olacağını önceden göster.

    `academic_year_start` = hedef akademik yılın Eylül-yılı (11-12/mezun
    kohort tahmini için). Verilmezse öğrencinin mevcut yılı kullanılır.
    """
    ref = today or date.today()

    cur_model = student.effective_curriculum_model
    ay_start = academic_year_start
    if ay_start is None and student.academic_year is not None:
        ay_start = student.academic_year.start_year
    new_model = _model_for(student, new_grade, new_is_graduate, ay_start)

    cur_key = getattr(cur_model, "value", None)
    new_key = getattr(new_model, "value", None)
    model_changes = bool(cur_key and new_key and cur_key != new_key)

    # --- Dönem sınırı (P2 kuralı) — henüz YAZILMAZ, yalnız hesaplanır
    current_period = grade_period_service.current_period(db, student.id)
    prev_start = current_period.started_on if current_period else None
    boundary = grade_period_service.compute_boundary(ref, prev_start)

    # Sınırdan ÖNCEKİ veri = geçen döneme yazılacak olan
    task_before = (
        db.query(Task.id)
        .filter(Task.student_id == student.id, Task.date < boundary)
        .count()
    )
    exam_before = (
        db.query(ExamResult.id)
        .filter(ExamResult.student_id == student.id, ExamResult.exam_date < boundary)
        .count()
    )

    # --- Arşiv adayları (P4) — güncel dönem başlangıcından önce atanmış kitaplar
    candidates = book_archive.archive_candidates(db, student.id, before=boundary)

    notes: list[str] = []
    if model_changes:
        notes.append(
            f"Müfredat modeli değişiyor: {CURRICULUM_LABELS.get(cur_key or '', '—')}"
            f" → {CURRICULUM_LABELS.get(new_key or '', '—')}. Öğrencinin konu"
            " omurgası tamamen değişir; eski kaynaklar yeni müfredatı kapsamaz."
        )
    if new_key is None:
        notes.append(
            "Yeni müfredat modeli belirlenemedi — akademik yıl seçilmemiş olabilir"
            " (11-12 ve mezunda kohort için gerekli)."
        )
    if candidates:
        notes.append(
            f"{len(candidates)} kitap geçen dönemde atanmış. Arşivlemek"
            " kütüphaneyi sadeleştirir; görev geçmişi ve çözülmüş testler SİLİNMEZ."
        )
    if task_before or exam_before:
        notes.append(
            f"{task_before} görev ve {exam_before} deneme geçen döneme yazılacak;"
            " güncel dönem tertemiz başlar. Veri silinmez, dönem seçicisinden"
            " her zaman görülebilir."
        )

    return {
        "student_id": student.id,
        "current_grade_label": _grade_label(
            student.grade_level, bool(student.is_graduate)
        ),
        "current_curriculum": cur_key,
        "current_curriculum_label": CURRICULUM_LABELS.get(cur_key or ""),
        "target_grade_label": _grade_label(new_grade, new_is_graduate),
        "target_curriculum": new_key,
        "target_curriculum_label": CURRICULUM_LABELS.get(new_key or ""),
        "model_changes": model_changes,
        # Sihirbaz YALNIZ model değişiminde gerekir (8→9 gibi); 9→10'da
        # normal yükseltme yeter — koçu gereksiz adımdan geçirmeyiz.
        "needs_wizard": model_changes,
        "period_boundary": boundary.isoformat(),
        "previous_period_label": (
            current_period.grade_label if current_period else None
        ),
        "previous_task_count": int(task_before),
        "previous_exam_count": int(exam_before),
        "archive_candidates": candidates,
        "notes": notes,
    }
