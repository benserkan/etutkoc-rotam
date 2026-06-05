# -*- coding: utf-8 -*-
"""API v2 /parent/students/{id}/weekly-report smoke.

Veliye doyurucu haftalık rapor — bu hafta özeti + geçen haftaya kıyas + ders
kırılımı (en çok çözülen / en çok aksatılan) + deneme net trendi + gün gün +
koç notu + verdict.

Senaryolar:
  1. weekly-report P1 happy → 200 + tam yapı
  2. start = haftanın Pazartesi'sine snap'lenir (orta-hafta tarihi verilince)
  3. daily 7 gün + weekday 0..6
  4. completion + comparison (bu hafta > geçen hafta → direction="up")
  5. ders kırılımı: most_completed=Mat, most_neglected=Türkçe (%20)
  6. test_completed deneme'yi DIŞLAR (tam_deneme 90 karışmaz)
  7. deneme net trendi: TYT son−önceki = +10
  8. active_days = 3
  9. varsayılan (week_start yok) → son tamamlanmış hafta
 10. P2 (bağlı değil) → 404
 11. teacher rolü → 403

Test verisi: prefix'li, gerçek hesaplara dokunulmaz; cleanup garantili.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, BookType, ParentRelation, ParentStudentLink,
    Subject, Task, TaskBookItem, TaskStatus, TaskType, User, UserRole,
)
from app.models.curriculum import ExamSection
from app.models.exam_result import ExamResult
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2wr_{secrets.token_hex(3)}"
PWD = "TestWeeklyRep!23"
passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PWD)
    today = date.today()
    this_mon = today - timedelta(days=today.weekday())
    report_mon = this_mon - timedelta(days=7)      # son tamamlanmış hafta
    prev_mon = report_mon - timedelta(days=7)

    with SessionLocal() as db:
        teacher = User(email=f"{PFX}_t@test.invalid", password_hash=pwd,
                       full_name=f"{PFX} T", role=UserRole.TEACHER, is_active=True,
                       password_changed_at=now, must_change_password=False)
        db.add(teacher); db.flush()
        stu = User(email=f"{PFX}_s@test.invalid", password_hash=pwd,
                   full_name=f"{PFX} S", role=UserRole.STUDENT, teacher_id=teacher.id,
                   grade_level=8, is_active=True, password_changed_at=now,
                   must_change_password=False,
                   created_at=now - timedelta(days=120))
        other = User(email=f"{PFX}_so@test.invalid", password_hash=pwd,
                     full_name=f"{PFX} SO", role=UserRole.STUDENT, teacher_id=teacher.id,
                     grade_level=8, is_active=True, password_changed_at=now,
                     must_change_password=False)
        p1 = User(email=f"{PFX}_p1@test.invalid", password_hash=pwd,
                  full_name=f"{PFX} P1", role=UserRole.PARENT, is_active=True,
                  password_changed_at=now, must_change_password=False)
        p2 = User(email=f"{PFX}_p2@test.invalid", password_hash=pwd,
                  full_name=f"{PFX} P2", role=UserRole.PARENT, is_active=True,
                  password_changed_at=now, must_change_password=False)
        db.add_all([stu, other, p1, p2]); db.flush()
        db.add(ParentStudentLink(parent_id=p1.id, student_id=stu.id,
                                 relation=ParentRelation.ANNE, is_primary=True))
        db.add(ParentStudentLink(parent_id=p2.id, student_id=other.id,
                                 relation=ParentRelation.ANNE, is_primary=True))

        mat = Subject(teacher_id=teacher.id, name="Mat", order=1)
        tur = Subject(teacher_id=teacher.id, name="Türkçe", order=2)
        db.add_all([mat, tur]); db.flush()
        sb_mat = Book(teacher_id=teacher.id, name="Mat SB", type=BookType.SORU_BANKASI, subject_id=mat.id)
        sb_tur = Book(teacher_id=teacher.id, name="Tür SB", type=BookType.SORU_BANKASI, subject_id=tur.id)
        dn = Book(teacher_id=teacher.id, name="GD", type=BookType.GENEL_DENEME, subject_id=mat.id)
        db.add_all([sb_mat, sb_tur, dn]); db.flush()
        sec_mat = BookSection(book_id=sb_mat.id, label="M1", order=1, test_count=500)
        sec_tur = BookSection(book_id=sb_tur.id, label="T1", order=1, test_count=500)
        sec_dn = BookSection(book_id=dn.id, label="D", order=1, test_count=50)
        db.add_all([sec_mat, sec_tur, sec_dn]); db.flush()

        def add_task(d, ttype, status, items):
            t = Task(student_id=stu.id, date=d, type=ttype, title="G",
                     is_draft=False, status=status)
            db.add(t); db.flush()
            for (bid, sid, planned, completed, label) in items:
                db.add(TaskBookItem(task_id=t.id, book_id=bid, book_section_id=sid,
                                    planned_count=planned, completed_count=completed, label=label))
            db.flush()
            return t

        # --- RAPOR HAFTASI (report_mon..) ---
        # Pzt: Mat 10/10 done + Türkçe 10/2 partial (aksatılan)
        add_task(report_mon, TaskType.TEST, TaskStatus.COMPLETED, [(sb_mat.id, sec_mat.id, 10, 10, None)])
        add_task(report_mon, TaskType.TEST, TaskStatus.PARTIAL, [(sb_tur.id, sec_tur.id, 10, 2, None)])
        # Sal: Mat 8/8 done
        add_task(report_mon + timedelta(days=1), TaskType.TEST, TaskStatus.COMPLETED, [(sb_mat.id, sec_mat.id, 8, 8, None)])
        # Çar: deneme 1/1 done + tam deneme 90/90 done (kitapsız)
        add_task(report_mon + timedelta(days=2), TaskType.TEST, TaskStatus.COMPLETED, [(dn.id, sec_dn.id, 1, 1, None)])
        add_task(report_mon + timedelta(days=2), TaskType.TEST, TaskStatus.COMPLETED, [(None, None, 90, 90, "Tam Deneme")])

        # --- GEÇEN HAFTA (prev_mon..) — düşük tamamlama (bu hafta yükselişte) ---
        add_task(prev_mon, TaskType.TEST, TaskStatus.PARTIAL, [(sb_mat.id, sec_mat.id, 10, 5, None)])

        # --- Denemeler (net trendi: TYT son 80, önceki 70 → +10) ---
        db.add(ExamResult(student_id=stu.id, created_by_id=teacher.id,
                          title="TYT Deneme 2", exam_date=today - timedelta(days=3),
                          section=ExamSection.TYT, total_correct=85, total_wrong=20, total_blank=15, net=80.0))
        db.add(ExamResult(student_id=stu.id, created_by_id=teacher.id,
                          title="TYT Deneme 1", exam_date=today - timedelta(days=20),
                          section=ExamSection.TYT, total_correct=75, total_wrong=20, total_blank=25, net=70.0))
        db.commit()

        return {
            "teacher_id": teacher.id, "stu_id": stu.id, "other_id": other.id,
            "p1_id": p1.id, "p2_id": p2.id,
            "report_mon": report_mon.isoformat(),
            "prev_mon": prev_mon.isoformat(),
        }


def _cleanup(seed: dict) -> None:
    from sqlalchemy import delete as sa_delete
    with SessionLocal() as db:
        sids = [seed["stu_id"], seed["other_id"]]
        uids = sids + [seed["teacher_id"], seed["p1_id"], seed["p2_id"]]
        tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(sids)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(sids)))
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(sids)))
        db.execute(sa_delete(ParentStudentLink).where(ParentStudentLink.parent_id.in_([seed["p1_id"], seed["p2_id"]])))
        for b in db.query(Book).filter(Book.teacher_id == seed["teacher_id"]).all():
            db.execute(sa_delete(BookSection).where(BookSection.book_id == b.id))
        db.execute(sa_delete(Book).where(Book.teacher_id == seed["teacher_id"]))
        db.execute(sa_delete(Subject).where(Subject.teacher_id == seed["teacher_id"]))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def _login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed {email}: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== /parent weekly-report smoke — {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    report_mon = seed["report_mon"]
    sid = seed["stu_id"]
    try:
        p1 = _login(f"{PFX}_p1@test.invalid")
        p2 = _login(f"{PFX}_p2@test.invalid")
        teacher = _login(f"{PFX}_t@test.invalid")

        # 1. happy + structure (rapor haftası açıkça verilir)
        r = p1.get(f"/api/v2/parent/students/{sid}/weekly-report",
                   params={"week_start": report_mon})
        body = r.json() if r.status_code == 200 else {}
        ok = (
            r.status_code == 200
            and body.get("student", {}).get("id") == sid
            and all(k in body for k in (
                "start", "end", "prev_start", "next_start", "daily", "subjects",
                "comparison", "exams", "verdict_level", "verdict_text",
                "completion_pct", "active_days",
            ))
        )
        check("1. weekly-report happy + tam yapı", ok,
              f"status={r.status_code} keys={list(body.keys())[:12]}")

        # 2. start = haftanın Pazartesi'si (orta-hafta tarih → Pzt'ye snap)
        mid = (date.fromisoformat(report_mon) + timedelta(days=3)).isoformat()
        r2 = p1.get(f"/api/v2/parent/students/{sid}/weekly-report",
                    params={"week_start": mid})
        b2 = r2.json() if r2.status_code == 200 else {}
        check("2. start Pazartesi'ye snap'lenir", b2.get("start") == report_mon,
              f"start={b2.get('start')} beklenen={report_mon}")

        # 3. daily 7 gün + weekday 0..6
        daily = body.get("daily", [])
        check("3. daily 7 gün + weekday 0..6",
              len(daily) == 7 and [d["weekday"] for d in daily] == list(range(7)),
              f"len={len(daily)}")

        # 4. completion + comparison direction up
        comp = body.get("comparison", {})
        check("4. completion_pct=80 (5 görev/4 done)", body.get("completion_pct") == 80,
              f"got {body.get('completion_pct')}")
        check("4b. comparison direction=up (geçen hafta %0)", comp.get("direction") == "up",
              f"dir={comp.get('direction')} last={comp.get('last_completion_pct')}")

        # 5. ders kırılımı
        check("5. most_completed=Mat", body.get("most_completed_subject") == "Mat",
              f"got {body.get('most_completed_subject')}")
        check("5b. most_neglected=Türkçe %20",
              body.get("most_neglected_subject") == "Türkçe" and body.get("most_neglected_pct") == 20,
              f"subj={body.get('most_neglected_subject')} pct={body.get('most_neglected_pct')}")

        # 6. test_completed deneme'yi dışlar (Mat 18 + Türkçe 2 = 20; 90 karışmaz)
        check("6. test_completed=20 (tam_deneme 90 HARİÇ)", body.get("test_completed") == 20,
              f"got {body.get('test_completed')}")

        # 7. deneme net trendi TYT +10
        check("7. exam_trend_delta=+10 (TYT)",
              body.get("exam_trend_delta") == 10.0 and body.get("exam_trend_section") == "TYT",
              f"delta={body.get('exam_trend_delta')} sec={body.get('exam_trend_section')}")
        check("7b. exams listesi >=2", len(body.get("exams", [])) >= 2,
              f"len={len(body.get('exams', []))}")

        # 8. active_days = 3 (Pzt/Sal/Çar)
        check("8. active_days=3", body.get("active_days") == 3, f"got {body.get('active_days')}")

        # 9. varsayılan (week_start yok) → son tamamlanmış hafta
        r9 = p1.get(f"/api/v2/parent/students/{sid}/weekly-report")
        b9 = r9.json() if r9.status_code == 200 else {}
        check("9. varsayılan → son tamamlanmış hafta", b9.get("start") == report_mon,
              f"start={b9.get('start')}")

        # 10. P2 (bağlı değil) → 404
        r10 = p2.get(f"/api/v2/parent/students/{sid}/weekly-report")
        check("10. P2 bağlı değil → 404",
              r10.status_code == 404 and r10.json().get("detail", {}).get("code") == "student_not_found",
              f"status={r10.status_code}")

        # 11. teacher rolü → 403
        r11 = teacher.get(f"/api/v2/parent/students/{sid}/weekly-report")
        check("11. teacher → 403 role_required",
              r11.status_code == 403 and r11.json().get("detail", {}).get("code") == "role_required",
              f"status={r11.status_code}")

    finally:
        _cleanup(seed)
        print("\n  test verileri temizlendi")

    print("\n=== SONUÇ ===")
    print(f"  PASSED: {passed}")
    print(f"  FAILED: {len(failed)}")
    for f in failed:
        print(f"    - {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
