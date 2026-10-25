"""Gelişim Raporu (360°) smoke — 2026-10-25.

Kurgu: bugün programın 3. günü. Öncesinde 8 program haftası (görevler test kalemli, D/Y GİRİLMEMİŞ),
4 TYT genel denemesi (net yükseliyor). Bu hafta 1. gün tamam, 2. gün yapılmadı.
  1. 200 + başlık + bu hafta aynı nokta (2 gün)
  2. Hafta tablosu: 8 geçmiş + bu hafta; deneme netleri doğru haftada
  3. Gelinen nokta: deneme ilk → son, hafta sayısı
  4. Risk: görev uyumu geçmişin en kötüsü · D/Y girilmiyor (veri girişi)
  5. Güçlü yan: deneme yükselişi · fırsat: hedef net belirle
  6. Aksiyon planı: kalan görevler (haftalık) + D/Y alışkanlığı (veri)
  7. Seansa ekle → queued; queue_count
  8. CANLI: dünün görevleri işaretlenince rapor (saklanmadan) değişir
  9. Başka koç 404 · öğrenci 403
"""
from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import date, datetime, time, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (Book, BookSection, ExamResult, Subject, Task, TaskBookItem, User,  # noqa: E402
                        UserRole, WeeklyProgram)
from app.models.book import BookType  # noqa: E402
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.exam_progress import SessionAgendaItem  # noqa: E402
from app.models.pool import StudyPeriod  # noqa: E402
from app.models.student_period import StudentGradePeriod  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.models.task import TaskStatus, TaskType  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"dvr_{secrets.token_hex(3)}"
PWD = "Gelisim!2345x"
today = date.today()
cur_start = today - timedelta(days=2)
passed = 0
failed: list[str] = []
ids: dict = {"users": [], "subject": None}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def login(email: str) -> TestClient:
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return c


def utc(d: date, hour: int) -> datetime:
    return datetime.combine(d, time(hour)) - timedelta(hours=3)


def seed() -> dict:
    with SessionLocal() as db:
        db.execute(sa_delete(StudentGradePeriod).where(~StudentGradePeriod.student_id.in_(db.query(User.id))))
        db.execute(sa_delete(TaskBookItem).where(~TaskBookItem.task_id.in_(db.query(Task.id))))
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Koç",
                     role=UserRole.TEACHER, is_active=True)
        other = User(email=f"{PFX}_o@test.invalid", password_hash=hash_password(PWD), full_name="Öbür",
                     role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other]); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Öğrenci",
                  role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                  must_change_password=False)
        db.add(st); db.flush()
        ids["users"] += [coach.id, other.id, st.id]
        subj = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id)
        db.add(subj); db.flush()
        ids["subject"] = subj.id
        book = Book(teacher_id=coach.id, subject_id=subj.id, name=f"{PFX} SB", type=BookType.SORU_BANKASI)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="Üslü", test_count=500, order=1)
        db.add(sec); db.flush()

        def add_week(start: date, cur: bool = False):
            db.add(WeeklyProgram(student_id=st.id, coach_id=coach.id, start_date=start,
                                 end_date=start + timedelta(days=6)))
            for day in range(7):
                d = start + timedelta(days=day)
                for j in range(3):
                    done = not (cur and (d >= today or day == 1))
                    t = Task(student_id=st.id, date=d, title=f"Görev {day}-{j}", type=TaskType.TEST,
                             status=TaskStatus.COMPLETED if done else TaskStatus.PENDING, is_draft=False,
                             order=j, completed_at=utc(d, 20) if done else None,
                             book_items=[TaskBookItem(book_id=book.id, book_section_id=sec.id, planned_count=2,
                                                      completed_count=2 if done else 0,
                                                      reservation_released_at=datetime.utcnow())])
                    db.add(t)

        for i in range(8):
            add_week(cur_start - timedelta(days=7 * (8 - i)))
        add_week(cur_start, cur=True)
        nets = [60.0, 63.5, 66.0, 70.25]
        for i, n in enumerate(nets):
            d = cur_start - timedelta(days=7 * (4 - i)) + timedelta(days=3)
            db.add(ExamResult(student_id=st.id, created_by_id=coach.id, title=f"TYT Genel {i + 1}",
                              exam_date=d, section=ExamSection.TYT, total_correct=int(n) + 10,
                              total_wrong=40, total_blank=120 - int(n) - 50, net=n,
                              subject_nets=json.dumps([{"name": "TYT Matematik", "net": n / 4,
                                                        "correct": 10, "wrong": 2, "blank": 3}])))
        db.commit()
        return {"st": st.id, "exam_week3": (cur_start - timedelta(days=7) + timedelta(days=3)).isoformat()}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(SessionAgendaItem).where(SessionAgendaItem.student_id.in_(u)))
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(u)))
        db.execute(sa_delete(WeeklyProgram).where(WeeklyProgram.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(StudentGradePeriod).where(StudentGradePeriod.student_id.in_(u)))
        if ids["subject"]:
            bids = [r[0] for r in db.query(Book.id).filter(Book.subject_id == ids["subject"]).all()]
            if bids:
                db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(bids)))
                db.execute(sa_delete(Book).where(Book.id.in_(bids)))
            db.execute(sa_delete(Subject).where(Subject.id == ids["subject"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def keys(lst):
    return {i["key"] for i in lst}


def main() -> int:
    d = seed()
    sid = d["st"]
    url = f"/api/v2/teacher/students/{sid}/development-report"
    print(f"\n=== gelişim raporu 360 — {PFX} ===\n")
    try:
        c = login(f"{PFX}_t@test.invalid")
        r = c.get(url)
        check("0 200", r.status_code == 200, r.text[:300])
        a = r.json()
        tw = a.get("this_week") or {}
        check("1a başlık var", bool(a["headline"]["text"]), str(a["headline"]))
        check("1b aynı nokta 2 gün", tw.get("week", {}).get("compare_days") == 2, str(tw.get("week")))
        ws = a["weeks"]
        check("2a hafta tablosu 8+1", len(ws) == 9 and ws[-1]["current"], str(len(ws)))
        check("2b bu hafta 3/6 görev", ws[-1]["gorev_done"] == 3 and ws[-1]["gorev_total"] == 6,
              f"{ws[-1]['gorev_done']}/{ws[-1]['gorev_total']}")
        wk = next((w for w in ws if w["start"] <= d["exam_week3"] <= w["end"]), None)
        check("2c deneme neti doğru haftada", wk is not None and wk["exam_nets"] == [70.25], str(wk and wk["exam_nets"]))
        j = a.get("journey") or {}
        check("3a gelinen nokta: deneme 60 → 70,25", (j.get("exam") or {}).get("first_net") == 60.0
              and j["exam"]["last_net"] == 70.25, str(j.get("exam")))
        check("3b 8 hafta", j.get("weeks") == 8, str(j.get("weeks")))
        rk = keys(a["risks"])
        check("4a risk: görev uyumu", "risk:wk:gorev_pct" in rk, str(rk))
        check("4b risk: D/Y girilmiyor", "data:results" in rk, str(a["data_quality"]))
        check("5a güçlü yan: deneme yükselişi", any(k.startswith("good:exam") for k in keys(a["strengths"])),
              str(keys(a["strengths"])))
        check("5b fırsat: hedef net belirle", "opp:set_target" in keys(a["opportunities"]),
              str(keys(a["opportunities"])))
        ak = keys(a["actions"])
        check("6a aksiyon: kalan görevler", "wp:carry" in ak, str(ak))
        check("6b aksiyon: D/Y alışkanlığı", "act:data:results" in ak, str(ak))
        check("6c her maddede gündem metni", all(i["agenda"] for i in a["actions"] + a["risks"]))

        r = c.post(f"/api/v2/teacher/students/{sid}/agenda-queue",
                   json={"items": [{"key": "risk:wk:gorev_pct", "text": "Görev uyumu konuşulacak", "source": "report"}]})
        check("7a seansa ekle 200", r.status_code == 200 and r.json()["added"] == 1, r.text[:200])
        check("7b invalidate rapor anahtarı", any(x.endswith(":development-report") for x in r.json()["invalidate"]))
        a2 = c.get(url).json()
        q = next((i for i in a2["risks"] if i["key"] == "risk:wk:gorev_pct"), {})
        check("7c işaret: seans gündeminde", q.get("queued") is True and a2["queue_count"] == 1, str(q.get("queued")))

        # CANLI: dünün görevleri işaretlenir → rapor kendiliğinden değişir
        with SessionLocal() as db:
            for t in db.query(Task).filter(Task.student_id == sid, Task.date == cur_start + timedelta(days=1)).all():
                t.status = TaskStatus.COMPLETED
                t.completed_at = utc(t.date, 21)
            db.commit()
        a3 = c.get(url).json()
        check("8a canlı: bu hafta 6/6", a3["weeks"][-1]["gorev_done"] == 6, str(a3["weeks"][-1]["gorev_done"]))
        check("8b canlı: görev uyumu riski kalktı", "risk:wk:gorev_pct" not in keys(a3["risks"]), str(keys(a3["risks"])))
        check("8c generated_at yeni", a3["generated_at"] >= a["generated_at"])

        o = login(f"{PFX}_o@test.invalid")
        check("9a başka koç 404", o.get(url).status_code == 404)
        s = login(f"{PFX}_s@test.invalid")
        check("9b öğrenci 403", s.get(url).status_code == 403)
    finally:
        cleanup()
    print(f"\n{passed} geçti, {len(failed)} kaldı")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
