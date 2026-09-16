"""Görev bağlantısı (video linki) + otomatik başlık tazeleme smoke (2026-09-16).

Saha: mobil/web öğrenci "videoyu izle" diye tıklayacak bir şey göremiyordu —
`Task.link_url` v2'de hiç dolmuyor/serialize edilmiyordu; web formu URL'i
notes'a gömüyordu. Koç kalem sayısı değiştirince/kalem ekleyince de başlık
eski sayıyı/bölümü söylüyordu.

Senaryolar:
   1. Eski istemci: video görevi, URL notes'ta → yanıt link_url = o URL, kolon dolar
   2. Yeni istemci: link_url açık + notes URL'siz → link_url alan, notes temiz
   3. Geçersiz şema (javascript:) → 422 invalid_link_url
   4. Test görevi (kitaplı) → link_url None
   5. Eski kayıt (kolon boş, URL notes'ta) → koç gün görünümünde link_url dolu
   6. Öğrenci gün görünümü aynı görevde link_url dolu; test görevinde None
   7. Koç notu düzenler (URL'i notes'tan siler) → link_url KORUNUR (kolona taşındı)
   8. PATCH link_url="" → bağlantı kaldırılır (None)
   9. PATCH link_url="youtu.be/x" (şemasız) → "https://youtu.be/x"
  10. Koç hafta görünümü de link_url taşır
  11. Kalem sayısı değişince otomatik başlık sayıyı tazeler ("Bölüm 1: 3 test")
  12. Göreve ikinci bölüm eklenince başlık iki bölümü de sayar
  13. Koçun ELLE yazdığı başlık kalem değişse de korunur
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    BookType,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"lnk_{secrets.token_hex(3)}"
PASSWORD = "TestPass123!@xyz"
T1 = f"{PFX}_t1@test.invalid"
S1 = f"{PFX}_s1@test.invalid"

passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label} — {detail}")


def _seed() -> dict:
    with SessionLocal() as db:
        t1 = User(email=T1, password_hash=hash_password(PASSWORD),
                  full_name=f"{PFX} Koç", role=UserRole.TEACHER, is_active=True)
        db.add(t1)
        db.flush()
        s1 = User(email=S1, password_hash=hash_password(PASSWORD),
                  full_name=f"{PFX} Öğr", role=UserRole.STUDENT,
                  teacher_id=t1.id, is_active=True, grade_level=8)
        db.add(s1)
        db.flush()
        subj = Subject(name=f"{PFX} Fizik", teacher_id=t1.id)
        db.add(subj)
        db.flush()
        book = Book(name=f"{PFX} Soru Bankası", subject_id=subj.id,
                    teacher_id=t1.id, type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        secs = []
        for i, cnt in enumerate((10, 10), start=1):
            sec = BookSection(book_id=book.id, label=f"Bölüm {i}", order=i, test_count=cnt)
            db.add(sec)
            db.flush()
            secs.append(sec.id)
        sb = StudentBook(student_id=s1.id, book_id=book.id)
        db.add(sb)
        db.flush()
        # Eski kayıt: URL yalnız notes'ta, link_url kolonu BOŞ
        legacy = Task(student_id=s1.id, title=f"{PFX} Fizik · Vektörler videosu",
                      type=TaskType.VIDEO, date=date.today(), status=TaskStatus.PENDING,
                      is_draft=False, notes="Vektörler giriş\nhttps://example.com/v/legacy")
        db.add(legacy)
        db.commit()
        return {"t1": t1.id, "s1": s1.id, "book": book.id, "secs": secs,
                "legacy": legacy.id, "today": date.today().isoformat()}


def _cleanup(ids: dict) -> None:
    with SessionLocal() as db:
        uids = [ids["t1"], ids["s1"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(uids)).all()]
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        sb_ids = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(uids)).all()]
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sb_ids)))
        db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sb_ids)))
        db.execute(sa_delete(BookSection).where(BookSection.id.in_(ids["secs"])))
        db.execute(sa_delete(Book).where(Book.teacher_id.in_(uids)))
        db.execute(sa_delete(Subject).where(Subject.teacher_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def main() -> int:
    ids = _seed()
    client = TestClient(app)
    get_login_limiter().reset()
    r = client.post("/api/v2/auth/login", json={"email": T1, "password": PASSWORD})
    assert r.status_code == 200, f"login {r.status_code}"
    sid, today = ids["s1"], ids["today"]
    base = f"/api/v2/teacher/students/{sid}/tasks"

    try:
        # 1. eski istemci — URL notes'ta
        r = client.post(base, json={
            "date": today, "type": "video", "title": "Fizik · video",
            "notes": "Trigonometri giriş\nhttps://youtu.be/abc123", "items": [], "is_draft": False,
        })
        d1 = r.json().get("data", {}) if r.status_code == 200 else {}
        check("1. URL notes'ta → link_url çıkarıldı",
              r.status_code == 200 and d1.get("link_url") == "https://youtu.be/abc123",
              f"{r.status_code} {str(r.json())[:200]}")
        with SessionLocal() as db:
            t = db.get(Task, d1.get("id", 0))
            check("1b. kolon dolduruldu (Task.link_url)",
                  t is not None and t.link_url == "https://youtu.be/abc123",
                  str(getattr(t, "link_url", None)))
        # 2. yeni istemci — açık alan
        r = client.post(base, json={
            "date": today, "type": "video", "title": "Fizik · Kuvvet videosu",
            "notes": "Kuvvet ve hareket", "link_url": "https://www.youtube.com/watch?v=xyz",
            "items": [], "is_draft": False,
        })
        d2 = r.json().get("data", {}) if r.status_code == 200 else {}
        check("2. açık link_url + temiz notes",
              r.status_code == 200 and d2.get("link_url") == "https://www.youtube.com/watch?v=xyz"
              and d2.get("notes") == "Kuvvet ve hareket",
              str(d2)[:200])
        # 3. geçersiz şema
        r = client.post(base, json={
            "date": today, "type": "video", "title": "x", "link_url": "javascript:alert(1)",
            "items": [], "is_draft": False,
        })
        check("3. javascript: şeması → 422 invalid_link_url",
              r.status_code == 422 and r.json().get("detail", {}).get("code") == "invalid_link_url",
              f"{r.status_code} {str(r.json())[:200]}")
        # 4. test görevi
        r = client.post(base, json={
            "date": today, "type": "test", "title": "Görev", "is_draft": False,
            "items": [{"book_id": ids["book"], "section_id": ids["secs"][0], "planned_count": 2}],
        })
        d4 = r.json().get("data", {}) if r.status_code == 200 else {}
        check("4. test görevi → link_url None", r.status_code == 200 and d4.get("link_url") is None,
              f"{r.status_code} {str(d4)[:200]}")
        test_task_id = d4.get("id")
        # 5. eski kayıt koç gün görünümü
        r = client.get(f"/api/v2/teacher/students/{sid}/day", params={"date": today})
        day_tasks = {t["id"]: t for t in r.json().get("tasks", [])} if r.status_code == 200 else {}
        leg = day_tasks.get(ids["legacy"], {})
        check("5. eski kayıt (kolon boş) → koç günde link_url dolu",
              leg.get("link_url") == "https://example.com/v/legacy", str(leg)[:200])
        # 10. hafta
        r = client.get(f"/api/v2/teacher/students/{sid}/week", params={"start": today})
        wk_tasks = {t["id"]: t for dd in r.json().get("days", []) for t in dd.get("tasks", [])} if r.status_code == 200 else {}
        check("10. koç hafta görünümü link_url taşır",
              wk_tasks.get(ids["legacy"], {}).get("link_url") == "https://example.com/v/legacy"
              and wk_tasks.get(d2.get("id"), {}).get("link_url") == "https://www.youtube.com/watch?v=xyz",
              str({k: v.get("link_url") for k, v in wk_tasks.items()})[:200])
        # 7. not düzenlemesi linki koparmaz
        r = client.patch(f"/api/v2/teacher/tasks/{ids['legacy']}", json={"notes": "Vektörler giriş (güncel)"})
        d7 = r.json().get("data", {}) if r.status_code == 200 else {}
        check("7. notes'tan URL silinse de link_url korunur",
              r.status_code == 200 and d7.get("link_url") == "https://example.com/v/legacy"
              and d7.get("notes") == "Vektörler giriş (güncel)",
              f"{r.status_code} {str(d7)[:200]}")
        # 9. şemasız link normalize
        r = client.patch(f"/api/v2/teacher/tasks/{ids['legacy']}", json={"link_url": "youtu.be/zzz"})
        d9 = r.json().get("data", {}) if r.status_code == 200 else {}
        check("9. şemasız bağlantı https:// ile normalize edilir",
              r.status_code == 200 and d9.get("link_url") == "https://youtu.be/zzz", str(d9)[:200])
        # 8. link kaldır
        r = client.patch(f"/api/v2/teacher/tasks/{ids['legacy']}", json={"link_url": ""})
        d8 = r.json().get("data", {}) if r.status_code == 200 else {}
        check("8. link_url='' → bağlantı kaldırıldı", r.status_code == 200 and d8.get("link_url") is None,
              str(d8)[:200])

        # 11-13. otomatik başlık tazeleme
        with SessionLocal() as db:
            item_id = db.query(TaskBookItem.id).filter(TaskBookItem.task_id == test_task_id).scalar()
        r = client.patch(f"/api/v2/teacher/tasks/{test_task_id}/items/{item_id}", json={"planned_count": 3})
        d11 = r.json().get("data", {}) if r.status_code == 200 else {}
        check("11. kalem sayısı 2→3 → başlık 'Bölüm 1: 3 test'",
              r.status_code == 200 and d11.get("title", "").endswith("Bölüm 1: 3 test"),
              f"{r.status_code} {d11.get('title')}")
        r = client.post(f"/api/v2/teacher/tasks/{test_task_id}/items",
                        json={"book_id": ids["book"], "section_id": ids["secs"][1], "planned_count": 2})
        d12 = r.json().get("data", {}) if r.status_code == 200 else {}
        check("12. ikinci bölüm eklenince başlık iki bölümü sayar",
              r.status_code == 200 and "Bölüm 1: 3 test" in d12.get("title", "")
              and "Bölüm 2: 2 test" in d12.get("title", ""),
              f"{r.status_code} {d12.get('title')}")
        # 13. elle başlık korunur
        r = client.patch(f"/api/v2/teacher/tasks/{test_task_id}", json={"title": "Koçun özel başlığı"})
        check("13a. elle başlık kaydedildi", r.status_code == 200 and r.json()["data"]["title"] == "Koçun özel başlığı",
              str(r.json())[:200])
        r = client.patch(f"/api/v2/teacher/tasks/{test_task_id}/items/{item_id}", json={"planned_count": 4})
        d13 = r.json().get("data", {}) if r.status_code == 200 else {}
        check("13b. kalem değişse de elle başlık korunur",
              r.status_code == 200 and d13.get("title") == "Koçun özel başlığı", f"{r.status_code} {d13.get('title')}")

        # 6. öğrenci gün görünümü
        get_login_limiter().reset()
        sc = TestClient(app)
        r = sc.post("/api/v2/auth/login", json={"email": S1, "password": PASSWORD})
        assert r.status_code == 200, f"student login {r.status_code}"
        r = sc.get("/api/v2/student/day", params={"date": today})
        st_tasks = {t["id"]: t for t in r.json().get("tasks", [])} if r.status_code == 200 else {}
        check("6. öğrenci günde video görevi link_url dolu, test görevi None",
              r.status_code == 200
              and st_tasks.get(d1.get("id"), {}).get("link_url") == "https://youtu.be/abc123"
              and st_tasks.get(d2.get("id"), {}).get("link_url") == "https://www.youtube.com/watch?v=xyz"
              and st_tasks.get(test_task_id, {}).get("link_url") is None,
              str({k: v.get("link_url") for k, v in st_tasks.items()})[:300])
    finally:
        _cleanup(ids)

    print(f"\n=== SONUÇ: {passed} PASS / {len(failed)} FAIL ===")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
