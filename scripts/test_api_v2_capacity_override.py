"""Kapasite: engelden uyarıya — smoke (P1, 2026-09-07).

KOÇ GERİ BİLDİRİMİ: "bir konuda 4 test girdiğimde öğrencinin testi kalmadığı
veya önceden çözdüğü zaman program kurarken sorun oluyor." Canlı veride 462
bölümün kapasitesi dolu ve konuların %66'sında tek kaynak var → koç tıkanıyor.

KURAL: kitabın test sayısı bir YARDIMCI, otorite değil. Koç bilinçli
"yine de ata" derse (allow_over_capacity) envanter engel olmaz; sayaç yine
tutulur, ızgarada fazladan kutu görünür, uyarı koça döner.

Senaryolar:
   1. Bayraksız dolu bölüme atama → 422 (ESKİ DAVRANIŞ KORUNUR)
   2. Bayraklı dolu bölüme atama → 200 + uyarı metni + görev gerçekten oluştu
   3. Rezerv sayacı aşımı DOĞRU yansıtır (kapasitenin üstüne çıkar)
   4. Kısmi aşım: 2 boşluk varken 5 test → uyarı "3 test aşıldı" der
   5. Aşım YOKken bayrak verilse de uyarı ÜRETİLMEZ (gürültü yok)
   6. Mevcut göreve kalem ekleme: bayraksız 422, bayraklı 200 + uyarı
   7. Kalem sayısını artırma (patch): bayraksız 422, bayraklı 200 + uyarı
   8. Izgara (book-grid) aşımda sahte "sayaç uyumsuzluğu" ÜRETMEZ
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import secrets
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    User,
    UserRole,
)
from app.models.book import BookType
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"cap_{secrets.token_hex(3)}"
PWDH = "CapTest!2345"

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


def main() -> int:
    print(f"\n=== kapasite aşımı smoke — {PFX} ===\n")
    get_login_limiter().reset()
    ids: dict[str, int] = {}
    try:
        with SessionLocal() as db:
            coach = User(
                email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWDH),
                full_name="Kapasite Koç", role=UserRole.TEACHER, is_active=True,
            )
            db.add(coach)
            db.flush()
            st = User(
                email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWDH),
                full_name="Kapasite Öğrenci", role=UserRole.STUDENT,
                is_active=True, teacher_id=coach.id, grade_level=12,
            )
            db.add(st)
            db.flush()

            subj = Subject(name=f"{PFX} Matematik", teacher_id=coach.id, order=1)
            db.add(subj)
            db.flush()
            book = Book(
                name=f"{PFX} Soru Bankası", teacher_id=coach.id,
                subject_id=subj.id, type=BookType.SORU_BANKASI,
            )
            db.add(book)
            db.flush()
            # DOLU bölüm: 4 test, 4'ü çözülmüş → kalan 0 (koçun tıkandığı hâl)
            full_sec = BookSection(book_id=book.id, label="Türev", order=1, test_count=4)
            # KISMİ bölüm: 5 test, 3'ü çözülmüş → kalan 2
            part_sec = BookSection(book_id=book.id, label="İntegral", order=2, test_count=5)
            # BOŞ bölüm: 6 test, hiç kullanılmamış → kalan 6
            free_sec = BookSection(book_id=book.id, label="Limit", order=3, test_count=6)
            db.add_all([full_sec, part_sec, free_sec])
            db.flush()
            sb = StudentBook(student_id=st.id, book_id=book.id)
            db.add(sb)
            db.flush()
            db.add_all([
                SectionProgress(
                    student_book_id=sb.id, book_section_id=full_sec.id,
                    reserved_count=0, completed_count=4,
                ),
                SectionProgress(
                    student_book_id=sb.id, book_section_id=part_sec.id,
                    reserved_count=0, completed_count=3,
                ),
            ])
            ids.update(
                coach=coach.id, student=st.id, subject=subj.id, book=book.id,
                full_sec=full_sec.id, part_sec=part_sec.id, free_sec=free_sec.id,
            )
            db.commit()

        c = TestClient(app)
        r = c.post(
            "/api/v2/auth/login",
            json={"email": f"{PFX}_t@test.invalid", "password": PWDH},
        )
        assert r.status_code == 200, r.text
        sid = ids["student"]
        day = (date.today() + timedelta(days=1)).isoformat()

        def add_task(section_id, count, allow, title="Kapasite testi"):
            item = {
                "book_id": ids["book"], "section_id": section_id,
                "planned_count": count,
            }
            if allow:
                item["allow_over_capacity"] = True
            return c.post(
                f"/api/v2/teacher/students/{sid}/tasks",
                json={
                    "date": day, "type": "test", "title": title,
                    "is_draft": False, "items": [item],
                },
            )

        # ---- 1. Bayraksız dolu bölüm → ESKİ davranış (422)
        r1 = add_task(ids["full_sec"], 3, allow=False)
        check(
            "1. bayraksız dolu bölüme atama → 422 (eski davranış korunur)",
            r1.status_code == 422, f"{r1.status_code} {r1.text[:120]}",
        )

        # ---- 2. Bayraklı dolu bölüm → 200 + uyarı + görev gerçekten oluştu
        r2 = add_task(ids["full_sec"], 3, allow=True)
        body2 = r2.json() if r2.status_code == 200 else {}
        warns2 = body2.get("warnings") or []
        task_id = (body2.get("data") or {}).get("id")
        check(
            "2. bayraklı dolu bölüme atama → 200 + uyarı + görev oluştu",
            r2.status_code == 200 and len(warns2) == 1
            and "3 test aşıldı" in warns2[0] and bool(task_id),
            f"{r2.status_code} warns={warns2}",
        )

        # ---- 3. Rezerv sayacı aşımı doğru yansıtıyor mu
        with SessionLocal() as db:
            sp = (
                db.query(SectionProgress)
                .filter(SectionProgress.book_section_id == ids["full_sec"])
                .first()
            )
            res, comp = (sp.reserved_count, sp.completed_count) if sp else (-1, -1)
        check(
            "3. sayaç aşımı yansıtır (rezerv 3 · çözülen 4 · kapasite 4)",
            res == 3 and comp == 4, f"reserved={res} completed={comp}",
        )

        # ---- 4. Kısmi aşım: 2 boşluk varken 5 test → "3 test aşıldı"
        r4 = add_task(ids["part_sec"], 5, allow=True, title="Kısmi aşım")
        warns4 = (r4.json().get("warnings") or []) if r4.status_code == 200 else []
        check(
            "4. kısmi aşım uyarısı doğru sayıyı söyler (3 test)",
            r4.status_code == 200 and bool(warns4)
            and "3 test aşıldı" in warns4[0] and "2/5 boştu" in warns4[0],
            f"{r4.status_code} {warns4}",
        )

        # ---- 5. Aşım yokken bayrak verilse de uyarı üretilmez
        r5 = add_task(ids["free_sec"], 2, allow=True, title="Aşımsız")
        warns5 = (r5.json().get("warnings") or []) if r5.status_code == 200 else []
        check(
            "5. aşım yokken bayrakla da uyarı ÜRETİLMEZ (gürültü yok)",
            r5.status_code == 200 and warns5 == [], f"{r5.status_code} {warns5}",
        )

        # ---- 6. Mevcut göreve kalem ekleme
        r6a = c.post(
            f"/api/v2/teacher/tasks/{task_id}/items",
            json={
                "book_id": ids["book"], "section_id": ids["full_sec"],
                "planned_count": 2,
            },
        )
        r6b = c.post(
            f"/api/v2/teacher/tasks/{task_id}/items",
            json={
                "book_id": ids["book"], "section_id": ids["full_sec"],
                "planned_count": 2, "allow_over_capacity": True,
            },
        )
        warns6 = (r6b.json().get("warnings") or []) if r6b.status_code == 200 else []
        check(
            "6. kalem ekleme: bayraksız 422 · bayraklı 200 + uyarı",
            r6a.status_code == 422 and r6b.status_code == 200 and bool(warns6),
            f"{r6a.status_code}/{r6b.status_code} {warns6}",
        )

        # ---- 7. Kalem sayısını artırma (patch)
        with SessionLocal() as db:
            item = (
                db.query(TaskBookItem)
                .filter(
                    TaskBookItem.task_id == task_id,
                    TaskBookItem.book_section_id == ids["full_sec"],
                )
                .order_by(TaskBookItem.id.asc())
                .first()
            )
            item_id = item.id if item else None
        r7a = c.patch(
            f"/api/v2/teacher/tasks/{task_id}/items/{item_id}",
            json={"planned_count": 9},
        )
        r7b = c.patch(
            f"/api/v2/teacher/tasks/{task_id}/items/{item_id}",
            json={"planned_count": 9, "allow_over_capacity": True},
        )
        warns7 = (r7b.json().get("warnings") or []) if r7b.status_code == 200 else []
        check(
            "7. kalem sayısı artırma: bayraksız 422 · bayraklı 200 + uyarı",
            r7a.status_code == 422 and r7b.status_code == 200 and bool(warns7),
            f"{r7a.status_code}/{r7b.status_code} {warns7}",
        )

        # ---- 8. Izgara aşımda sahte "sayaç uyumsuzluğu" üretmemeli:
        #         kayıtlı sayaç == slotlardan türetilen sayı olmalı
        r8 = c.get(f"/api/v2/teacher/students/{sid}/books/{ids['book']}/book-grid")
        ok8 = False
        detail8 = f"{r8.status_code}"
        if r8.status_code == 200:
            secs = r8.json().get("sections") or []
            row = next(
                (s for s in secs if s.get("section_id") == ids["full_sec"]), None
            )
            if row:
                cells = row.get("cells") or []
                comp_cells = sum(1 for x in cells if x.get("state") == "DONE")
                res_cells = sum(1 for x in cells if x.get("state") == "RESERVED")
                ok8 = (
                    comp_cells == row.get("completed")
                    and res_cells == row.get("reserved")
                    and len(cells) > row.get("test_count", 0)
                )
                detail8 = (
                    f"kayıtlı {row.get('completed')}/{row.get('reserved')} "
                    f"slot {comp_cells}/{res_cells} kutu={len(cells)} "
                    f"kapasite={row.get('test_count')}"
                )
        check("8. ızgara aşımda sahte 'sayaç uyumsuzluğu' üretmez", ok8, detail8)

    finally:
        with SessionLocal() as db:
            uid = [v for k, v in ids.items() if k in ("coach", "student")]
            if uid:
                tids = [
                    r[0] for r in db.query(Task.id)
                    .filter(Task.student_id.in_(uid)).all()
                ]
                if tids:
                    db.execute(
                        sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids))
                    )
                    db.execute(sa_delete(Task).where(Task.id.in_(tids)))
            if ids.get("book"):
                sbids = [
                    r[0] for r in db.query(StudentBook.id)
                    .filter(StudentBook.book_id == ids["book"]).all()
                ]
                if sbids:
                    db.execute(
                        sa_delete(SectionProgress)
                        .where(SectionProgress.student_book_id.in_(sbids))
                    )
                    db.execute(
                        sa_delete(StudentBook).where(StudentBook.id.in_(sbids))
                    )
                db.execute(
                    sa_delete(BookSection).where(BookSection.book_id == ids["book"])
                )
                db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            if ids.get("subject"):
                db.execute(sa_delete(Subject).where(Subject.id == ids["subject"]))
            if uid:
                db.execute(sa_delete(User).where(User.id.in_(uid)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
