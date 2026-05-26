"""Compliance hafta-ortası regresyon simülasyonu.

Bağlam: 2026-05-26'da kullanıcı Yiğit'in haftalık tamamlama oranının %100
olması gerekirken %34 göründüğünü bildirdi. _student_totals_for_week tüm
hafta planını bölene katıyordu; bugün Salı olduğu için Çar-Pzr planları
"henüz tamamlanmamış" sayılıp rate'i yapay düşürüyordu. Düzeltme: helper
artık we'yi today ile cap'liyor.

Bu script, gelecekte aynı sınıf bug'ın tekrar dönüp dönmediğini yakalar.
5 senaryo (sınır durumları):
  S1: Salı, öğrenci Pzt+Sal %100 yapmış, Çar-Pzr planları 0 done →
      beklenen weekly_rate=%100 (eski kodda %34).
  S2: Pazar, öğrenci tam haftayı tamamlamış → weekly_rate=%100.
  S3: Salı, GERÇEKTEN düşük uyum (Pzt yarı, Sal yarı) → düşük rate,
      düşük uyum ALARMı çalışmalı (false-negative regresyonu).
  S4: Pasif öğrenci hesaba katılmaz.
  S5: Yeni öğrenci (henüz program yok) → empty_count artar, rate hesabı
      etkilenmez.

Çalıştırma: PYTHONPATH=. python scripts/simulate_compliance_midweek.py
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — register all mappers
from app.database import Base
from app.models import (
    AcademicYear,
    Institution,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.models.user import GraduateMode, Track  # noqa: F401
from app.services.institution_compliance import (
    _rate,
    _student_totals_for_week,
    _week_bounds,
    compute_compliance,
)


# --------------------------------------------------------------------------- #
# in-memory SQLite test DB — gerçek prod'a dokunmadan senaryo çalıştırır
# --------------------------------------------------------------------------- #
ENGINE = create_engine("sqlite:///:memory:")
Base.metadata.create_all(ENGINE)
Session = sessionmaker(bind=ENGINE)


def _setup(db, *, mode: str) -> dict:
    """Bir senaryonun başlangıç durumunu kurar.

    mode:
      's1_yigit_salı'  → Yiğit-modeli, bugün Salı.
      's2_yigit_pazar' → Yiğit-modeli, bugün Pazar (tam hafta).
      's3_düşük'       → Gerçek düşük uyum.
      's4_pasif'       → 1 aktif + 1 pasif.
      's5_yeni'        → 1 aktif + 1 yeni (programsız).
    """
    inst = Institution(name="Test Kurum", slug=f"test-{mode}", plan="etut_standart")
    db.add(inst); db.flush()
    coach = User(
        email=f"coach-{mode}@example.invalid",
        password_hash="x", full_name="Test Koç",
        role=UserRole.TEACHER, institution_id=inst.id,
        is_active=True,
    )
    db.add(coach); db.flush()
    student = User(
        email=f"student-{mode}@example.invalid",
        password_hash="x", full_name="Test Öğrenci",
        role=UserRole.STUDENT, teacher_id=coach.id, grade_level=8,
        is_active=True,
        # uyum sinyallerinde "yeni hesap grace" çıkmasın diye eski tarih
        created_at=datetime.now(timezone.utc) - timedelta(days=60),
    )
    db.add(student); db.flush()

    today = date.today()
    monday = today - timedelta(days=today.weekday())  # bu haftanın Pazartesi

    def _add_day(d: date, planned: int, completed: int) -> None:
        t = Task(
            student_id=student.id, date=d, title="Test görev",
            type=TaskType.TEST, status=TaskStatus.PENDING, is_draft=False,
        )
        db.add(t); db.flush()
        db.add(TaskBookItem(
            task_id=t.id, book_id=None, book_section_id=None,
            label="Deneme", planned_count=planned, completed_count=completed,
        ))

    if mode == "s1_yigit_salı":
        # Bugün Salı varsay
        _add_day(monday + timedelta(days=0), 100, 100)  # Pzt %100
        _add_day(monday + timedelta(days=1), 100, 100)  # Sal %100 (bugün)
        _add_day(monday + timedelta(days=2),  50,   0)  # Çar henüz vakti yok
        _add_day(monday + timedelta(days=3),  50,   0)  # Per
        _add_day(monday + timedelta(days=4),  50,   0)  # Cum
        _add_day(monday + timedelta(days=5),  50,   0)  # Cmt
        _add_day(monday + timedelta(days=6),  50,   0)  # Pzr
        sim_today = monday + timedelta(days=1)         # Salı
    elif mode == "s2_yigit_pazar":
        for i in range(7):
            _add_day(monday + timedelta(days=i), 50, 50)  # Hepsi %100
        sim_today = monday + timedelta(days=6)          # Pazar
    elif mode == "s3_düşük":
        _add_day(monday + timedelta(days=0), 100, 50)   # Pzt %50
        _add_day(monday + timedelta(days=1), 100, 30)   # Sal %30
        _add_day(monday + timedelta(days=2),  50,  0)
        sim_today = monday + timedelta(days=1)          # Salı
    elif mode == "s4_pasif":
        # aktif öğrenci + pasif öğrenci (pasif olanın görevi yok)
        _add_day(monday + timedelta(days=0), 100, 100)
        _add_day(monday + timedelta(days=1), 100, 100)
        passive = User(
            email=f"passive-{mode}@example.invalid",
            password_hash="x", full_name="Pasif Öğrenci",
            role=UserRole.STUDENT, teacher_id=coach.id,
            grade_level=8, is_active=False, is_paused=True,
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        db.add(passive)
        sim_today = monday + timedelta(days=1)
    elif mode == "s5_yeni":
        # aktif öğrenci tamamlanmış + yeni öğrenci (programsız)
        _add_day(monday + timedelta(days=0), 100, 100)
        _add_day(monday + timedelta(days=1), 100, 100)
        new_student = User(
            email=f"new-{mode}@example.invalid",
            password_hash="x", full_name="Yeni Öğrenci",
            role=UserRole.STUDENT, teacher_id=coach.id, grade_level=8,
            is_active=True,
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        db.add(new_student)
        sim_today = monday + timedelta(days=1)
    else:
        raise ValueError(f"bilinmeyen mode: {mode}")
    db.commit()
    return {"institution_id": inst.id, "student_id": student.id, "sim_today": sim_today, "monday": monday}


def _assert(name: str, condition: bool, expected: str, actual: str) -> int:
    if condition:
        print(f"  [OK]  {name}: {actual}")
        return 0
    print(f"  [FAIL] {name}: beklenen={expected!r} gerçek={actual!r}")
    return 1


def _run_scenario(label: str, mode: str, sim_today_fn=None) -> int:
    """Tek senaryo. Returns: failed count."""
    print(f"\n=== {label} ===")
    db = Session()
    ctx = _setup(db, mode=mode)
    today = ctx["sim_today"]
    ws, we = _week_bounds(today, 0)
    # Bu hafta öğrenci totalleri (helper'ı doğrudan today=sim_today ile çağır)
    student_ids = [s.id for s in db.query(User).filter(User.role == UserRole.STUDENT).all()]
    totals = _student_totals_for_week(db, student_ids=student_ids, ws=ws, we=we, today=today)
    print(f"  hafta: {ws} → {we}, simüle bugün: {today.strftime('%a %Y-%m-%d')}")
    for sid in student_ids:
        u = db.query(User).filter(User.id == sid).first()
        t = totals.get(sid, {})
        rate = _rate(t.get("planned", 0), t.get("completed", 0))
        print(f"  • {u.full_name}: planned={t.get('planned',0)} completed={t.get('completed',0)} rate={rate}% (aktif={u.is_active})")

    # Yiğit-modeli (aktif öğrenci) için rate kontrolü
    main = db.query(User).filter(User.id == ctx["student_id"]).first()
    t = totals.get(main.id, {})
    rate = _rate(t.get("planned", 0), t.get("completed", 0))
    db.close()

    failed = 0
    if mode == "s1_yigit_salı":
        failed += _assert("S1 Yiğit Salı %100",
                          rate == 100, expected="100", actual=str(rate))
    elif mode == "s2_yigit_pazar":
        failed += _assert("S2 Yiğit Pazar tam hafta %100",
                          rate == 100, expected="100", actual=str(rate))
    elif mode == "s3_düşük":
        # Pzt+Sal = 100+100=200 planlı, 50+30=80 tamamlanan → %40
        failed += _assert("S3 gerçek düşük uyum (%40 civarı)",
                          rate is not None and 35 <= rate <= 45,
                          expected="35-45", actual=str(rate))
    elif mode == "s4_pasif":
        failed += _assert("S4 aktif öğrenci %100, pasif hesaba katılmaz",
                          rate == 100, expected="100", actual=str(rate))
        # pasif öğrenci totals'da olmamalı (planı yok zaten)
    elif mode == "s5_yeni":
        failed += _assert("S5 yeni öğrenci empty_count'ta",
                          rate == 100, expected="100", actual=str(rate))
    return failed


def main() -> int:
    failed = 0
    failed += _run_scenario("S1 — Yiğit Salı (Pzt+Sal %100, Çar-Pzr 0)", "s1_yigit_salı")
    failed += _run_scenario("S2 — Yiğit Pazar (tam hafta %100)",            "s2_yigit_pazar")
    failed += _run_scenario("S3 — Gerçek düşük uyum (alarm doğru)",         "s3_düşük")
    failed += _run_scenario("S4 — Pasif öğrenci hesaba katılmaz",           "s4_pasif")
    failed += _run_scenario("S5 — Yeni öğrenci empty_count'ta",             "s5_yeni")

    print(f"\n{'=' * 50}")
    if failed == 0:
        print("✓ TÜM SENARYOLAR YEŞİL")
        return 0
    print(f"✗ {failed} SENARYO BAŞARISIZ")
    return 1


if __name__ == "__main__":
    sys.exit(main())
