"""Görev şablonu (TaskTemplate) smoke — oluştur/listele/uygula/görevden-kaydet/sil.

Senaryolar:
  1. formdan oluştur (kitap+bölüm+sayı) → item_count + total_planned
  2. listele → görünür
  3. öğrenciye uygula (from-template) → görev oluşur (tek tıkla)
  4. mevcut görevden şablon kaydet (from-task)
  5. sil → listeden çıkar
  6. sahiplik: başka koç uygulayamaz/silemez → 404
  7. validasyon: boş kalem → 422 · sahip olunmayan kitap → 404
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    Subject,
    TaskTemplate,
    TaskTemplateItem,
    User,
    UserRole,
)
from app.models.book import BookType
from app.models.curriculum import CurriculumModel
from app.models.progress import SectionProgress, StudentBook
from app.models.suspicious_ip import SuspiciousIp
from app.models.task import Task, TaskBookItem
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"tasktpl_{secrets.token_hex(3)}"
PWD = hash_password("TaskTpl!23")
PWDH = "TaskTpl!23"
now = datetime.now(timezone.utc)
ctx: dict = {}
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def _code(r):
    try:
        return (r.json().get("detail", {}) or {}).get("code")
    except Exception:
        return None


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        def coach(suffix):
            u = User(email=f"{PFX}_{suffix}@test.invalid", password_hash=PWD, full_name=f"{PFX} {suffix}",
                     role=UserRole.TEACHER, institution_id=None, is_active=True, plan="solo_pro",
                     password_changed_at=now, must_change_password=False)
            db.add(u); db.flush()
            return u
        c1 = coach("c1"); c2 = coach("c2")
        stu = User(email=f"{PFX}_s@test.invalid", password_hash=PWD, full_name=f"{PFX} Ogr",
                   role=UserRole.STUDENT, teacher_id=c1.id, institution_id=None, grade_level=8,
                   is_active=True, password_changed_at=now, must_change_password=False)
        db.add(stu); db.flush()
        subj = Subject(name=f"{PFX} Mat", order=0, is_builtin=False, teacher_id=c1.id,
                       available_for_graduate=False, curriculum_model=CurriculumModel.LGS)
        db.add(subj); db.flush()
        book = Book(teacher_id=c1.id, subject_id=subj.id, name=f"{PFX} SB", publisher="T",
                    type=BookType.SORU_BANKASI, target_graduate=False)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="Ünite 1", test_count=100, order=0)
        db.add(sec); db.flush()
        sb = StudentBook(student_id=stu.id, book_id=book.id)
        db.add(sb); db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
        db.commit()
        ctx.update(c1=c1.id, c2=c2.id, student_id=stu.id, subject_id=subj.id,
                   book_id=book.id, section_id=sec.id)


def login(suffix):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{suffix}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {suffix}: {r.status_code}")
    return c


def main() -> int:
    print(f"\n=== GÖREV ŞABLONU (TaskTemplate) — {PFX} ===\n")
    setup()
    sid, bid, secid = ctx["student_id"], ctx["book_id"], ctx["section_id"]
    today = date.today().isoformat()
    try:
        c = login("c1")
        # 1. formdan oluştur
        r = c.post("/api/v2/teacher/task-templates", json={
            "name": "Günlük 20 test", "type": "test",
            "items": [{"book_id": bid, "section_id": secid, "planned_count": 20}]})
        ok = r.status_code == 200
        tpl = r.json()["data"] if ok else {}
        check("1. formdan oluştur → 200 + item_count=1 + total_planned=20",
              ok and tpl.get("item_count") == 1 and tpl.get("total_planned") == 20, f"{r.status_code} {r.text[:120]}")
        tid = tpl.get("id")

        # 2. listele
        lst = c.get("/api/v2/teacher/task-templates").json()
        check("2. listede görünür", any(t["id"] == tid for t in lst["items"]), f"{[t['id'] for t in lst['items']]}")

        # 3. uygula → görev oluşur
        r = c.post(f"/api/v2/teacher/students/{sid}/tasks/from-template", json={
            "template_id": tid, "date": today})
        check("3. öğrenciye uygula (tek tıkla) → 200 görev oluştu",
              r.status_code == 200 and r.json()["data"].get("id"), f"{r.status_code} {r.text[:140]}")
        with SessionLocal() as db:
            tcount = db.query(Task).filter(Task.student_id == sid, Task.date == date.today()).count()
        check("3b. görev DB'de var", tcount >= 1, f"task_count={tcount}")

        # 4. mevcut görevden şablon kaydet
        with SessionLocal() as db:
            task = db.query(Task).filter(Task.student_id == sid).first()
            task_id = task.id
        r = c.post(f"/api/v2/teacher/task-templates/from-task/{task_id}", json={"name": "Görevden şablon"})
        check("4. mevcut görevden şablon kaydet → 200 + kalem kopyalandı",
              r.status_code == 200 and r.json()["data"]["item_count"] >= 1, f"{r.status_code} {r.text[:120]}")
        tid2 = r.json()["data"]["id"] if r.status_code == 200 else None

        # 5. sil
        r = c.post(f"/api/v2/teacher/task-templates/{tid}/delete") if False else c.request(
            "DELETE", f"/api/v2/teacher/task-templates/{tid}")
        check("5. sil → 200", r.status_code == 200, f"{r.status_code}")
        lst = c.get("/api/v2/teacher/task-templates").json()
        check("5b. silinen listede yok", not any(t["id"] == tid for t in lst["items"]), "hâlâ var")

        # 6. sahiplik
        c2 = login("c2")
        r = c2.request("DELETE", f"/api/v2/teacher/task-templates/{tid2}")
        check("6. başka koç silemez → 404", r.status_code == 404, f"{r.status_code}")
        r = c2.post(f"/api/v2/teacher/students/{sid}/tasks/from-template", json={"template_id": tid2, "date": today})
        check("6b. başka koç (öğrenci sahibi değil) uygulayamaz → 404", r.status_code == 404, f"{r.status_code}")

        # 7. validasyon
        r = c.post("/api/v2/teacher/task-templates", json={"name": "Boş", "type": "test", "items": []})
        check("7. boş kalem → 422 no_items", r.status_code == 422 and _code(r) == "no_items", f"{r.status_code}")
        r = c.post("/api/v2/teacher/task-templates", json={
            "name": "Yabancı kitap", "type": "test",
            "items": [{"book_id": 999999, "section_id": secid, "planned_count": 5}]})
        check("7b. sahip olunmayan kitap → 404 book_not_found",
              r.status_code == 404 and _code(r) == "book_not_found", f"{r.status_code}")

    finally:
        with SessionLocal() as db:
            ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            cids = [ctx.get("c1"), ctx.get("c2")]
            tplids = [r[0] for r in db.query(TaskTemplate.id).filter(TaskTemplate.teacher_id.in_([c for c in cids if c])).all()]
            if tplids:
                db.execute(sa_delete(TaskTemplateItem).where(TaskTemplateItem.template_id.in_(tplids)))
                db.execute(sa_delete(TaskTemplate).where(TaskTemplate.id.in_(tplids)))
            if ids:
                tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(ids)).all()]
                if tids:
                    db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
                    db.execute(sa_delete(Task).where(Task.id.in_(tids)))
                sbids = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(ids)).all()]
                if sbids:
                    db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbids)))
                    db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(ids)))
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
