"""Serbest iş bloğu (CoachWorkBlock, Katman 3) smoke.

Senaryolar:
  1. blok oluştur → 200 + total/unit + distributed=0 + remaining=total
  2. listele → aktif blok görünür
  3. bloğa bağlı görev ekle (kitapsız kalem + work_block_id) → görev oluşur,
     serializer work_block_title/unit döner
  4. listele → distributed=3, remaining=total-3, task_count=1
  5. ikinci bağlı görev → distributed birikir (3+4=7)
  6. blok güncelle (total 10→12) → remaining yeniden hesaplanır
  7. validasyon: boş ad → 422 · total<1 → 422
  8. sahiplik: c2 listeleyemez(boş)/güncelleyemez/silemez → 404
  9. bağsız: olmayan/yabancı blok ile görev → 404 work_block_not_found
 10. arşivle → varsayılan listede yok; include_archived ile var
 11. sil → blok gider, bağlı görev KALIR (work_block_id NULL)
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
    CoachWorkBlock,
    Subject,
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

PFX = f"wblk_{secrets.token_hex(3)}"
PWD = hash_password("WorkBlk!23")
PWDH = "WorkBlk!23"
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
            u = User(email=f"{PFX}_{suffix}@test.invalid", password_hash=PWD,
                     full_name=f"{PFX} {suffix}", role=UserRole.TEACHER,
                     institution_id=None, is_active=True, plan="solo_pro",
                     password_changed_at=now, must_change_password=False)
            db.add(u); db.flush()
            return u
        c1 = coach("c1"); c2 = coach("c2")
        stu = User(email=f"{PFX}_s@test.invalid", password_hash=PWD,
                   full_name=f"{PFX} Ogr", role=UserRole.STUDENT, teacher_id=c1.id,
                   institution_id=None, grade_level=8, is_active=True,
                   password_changed_at=now, must_change_password=False)
        db.add(stu); db.flush()
        subj = Subject(name=f"{PFX} Mat", order=0, is_builtin=False, teacher_id=c1.id,
                       available_for_graduate=False, curriculum_model=CurriculumModel.LGS)
        db.add(subj); db.flush()
        db.commit()
        ctx.update(c1=c1.id, c2=c2.id, student_id=stu.id, subject_id=subj.id)


def login(suffix):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login",
               json={"email": f"{PFX}_{suffix}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {suffix}: {r.status_code}")
    return c


def _block_in_list(c, sid, block_id, include_archived=False):
    qs = "?include_archived=true" if include_archived else ""
    lst = c.get(f"/api/v2/teacher/students/{sid}/work-blocks{qs}").json()
    for b in lst["items"]:
        if b["id"] == block_id:
            return b
    return None


def main() -> int:
    print(f"\n=== SERBEST İŞ BLOĞU (CoachWorkBlock) — {PFX} ===\n")
    setup()
    sid = ctx["student_id"]
    subj_id = ctx["subject_id"]
    today = date.today().isoformat()
    try:
        c = login("c1")

        # 1. oluştur
        r = c.post(f"/api/v2/teacher/students/{sid}/work-blocks", json={
            "title": "Özel Ders Mat — 10 test", "total_count": 10,
            "unit": "test", "subject_id": subj_id})
        ok = r.status_code == 200
        blk = r.json()["data"] if ok else {}
        check("1. oluştur → 200 + total=10 + distributed=0 + remaining=10",
              ok and blk.get("total_count") == 10 and blk.get("distributed") == 0
              and blk.get("remaining") == 10 and blk.get("unit") == "test",
              f"{r.status_code} {r.text[:140]}")
        bid = blk.get("id")

        # 2. listele
        found = _block_in_list(c, sid, bid)
        check("2. aktif blok listede", found is not None, "yok")

        # 3. bloğa bağlı görev ekle (kitapsız kalem, 3 test)
        r = c.post(f"/api/v2/teacher/students/{sid}/tasks", json={
            "date": today, "type": "other", "title": "Özel Ders Mat — bölüm 1",
            "work_block_id": bid,
            "items": [{"book_id": None, "section_id": None,
                       "label": "Özel Ders Mat — bölüm 1", "planned_count": 3}]})
        ok = r.status_code == 200
        tdata = r.json()["data"] if ok else {}
        check("3. bağlı görev → 200 + work_block_id + work_block_title set",
              ok and tdata.get("work_block_id") == bid
              and tdata.get("work_block_title") == "Özel Ders Mat — 10 test"
              and tdata.get("work_block_unit") == "test",
              f"{r.status_code} {r.text[:160]}")
        task1_id = tdata.get("id")

        # 4. listele → distributed=3
        found = _block_in_list(c, sid, bid)
        check("4. distributed=3 · remaining=7 · task_count=1",
              found and found["distributed"] == 3 and found["remaining"] == 7
              and found["task_count"] == 1, f"{found}")

        # 5. ikinci bağlı görev (4 test) → distributed=7
        r = c.post(f"/api/v2/teacher/students/{sid}/tasks", json={
            "date": today, "type": "other", "title": "Özel Ders Mat — bölüm 2",
            "work_block_id": bid,
            "items": [{"book_id": None, "section_id": None,
                       "label": "Özel Ders Mat — bölüm 2", "planned_count": 4}]})
        check("5a. ikinci bağlı görev → 200", r.status_code == 200,
              f"{r.status_code} {r.text[:120]}")
        found = _block_in_list(c, sid, bid)
        check("5b. distributed=7 · remaining=3 · task_count=2",
              found and found["distributed"] == 7 and found["remaining"] == 3
              and found["task_count"] == 2, f"{found}")

        # 6. güncelle (total 10→12)
        r = c.post(f"/api/v2/teacher/work-blocks/{bid}", json={"total_count": 12})
        check("6. güncelle total=12 → remaining=5",
              r.status_code == 200 and r.json()["data"]["remaining"] == 5,
              f"{r.status_code} {r.text[:120]}")

        # 7. validasyon
        r = c.post(f"/api/v2/teacher/students/{sid}/work-blocks", json={
            "title": "  ", "total_count": 5})
        check("7a. boş ad → 422 title_required",
              r.status_code == 422 and _code(r) == "title_required", f"{r.status_code}")
        r = c.post(f"/api/v2/teacher/students/{sid}/work-blocks", json={
            "title": "Sıfır", "total_count": 0})
        check("7b. total<1 → 422 invalid_total",
              r.status_code == 422 and _code(r) == "invalid_total", f"{r.status_code}")

        # 8. sahiplik (c2)
        c2 = login("c2")
        check("8a. c2 öğrenci listesini göremez → 404",
              c2.get(f"/api/v2/teacher/students/{sid}/work-blocks").status_code == 404,
              "")
        r = c2.post(f"/api/v2/teacher/work-blocks/{bid}", json={"total_count": 99})
        check("8b. c2 güncelleyemez → 404", r.status_code == 404, f"{r.status_code}")
        r = c2.request("DELETE", f"/api/v2/teacher/work-blocks/{bid}")
        check("8c. c2 silemez → 404", r.status_code == 404, f"{r.status_code}")

        # 9. olmayan/yabancı blok ile görev
        r = c.post(f"/api/v2/teacher/students/{sid}/tasks", json={
            "date": today, "type": "other", "title": "Hatalı",
            "work_block_id": 99999999,
            "items": [{"book_id": None, "section_id": None, "label": "x",
                       "planned_count": 2}]})
        check("9. olmayan blok → 404 work_block_not_found",
              r.status_code == 404 and _code(r) == "work_block_not_found",
              f"{r.status_code}")

        # 10. arşivle
        r = c.post(f"/api/v2/teacher/work-blocks/{bid}/archive")
        check("10a. arşivle → 200", r.status_code == 200, f"{r.status_code}")
        check("10b. varsayılan listede yok", _block_in_list(c, sid, bid) is None, "hâlâ var")
        check("10c. include_archived ile var",
              _block_in_list(c, sid, bid, include_archived=True) is not None, "yok")

        # 11. sil → blok gider, görev kalır (work_block_id NULL)
        r = c.request("DELETE", f"/api/v2/teacher/work-blocks/{bid}")
        check("11a. sil → 200", r.status_code == 200, f"{r.status_code}")
        with SessionLocal() as db:
            exists = db.query(CoachWorkBlock).filter(CoachWorkBlock.id == bid).first()
            t1 = db.query(Task).filter(Task.id == task1_id).first()
        check("11b. blok DB'den silindi", exists is None, "hâlâ var")
        check("11c. bağlı görev KALDI + work_block_id NULL",
              t1 is not None and t1.work_block_id is None,
              f"task={t1} wb={getattr(t1,'work_block_id',None)}")

    finally:
        with SessionLocal() as db:
            ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if ids:
                tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(ids)).all()]
                if tids:
                    db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
                    db.execute(sa_delete(Task).where(Task.id.in_(tids)))
                db.execute(sa_delete(CoachWorkBlock).where(CoachWorkBlock.student_id.in_(ids)))
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
