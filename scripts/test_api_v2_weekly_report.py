# -*- coding: utf-8 -*-
"""API v2 haftalık koç raporu smoke (2026-08-19).

Senaryolar:
   1. Anonim → 401
   2. POST create (pencere otomatik) → 200 + hafta = programın işlendiği son güne göre
   3. Rapor listesi → 1 satır + agenda_count > 0
   4. GET detay → kural motoru gündemi (summary + zayıf konu + bekleyen mesaj kuralları)
   5. GET html → 200 + öğrenci adı + "Seans gündemi" bölümü
   6. Aynı hafta yeniden üret → version 2
   7. Yabancı koç rapor GET → 404 (sahiplik)
   8. week_end verilerek üretim → pencere doğru
   9. invalid days → 422
  10. Seans create report_id + agenda_items → row'da döner; rapor satırında session_count=1
  11. Yabancı rapor id ile seans → 422 report_mismatch
  12. prefill → latest_report_id + latest_report_agenda dolu
  13. AI gündem (monkeypatch) → detail.ai_agenda dolu + has_ai_agenda + ikinci GET ücretsiz cache
  14. KS4 içgörü prompt'una weekly_report paketi giriyor (monkeypatch ile yakala)
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, BookType, CoachingReport, CoachingSession, SectionProgress,
    StudentBook, Task, TaskBookItem, TaskRequest, TaskStatus, TaskType, Subject, User, UserRole,
)
from app.models.task_request import RequestStatus, RequestType
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2wrep{secrets.token_hex(3)}"
T_EMAIL = f"{PFX}_t@test.invalid"
T2_EMAIL = f"{PFX}_t2@test.invalid"
PASSWORD = "WrepPass1!@xyz"

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed():
    pwd = hash_password(PASSWORD)
    today = date.today()
    with SessionLocal() as db:
        t = User(email=T_EMAIL, password_hash=pwd, full_name=f"{PFX} Koç",
                 role=UserRole.TEACHER, is_active=True, plan="solo_pro",
                 subscription_status="active")
        t2 = User(email=T2_EMAIL, password_hash=pwd, full_name=f"{PFX} Koç2",
                  role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add_all([t, t2]); db.flush()
        s = User(email=f"{PFX}_s@test.invalid", password_hash=pwd, full_name=f"{PFX} Öğrenci",
                 role=UserRole.STUDENT, is_active=True, grade_level=12, teacher_id=t.id)
        db.add(s); db.flush()
        subj = Subject(name=f"{PFX} Matematik", teacher_id=t.id)
        db.add(subj); db.flush()
        b = Book(name=f"{PFX} Soru Bankası", type=BookType.SORU_BANKASI,
                 teacher_id=t.id, subject_id=subj.id)
        db.add(b); db.flush()
        sec = BookSection(book_id=b.id, label=f"{PFX} Konu A", test_count=20)
        db.add(sec); db.flush()
        sb = StudentBook(student_id=s.id, book_id=b.id)
        db.add(sb); db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                               completed_count=6, reserved_count=0))
        # görevler: 3 gün önce tamam (D/Y'li), 2 gün önce tamam (düşük doğruluk), dün yapılmadı
        def mk_task(d, done, correct, wrong, planned=3):
            tk = Task(student_id=s.id, date=d, type=TaskType.TEST,
                      title=f"{PFX} SB — Konu A: {planned} test",
                      status=TaskStatus.COMPLETED if done else TaskStatus.PENDING,
                      is_draft=False)
            db.add(tk); db.flush()
            db.add(TaskBookItem(task_id=tk.id, book_id=b.id, book_section_id=sec.id,
                                planned_count=planned,
                                completed_count=planned if done else 0,
                                correct_count=correct, wrong_count=wrong))
            return tk
        mk_task(today - timedelta(days=3), True, 25, 2)
        mk_task(today - timedelta(days=2), True, 12, 12)   # %50 doğruluk → zayıf konu kuralı
        mk_task(today - timedelta(days=1), False, None, None)
        # bekleyen öğrenci mesajı → kural 7
        db.add(TaskRequest(student_id=s.id, teacher_id=t.id, type=RequestType.QUESTION,
                           status=RequestStatus.PENDING,
                           message=f"{PFX} hocam bu kitap bitti"))
        out = {"t_id": t.id, "t2_id": t2.id, "s_id": s.id, "book_id": b.id,
               "sec_id": sec.id, "subj_id": subj.id, "sb_id": sb.id}
        db.commit()
        return out


def _cleanup(seed):
    with SessionLocal() as db:
        sid = seed["s_id"]
        db.execute(sa_delete(CoachingSession).where(CoachingSession.student_id == sid))
        db.execute(sa_delete(CoachingReport).where(CoachingReport.student_id == sid))
        db.execute(sa_delete(TaskRequest).where(TaskRequest.student_id == sid))
        for t in db.query(Task).filter(Task.student_id == sid).all():
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id == t.id))
            db.delete(t)
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == seed["sb_id"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.id == seed["sb_id"]))
        db.execute(sa_delete(BookSection).where(BookSection.id == seed["sec_id"]))
        db.execute(sa_delete(Book).where(Book.id == seed["book_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subj_id"]))
        db.execute(sa_delete(User).where(User.id.in_([seed["t_id"], seed["t2_id"], sid])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {r.status_code} {r.text[:120]}")
    return c


def main():
    print(f"\n=== API v2 haftalık koç raporu smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient")); db.commit()
    seed = _seed()
    today = date.today()
    try:
        tc = _login(T_EMAIL)
        t2c = _login(T2_EMAIL)
        sid = seed["s_id"]

        r = TestClient(app).get(f"/api/v2/teacher/students/{sid}/weekly-reports")
        check("1. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 2. create (otomatik pencere: son yayınlanmış görev = dün)
        r = tc.post(f"/api/v2/teacher/students/{sid}/weekly-reports", json={})
        j = r.json()
        exp_end = (today - timedelta(days=1)).isoformat()
        ok = (r.status_code == 200 and j["data"]["week_end"] == exp_end
              and j["data"]["version"] == 1 and j["data"]["agenda_count"] > 0)
        check("2. POST create → pencere son görev gününe göre + gündem üretildi", ok,
              f"status={r.status_code} {r.text[:200]}")
        rep_id = j["data"]["id"] if r.status_code == 200 else None

        # 3. liste
        r = tc.get(f"/api/v2/teacher/students/{sid}/weekly-reports")
        j = r.json()
        check("3. liste → 1 satır", r.status_code == 200 and len(j["rows"]) == 1
              and j["rows"][0]["id"] == rep_id, f"status={r.status_code}")

        # 4. detay + kural motoru içerikleri
        r = tc.get(f"/api/v2/teacher/weekly-reports/{rep_id}")
        j = r.json()
        keys = {a["key"] for a in j.get("agenda", [])}
        ok = (r.status_code == 200 and "summary" in keys and "pending_requests" in keys
              and any(a["key"] == "weak_topics" for a in j["agenda"]))
        check("4. detay → kural motoru (özet + zayıf konu + bekleyen mesaj)", ok,
              f"status={r.status_code} keys={keys}")

        # 5. html
        r = tc.get(f"/api/v2/teacher/weekly-reports/{rep_id}/html")
        ok = (r.status_code == 200 and "Seans gündemi" in r.text
              and f"{PFX} Öğrenci" in r.text and "Haftanın seyri" in r.text)
        check("5. HTML görünüm → başlıklar + öğrenci adı", ok, f"status={r.status_code}")

        # 6. aynı hafta → version 2
        r = tc.post(f"/api/v2/teacher/students/{sid}/weekly-reports", json={})
        check("6. yeniden üret → version 2", r.status_code == 200 and r.json()["data"]["version"] == 2,
              f"status={r.status_code} {r.text[:120]}")
        rep2_id = r.json()["data"]["id"]

        # 7. yabancı koç → 404
        r = t2c.get(f"/api/v2/teacher/weekly-reports/{rep_id}")
        check("7. yabancı koç GET → 404", r.status_code == 404, f"status={r.status_code}")
        r = t2c.post(f"/api/v2/teacher/students/{sid}/weekly-reports", json={})
        check("7b. yabancı koç create → 404", r.status_code == 404, f"status={r.status_code}")

        # 8. week_end ile üretim
        we = (today - timedelta(days=2)).isoformat()
        r = tc.post(f"/api/v2/teacher/students/{sid}/weekly-reports", json={"week_end": we, "days": 5})
        j = r.json()
        exp_start = (today - timedelta(days=6)).isoformat()
        check("8. week_end + days → pencere doğru", r.status_code == 200
              and j["data"]["week_end"] == we and j["data"]["week_start"] == exp_start,
              f"status={r.status_code} {r.text[:160]}")

        # 9. invalid days
        r = tc.post(f"/api/v2/teacher/students/{sid}/weekly-reports", json={"days": 99})
        check("9. days=99 → 422 invalid_days", r.status_code == 422
              and r.json()["detail"]["code"] == "invalid_days", f"status={r.status_code}")

        # 10. seans create report_id + agenda_items
        r = tc.post(f"/api/v2/teacher/students/{sid}/sessions", json={
            "session_date": today.isoformat(), "agenda": "Rapor gündemiyle seans",
            "report_id": rep_id, "agenda_items": ["Haftanın özeti", "Zayıf konular"]})
        j = r.json()
        ok = (r.status_code == 200 and j["data"]["report_id"] == rep_id
              and j["data"]["agenda_items"] == ["Haftanın özeti", "Zayıf konular"])
        check("10. seans → report_id + agenda_items döner", ok, f"status={r.status_code} {r.text[:200]}")
        r = tc.get(f"/api/v2/teacher/students/{sid}/weekly-reports")
        row = next((x for x in r.json()["rows"] if x["id"] == rep_id), None)
        check("10b. rapor satırında session_count=1", row is not None and row["session_count"] == 1,
              f"{row}")

        # 11. yabancı rapor id → 422 (t2'nin öğrencisi yok; kendi öğrencime yabancı student raporu bağlanamaz)
        with SessionLocal() as db:
            other = CoachingReport(student_id=seed["t2_id"], coach_id=seed["t2_id"],
                                   week_start=today, week_end=today, data_json="{}")
            db.add(other); db.commit(); other_id = other.id
        r = tc.post(f"/api/v2/teacher/students/{sid}/sessions", json={
            "session_date": today.isoformat(), "agenda": "x", "report_id": other_id})
        check("11. başka öğrencinin raporu → 422 report_mismatch", r.status_code == 422
              and r.json()["detail"]["code"] == "report_mismatch", f"status={r.status_code}")
        with SessionLocal() as db:
            db.execute(sa_delete(CoachingReport).where(CoachingReport.id == other_id)); db.commit()

        # 12. prefill → latest report
        r = tc.get(f"/api/v2/teacher/students/{sid}/sessions/prefill")
        j = r.json()
        check("12. prefill → latest_report_id + agenda", r.status_code == 200
              and j.get("latest_report_id") is not None and len(j.get("latest_report_agenda") or []) > 0,
              f"status={r.status_code} latest={j.get('latest_report_id')}")

        # AI rıza (13 + 14 için)
        with SessionLocal() as db:
            from datetime import datetime, timezone
            u = db.get(User, seed["t_id"]); u.ai_capture_consent_at = datetime.now(timezone.utc); db.commit()

        # 13. AI gündem (monkeypatch)
        import app.services.ai_coaching_insight as aci
        captured: dict = {}
        def fake_report_agenda(name, bundle, sessions=None, **kw):
            captured["bundle"] = bundle
            return {"summary": "Güçlü hafta.",
                    "agenda": [{"title": "Takdir", "detail": "%93 tamamlama — kutla."},
                               {"title": "Zayıf konu", "detail": "Konu A %50 — tekrar planla."}],
                    "psychological_tips": ["Sıcak başla"], "watch_outs": []}
        orig = aci.generate_report_agenda
        aci.generate_report_agenda = fake_report_agenda
        try:
            r = tc.post(f"/api/v2/teacher/weekly-reports/{rep_id}/ai-agenda")
            j = r.json()
            ok = (r.status_code == 200 and j.get("ai_agenda") and len(j["ai_agenda"]) == 2
                  and j.get("ai_summary") == "Güçlü hafta."
                  and captured.get("bundle", {}).get("totals", {}).get("gorev_total") is not None
                  and any(a.get("key") == "pending_requests" for a in captured["bundle"]["rule_agenda"] if isinstance(a, dict)) is not None)
            check("13. AI gündem → cache + bundle rakamlı", ok, f"status={r.status_code} {r.text[:200]}")
        finally:
            aci.generate_report_agenda = orig
        r = tc.get(f"/api/v2/teacher/weekly-reports/{rep_id}")
        check("13b. GET → AI cache ücretsiz okunur + has_ai_agenda", r.status_code == 200
              and r.json().get("ai_agenda"), f"status={r.status_code}")
        r = tc.get(f"/api/v2/teacher/weekly-reports/{rep_id}/html")
        check("13c. HTML'de AI gündemi + kural detayları", r.status_code == 200
              and "Kural motorunun ham maddeleri" in r.text, f"status={r.status_code}")

        # 14. KS4 içgörü prompt'una weekly_report paketi
        captured2: dict = {}
        def fake_insight(name, sessions, academic, **kw):
            captured2["academic"] = academic
            return {"summary": "ok", "agenda_suggestions": ["a"], "psychological_tips": [], "watch_outs": []}
        orig2 = aci.generate_coaching_insight
        aci.generate_coaching_insight = fake_insight
        try:
            import app.routes.api_v2.teacher as tmod
            tmod.generate_coaching_insight = fake_insight  # locally imported olmadığından modül üzerinden
        except Exception:
            pass
        try:
            r = tc.post(f"/api/v2/teacher/students/{sid}/coaching-insight")
            wr = (captured2.get("academic") or {}).get("weekly_report")
            check("14. KS4 içgörü → weekly_report paketi prompt girdisinde", r.status_code == 200
                  and wr is not None and wr.get("totals", {}).get("gorev_total") is not None,
                  f"status={r.status_code} wr={'ok' if wr else None} {r.text[:160]}")
        finally:
            aci.generate_coaching_insight = orig2

    finally:
        _cleanup(seed)

    print(f"\n=== SONUÇ: {passed} PASS, {len(failed)} FAIL ===")
    for f in failed:
        print(f"  FAIL: {f}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
