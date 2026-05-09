"""Stage 11 (Faz 3) — Otomatik hedef türetme.

Bir öğrencinin sınav hedefi (LGS/YKS) belirlendiğinde standart hedef ağacı
şablonu oluşturulur. Öğretmen/öğrenci sonradan özelleştirebilir.

Akış:
1. `seed_for_exam_target(student)` — root EXAM_TARGET + altına SUBJECT'leri kur
2. Auto-generated flag set edilir → öğretmen panelinde işaretlenir
3. Mevcut hedefler varsa silinmez (idempotent: sadece eksik düğümler eklenir)

Not: Bu modül "öneri" değil "şablon kurma" yapar. AI önerisi (mevcut
performansa göre realistic hedef sayısı) Faz 5+'da eklenebilir.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models import (
    GoalKind,
    GoalStatus,
    StudentGoal,
    User,
    UserRole,
)
from app.services.goals import create_goal


logger = logging.getLogger(__name__)


# Standart subject şablonları — sınav türüne göre.
# Bu liste eğitimci kararı; gerekirse curriculum service'inden türetilebilir.
LGS_SUBJECTS: tuple[tuple[str, str], ...] = (
    ("Türkçe", "20 net"),
    ("Matematik", "20 net"),
    ("Fen Bilimleri", "20 net"),
    ("T.C. İnkılap Tarihi", "10 net"),
    ("Din Kültürü", "10 net"),
    ("İngilizce", "10 net"),
)

YKS_TYT_SUBJECTS: tuple[tuple[str, str], ...] = (
    ("TYT Türkçe", "40 net"),
    ("TYT Matematik", "40 net"),
    ("TYT Sosyal Bilimler", "20 net"),
    ("TYT Fen Bilimleri", "20 net"),
)

YKS_AYT_SAYISAL: tuple[tuple[str, str], ...] = (
    ("AYT Matematik", "40 net"),
    ("AYT Fizik", "14 net"),
    ("AYT Kimya", "13 net"),
    ("AYT Biyoloji", "13 net"),
)

YKS_AYT_EA: tuple[tuple[str, str], ...] = (
    ("AYT Matematik", "40 net"),
    ("AYT Türk Dili ve Edebiyatı", "24 net"),
    ("AYT Tarih-1", "10 net"),
    ("AYT Coğrafya-1", "6 net"),
)

YKS_AYT_SOZEL: tuple[tuple[str, str], ...] = (
    ("AYT Türk Dili ve Edebiyatı", "24 net"),
    ("AYT Tarih-1", "10 net"),
    ("AYT Tarih-2", "11 net"),
    ("AYT Coğrafya-1", "6 net"),
    ("AYT Coğrafya-2", "11 net"),
    ("AYT Felsefe Grubu", "12 net"),
    ("AYT Din Kültürü", "6 net"),
)

YKS_AYT_DIL: tuple[tuple[str, str], ...] = (
    ("AYT Yabancı Dil", "80 net"),
)


def _parse_target_str(target_str: str) -> tuple[float | None, str | None]:
    """'20 net' → (20, 'net') gibi parse."""
    parts = target_str.strip().split(maxsplit=1)
    if not parts:
        return None, None
    try:
        val = float(parts[0])
        unit = parts[1] if len(parts) > 1 else None
        return val, unit
    except ValueError:
        return None, None


def _get_yks_ayt_subjects(student: User) -> tuple[tuple[str, str], ...]:
    """Öğrencinin alanına göre AYT subject listesi döndür."""
    track = getattr(student, "track", None)
    if track is None:
        return ()
    # Track enum: .value küçük harfli ('sayisal', 'ea', 'sozel', 'dil')
    track_value = (
        track.value if hasattr(track, "value") else str(track)
    ).lower()
    if track_value == "sayisal":
        return YKS_AYT_SAYISAL
    if track_value == "ea":
        return YKS_AYT_EA
    if track_value == "sozel":
        return YKS_AYT_SOZEL
    if track_value == "dil":
        return YKS_AYT_DIL
    return ()


def seed_for_exam_target(
    db: Session, *, student: User,
    created_by_user_id: int | None = None,
    autocommit: bool = True,
) -> dict:
    """Öğrencinin sınav hedefine göre standart hedef ağacını kur.

    İdempotent: zaten EXAM_TARGET kök hedefi varsa subject altları eklenmez
    (öğretmen müdahalesini yenmek istemiyoruz). Yeni öğrenci için ilk seed.

    Returns: {'created': N, 'skipped_existing': bool, 'exam_target': str | None}
    """
    target = student.effective_exam_target
    if target is None:
        return {"created": 0, "skipped_existing": False, "exam_target": None}

    # Zaten EXAM_TARGET kök hedefi var mı?
    existing_root = (
        db.query(StudentGoal)
        .filter(
            StudentGoal.student_id == student.id,
            StudentGoal.kind == GoalKind.EXAM_TARGET,
            StudentGoal.parent_id.is_(None),
            StudentGoal.status != GoalStatus.ABANDONED,
        )
        .first()
    )
    if existing_root is not None:
        return {
            "created": 0, "skipped_existing": True, "exam_target": target,
        }

    target_label = student.effective_exam_label
    target_date_value: date | None = student.effective_exam_date

    # Kök hedef oluştur
    root = create_goal(
        db, student=student, kind=GoalKind.EXAM_TARGET,
        title=target_label,
        description=f"{target} sınavı genel hedef",
        target_date=target_date_value,
        is_auto_generated=True,
        created_by_user_id=created_by_user_id,
        autocommit=False,
    )
    created_count = 1

    # Subject şablonu seç
    if target == "LGS":
        subjects = LGS_SUBJECTS
    elif target == "YKS":
        # TYT + AYT alana göre
        subjects = YKS_TYT_SUBJECTS + _get_yks_ayt_subjects(student)
    else:
        subjects = ()

    for sub_title, sub_target_str in subjects:
        target_value, unit = _parse_target_str(sub_target_str)
        create_goal(
            db, student=student, kind=GoalKind.SUBJECT,
            title=sub_title, parent_id=root.id,
            target_value=target_value, unit=unit,
            is_auto_generated=True,
            created_by_user_id=created_by_user_id,
            autocommit=False,
        )
        created_count += 1

    if autocommit:
        db.commit()
    else:
        db.flush()
    logger.info(
        "seed_for_exam_target: student=%s target=%s created=%d",
        student.id, target, created_count,
    )
    return {
        "created": created_count, "skipped_existing": False,
        "exam_target": target,
    }


def bulk_seed_for_institution(
    db: Session, *, institution_id: int,
    created_by_user_id: int | None = None,
) -> dict:
    """Bir kurumdaki tüm öğrenciler için seed (mevcut hedefi olanları atla)."""
    students = (
        db.query(User)
        .filter(
            User.institution_id == institution_id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
        )
        .all()
    )
    counts = {"seeded": 0, "skipped_existing": 0, "skipped_no_target": 0}
    for s in students:
        result = seed_for_exam_target(
            db, student=s, created_by_user_id=created_by_user_id,
            autocommit=False,
        )
        if result["exam_target"] is None:
            counts["skipped_no_target"] += 1
        elif result["skipped_existing"]:
            counts["skipped_existing"] += 1
        else:
            counts["seeded"] += 1
    db.commit()
    return counts
