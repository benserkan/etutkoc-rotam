"""Seed müfredatı (LGS + Klasik Lise + Maarif Modeli) ve isteğe bağlı demo öğretmen.

Kullanım:
    python -m scripts.seed                    # tüm müfredatları ekle (idempotent)
    python -m scripts.seed --teacher          # ek olarak demo öğretmen oluştur
    python -m scripts.seed --only LGS         # sadece belirli modeli seed et

Idempotency:
- Subject: (teacher_id=None, name, curriculum_model) tek olmalı; varsa güncelleme,
  yoksa ekleme yapar.
- Topic: (subject_id, name, grade_level) eşleşirse atlanır, yoksa eklenir.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Proje kökünü path'e ekle
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    CurriculumModel,
    ExamSection,
    Subject,
    Topic,
    User,
    UserRole,
)
from app.services.security import hash_password
from scripts.curriculum_data import ALL_CURRICULA


def _enum_or_none(enum_cls, value: str | None):
    """String'i enum'a çevir; None veya geçersizse None döndür."""
    if value is None:
        return None
    try:
        return enum_cls[value]
    except KeyError:
        return None


def seed_curriculum(db: Session, *, only_model: str | None = None) -> dict[str, int]:
    """Tüm müfredat modellerini idempotent şekilde seed et.

    Returns: {model_name: yeni_eklenen_topic_sayısı}
    """
    counts: dict[str, int] = {}

    for model_name, curriculum in ALL_CURRICULA.items():
        if only_model and model_name != only_model:
            continue
        if not curriculum:
            print(f"  ({model_name}): boş, atlandı")
            continue

        cm_enum = CurriculumModel[model_name]
        added_topics = 0

        print(f"  [{model_name}]")
        for order, (subject_name, spec) in enumerate(curriculum.items()):
            exam_section_enum = _enum_or_none(ExamSection, spec.get("exam_section"))

            # Subject — (teacher_id=None, name, curriculum_model) ile ara
            subject = (
                db.query(Subject)
                .filter(
                    Subject.is_builtin.is_(True),
                    Subject.teacher_id.is_(None),
                    Subject.name == subject_name,
                    Subject.curriculum_model == cm_enum,
                )
                .first()
            )
            if not subject:
                subject = Subject(
                    name=subject_name,
                    order=order,
                    is_builtin=True,
                    teacher_id=None,
                    min_grade_level=spec.get("min_grade"),
                    max_grade_level=spec.get("max_grade"),
                    available_for_graduate=spec.get("available_for_graduate", False),
                    exam_section=exam_section_enum,
                    curriculum_model=cm_enum,
                )
                db.add(subject)
                db.flush()
                print(f"    + Ders: {subject_name} ({spec.get('min_grade')}-{spec.get('max_grade')})")
            else:
                # Mevcut subject — alanları güncelle (config drift'i önle)
                subject.order = order
                subject.min_grade_level = spec.get("min_grade")
                subject.max_grade_level = spec.get("max_grade")
                subject.available_for_graduate = spec.get("available_for_graduate", False)
                subject.exam_section = exam_section_enum
                subject.curriculum_model = cm_enum

            # Topics — (subject_id, name, grade_level) ile ara
            existing_keys = {(t.name, t.grade_level) for t in subject.topics}
            for topic_order, (topic_name, topic_grade) in enumerate(spec["topics"]):
                if (topic_name, topic_grade) in existing_keys:
                    continue
                db.add(Topic(
                    subject_id=subject.id,
                    name=topic_name,
                    order=topic_order,
                    grade_level=topic_grade,
                    is_builtin=True,
                    teacher_id=None,
                    curriculum_model=cm_enum,
                ))
                added_topics += 1

        counts[model_name] = added_topics
        print(f"    Toplam yeni topic: {added_topics}")

    db.commit()
    return counts


def seed_demo_teacher(db: Session) -> None:
    email = "ogretmen@lgs.local"
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        print(f"  = Demo öğretmen zaten var: {email}")
        return
    teacher = User(
        email=email,
        password_hash=hash_password("ogretmen123"),
        full_name="Demo Öğretmen",
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.commit()
    print(f"  + Demo öğretmen oluşturuldu: {email} / şifre: ogretmen123")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher", action="store_true", help="Demo öğretmen oluştur")
    parser.add_argument(
        "--only",
        choices=["LGS", "MAARIF_LISE", "KLASIK_LISE"],
        help="Sadece belirli müfredat modelini seed et",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("Müfredat seed başlıyor...")
        counts = seed_curriculum(db, only_model=args.only)
        print(f"Özet: {counts}")
        if args.teacher:
            seed_demo_teacher(db)
        print("Tamamlandı.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
