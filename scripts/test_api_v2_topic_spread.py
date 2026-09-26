"""İskelet F2-3 — çapa satırı + konuyu yay (smoke, 2026-09-26).

Koç kuralları:
  · birim KONU; hedef adet bir kitapta yetmezse aynı konudaki başka kitaptan
    tamamlanır (gün × kitap ayrı görev)
  · ÇAPAYA ÖNCELİK: gün boşluğu = kapasite − yazılı − o günün çapa payı
  · yayma bir sonraki AYNI dersin çapa gününden önce biter
  · kapasite geçmişten öğrenilir, koç düzeltir

Senaryolar:
   1. Hayalette çapa işareti (is_anchor) + iskelet yanıtında kapasite tablosu
   2. Fizik yayma: T+1 çapa payı yüzünden atlanır · T+3 dolu → atlanır ·
      T+2 ve T+4'e 3'er · pencere T+5 (sonraki Fizik) öncesi biter + gerekçe
   3. Kitaplar arası tamamlama: A'da 4 kaldı → gün1 A 3 · gün2 A 1 + B 2
   4. Uygula: gün2 → iki görev (kitap başına), ileri tarih taslak
   5. Konu o gün zaten varsa gün atlanır
   6. Sığmayan kısım leftover olarak söylenir
   7. Kapatılmış konu → boş önizleme
   8. Doğrulama: konu yok 422 · geçmiş gün 422 · yabancı bölüm 404
   9. Öğrenilen kapasite: yazılı testlerin %90'lık dilimi
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
    TopicClosure,
    User,
    UserRole,
)
from app.models.book import BookType
from app.models.weekly_skeleton import SkeletonGhostAction, WeeklySkeleton
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"tsp_{secrets.token_hex(3)}"
PWD = "TopSp!234567xy"
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
    print(f"\n=== konuyu yay smoke — {PFX} ===\n")
    get_login_limiter().reset()
    T = date.today()
    D = [T + timedelta(days=i) for i in range(15)]
    ids: dict = {}
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                         full_name="Yay Koç", role=UserRole.TEACHER, is_active=True)
            db.add(coach)
            db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                      full_name="Yay Öğrenci", role=UserRole.STUDENT, is_active=True,
                      teacher_id=coach.id, grade_level=12)
            db.add(st)
            db.flush()
            fiz = Subject(name=f"{PFX} Fizik", teacher_id=coach.id, order=1)
            mat = Subject(name=f"{PFX} Matematik", teacher_id=coach.id, order=2)
            kim = Subject(name=f"{PFX} Kimya", teacher_id=coach.id, order=3)
            db.add_all([fiz, mat, kim])
            db.flush()
            t_kuv = Topic(subject_id=fiz.id, name="Kuvvet", order=1, teacher_id=coach.id)
            t_oran = Topic(subject_id=mat.id, name="Oran Orantı", order=1, teacher_id=coach.id)
            t_sayi = Topic(subject_id=mat.id, name="Sayılar", order=2, teacher_id=coach.id)
            t_mol = Topic(subject_id=kim.id, name="Mol", order=1, teacher_id=coach.id)
            t_kapali = Topic(subject_id=mat.id, name="Kapalı", order=3, teacher_id=coach.id)
            db.add_all([t_kuv, t_oran, t_sayi, t_mol, t_kapali])
            db.flush()
            bf = Book(name=f"{PFX} Fizik SB", teacher_id=coach.id, subject_id=fiz.id, type=BookType.SORU_BANKASI)
            ba = Book(name=f"{PFX} Bilgi Sarmal", teacher_id=coach.id, subject_id=mat.id, type=BookType.SORU_BANKASI)
            bb = Book(name=f"{PFX} 345", teacher_id=coach.id, subject_id=mat.id, type=BookType.SORU_BANKASI)
            bk = Book(name=f"{PFX} Kimya SB", teacher_id=coach.id, subject_id=kim.id, type=BookType.SORU_BANKASI)
            db.add_all([bf, ba, bb, bk])
            db.flush()
            secs = {}
            for key, book, topic, total, order in (
                ("kuv", bf, t_kuv, 6, 1), ("oranA", ba, t_oran, 6, 1), ("sayiA", ba, t_sayi, 40, 2),
                ("kapA", ba, t_kapali, 10, 3), ("oranB", bb, t_oran, 10, 1), ("mol", bk, t_mol, 10, 1),
            ):
                secs[key] = BookSection(book_id=book.id, label=f"{topic.name} Testleri",
                                        order=order, test_count=total, topic_id=topic.id)
            db.add_all(secs.values())
            db.flush()
            sbs = {}
            for b in (bf, ba, bb, bk):
                sbs[b.id] = StudentBook(student_id=st.id, book_id=b.id)
                db.add(sbs[b.id])
            db.flush()
            used = {k: 0 for k in secs}

            def task(d, key, n):
                t = Task(student_id=st.id, date=d, type=TaskType.TEST, title="x", is_draft=d > T)
                db.add(t)
                db.flush()
                s = secs[key]
                db.add(TaskBookItem(task_id=t.id, book_id=s.book_id, book_section_id=s.id,
                                    planned_count=n))
                used[key] += n
                db.flush()

            # Bilgi Sarmal Oran Orantı başlanmış: 2 çözülmüş → 4 kaldı
            task(T - timedelta(days=2), "oranA", 2)
            # gelecekteki yük: T+1'de 5 test, T+3'te 9 test (Sayılar)
            task(D[1], "sayiA", 5)
            task(D[3], "sayiA", 9)
            for k, n in used.items():
                s = secs[k]
                db.add(SectionProgress(student_book_id=sbs[s.book_id].id, book_section_id=s.id,
                                       completed_count=n if k == "oranA" else 0,
                                       reserved_count=0 if k == "oranA" else n))
            db.add(TopicClosure(student_id=st.id, topic_id=t_kapali.id, closed_by_id=coach.id))
            ids.update(coach=coach.id, st=st.id, fiz=fiz.id, mat=mat.id, kim=kim.id,
                       books=[bf.id, ba.id, bb.id, bk.id], sbs=[x.id for x in sbs.values()],
                       topics=[t_kuv.id, t_oran.id, t_sayi.id, t_mol.id, t_kapali.id],
                       t_kuv=t_kuv.id, t_oran=t_oran.id, t_kapali=t_kapali.id,
                       secs={k: v.id for k, v in secs.items()}, ba=ba.id, bb=bb.id)
            db.commit()

        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        base = f"/api/v2/teacher/students/{ids['st']}"
        S = ids["secs"]

        # iskelet: T Fizik çapa · T+1 Kimya çapa (adet 3) · T+5 Fizik çapa; kapasite 10
        slots = [
            {"weekday": D[0].weekday(), "subject_id": ids["fiz"], "is_anchor": True, "position": 0},
            {"weekday": D[1].weekday(), "subject_id": ids["kim"], "is_anchor": True,
             "default_count": 3, "position": 0},
            {"weekday": D[5].weekday(), "subject_id": ids["fiz"], "is_anchor": True, "position": 0},
        ]
        slots = [dict({"period": None, "is_routine": False, "default_count": None}, **x) for x in slots]
        r0 = c.post(f"{base}/skeleton", json={"slots": slots,
                                              "day_capacity": {str(i): 10 for i in range(7)}})
        sk0 = r0.json()["data"]
        g1 = c.get(f"{base}/skeleton/ghosts", params={"start": D[1].isoformat(), "end": D[1].isoformat()}).json()
        kg = next((x for x in g1["days"][0]["ghosts"] if x["subject_id"] == ids["kim"]), None)
        cap_eff = {x["weekday"]: x["effective"] for x in sk0["capacity"]}
        check("1. çapa hayaleti is_anchor + kapasite tablosunda düzeltme etkin",
              bool(kg and kg["is_anchor"]) and all(cap_eff[i] == 10 for i in range(7))
              and any(s["is_anchor"] for s in sk0["slots"]), f"{kg} {cap_eff}")

        # 2 — Fizik (Kuvvet 6 test) T+1'den, günde 3
        p2 = c.get(f"{base}/topic-spread", params={"topic_id": ids["t_kuv"], "start": D[1].isoformat(),
                                                   "per_day": 3}).json()
        days2 = [d["date"] for d in p2["days"]]
        sk2 = {d["date"]: d["reason"] for d in p2["skipped"]}
        check("2. çapaya öncelik + dolu gün atlanır + sonraki Fizik gününden önce biter",
              days2 == [D[2].isoformat(), D[4].isoformat()]
              and "dershane payı 3" in sk2.get(D[1].isoformat(), "")
              and "yer yok" in sk2.get(D[3].isoformat(), "")
              and p2["window_end"] == D[4].isoformat() and "bir sonraki" in (p2["stop_reason"] or "")
              and p2["leftover"] == 0, str(p2)[:600])

        # 3 — Oran Orantı: A'da 4 kaldı, B 10
        p3 = c.get(f"{base}/topic-spread", params={"topic_id": ids["t_oran"], "start": D[4].isoformat(),
                                                   "per_day": 3}).json()
        d1, d2 = p3["days"][0], p3["days"][1]
        check("3. kitaplar arası tamamlama: gün1 A 3 · gün2 A 1 + B 2",
              [(i["book_id"], i["count"]) for i in d1["items"]] == [(ids["ba"], 3)]
              and [(i["book_id"], i["count"]) for i in d2["items"]] == [(ids["ba"], 1), (ids["bb"], 2)],
              str(p3["days"][:2]))

        # 4 — uygula gün2
        r4 = c.post(f"{base}/topic-spread", json={"days": [{"date": d2["date"], "items": [
            {"section_id": i["section_id"], "count": i["count"]} for i in d2["items"]]}]})
        with SessionLocal() as db:
            tt = db.query(Task).filter(Task.student_id == ids["st"], Task.date == date.fromisoformat(d2["date"])).all()
            books_of = sorted({it.book_id for t in tt for it in t.book_items})
            drafts = all(t.is_draft for t in tt)
        check("4. uygula → kitap başına ayrı görev, ileri tarih taslak",
              r4.status_code == 200 and r4.json()["data"]["created"] == 2
              and books_of == sorted([ids["ba"], ids["bb"]]) and drafts, f"{r4.status_code} {r4.text[:200]}")

        # 5 — konu o gün var → atlanır
        p5 = c.get(f"{base}/topic-spread", params={"topic_id": ids["t_oran"], "start": D[4].isoformat(),
                                                   "per_day": 3}).json()
        sk5 = {d["date"]: d["reason"] for d in p5["skipped"]}
        check("5. konu o gün zaten varsa gün atlanır",
              "zaten var" in sk5.get(d2["date"], "") and d2["date"] not in [d["date"] for d in p5["days"]],
              str(sk5))

        # 6 — sığmayan kısım: kapasiteyi 2'ye indir, Kuvvet günde 3 → hiçbir gün sığmaz
        c.post(f"{base}/skeleton", json={"slots": slots, "day_capacity": {str(i): 2 for i in range(7)}})
        p6 = c.get(f"{base}/topic-spread", params={"topic_id": ids["t_kuv"], "start": D[1].isoformat(),
                                                   "per_day": 3}).json()
        check("6. sığmayan kısım leftover olarak söylenir",
              p6["days"] == [] and p6["leftover"] == 6 and p6["total_remaining"] == 6, str(p6)[:300])

        # 7
        p7 = c.get(f"{base}/topic-spread", params={"topic_id": ids["t_kapali"], "start": D[1].isoformat()}).json()
        check("7. kapatılmış konu → boş önizleme", p7["days"] == [] and p7["total_remaining"] == 0, str(p7))

        # 8
        r8a = c.get(f"{base}/topic-spread", params={"start": D[1].isoformat()})
        r8b = c.post(f"{base}/topic-spread", json={"days": [{"date": (T - timedelta(days=1)).isoformat(),
                                                             "items": [{"section_id": S["mol"], "count": 1}]}]})
        r8c = c.post(f"{base}/topic-spread", json={"days": [{"date": D[2].isoformat(),
                                                             "items": [{"section_id": 99999999, "count": 1}]}]})
        check("8. konu yok 422 · geçmiş gün 422 · yabancı bölüm 404",
              [r8a.status_code, r8b.status_code, r8c.status_code] == [422, 422, 404],
              f"{r8a.status_code} {r8b.status_code} {r8c.status_code}")

        # 9 — öğrenilen kapasite: düzeltmeyi kaldır → T+3 günü 9 test (tek örnek) medyan 9
        c.post(f"{base}/skeleton", json={"slots": slots, "day_capacity": {str(i): None for i in range(7)}})
        cap = {x["weekday"]: x for x in c.get(f"{base}/skeleton").json()["capacity"]}
        c3 = cap[D[3].weekday()]
        check("9. öğrenilen kapasite = yazılı testlerin %90'lık dilimi · düzeltme kalktı",
              c3["learned"] == 9 and c3["override"] is None and c3["effective"] == 9, str(c3))
    finally:
        with SessionLocal() as db:
            if ids.get("st"):
                db.execute(sa_delete(SkeletonGhostAction).where(SkeletonGhostAction.student_id == ids["st"]))
                for x in db.query(WeeklySkeleton).filter(WeeklySkeleton.student_id == ids["st"]):
                    db.delete(x)
                tids = [t.id for t in db.query(Task).filter(Task.student_id == ids["st"])]
                if tids:
                    db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
                db.execute(sa_delete(Task).where(Task.student_id == ids["st"]))
                db.execute(sa_delete(TopicClosure).where(TopicClosure.student_id == ids["st"]))
                db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(ids["sbs"])))
                db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(ids["sbs"])))
                db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
                db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
                db.execute(sa_delete(Topic).where(Topic.id.in_(ids["topics"])))
                db.execute(sa_delete(Subject).where(Subject.id.in_([ids["fiz"], ids["mat"], ids["kim"]])))
                db.execute(sa_delete(User).where(User.id.in_([ids["st"], ids["coach"]])))
                db.commit()
    print(f"\n=== {passed}/{passed + len(failed)} geçti ===")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
