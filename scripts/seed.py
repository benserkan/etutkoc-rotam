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
    CronSchedule,
    CurriculumModel,
    ExamSection,
    Subject,
    Topic,
    User,
    UserRole,
)
from app.services.security import hash_password
from scripts.curriculum_data import ALL_CURRICULA, EXAM_CURRICULUM


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

            # Topics — iki format DESTEKLENİR + aynı derste BİRLİKTE olabilir:
            #   1) "topics": [(name, grade), ...]  → düz konu (LGS 8, Klasik)
            #   2) "units":  [(no, name, grade, [alt_başlık, ...]), ...]
            #      → her ünite/tema PARENT Topic, alt başlıklar parent_id ile CHILD
            #        (Maarif + LGS 5-7; test kitapları alt başlıkla düzenlenir). Sıralama:
            #        order = grade*10000 + unit_no*100 (+ alt sırası) → sınıf→ünite→alt.
            # NOT: bir derste hem "topics" (örn. LGS 8 düz) hem "units" (LGS 5-7 tema+
            # alt başlık) bulunabilir → ikisi de işlenir.
            existing_keys = {(t.name, t.grade_level, t.parent_id) for t in subject.topics}
            units = spec.get("units")
            if units:
                term = spec.get("unit_term", "Ünite")
                for unit_no, unit_name, grade, subtopics in units:
                    parent_name = f"{unit_no}. {term}: {unit_name}"
                    parent_order = grade * 10000 + unit_no * 100
                    parent = next(
                        (t for t in subject.topics
                         if t.name == parent_name and t.grade_level == grade
                         and t.parent_id is None),
                        None,
                    )
                    if parent is None:
                        parent = Topic(
                            subject_id=subject.id, name=parent_name, order=parent_order,
                            grade_level=grade, is_builtin=True, teacher_id=None,
                            curriculum_model=cm_enum, parent_id=None,
                        )
                        db.add(parent); db.flush()
                        added_topics += 1
                    for sub_idx, sub_name in enumerate(subtopics):
                        if (sub_name, grade, parent.id) in existing_keys:
                            continue
                        db.add(Topic(
                            subject_id=subject.id, name=sub_name,
                            order=parent_order + sub_idx + 1, grade_level=grade,
                            is_builtin=True, teacher_id=None,
                            curriculum_model=cm_enum, parent_id=parent.id,
                        ))
                        added_topics += 1
            # "topics" (düz) — units'ten BAĞIMSIZ işlenir (ikisi bir arada olabilir)
            for topic_order, (topic_name, topic_grade) in enumerate(spec.get("topics", [])):
                if (topic_name, topic_grade, None) in existing_keys:
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


def seed_exam_curriculum(db: Session) -> int:
    """Sınav-bazlı kanonik taksonomi (TYT/AYT) — model-bağımsız, idempotent.

    Okul müfredatından (LGS/Maarif/Klasik) AYRI dersler: `curriculum_model=None`
    + `exam_section` set. Test kitapları + YKS koçluğu bu omurgayla eşleşir.
    Düz `topics` formatı (parent/child yok). Returns: yeni eklenen topic sayısı.
    """
    added = 0
    print("  [EXAM — TYT/AYT kanonik]")
    base_order = 900  # okul derslerinden sonra sırala
    for idx, (subject_name, spec) in enumerate(EXAM_CURRICULUM.items()):
        exam_section_enum = _enum_or_none(ExamSection, spec.get("exam_section"))
        subject = (
            db.query(Subject)
            .filter(
                Subject.is_builtin.is_(True),
                Subject.teacher_id.is_(None),
                Subject.name == subject_name,
                Subject.curriculum_model.is_(None),
            )
            .first()
        )
        if not subject:
            subject = Subject(
                name=subject_name, order=base_order + idx, is_builtin=True,
                teacher_id=None, min_grade_level=spec.get("min_grade"),
                max_grade_level=spec.get("max_grade"),
                available_for_graduate=spec.get("available_for_graduate", False),
                exam_section=exam_section_enum, curriculum_model=None,
            )
            db.add(subject); db.flush()
            print(f"    + Ders: {subject_name} ({spec.get('exam_section')})")
        else:
            subject.order = base_order + idx
            subject.min_grade_level = spec.get("min_grade")
            subject.max_grade_level = spec.get("max_grade")
            subject.available_for_graduate = spec.get("available_for_graduate", False)
            subject.exam_section = exam_section_enum

        existing = {(t.name, t.grade_level) for t in subject.topics}
        for topic_order, (topic_name, topic_grade) in enumerate(spec.get("topics", [])):
            if (topic_name, topic_grade) in existing:
                continue
            db.add(Topic(
                subject_id=subject.id, name=topic_name, order=topic_order,
                grade_level=topic_grade, is_builtin=True, teacher_id=None,
                curriculum_model=None,
            ))
            added += 1
    db.commit()
    print(f"    Toplam yeni topic: {added}")
    return added


def seed_cron_schedules(db: Session) -> int:
    """Bildirim cron job'larını idempotent olarak ekle.

    Production deploy sonrası bunlar olmadan veli bildirimleri tetiklenmez.
    job_key UniqueConstraint koruyor — varsa atlar, yoksa ekler.
    """
    schedules = [
        ("daily_summary", 21, 0, None,
         "Her akşam 21:00 UTC — günlük özet + boş gün uyarısı"),
        ("weekly_backstop", 23, 55, None,
         "Her gece 23:55 UTC — haftalık rapor backstop"),
        ("drop_alert", 6, 0, 0,
         "Pazartesi 06:00 UTC — geçen haftaya göre %30+ düşüş"),
        ("exam_approaching", 8, 15, None,
         "Her gün 08:15 UTC — D-30/D-7/D-1 sınav yaklaşıyor"),
    ]
    added = 0
    for job_key, hour, minute, dow, desc in schedules:
        existing = (
            db.query(CronSchedule)
            .filter(CronSchedule.job_key == job_key)
            .first()
        )
        if existing:
            continue
        db.add(CronSchedule(
            job_key=job_key,
            description=desc,
            hour=hour,
            minute=minute,
            day_of_week=dow,
            enabled=True,
        ))
        added += 1
    db.commit()
    print(f"  + {added} yeni cron schedule eklendi (toplam {len(schedules)})")
    return added


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


def seed_super_admin(
    db: Session, *, email: str, password: str, full_name: str = "Süper Admin"
) -> None:
    """İlk SUPER_ADMIN hesabını oluştur (idempotent — varsa atla)."""
    from app.models import UserRole
    existing = db.query(User).filter(User.email == email.lower().strip()).first()
    if existing:
        print(f"  = SUPER_ADMIN zaten var: {email}")
        return
    admin = User(
        email=email.lower().strip(),
        password_hash=hash_password(password),
        full_name=full_name,
        role=UserRole.SUPER_ADMIN,
    )
    db.add(admin)
    db.commit()
    print(f"  + SUPER_ADMIN oluşturuldu: {email}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher", action="store_true", help="Demo öğretmen oluştur")
    parser.add_argument(
        "--only",
        choices=["LGS", "MAARIF_LISE", "KLASIK_LISE"],
        help="Sadece belirli müfredat modelini seed et",
    )
    parser.add_argument(
        "--super-admin",
        nargs=2,
        metavar=("EMAIL", "PASSWORD"),
        help="İlk SUPER_ADMIN hesabını oluştur (örn: --super-admin you@x.com pass123)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("Müfredat seed başlıyor...")
        counts = seed_curriculum(db, only_model=args.only)
        print(f"Özet: {counts}")
        if not args.only:
            print("Sınav-bazlı kanonik taksonomi (TYT/AYT) seed...")
            seed_exam_curriculum(db)
        print("Cron schedules seed...")
        seed_cron_schedules(db)
        if args.teacher:
            seed_demo_teacher(db)
        if args.super_admin:
            email, password = args.super_admin
            seed_super_admin(db, email=email, password=password)
        print("Tamamlandı.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
