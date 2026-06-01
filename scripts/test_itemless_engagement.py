"""İtemless (Diğer/etkinlik) görevlerin ENGAGEMENT hesaplarına doğru dahil edilmesi.

Bug (kullanıcı 2026-06-01): etkinlik görevi (kalemsiz / soru sayısı 0) tamamlandığında
soru-bazlı hesaplar bunu GÖRMÜYORDU → "bugün hiç tik yapmadı" / "üst üste boş gün" /
"programsız" / istikrar=0 yanlış-pozitifleri (Elvin: 1 OTHER görev COMPLETED ama
"bugün tik yapmadı").

İlke: ENGAGEMENT (tik yaptı mı / aktif gün / boş gün / programı var mı) = görev
tamamlama (status COMPLETED veya completed_count>0), ETKİNLİK DAHİL. TEST HACMİ
(soru/test sayısı, hız test/gün) soru-only KALIR — etkinlik fake sayı eklemez.

Doğrudan analytics/risk_analysis fonksiyonlarını sınar (HTTP yok, deterministik).
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import User, UserRole
from app.models.task import Task, TaskBookItem, TaskType, TaskStatus
from app.services.security import hash_password
from app.services import analytics, risk_analysis

PFX = "itleng_" + secrets.token_hex(3)
PWD = "ItlEng!2345"
now = datetime.now(timezone.utc)
today = date.today()
passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def mk_student(db, idx, age_days=10):
    s = User(
        email=f"{PFX}_{idx}@t.invalid", password_hash=hash_password(PWD),
        full_name=f"Ogr {idx}", role=UserRole.STUDENT, grade_level=8, is_active=True,
        must_change_password=False, password_changed_at=now,
        created_at=now - timedelta(days=age_days), last_login_at=now,
    )
    db.add(s)
    db.flush()
    return s


def add_numeric_task(db, sid, d, planned, completed=0, status=TaskStatus.PENDING):
    """Soru-sayılı görev (kitapsız deneme kalemi ile — gerçek kitap gerekmez)."""
    t = Task(student_id=sid, date=d, type=TaskType.OTHER, status=status,
             title="Deneme", is_draft=False)
    if status == TaskStatus.COMPLETED:
        t.completed_at = now
    db.add(t)
    db.flush()
    db.add(TaskBookItem(
        task_id=t.id, book_id=None, book_section_id=None,
        label="Deneme", planned_count=planned, completed_count=completed,
    ))
    db.flush()
    return t


def add_activity_task(db, sid, d, status=TaskStatus.COMPLETED):
    """Kalemsiz etkinlik görevi (Diğer/Video/...) — soru sayısı yok."""
    t = Task(student_id=sid, date=d, type=TaskType.OTHER, status=status,
             title="Mebi Deneme izle", is_draft=False)
    if status == TaskStatus.COMPLETED:
        t.completed_at = now
    db.add(t)
    db.flush()
    return t


def codes(warnings):
    return {w.code for w in warnings}


def risk_codes(db, s):
    a = risk_analysis.compute_risk_score(db=db, student=s, today=today, now=now)
    return {i.code for i in a.indicators}


def main() -> int:
    print(f"\n=== İTEMLESS ENGAGEMENT — {PFX} ===\n")
    ids = []
    try:
        with SessionLocal() as db:
            # S1 — kontrol: bugün soru-planı var, hiç tamamlama yok → today_no_tick FIRES
            s1 = mk_student(db, 1)
            add_numeric_task(db, s1.id, today, planned=10)
            # S2 — FIX: soru-planı + tamamlanmış ETKİNLİK görevi → today_no_tick YOK
            s2 = mk_student(db, 2)
            add_numeric_task(db, s2.id, today, planned=10)
            add_activity_task(db, s2.id, today, status=TaskStatus.COMPLETED)
            # S3 — FIX: hafta yalnız etkinlik görevi (soru yok) → no_program/consecutive YOK
            s3 = mk_student(db, 3)
            add_activity_task(db, s3.id, today, status=TaskStatus.COMPLETED)
            # S4 — kontrol: hiç görev yok → no_program FIRES
            s4 = mk_student(db, 4)
            # S5 — FIX: bugün soru-planı + tamamlanmış etkinlik → consecutive_empty YOK
            s5 = mk_student(db, 5)
            add_numeric_task(db, s5.id, today, planned=10)
            add_numeric_task(db, s5.id, today - timedelta(days=1), planned=10)
            add_numeric_task(db, s5.id, today - timedelta(days=2), planned=10)
            add_activity_task(db, s5.id, today, status=TaskStatus.COMPLETED)
            # S6 — volume sanity: soru tamamlandı → rate_7d > 0 (test hacmi sayar)
            s6 = mk_student(db, 6)
            add_numeric_task(db, s6.id, today, planned=10, completed=8, status=TaskStatus.COMPLETED)
            db.commit()
            ids = [s.id for s in (s1, s2, s3, s4, s5, s6)]

            # --- S1 kontrol ---
            w1 = codes(analytics.student_snapshot(db, s1, today=today).warnings)
            chk("S1 kontrol: plan var + tamamlama yok → 'today_no_tick' VAR",
                "today_no_tick" in w1, str(w1))

            # --- S2 fix ---
            snap2 = analytics.student_snapshot(db, s2, today=today)
            w2 = codes(snap2.warnings)
            chk("S2 FIX: etkinlik tamamlandı → 'today_no_tick' YOK",
                "today_no_tick" not in w2, str(w2))
            chk("S2 FIX: istikrar (consistency_7d) > 0 (bugün aktif)",
                snap2.consistency_7d > 0, f"consistency={snap2.consistency_7d}")
            chk("S2 VOLUME: rate_7d == 0 (etkinlik test hacmine sayılmaz)",
                abs(snap2.rate_7d) < 1e-9, f"rate_7d={snap2.rate_7d}")

            # --- S3 fix ---
            r3 = risk_codes(db, s3)
            chk("S3 FIX: etkinlik-only hafta → 'no_program' YOK (görev var)",
                "no_program" not in r3, str(r3))
            chk("S3 FIX: etkinlik-only hafta → 'consecutive_empty' YOK",
                "consecutive_empty" not in r3, str(r3))
            chk("S3 FIX: etkinlik tamamlanan sağlıklı öğrenci → risk göstergesi YOK",
                len(r3) == 0, str(r3))

            # --- S4 kontrol ---
            r4 = risk_codes(db, s4)
            chk("S4 kontrol: hiç görev yok → 'no_program' VAR (gösterge hâlâ çalışıyor)",
                "no_program" in r4, str(r4))

            # --- S5 fix ---
            r5 = risk_codes(db, s5)
            chk("S5 FIX: bugün etkinlik tamamlandı → 'consecutive_empty' YOK",
                "consecutive_empty" not in r5, str(r5))

            # --- S6 volume sanity ---
            snap6 = analytics.student_snapshot(db, s6, today=today)
            chk("S6 VOLUME: soru tamamlandı → rate_7d > 0 (test/gün sayar)",
                snap6.rate_7d > 0, f"rate_7d={snap6.rate_7d}")
    finally:
        with SessionLocal() as db:
            if ids:
                task_ids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(ids)).all()]
                if task_ids:
                    db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(task_ids)))
                    db.execute(sa_delete(Task).where(Task.id.in_(task_ids)))
                db.execute(sa_delete(User).where(User.id.in_(ids)))
                db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
