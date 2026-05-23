"""Kapsamlı simülasyon — deneme bitti + 20 öğrenci: paywall + arşivleme + AI.

Gerçek koç 94 (demo.a@etutkoc.test, solo_free, 20 öğrenci, deneme bitti)
senaryosunu BİREBİR taklit eden geçici bir koçla test eder (gerçek hesabın
şifresine dokunulmaz — kırmızı çizgi).

TEST 1 — Süre bitiminde program hazırlama (paywall, 20 aktif öğrenci):
   1.1 publish-day            → 403 paywall_active
   1.2 bulk-tasks {tasks:[]}  → 403 paywall_active
   1.3 POST /tasks (gerçek kitap) → 403 paywall_active
   1.4 yeni öğrenci ekle      → 403 paywall_active (kota da aktif-koçluk sayar)
   1.5 durum: paywall=True, öğrenci=20

TEST 2 — 17 öğrenci arşivle + sonrası (3 aktif kalır):
   2.1 17 öğrenci pasifleştir (deactivate) → her biri 200
   2.2 durum: öğrenci=3, over_limit=False, paywall=False
   2.3 POST /tasks (kalan öğrenci, atanmış kitap) → 200  (program hazırlama DEVAM)
   2.4 publish-day → 200
   2.5 yeni öğrenci ekle (3→4 > 3) → 422 plan_quota_exceeded (kapı geçti, limit aktif)
   2.6 arşivlenmişi geri aç (3→4)  → 422 plan_quota_exceeded

TEST 3 — AI özellikleri (solo_free, deneme bitti → ai_premium=False):
   3.1 coaching-insight POST → 403 plan_upgrade_required
   3.2 parse-photo POST      → 403 plan_upgrade_required
   3.3 transcribe POST       → 403 plan_upgrade_required
   3.4 kitap-AI ünite önerisi (ai-suggest) → 403 plan_upgrade_required  [TUTARLILIK]
       (suggest_sections stub'lanır; gerçek Gemini çağrısı YOK)
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timezone

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
from app.models.task import Task
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"pwarc_{secrets.token_hex(3)}"
PWD = hash_password("PwArcTest!23")
PWDH = "PwArcTest!23"
now = datetime.now(timezone.utc)

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


def setup():
    with SessionLocal() as db:
        coach = User(
            email=f"{PFX}_coach@test.invalid", password_hash=PWD,
            full_name=f"{PFX} Koç", role=UserRole.TEACHER, institution_id=None,
            is_active=True, plan="solo_free", trial_ends_at=None,
            post_trial_plan="solo_free",
            password_changed_at=now, must_change_password=False)
        db.add(coach); db.flush()
        cid = coach.id

        students = []
        for i in range(20):
            s = User(
                email=f"{PFX}_s{i}@test.invalid", password_hash=PWD,
                full_name=f"{PFX} Öğr {i}", role=UserRole.STUDENT,
                teacher_id=cid, institution_id=None, grade_level=8,
                is_active=True, password_changed_at=now, must_change_password=False)
            db.add(s); students.append(s)
        db.flush()
        sids = [s.id for s in students]

        subj = Subject(
            name=f"{PFX} Matematik", order=0, is_builtin=False,
            teacher_id=cid, available_for_graduate=False,
            curriculum_model=CurriculumModel.LGS)
        db.add(subj); db.flush()

        book_full = Book(
            teacher_id=cid, subject_id=subj.id, name=f"{PFX} SB",
            publisher="Test Yay", type=BookType.SORU_BANKASI,
            target_graduate=False)
        db.add(book_full); db.flush()
        section = BookSection(book_id=book_full.id, label="Ünite 1", test_count=100, order=0)
        db.add(section); db.flush()

        # atanan kitap → ilk 3 öğrenci (arşivden sonra kalacaklar)
        for sid in sids[:3]:
            sb = StudentBook(student_id=sid, book_id=book_full.id)
            db.add(sb); db.flush()
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=section.id,
                                   reserved_count=0, completed_count=0))

        book_empty = Book(
            teacher_id=cid, subject_id=subj.id, name=f"{PFX} Boş Kitap",
            publisher="Test Yay", type=BookType.SORU_BANKASI,
            target_grade_min=8, target_grade_max=8, target_graduate=False)
        db.add(book_empty); db.flush()

        db.commit()
        ctx.update(coach_id=cid, student_ids=sids, subject_id=subj.id,
                   book_full_id=book_full.id, section_id=section.id,
                   book_empty_id=book_empty.id)


def login():
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_coach@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login: {r.status_code} {r.text}")
    return c


def status_of():
    from app.services import plans
    with SessionLocal() as db:
        coach = db.get(User, ctx["coach_id"])
        return plans.solo_trial_status(db, user=coach)


def main() -> int:
    print(f"\n=== KAPSAMLI: paywall + arşivleme + AI — {PFX} ===\n")
    get_login_limiter().reset()
    setup()
    sids = ctx["student_ids"]
    today = date.today().isoformat()
    bf, sec = ctx["book_full_id"], ctx["section_id"]
    try:
        c = login()

        # ── TEST 1 — Süre bitiminde program hazırlama (paywall) ──
        print("TEST 1 — Süre bitti, 20 öğrenci → program hazırlama ENGELLİ:")
        st = status_of()
        check("1.5 başlangıç durumu: paywall=True, 20 öğrenci",
              st["paywall"] is True and st["student_count"] == 20 and st["over_limit"] is True,
              f"{st}")

        r = c.post(f"/api/v2/teacher/students/{sids[0]}/publish-day", json={"task_date": today})
        check("1.1 publish-day → 403 paywall_active",
              r.status_code == 403 and _code(r) == "paywall_active", f"status={r.status_code} {r.text[:120]}")

        r = c.post(f"/api/v2/teacher/students/{sids[0]}/bulk-tasks", json={"tasks": []})
        check("1.2 bulk-tasks → 403 paywall_active",
              r.status_code == 403 and _code(r) == "paywall_active", f"status={r.status_code} {r.text[:120]}")

        r = c.post(f"/api/v2/teacher/students/{sids[0]}/tasks", json={
            "date": today, "type": "test", "title": "Deneme görevi",
            "items": [{"book_id": bf, "section_id": sec, "planned_count": 5}]})
        check("1.3 POST /tasks (gerçek kitap) → 403 paywall_active",
              r.status_code == 403 and _code(r) == "paywall_active", f"status={r.status_code} {r.text[:120]}")

        r = c.post("/api/v2/teacher/students", json={
            "full_name": "Yeni Öğrenci", "email": f"{PFX}_new@test.invalid", "grade_level": 8})
        check("1.4 yeni öğrenci ekle → 403 paywall_active",
              r.status_code == 403 and _code(r) == "paywall_active", f"status={r.status_code} {r.text[:120]}")

        # ── TEST 2 — 17 öğrenci arşivle + sonrası ──
        print("\nTEST 2 — 17 öğrenci arşivle (20→3) → program hazırlama DEVAM:")
        archived_ok = 0
        for sid in sids[3:]:   # 17 öğrenci (index 3..19)
            r = c.post(f"/api/v2/teacher/students/{sid}/deactivate")
            if r.status_code == 200:
                archived_ok += 1
        check("2.1 17 öğrenci pasifleştir → hepsi 200", archived_ok == 17, f"ok={archived_ok}/17")

        st = status_of()
        check("2.2 durum: 3 öğrenci, over_limit=False, paywall=False",
              st["student_count"] == 3 and st["over_limit"] is False and st["paywall"] is False, f"{st}")

        r = c.post(f"/api/v2/teacher/students/{sids[0]}/tasks", json={
            "date": today, "type": "test", "title": "Görev (arşiv sonrası)",
            "items": [{"book_id": bf, "section_id": sec, "planned_count": 5}]})
        check("2.3 POST /tasks (arşiv sonrası, atanmış kitap) → 200 (program DEVAM)",
              r.status_code == 200, f"status={r.status_code} {r.text[:160]}")

        r = c.post(f"/api/v2/teacher/students/{sids[1]}/publish-day", json={"task_date": today})
        check("2.4 publish-day → 200 (kapı geçti)", r.status_code == 200, f"status={r.status_code} {r.text[:120]}")

        r = c.post("/api/v2/teacher/students", json={
            "full_name": "Dördüncü Öğrenci", "email": f"{PFX}_n4@test.invalid", "grade_level": 8})
        check("2.5 yeni öğrenci (3→4 > 3) → 422 plan_quota_exceeded (limit aktif)",
              r.status_code == 422 and _code(r) == "plan_quota_exceeded", f"status={r.status_code} {r.text[:120]}")

        r = c.post(f"/api/v2/teacher/students/{sids[5]}/reactivate")
        check("2.6 arşivlenmişi geri aç (3→4) → 422 plan_quota_exceeded",
              r.status_code == 422 and _code(r) == "plan_quota_exceeded", f"status={r.status_code} {r.text[:120]}")

        # ── TEST 3 — AI özellikleri (deneme bitti → kapalı) ──
        print("\nTEST 3 — AI özellikleri (solo_free, deneme bitti → ücretli kapı):")
        r = c.post(f"/api/v2/teacher/students/{sids[0]}/coaching-insight")
        check("3.1 coaching-insight → 403 plan_upgrade_required",
              r.status_code == 403 and _code(r) == "plan_upgrade_required", f"status={r.status_code} {r.text[:120]}")

        r = c.post(f"/api/v2/teacher/students/{sids[0]}/sessions/parse-photo",
                   json={"image_base64": "AAAA", "media_type": "image/png"})
        check("3.2 parse-photo → 403 plan_upgrade_required",
              r.status_code == 403 and _code(r) == "plan_upgrade_required", f"status={r.status_code} {r.text[:120]}")

        r = c.post(f"/api/v2/teacher/students/{sids[0]}/sessions/transcribe",
                   json={"audio_base64": "AAAA", "media_type": "audio/webm"})
        check("3.3 transcribe → 403 plan_upgrade_required",
              r.status_code == 403 and _code(r) == "plan_upgrade_required", f"status={r.status_code} {r.text[:120]}")

        # 3.4 kitap-AI ünite önerisi — suggest_sections stub'lanır (gerçek Gemini YOK).
        # Beklenen TUTARLI davranış: ücretli kapıdan 403; AI çağrısına ulaşmamalı.
        orig_is_enabled = ff.is_enabled
        orig_suggest = abt.suggest_sections

        def _enabled_stub(*a, **k):
            return True

        def _suggest_stub(*a, **k):
            raise abt.AIServiceUnavailable("STUB — bu noktaya ulaşılmamalıydı")

        ff.is_enabled = _enabled_stub
        abt.suggest_sections = _suggest_stub
        try:
            r = c.post(f"/api/v2/teacher/library/books/{ctx['book_empty_id']}/ai-suggest", json={})
        finally:
            ff.is_enabled = orig_is_enabled
            abt.suggest_sections = orig_suggest
        check("3.4 kitap-AI ünite önerisi → 403 plan_upgrade_required (tutarlı)",
              r.status_code == 403 and _code(r) == "plan_upgrade_required",
              f"status={r.status_code} code={_code(r)} {r.text[:160]}")

    finally:
        with SessionLocal() as db:
            sids_all = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if sids_all:
                sbids = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(sids_all)).all()]
                if sbids:
                    db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbids)))
                db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(sids_all)))
                tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(sids_all)).all()]
                if tids:
                    from app.models.task import TaskBookItem
                    db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
                    db.execute(sa_delete(Task).where(Task.id.in_(tids)))
            bids = [r[0] for r in db.query(Book.id).filter(Book.teacher_id == ctx.get("coach_id")).all()]
            if bids:
                db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(bids)))
                db.execute(sa_delete(Book).where(Book.id.in_(bids)))
            if ctx.get("subject_id"):
                db.execute(sa_delete(Subject).where(Subject.id == ctx["subject_id"]))
            cid = ctx.get("coach_id")
            if cid:
                db.execute(sa_delete(UsageEvent).where(UsageEvent.owner_id == cid))
                db.execute(sa_delete(CreditAccount).where(CreditAccount.owner_id == cid))
            if sids_all:
                db.execute(sa_delete(User).where(User.id.in_(sids_all)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
