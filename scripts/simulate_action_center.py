"""Müdahale Merkezi (institution_action_center) DOĞRULAMA simülasyonu.

Soru (kullanıcı 2026-05-24): kart değerleri (KRİTİK/UYARI/TOPLAM) doğru veriyi
gösteriyor mu? Sağlıklıyken 0 mı, kötü koşullarda doğru şiddetle artıyor mu?

Yaklaşım: tek temp kurum + koç; her senaryoda öğrenci/görev kurup
compute_action_center'ı DOĞRUDAN çağırır, summary + item kategorisi/şiddetini
doğrular, sonra temizler. Görev hacmi için kitapsız "deneme" kalemi kullanılır
(kitap kurmaya gerek yok; compliance planned/completed'i sayar).

Eşikler: boş program ≥3 kritik / 1-2 uyarı · uyum <%25 kritik / <%40 uyarı ·
risk critical→kritik / high→uyarı.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import Institution, Task, TaskBookItem, TaskStatus, TaskType, User, UserRole
from app.models.audit_log import AuditLog
from app.services.institution_action_center import compute_action_center

PFX = "ac_" + secrets.token_hex(3)
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


def make_student(db, tid, iid, *, age_days: int, last_login_days, suffix: str) -> int:
    """Öğrenci oluştur. last_login_days None → hiç giriş yok.
    GERÇEK akıştaki gibi institution_id set edilir (koç öğrenci yaratınca
    institution_id=teacher.institution_id — teacher.py:4215)."""
    created = now - timedelta(days=age_days)
    ll = None if last_login_days is None else now - timedelta(days=last_login_days)
    s = User(
        email=f"{PFX}_{suffix}@t.invalid", password_hash="x", full_name=f"Ogr {suffix}",
        role=UserRole.STUDENT, teacher_id=tid, institution_id=iid, grade_level=8,
        is_active=True, created_at=created, last_login_at=ll,
        password_changed_at=now, must_change_password=False,
    )
    db.add(s); db.flush()
    return s.id


def add_program(db, sid, *, planned: int, completed: int, d: date | None = None):
    """Yayınlanmış görev + kitapsız kalem (planned/completed). d verilmezse bugün."""
    t = Task(student_id=sid, date=d or today, type=TaskType.OTHER, title="Sim Program",
             status=TaskStatus.PENDING, order=0, is_draft=False, published_at=now)
    db.add(t); db.flush()
    db.add(TaskBookItem(task_id=t.id, book_id=None, book_section_id=None,
                        label="Sim", planned_count=planned, completed_count=completed))
    db.flush()


def clear_students(db, iid, tid):
    sids = [r[0] for r in db.query(User.id).filter(User.teacher_id == tid, User.role == UserRole.STUDENT).all()]
    if sids:
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(
            db.query(Task.id).filter(Task.student_id.in_(sids)).subquery().select())))
        db.execute(sa_delete(Task).where(Task.student_id.in_(sids)))
        db.execute(sa_delete(User).where(User.id.in_(sids)))
    db.commit()


def summary(db, iid):
    return compute_action_center(db, institution_id=iid)


def items_of(res, category=None, severity=None):
    return [
        i for i in res["items"]
        if (category is None or i["category"] == category)
        and (severity is None or i["severity"] == severity)
    ]


def main() -> int:
    print(f"\n=== MÜDAHALE MERKEZİ DOĞRULAMA — {PFX} ===\n")
    with SessionLocal() as db:
        inst = Institution(name=PFX, slug=PFX, plan="etut_standart", is_active=True)
        db.add(inst); db.flush()
        iid = inst.id
        coach = User(email=f"{PFX}_c@t.invalid", password_hash="x", full_name="Koc Ali",
                     role=UserRole.TEACHER, institution_id=iid, is_active=True,
                     password_changed_at=now, must_change_password=False)
        db.add(coach); db.commit()
        tid = coach.id

    try:
        with SessionLocal() as db:
            # 0) BASELINE — hiç öğrenci yok → her şey 0
            r = summary(db, iid)
            chk("0. Boş kurum → KRİTİK=0 UYARI=0 TOPLAM=0",
                r["summary"]["critical"] == 0 and r["summary"]["warn"] == 0 and r["summary"]["total"] == 0,
                str(r["summary"]))

            # 1) SAĞLIKLI öğrenci (eski hesap + yakın giriş + iyi program) → 0
            sid = make_student(db, tid, iid, age_days=30, last_login_days=0, suffix="healthy")
            add_program(db, sid, planned=10, completed=9)  # %90
            db.commit()
            r = summary(db, iid)
            chk("1. Sağlıklı öğrenci → TOPLAM=0 (boş yok / uyum yüksek / risk yok)",
                r["summary"]["total"] == 0, str(r["summary"]) + " " + str([i["title"] for i in r["items"]]))
            clear_students(db, iid, tid)

        with SessionLocal() as db:
            # 2) BOŞ PROGRAM — 2 öğrenci (hesap 3g, grace dışı) programsız → UYARI
            #    + 1 YENİ öğrenci (hesap 0g, grace içinde) → SAYILMAZ.
            for i in range(2):
                make_student(db, tid, iid, age_days=3, last_login_days=0, suffix=f"empty2_{i}")
            make_student(db, tid, iid, age_days=0, last_login_days=0, suffix="empty2_new")
            db.commit()
            r = summary(db, iid)
            ep = items_of(r, category="empty_program")
            chk("2. 2 programsız(3g) + 1 yeni(grace) → empty_program UYARI count=2 (yeni sayılmaz)",
                len(ep) == 1 and ep[0]["severity"] == "warn" and ep[0]["count"] == 2, str(r["summary"]) + " " + str(ep))
            chk("2b. boş-program onboarding grace: yeni öğrenci empty/at_risk üretmez",
                len(items_of(r, category="at_risk")) == 0, str(items_of(r, category="at_risk")))
            clear_students(db, iid, tid)

        with SessionLocal() as db:
            # 3) BOŞ PROGRAM — 3 öğrenci (hesap 3g, grace dışı) programsız → KRİTİK
            for i in range(3):
                make_student(db, tid, iid, age_days=3, last_login_days=0, suffix=f"empty3_{i}")
            db.commit()
            r = summary(db, iid)
            ep = items_of(r, category="empty_program", severity="critical")
            chk("3. 3 boş program → empty_program KRİTİK (count=3)",
                len(ep) == 1 and ep[0]["count"] == 3, str(r["summary"]) + " " + str(items_of(r, category="empty_program")))
            chk("3b. KRİTİK sayacı ≥1", r["summary"]["critical"] >= 1, str(r["summary"]))
            clear_students(db, iid, tid)

        with SessionLocal() as db:
            # 4) DÜŞÜK UYUM — program var ama %10 (yakın giriş, eski hesap) → KRİTİK
            sid = make_student(db, tid, iid, age_days=30, last_login_days=0, suffix="low_crit")
            add_program(db, sid, planned=100, completed=10)  # %10 < 25
            db.commit()
            r = summary(db, iid)
            lc = items_of(r, category="low_compliance", severity="critical")
            chk("4. uyum %10 → low_compliance KRİTİK", len(lc) == 1, str([(i["category"], i["severity"], i["title"]) for i in r["items"]]))
            clear_students(db, iid, tid)

        with SessionLocal() as db:
            # 5) DÜŞÜK UYUM — %30 (25-40 arası) → UYARI
            sid = make_student(db, tid, iid, age_days=30, last_login_days=0, suffix="low_warn")
            add_program(db, sid, planned=100, completed=30)  # %30
            db.commit()
            r = summary(db, iid)
            lc = items_of(r, category="low_compliance")
            chk("5. uyum %30 → low_compliance UYARI", len(lc) == 1 and lc[0]["severity"] == "warn", str([(i["category"], i["severity"]) for i in r["items"]]))
            clear_students(db, iid, tid)

        with SessionLocal() as db:
            # 6) RİSKLİ (high) — eski hesap + HİÇ giriş yok (25) + düşük tamamlama (30)
            # + 3 gün üst üste boş (20) = skor ~75 → "Risk" (high) → at_risk fire eder.
            sid = make_student(db, tid, iid, age_days=25, last_login_days=None, suffix="risk")
            for off in (0, 1, 2):
                add_program(db, sid, planned=20, completed=0, d=today - timedelta(days=off))
            db.commit()
            r = summary(db, iid)
            ar = items_of(r, category="at_risk")
            chk("6. eski+giriş yok+düşük tamamlama+boş günler → at_risk (high/critical) fire etti",
                len(ar) >= 1, str([(i["category"], i["severity"], i["title"]) for i in r["items"]]))
            clear_students(db, iid, tid)

        with SessionLocal() as db:
            # 6c) PROGRAMI VAR AMA YAPMIYOR (medium) — giriş bugün (no_login YOK) +
            # erken günler tamamlandı (haftalık uyum ≥%40 → low_completion YOK) +
            # son 3 gün boş → consecutive_empty (20) = medium. Eskiden high eşiğine
            # düşmediği için GÖRÜNMÜYORDU; artık inactive_program UYARI fire eder.
            sid = make_student(db, tid, iid, age_days=30, last_login_days=0, suffix="inactive_med")
            for off in (6, 5, 4, 3):  # aktif günler (completed>0)
                add_program(db, sid, planned=10, completed=10, d=today - timedelta(days=off))
            for off in (2, 1, 0):     # son 3 gün boş
                add_program(db, sid, planned=10, completed=0, d=today - timedelta(days=off))
            db.commit()
            r = summary(db, iid)
            inact = items_of(r, category="inactive_program")
            atr = items_of(r, category="at_risk")
            chk("6c. programı var + 3 gün boş (medium) → inactive_program UYARI (eskiden 0)",
                len(inact) == 1 and inact[0]["severity"] == "warn" and len(atr) == 0,
                str([(i["category"], i["severity"], i["title"]) for i in r["items"]]))
            clear_students(db, iid, tid)

        with SessionLocal() as db:
            # 7) SON: temizlikten sonra tekrar 0 (değerler GERÇEKTEN duruma bağlı)
            r = summary(db, iid)
            chk("7. temizlik sonrası tekrar TOPLAM=0 (değerler duruma bağlı, sabit değil)",
                r["summary"]["total"] == 0, str(r["summary"]))

    finally:
        with SessionLocal() as db:
            sids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if sids:
                db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(
                    db.query(Task.id).filter(Task.student_id.in_(sids)).subquery().select())))
                db.execute(sa_delete(Task).where(Task.student_id.in_(sids)))
                db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(sids)))
                db.execute(sa_delete(User).where(User.id.in_(sids)))
            db.execute(sa_delete(Institution).where(Institution.slug == PFX))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
