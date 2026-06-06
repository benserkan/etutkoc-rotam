"""API v2 Veli deneme geçmişi (P2a) + AI veli içgörüsü (P2b) smoke.

P2a:
  1. Veli GET exams bağlı çocuk → 200 + count + koça-özel not gizli
  2. Veli GET exams başka çocuk → 404
P2b:
  3. GET insight (yok) → insight null + ai_available (koç premium+consent)
  4. POST insight (koç premium değil) → 403 ai_not_available
  5. POST insight (premium+consent, monkeypatch) → 200 + kredi düşer
  6. GET insight → insight var + is_stale False
  7. Yeni deneme ekle → GET is_stale True
  8. POST yeterli veri yok (boş öğrenci) → 422 not_enough_data
  9. Başka veli → 404
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

import app.services.ai_parent_insight as ai_parent_insight
from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, BookType, ExamResult, ExamSection, ParentInsight,
    ParentRelation, ParentStudentLink, Subject, Task, TaskBookItem, TaskStatus,
    TaskType, User, UserRole,
)
from app.models.suspicious_ip import SuspiciousIp
from app.models.exam_result import compute_net
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2pi{secrets.token_hex(3)}"
PW = "ParentIns1!@xyz"

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
    pwd = hash_password(PW)
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        # premium koç (solo_pro + consent) + ücretsiz koç
        t = User(email=f"{PFX}_t@x.invalid", password_hash=pwd, full_name=f"{PFX} Koç",
                 role=UserRole.TEACHER, is_active=True, plan="solo_pro", ai_capture_consent_at=now)
        tf = User(email=f"{PFX}_tf@x.invalid", password_hash=pwd, full_name=f"{PFX} KoçF",
                  role=UserRole.TEACHER, is_active=True, plan="solo_free")
        db.add_all([t, tf]); db.flush()
        s = User(email=f"{PFX}_s@x.invalid", password_hash=pwd, full_name="Çocuk",
                 role=UserRole.STUDENT, is_active=True, grade_level=12, teacher_id=t.id)
        sf = User(email=f"{PFX}_sf@x.invalid", password_hash=pwd, full_name="ÇocukF",
                  role=UserRole.STUDENT, is_active=True, grade_level=12, teacher_id=tf.id)
        sother = User(email=f"{PFX}_so@x.invalid", password_hash=pwd, full_name="Yabancı",
                      role=UserRole.STUDENT, is_active=True, grade_level=12, teacher_id=t.id)
        p = User(email=f"{PFX}_p@x.invalid", password_hash=pwd, full_name="Veli",
                 role=UserRole.PARENT, is_active=True)
        p2 = User(email=f"{PFX}_p2@x.invalid", password_hash=pwd, full_name="Veli2",
                  role=UserRole.PARENT, is_active=True)
        db.add_all([s, sf, sother, p, p2]); db.flush()
        db.add(ParentStudentLink(parent_id=p.id, student_id=s.id, relation=ParentRelation.ANNE, is_primary=True))
        db.add(ParentStudentLink(parent_id=p.id, student_id=sf.id, relation=ParentRelation.ANNE, is_primary=False))

        subj = Subject(teacher_id=t.id, name="Matematik", order=1)
        db.add(subj); db.flush()
        book = Book(teacher_id=t.id, name="Mat SB", type=BookType.SORU_BANKASI, subject_id=subj.id)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="Türev", order=1, test_count=100)
        db.add(sec); db.flush()
        task = Task(student_id=s.id, date=date(2026, 5, 1), type=TaskType.TEST, title="Mat",
                    is_draft=False, status=TaskStatus.COMPLETED, completed_at=now)
        db.add(task); db.flush()
        db.add(TaskBookItem(task_id=task.id, book_id=book.id, book_section_id=sec.id,
                            planned_count=5, completed_count=5, correct_count=40, wrong_count=10))
        # 1 deneme
        net = compute_net(20, 6, ExamSection.LGS)
        db.add(ExamResult(student_id=s.id, created_by_id=t.id, title="LGS 1",
                          exam_date=date(2026, 5, 2), section=ExamSection.LGS,
                          total_correct=20, total_wrong=6, total_blank=4, net=net,
                          note="koça özel not"))
        out = {"t_id": t.id, "s_id": s.id, "sf_id": sf.id, "sother_id": sother.id, "p_id": p.id}
        db.commit()
        return out


def _cleanup():
    with SessionLocal() as db:
        ids = [u.id for u in db.query(User).filter(User.email.like(f"{PFX}%")).all()]
        if ids:
            db.execute(sa_delete(ParentInsight).where(ParentInsight.student_id.in_(ids)))
            db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(ids)))
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(
                db.query(Task.id).filter(Task.student_id.in_(ids)).subquery().select())))
            db.execute(sa_delete(Task).where(Task.student_id.in_(ids)))
            secs = db.query(BookSection.id).join(Book, Book.id == BookSection.book_id).filter(Book.teacher_id.in_(ids))
            db.execute(sa_delete(BookSection).where(BookSection.id.in_(secs.subquery().select())))
            db.execute(sa_delete(Book).where(Book.teacher_id.in_(ids)))
            db.execute(sa_delete(Subject).where(Subject.teacher_id.in_(ids)))
            db.execute(sa_delete(ParentStudentLink).where(ParentStudentLink.student_id.in_(ids)))
            db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PW})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {email} {r.status_code} {r.text[:120]}")
    return c


def main():
    print(f"\n=== Veli deneme + AI içgörü smoke — prefix: {PFX} ===\n")
    # AI üretimini sahtele (gerçek Gemini çağrısı yok)
    ai_parent_insight.generate_parent_insight = lambda *a, **k: {
        "summary": "Çocuğunuz matematikte istikrarlı ilerliyor.",
        "strengths": ["Türev konusunda doğruluk yüksek"],
        "focus_areas": ["Deneme sıklığı artırılabilir"],
        "parent_tips": ["Akşam 30 dakika birlikte tekrar yapın"],
    }
    get_login_limiter().reset()
    seed = _seed()
    try:
        with SessionLocal() as db:
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()
        pc = _login(f"{PFX}_p@x.invalid")
        p2c = _login(f"{PFX}_p2@x.invalid")
        sid, sfid, soid = seed["s_id"], seed["sf_id"], seed["sother_id"]

        # P2a — deneme geçmişi
        r = pc.get(f"/api/v2/parent/students/{sid}/exams")
        j = r.json()
        check("1. Veli exams bağlı çocuk → 200 + 1 deneme", r.status_code == 200 and j["summary"]["count"] == 1,
              f"status={r.status_code} {j.get('summary')}")
        check("1b. koça-özel not gizli (note null)",
              r.status_code == 200 and (j["rows"][0].get("note") is None), f"{j['rows'][0] if j.get('rows') else None}")
        r = pc.get(f"/api/v2/parent/students/{soid}/exams")
        check("2. Veli exams başka çocuk → 404", r.status_code == 404, f"status={r.status_code}")

        # P2b — içgörü
        r = pc.get(f"/api/v2/parent/students/{sid}/insight")
        j = r.json()
        check("3. GET insight (yok) → null + ai_available True",
              r.status_code == 200 and j["insight"] is None and j["ai_available"] is True,
              f"status={r.status_code} {j}")

        r = pc.get(f"/api/v2/parent/students/{sfid}/insight")
        j = r.json()
        check("4a. GET insight ücretsiz koç çocuğu → ai_available False",
              r.status_code == 200 and j["ai_available"] is False, f"{j}")
        r = pc.post(f"/api/v2/parent/students/{sfid}/insight")
        check("4b. POST ücretsiz koç → 403 ai_not_available",
              r.status_code == 403 and r.json()["detail"]["code"] == "ai_not_available", f"status={r.status_code} {r.text[:120]}")

        r = pc.post(f"/api/v2/parent/students/{sid}/insight")
        j = r.json()
        check("5. POST insight (premium+monkeypatch) → 200 + summary",
              r.status_code == 200 and j["insight"] and "matematik" in j["insight"]["summary"].lower(),
              f"status={r.status_code} {r.text[:160]}")

        r = pc.get(f"/api/v2/parent/students/{sid}/insight")
        j = r.json()
        check("6. GET insight → var + is_stale False",
              r.status_code == 200 and j["insight"] is not None and j["is_stale"] is False, f"{j.get('is_stale')}")

        # 7. yeni deneme ekle → stale
        with SessionLocal() as db:
            net = compute_net(25, 4, ExamSection.LGS)
            db.add(ExamResult(student_id=sid, created_by_id=seed["t_id"], title="LGS 2",
                              exam_date=date(2026, 5, 9), section=ExamSection.LGS,
                              total_correct=25, total_wrong=4, total_blank=1, net=net))
            db.commit()
        r = pc.get(f"/api/v2/parent/students/{sid}/insight")
        check("7. Yeni deneme → is_stale True", r.status_code == 200 and r.json()["is_stale"] is True, f"{r.json().get('is_stale')}")

        # 8. yeterli veri yok (sother — veri yok ama parent bağlı değil → önce link gerek)
        #    sother parent'a bağlı değil → 404; yeterli-veri yolunu sf ile test edemeyiz (premium değil).
        #    Bunun yerine: sother'ı p'ye bağla + premium koç + veri yok → 422.
        with SessionLocal() as db:
            db.add(ParentStudentLink(parent_id=seed["p_id"], student_id=soid,
                                     relation=ParentRelation.ANNE, is_primary=False))
            db.commit()
        r = pc.post(f"/api/v2/parent/students/{soid}/insight")
        check("8. POST yeterli veri yok → 422 not_enough_data",
              r.status_code == 422 and r.json()["detail"]["code"] == "not_enough_data", f"status={r.status_code} {r.text[:120]}")

        # 9. başka veli → 404
        r = p2c.get(f"/api/v2/parent/students/{sid}/insight")
        check("9. Başka veli → 404", r.status_code == 404, f"status={r.status_code}")

    finally:
        _cleanup()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
