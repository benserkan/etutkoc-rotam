"""Abonelik iptal akışı + aktifken AI — kapsamlı test.

Kullanıcının soruları:
  - İptal edince ne olur? Sonraki yenilemeye kadar kullanmaya devam eder mi,
    o tarihte mi ücretsize/pasif duruma düşer?
  - Abonelik aktifken AI vb. özellikleri serbestçe kullanabilir mi?

AI çağrıları STUB'lanır (gerçek Gemini YOK): ai-suggest için suggest_sections
AIServiceUnavailable fırlatır → kapı AÇIKSA 502 (AI'ya ulaştı, rollback), kapı
KAPALIYSA 403 plan_upgrade_required. Böylece "AI kullanılabilir mi" net ölçülür.

Senaryo CANCEL (solo_pro, dönem sonu now+10g, 5 öğrenci > 3):
  AKTİF:        ai_premium=True · paywall=False · ai-suggest 502 · /tasks 200
  İPTAL (dönem içi): status=canceled · plan hâlâ solo_pro · ai_premium=True ·
                paywall=False · /tasks 200 · ai-suggest 502  (erişim SÜRER)
  CRON dönem-öncesi: canceled_dropped=0 (hiçbir şey değişmez)
  CRON dönem-sonrası: canceled → solo_free + sub alanları temizlenir ·
                ai_premium=False · paywall=True · ai-suggest 403 · /tasks 403
Senaryo RESUME (iptali geri al): canceled → resume → active, erişim sürer.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

import app.services.ai_book_template as abt
import app.services.feature_flags as ff
from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    CreditAccount,
    Subject,
    UsageEvent,
    User,
    UserRole,
)
from app.models.book import BookType
from app.models.curriculum import CurriculumModel
from app.models.progress import SectionProgress, StudentBook
from app.models.suspicious_ip import SuspiciousIp
from app.models.task import Task, TaskBookItem
from app.services import plans, trial_notifications
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"cancel_{secrets.token_hex(3)}"
PWD = hash_password("CancelTest!23")
PWDH = "CancelTest!23"
now = datetime.now(timezone.utc)
PERIOD_END = now + timedelta(days=10)

passed = 0
failed: list[str] = []
ctx: dict = {}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _code(r):
    try:
        return (r.json().get("detail", {}) or {}).get("code")
    except Exception:
        return None


def _ai_premium(coach_id):
    with SessionLocal() as db:
        return plans.ai_premium_allowed(db, db.get(User, coach_id))


def _paywall(coach_id):
    with SessionLocal() as db:
        return plans.solo_trial_status(db, user=db.get(User, coach_id))["paywall"]


def _plan_status(coach_id):
    with SessionLocal() as db:
        u = db.get(User, coach_id)
        return u.plan, u.subscription_status


def login(suffix):
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{suffix}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {suffix}: {r.status_code} {r.text}")
    return c


def _ai_probe(client, book_empty_id):
    """ai-suggest'i stub'la çağır: kapı açıksa 502, kapalıysa 403."""
    o_en, o_sg = ff.is_enabled, abt.suggest_sections
    ff.is_enabled = lambda *a, **k: True

    def _raise(*a, **k):
        raise abt.AIServiceUnavailable("STUB")

    abt.suggest_sections = _raise
    try:
        return client.post(f"/api/v2/teacher/library/books/{book_empty_id}/ai-suggest", json={})
    finally:
        ff.is_enabled, abt.suggest_sections = o_en, o_sg


def setup():
    with SessionLocal() as db:
        def coach(suffix):
            u = User(
                email=f"{PFX}_{suffix}@test.invalid", password_hash=PWD,
                full_name=f"{PFX} {suffix}", role=UserRole.TEACHER, institution_id=None,
                is_active=True, plan="solo_pro", trial_ends_at=None,
                subscription_status="active", subscription_cycle="monthly",
                subscription_period_end=PERIOD_END,
                ai_capture_consent_at=now,
                password_changed_at=now, must_change_password=False)
            db.add(u); db.flush()
            return u

        c1 = coach("c1")
        c2 = coach("c2")
        # 5 öğrenci (>3) → düşünce paywall
        for cobj in (c1, c2):
            for i in range(5):
                db.add(User(
                    email=f"{PFX}_{cobj.id}_s{i}@test.invalid", password_hash=PWD,
                    full_name=f"{PFX} Öğr {cobj.id}-{i}", role=UserRole.STUDENT,
                    teacher_id=cobj.id, institution_id=None, grade_level=8,
                    is_active=True, password_changed_at=now, must_change_password=False))
        db.flush()

        subj = Subject(name=f"{PFX} Mat", order=0, is_builtin=False, teacher_id=c1.id,
                       available_for_graduate=False, curriculum_model=CurriculumModel.LGS)
        db.add(subj); db.flush()
        book = Book(teacher_id=c1.id, subject_id=subj.id, name=f"{PFX} SB",
                    publisher="T", type=BookType.SORU_BANKASI, target_graduate=False)
        db.add(book); db.flush()
        section = BookSection(book_id=book.id, label="Ünite 1", test_count=100, order=0)
        db.add(section); db.flush()
        s0 = db.query(User).filter(User.teacher_id == c1.id, User.role == UserRole.STUDENT).first()
        sb = StudentBook(student_id=s0.id, book_id=book.id)
        db.add(sb); db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=section.id,
                               reserved_count=0, completed_count=0))
        book_empty = Book(teacher_id=c1.id, subject_id=subj.id, name=f"{PFX} Boş",
                          publisher="T", type=BookType.SORU_BANKASI,
                          target_grade_min=8, target_grade_max=8, target_graduate=False)
        db.add(book_empty); db.flush()
        db.commit()
        ctx.update(c1=c1.id, c2=c2.id, subject_id=subj.id, book_id=book.id,
                   section_id=section.id, student0=s0.id, book_empty_id=book_empty.id)


def main() -> int:
    print(f"\n=== ABONELİK İPTAL AKIŞI + AKTİFKEN AI — {PFX} ===\n")
    get_login_limiter().reset()
    setup()
    c1, c2 = ctx["c1"], ctx["c2"]
    bf, sec, s0, be = ctx["book_id"], ctx["section_id"], ctx["student0"], ctx["book_empty_id"]
    today = date.today().isoformat()
    try:
        cli = login("c1")

        # ── AKTİF ──
        print("AKTİF abonelik (solo_pro, active):")
        check("A1 ai_premium=True (AI açık)", _ai_premium(c1) is True)
        check("A2 paywall=False", _paywall(c1) is False)
        r = _ai_probe(cli, be)
        check("A3 ai-suggest → 502 (AI kapısı AÇIK, AI'ya ulaştı)",
              r.status_code == 502 and _code(r) == "ai_provider_error", f"status={r.status_code} {r.text[:120]}")
        r = cli.post(f"/api/v2/teacher/students/{s0}/tasks", json={
            "date": today, "type": "test", "title": "G", "items": [{"book_id": bf, "section_id": sec, "planned_count": 3}]})
        check("A4 POST /tasks → 200 (program serbest)", r.status_code == 200, f"status={r.status_code} {r.text[:120]}")

        # ── İPTAL (dönem içi) ──
        print("\nİPTAL (dönem sonuna 10 gün var):")
        r = cli.post("/api/v2/teacher/subscription/cancel")
        check("B1 cancel → 200 + status=canceled", r.status_code == 200 and _plan_status(c1)[1] == "canceled",
              f"status={r.status_code} st={_plan_status(c1)}")
        check("B2 plan hâlâ solo_pro (düşmedi)", _plan_status(c1)[0] == "solo_pro", f"{_plan_status(c1)}")
        check("B3 ai_premium hâlâ True (erişim SÜRER)", _ai_premium(c1) is True)
        check("B4 paywall=False (dönem sonuna kadar)", _paywall(c1) is False)
        r = cli.post(f"/api/v2/teacher/students/{s0}/tasks", json={
            "date": today, "type": "test", "title": "G2", "items": [{"book_id": bf, "section_id": sec, "planned_count": 2}]})
        check("B5 POST /tasks → 200 (iptalden sonra da erişim sürüyor)", r.status_code == 200, f"status={r.status_code}")
        r = _ai_probe(cli, be)
        check("B6 ai-suggest → 502 (AI hâlâ açık)", r.status_code == 502, f"status={r.status_code}")

        # ── CRON dönem-öncesi ──
        # GÜVENLİK: cron global çalışır → diğer (demo/gerçek) koçları etkilememek
        # için DAİMA gerçek `now` ile çalıştırılır; hedef koçun period_end'i geçmişe
        # alınarak izole edilir (mevcut renewal smoke deseni). Gelecek `now` YASAK.
        print("\nCRON (dönem sonu HENÜZ gelmedi):")
        with SessionLocal() as db:
            res = trial_notifications.process_renewals(db, now=now)
        check("C1 canceled_dropped=0 (hiçbir şey değişmez)", res.get("canceled_dropped", 0) == 0, f"{res}")
        check("C2 hâlâ canceled + solo_pro", _plan_status(c1) == ("solo_pro", "canceled"), f"{_plan_status(c1)}")

        # ── CRON dönem-sonrası ──
        print("\nCRON (dönem sonu GEÇTİ → ücretsize düşer):")
        with SessionLocal() as db:
            db.get(User, c1).subscription_period_end = now - timedelta(days=1)
            db.commit()
        with SessionLocal() as db:
            res = trial_notifications.process_renewals(db, now=now)
        check("D1 canceled_dropped≥1", res.get("canceled_dropped", 0) >= 1, f"{res}")
        check("D2 plan=solo_free + status temizlendi (None)", _plan_status(c1) == ("solo_free", None), f"{_plan_status(c1)}")
        check("D3 ai_premium=False (AI KAPANDI)", _ai_premium(c1) is False)
        check("D4 paywall=True (5 öğr > 3)", _paywall(c1) is True)
        r = _ai_probe(cli, be)
        check("D5 ai-suggest → 403 plan_upgrade_required (AI engellendi)",
              r.status_code == 403 and _code(r) == "plan_upgrade_required", f"status={r.status_code} {r.text[:120]}")
        r = cli.post(f"/api/v2/teacher/students/{s0}/tasks", json={
            "date": today, "type": "test", "title": "G3", "items": [{"book_id": bf, "section_id": sec, "planned_count": 1}]})
        check("D6 POST /tasks → 403 paywall_active (program engellendi)",
              r.status_code == 403 and _code(r) == "paywall_active", f"status={r.status_code} {r.text[:120]}")
        check("D7 öğrenciler hâlâ AKTİF (otomatik pasifleşmedi)",
              plans.count_solo_students(SessionLocal(), teacher_id=c1) == 5,
              f"aktif={plans.count_solo_students(SessionLocal(), teacher_id=c1)}")

        # ── RESUME (iptali geri al) ──
        print("\nRESUME (iptal → geri al):")
        cli2 = login("c2")
        r = cli2.post("/api/v2/teacher/subscription/cancel")
        check("E1 c2 cancel → canceled", r.status_code == 200 and _plan_status(c2)[1] == "canceled", f"{_plan_status(c2)}")
        r = cli2.post("/api/v2/teacher/subscription/resume")
        check("E2 c2 resume → active", r.status_code == 200 and _plan_status(c2)[1] == "active", f"{_plan_status(c2)}")
        check("E3 c2 ai_premium=True + paywall=False (erişim sürer)",
              _ai_premium(c2) is True and _paywall(c2) is False)
        # resume sonrası dönem içi cron'da DÜŞMEZ (period_end hâlâ +10g → gerçek now'da yakalanmaz).
        with SessionLocal() as db:
            trial_notifications.process_renewals(db, now=now)
        check("E4 cron (dönem içi) → c2 hâlâ active", _plan_status(c2) == ("solo_pro", "active"), f"{_plan_status(c2)}")

    finally:
        with SessionLocal() as db:
            ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if ids:
                sbids = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(ids)).all()]
                if sbids:
                    db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbids)))
                db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(ids)))
                tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(ids)).all()]
                if tids:
                    db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
                    db.execute(sa_delete(Task).where(Task.id.in_(tids)))
                db.execute(sa_delete(UsageEvent).where(UsageEvent.owner_id.in_(ids)))
                db.execute(sa_delete(CreditAccount).where(CreditAccount.owner_id.in_(ids)))
            bids = [r[0] for r in db.query(Book.id).filter(Book.teacher_id == ctx.get("c1")).all()]
            if bids:
                db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(bids)))
                db.execute(sa_delete(Book).where(Book.id.in_(bids)))
            if ctx.get("subject_id"):
                db.execute(sa_delete(Subject).where(Subject.id == ctx["subject_id"]))
            if ids:
                db.execute(sa_delete(User).where(User.id.in_(ids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
