"""Haftalık İskelet — "konuyu 2. kaynakta bitir" (smoke, 2026-09-30).

Saha (Zeynep Ela · TYT Geometri, Orijinal + 3D): ana kaynakta bir konunun
testleri bitince yeni konuya geçilmez; aynı müfredat konusu 2. kaynakta da
SINIRSIZ bitirilir, sonra ana kaynakta sıradaki konu. Konu satırında da aynı
kural otomatik (koç seçmez). Aynı gün aynı derste okul/dershane + rutin satırı
varsa TEK görev: rutin.

Kitaplar: P (ana) = A[T1, 2 test] · B[T2, 3 test]
          Q (2.)  = a[T1, 3 test] · x[konusuz, 2] · b[T2, 2 test]

Senaryolar:
   1. rutin: P'de A'dan 1 test kaldı → günün 3 testi A:1 + a:2, kitap başına ayrı görev
   2. rutin 3 gün: A bitti → Q·a 3 · P·B 3 · Q·b 2 (konusuz x hiç girmez)
   3. gerekçe kaynak geçişini söyler
   4. aynı gün okul/dershane + rutin → yalnız rutin hayaleti
   5. konu satırı: A bitti → Q·a İLK öneri (seçim işareti yok)
   6. konu satırı: a da bitti → P·B İLK öneri (Q'nun sıradaki b'sine kaymaz)
   7. doğrulama: iki_kaynak biçimi 2. kaynaksız → 422 second_required
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    TaskType,
    Topic,
    User,
    UserRole,
)
from app.models.book import BookType
from app.models.weekly_skeleton import SkeletonGhostAction, WeeklySkeleton
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"sk2_{secrets.token_hex(3)}"
PWD = "SkelTwo!234567x"
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
    print(f"\n=== iskelet iki kaynak smoke — {PFX} ===\n")
    get_login_limiter().reset()
    today = date.today()
    yday = today - timedelta(days=1)
    ids: dict = {}
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                         full_name="İki Kaynak Koç", role=UserRole.TEACHER, is_active=True)
            db.add(coach)
            db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                      full_name="İki Kaynak Öğrenci", role=UserRole.STUDENT, is_active=True,
                      teacher_id=coach.id, grade_level=12)
            db.add(st)
            db.flush()
            geo = Subject(name=f"{PFX} TYT Geometri", teacher_id=coach.id, order=1)
            db.add(geo)
            db.flush()
            t1 = Topic(subject_id=geo.id, name="Dik Üçgen", order=1, teacher_id=coach.id)
            t2 = Topic(subject_id=geo.id, name="İkizkenar Üçgen", order=2, teacher_id=coach.id)
            db.add_all([t1, t2])
            db.flush()
            P = Book(name=f"{PFX} Orijinal Geometri", teacher_id=coach.id, subject_id=geo.id,
                     type=BookType.SORU_BANKASI)
            Q = Book(name=f"{PFX} 3D Geometri", teacher_id=coach.id, subject_id=geo.id,
                     type=BookType.SORU_BANKASI)
            DN = Book(name=f"{PFX} 32'li Problem Denemesi", teacher_id=coach.id,
                      subject_id=geo.id, type=BookType.BRANS_DENEMESI)
            db.add_all([P, Q, DN])
            db.flush()
            secs = {}
            for key, book, label, n, order, topic in [
                ("A", P, "Dik ve Özel Üçgenler", 2, 0, t1),
                ("B", P, "İkizkenar Üçgen", 3, 1, t2),
                ("a", Q, "Dik Üçgen", 3, 0, t1),
                ("x", Q, "Karma Tekrar", 2, 1, None),
                ("b", Q, "İkizkenar", 2, 2, t2),
                ("d1", DN, "Deneme 1 (12 soru)", 1, 0, None),
                ("d2", DN, "Deneme 2 (12 soru)", 1, 1, None),
            ]:
                sec = BookSection(book_id=book.id, label=label, order=order, test_count=n,
                                  topic_id=topic.id if topic else None)
                db.add(sec)
                db.flush()
                secs[key] = sec
            sbs = {}
            for book in (P, Q, DN):
                sbs[book.id] = StudentBook(student_id=st.id, book_id=book.id)
                db.add(sbs[book.id])
            db.flush()
            # Dün P·A'dan 1 test çözüldü → A'da 1 test kaldı
            t = Task(student_id=st.id, date=yday, type=TaskType.TEST, title="x", is_draft=False)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=P.id, book_section_id=secs["A"].id,
                                planned_count=1, completed_count=1))
            progA = SectionProgress(student_book_id=sbs[P.id].id, book_section_id=secs["A"].id,
                                    completed_count=1, reserved_count=0)
            db.add(progA)
            db.commit()
            ids.update(coach=coach.id, st=st.id, geo=geo.id, P=P.id, Q=Q.id,
                       topics=[t1.id, t2.id], books=[P.id, Q.id, DN.id], DN=DN.id,
                       sbs=[s.id for s in sbs.values()], S={k: v.id for k, v in secs.items()},
                       progA=progA.id, sbP=sbs[P.id].id, sbQ=sbs[Q.id].id)

        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        base = f"/api/v2/teacher/students/{ids['st']}/skeleton"
        S = ids["S"]
        wd = today.weekday()

        def save(slots):
            rr = c.post(base, json={"slots": slots})
            assert rr.status_code == 200, rr.text
            return rr

        routine = {"weekday": None, "period": None, "subject_id": ids["geo"], "position": 1,
                   "is_routine": True, "default_count": 3, "book_id": ids["P"],
                   "routine_mode": "iki_kaynak", "second_book_id": ids["Q"]}
        anchor = {"weekday": wd, "period": None, "subject_id": ids["geo"], "position": 0,
                  "is_routine": False, "is_anchor": True, "default_count": 3,
                  "book_id": ids["P"]}
        save([dict(routine, weekday=(today + timedelta(days=i)).weekday()) for i in range(3)]
             + [anchor])

        def preview(start, end=None):
            rr = c.post(f"{base}/ghosts/accept-routine",
                        json={"date": start.isoformat(),
                              "end": (end or start).isoformat(), "dry_run": True})
            return rr.json()["data"]["preview"] if rr.status_code == 200 else rr.text

        def secmap(p):
            return [(it["section_label"], it["count"]) for it in p["items"]]

        # 1 — A'da 1 test kaldı: A:1 + a:2, kitap başına ayrı görev
        p1 = preview(today)
        check("1. günün 3 testi: ana kaynakta A:1 + 2. kaynakta a:2 (iki ayrı görev)",
              isinstance(p1, list) and len(p1) == 2
              and secmap(p1[0]) + secmap(p1[1]) in (
                  [("Dik ve Özel Üçgenler", 1), ("Dik Üçgen", 2)],
                  [("Dik Üçgen", 2), ("Dik ve Özel Üçgenler", 1)]),
              str(p1))

        # 2 — A bitti: 3 gün → a:3 · B:3 · b:2
        with SessionLocal() as db:
            db.get(SectionProgress, ids["progA"]).completed_count = 2
            db.commit()
        p2 = preview(today, today + timedelta(days=2))
        got = [secmap(x) for x in p2] if isinstance(p2, list) else p2
        check("2. A bitti → 2. kaynakta aynı konu (a:3) → ana kaynak B:3 → 2. kaynak b:2",
              got == [[("Dik Üçgen", 3)], [("İkizkenar Üçgen", 3)], [("İkizkenar", 2)]], str(got))
        check("2b. konusuz 2. kaynak bölümü (Karma Tekrar) zincire girmez",
              isinstance(p2, list) and not any(
                  it["section_label"] == "Karma Tekrar" for x in p2 for it in x["items"]))

        # 3 — gerekçe
        g = c.get(f"{base}/ghosts", params={"start": today.isoformat(), "end": today.isoformat()}).json()
        gh = g["days"][0]["ghosts"]
        rch = next((x["chips"][0] for x in gh if x["is_routine"] and x["chips"]), None)
        check("3. rutin gerekçesi: konu 2. kaynakta bitiriliyor",
              bool(rch and "2. kaynakta" in rch["reason"]), str(rch))

        # 4 — okul/dershane + rutin aynı gün → tek hayalet
        check("4. aynı gün okul/dershane + rutin → yalnız rutin hayaleti",
              len(gh) == 1 and gh[0]["is_routine"] and not gh[0]["is_anchor"],
              str([(x["is_routine"], x["is_anchor"]) for x in gh]))

        # 5 — konu satırı: A bitti → a ilk öneri
        topic_slot = {"weekday": wd, "period": None, "subject_id": ids["geo"], "position": 0,
                      "is_routine": False, "default_count": 3, "book_id": ids["P"],
                      "second_book_id": ids["Q"]}
        save([topic_slot])
        g5 = c.get(f"{base}/ghosts", params={"start": today.isoformat(), "end": today.isoformat()}).json()
        ch5 = g5["days"][0]["ghosts"][0]["chips"]
        check("5. konu satırı: A bitti → 2. kaynakta aynı konu (a) İLK öneri, seçim işareti yok",
              bool(ch5) and ch5[0]["section_id"] == S["a"] and ch5[0]["kind"] == "second"
              and not g5["days"][0]["ghosts"][0]["source_choice"],
              str([(x["section_label"], x["kind"]) for x in ch5]))

        # 6 — a da bitti → P·B ilk öneri (Q'nun sıradaki b'si değil)
        with SessionLocal() as db:
            t = Task(student_id=ids["st"], date=yday, type=TaskType.TEST, title="x", is_draft=False)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=ids["Q"], book_section_id=S["a"],
                                planned_count=3, completed_count=3))
            db.add(SectionProgress(student_book_id=ids["sbQ"], book_section_id=S["a"],
                                   completed_count=3, reserved_count=0))
            db.commit()
        g6 = c.get(f"{base}/ghosts", params={"start": today.isoformat(), "end": today.isoformat()}).json()
        ch6 = g6["days"][0]["ghosts"][0]["chips"]
        check("6. konu iki kaynakta da bitti → ana kaynakta sıradaki konu (B) İLK öneri",
              bool(ch6) and ch6[0]["section_id"] == S["B"] and "iki kaynakta" in ch6[0]["reason"],
              str([(x["section_label"], x["reason"]) for x in ch6]))

        # 7 — doğrulama
        bad = c.post(base, json={"slots": [dict(routine, weekday=wd, second_book_id=None)]})
        check("7. iki_kaynak biçimi 2. kaynaksız → 422 second_required",
              bad.status_code == 422 and bad.json()["detail"]["code"] == "second_required",
              f"{bad.status_code} {bad.text[:200]}")

        # 8 — deneme kitabı: yalnız rutinde kaynak, adet boşsa günde 1 deneme, sırayla
        opts = c.get(base).json()["books"]
        dn_opt = next((b for b in opts if b["id"] == ids["DN"]), None)
        check("8a. deneme kitabı kaynak listesinde (is_deneme işaretli)",
              bool(dn_opt and dn_opt["is_deneme"]), str(dn_opt))
        r8 = c.post(base, json={"slots": [{
            "weekday": wd, "period": None, "subject_id": ids["geo"], "position": 0,
            "is_routine": True, "default_count": None, "book_id": ids["DN"],
            "routine_mode": "karma"}]})
        p8 = preview(today, today + timedelta(days=7))
        got8 = [secmap(x) for x in p8] if isinstance(p8, list) else p8
        check("8b. deneme rutini kaydedilir · biçim sırayla · adet boş → günde 1 deneme",
              r8.status_code == 200 and r8.json()["data"]["slots"][0]["routine_mode"] == "sirali"
              and got8 == [[("Deneme 1 (12 soru)", 1)], [("Deneme 2 (12 soru)", 1)]],
              f"{r8.status_code} {got8}")
        r8c = c.post(base, json={"slots": [{
            "weekday": wd, "period": None, "subject_id": ids["geo"], "position": 0,
            "is_routine": False, "is_anchor": True, "default_count": None, "book_id": ids["DN"]}]})
        g8 = c.get(f"{base}/ghosts", params={"start": today.isoformat(), "end": today.isoformat()}).json()
        ch8 = (g8["days"][0]["ghosts"] or [{}])[0].get("chips", [])
        check("8c. deneme kitabı okul/dershane (ve konu) satırında da kaynak · öneri sıradaki deneme (1)",
              r8c.status_code == 200 and bool(ch8)
              and [(it["section_label"], it["count"]) for it in (ch8[0].get("items") or [])]
              == [("Deneme 1 (12 soru)", 1)] and "deneme" in ch8[0]["reason"],
              f"{r8c.status_code} {ch8[:1]}")
        # 8d — deneme bölümleri başka konu satırlarının önerisine sızmaz
        with SessionLocal() as db:
            t = Task(student_id=ids["st"], date=yday, type=TaskType.TEST, title="x", is_draft=False)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=ids["DN"], book_section_id=S["d1"],
                                planned_count=1, completed_count=0))
            db.commit()
        save([topic_slot])
        g8d = c.get(f"{base}/ghosts", params={"start": today.isoformat(), "end": today.isoformat()}).json()
        ch8d = g8d["days"][0]["ghosts"][0]["chips"]
        check("8d. deneme bölümü Orijinal konu satırının önerilerine sızmaz",
              not any(x["book_id"] == ids["DN"] for x in ch8d), str([x["section_label"] for x in ch8d]))
    finally:
        with SessionLocal() as db:
            if ids.get("st"):
                db.execute(sa_delete(SkeletonGhostAction).where(SkeletonGhostAction.student_id == ids["st"]))
                db.execute(sa_delete(WeeklySkeleton).where(WeeklySkeleton.student_id == ids["st"]))
                tids = [t.id for t in db.query(Task).filter(Task.student_id == ids["st"])]
                if tids:
                    db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
                db.execute(sa_delete(Task).where(Task.student_id == ids["st"]))
                db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(ids["sbs"])))
                db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(ids["sbs"])))
                db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
                db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
                db.execute(sa_delete(Topic).where(Topic.id.in_(ids["topics"])))
                db.execute(sa_delete(Subject).where(Subject.id == ids["geo"]))
                db.execute(sa_delete(User).where(User.id.in_([ids["st"], ids["coach"]])))
                db.commit()
    print(f"\n=== {passed}/{passed + len(failed)} geçti ===")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
