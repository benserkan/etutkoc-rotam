"""Haftalık İskelet F2-4 — problem rutini kapsamı + kaynak sırası + 2. kaynak (smoke, 2026-09-27).

Saha (Zeynep Ela · TYT Matematik): rutin yalnız PROBLEMLER; problemler
Orijinal'den başladı. Rutin "kitapta sırayla" ilerleyince konu hattına
(Polinomlar) kayıyordu. Koç kuralları:
  · problem rutini kaynağın problemlerini sırayla bitirir, sonra sıradaki SORU
    BANKASININ problemlerinden baştan (Oran-Orantı) devam eder
  · video destekli defter / konu anlatımlı kitap ana kaynak DEĞİLDİR
  · konu satırında 1. kaynakta konu bitince koç seçer: 2. kaynaktan aynı konu ya
    da 1. kaynakta sıradaki konu (sistem seçmez)

Senaryolar:
   1. problem bölümleri: Oran-Orantı + problem konuları + Problem Denemeleri;
      ÖSYM çıkmış + blok içindeki konu bölümü + bloktan önceki 'problem' konulu
      bölüm HARİÇ
   2. Bu haftadan iskelet: problem görevleri → rutin + kapsam 'problems' + adet 2;
      konu satırı rutin değil, 2. kaynağı = haftada kullanılan diğer soru bankası
   3. Hayalet (problem rutini): Orijinal'in son problem testi + sıradaki soru
      bankasının Oran-Orantı'sı; video defter yok; Polinomlar/Fonksiyon yok
   4. Konu satırı: problem bölümü önerilmez; 1. kaynakta konu bitti → "2. kaynaktan
      aynı konu" + "kitapta sıradaki konu" çipleri, ikisi de seçim işaretli
   5. Rutin kabul: kaynaklar arası çip kitap başına AYRI görev yazar; problem
      rutini hayaleti dolar, konu satırı hayaleti kalır
   6. Ertesi gün problem rutini yeni kaynakta kaldığı yerden devam eder
   7. Kitap seçenekleri: soru bankası / problem kaynağı işaretleri
   8. Doğrulama: 2. kaynak video defter → 422 · aynı kitap → 422 · kapsam → 422
   9. Kaydet/oku: kapsam + 2. kaynak adı döner
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
from app.services import skeleton_suggest as sks
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"skp_{secrets.token_hex(3)}"
PWD = "SkelP!234567xy"
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
    print(f"\n=== iskelet problem rutini smoke — {PFX} ===\n")
    get_login_limiter().reset()
    today = date.today()
    hist_days = [today - timedelta(days=i) for i in range(7, 0, -1)]
    ids: dict = {}
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                         full_name="Problem Koç", role=UserRole.TEACHER, is_active=True)
            db.add(coach)
            db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                      full_name="Problem Öğrenci", role=UserRole.STUDENT, is_active=True,
                      teacher_id=coach.id, grade_level=12)
            db.add(st)
            db.flush()
            mat = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, order=1)
            db.add(mat)
            db.flush()
            topics: dict = {}
            for i, n in enumerate(["Temel Kavramlar", "Sayısal Yetenek Problemleri",
                                   "Oran ve Orantı", "Birinci Dereceden Denklemler",
                                   "Yaş Problemleri", "Fonksiyonlar", "Polinomlar"]):
                t = Topic(subject_id=mat.id, name=n, order=i + 1, teacher_id=coach.id)
                db.add(t)
                db.flush()
                topics[n] = t
            orj = Book(name=f"{PFX} Orijinal TYT Mat", teacher_id=coach.id, subject_id=mat.id,
                       type=BookType.SORU_BANKASI)
            fen = Book(name=f"{PFX} Fen Bilimleri TYT Mat", teacher_id=coach.id,
                       subject_id=mat.id, type=BookType.SORU_BANKASI)
            # Adı alfabede önde: yine de kaynak sırasına ASLA girmemeli.
            vdd = Book(name=f"{PFX} AAA 3D Video Destekli Defter", teacher_id=coach.id,
                       subject_id=mat.id, type=BookType.KONU_ANLATIMLI)
            db.add_all([orj, fen, vdd])
            db.flush()
            secs: dict = {}
            sbs: dict = {}

            def add_sec(book, key, label, total, order, topic=None):
                sec = BookSection(book_id=book.id, label=label, order=order, test_count=total,
                                  topic_id=topics[topic].id if topic else None)
                db.add(sec)
                db.flush()
                secs[key] = sec

            add_sec(orj, "o_temel", "Temel Kavramlar", 4, 0, "Temel Kavramlar")
            add_sec(orj, "o_ozel", "Özel Sayı Tanımlama", 1, 1, "Sayısal Yetenek Problemleri")
            add_sec(orj, "o_osym1", "ÖSYM'DE ÇIKMIŞ SORULAR (1. BÖLÜM)", 2, 2)
            add_sec(orj, "o_oran", "Oran - Orantı", 4, 3, "Oran ve Orantı")
            add_sec(orj, "o_yas", "Yaş Problemleri", 4, 4, "Yaş Problemleri")
            add_sec(orj, "o_osym2", "ÖSYM'DE ÇIKMIŞ SORULAR (2. BÖLÜM)", 2, 5)
            add_sec(orj, "o_pd", "Problem Denemeleri", 7, 6)
            add_sec(orj, "o_fonk", "Fonksiyon", 4, 7, "Fonksiyonlar")
            add_sec(orj, "o_pol", "Polinomlar", 3, 8, "Polinomlar")
            add_sec(fen, "f_temel", "Temel Kavramlar", 10, 0, "Temel Kavramlar")
            add_sec(fen, "f_oran", "Oran ve Orantı", 10, 1, "Oran ve Orantı")
            add_sec(fen, "f_bir", "Birinci Dereceden Denklemler", 10, 2,
                    "Birinci Dereceden Denklemler")
            add_sec(fen, "f_yas", "Yaş Problemleri", 10, 3, "Yaş Problemleri")
            add_sec(fen, "f_fonk", "Fonksiyonlar", 10, 4, "Fonksiyonlar")
            add_sec(vdd, "v_oran", "Oran - Orantı", 3, 0, "Oran ve Orantı")
            add_sec(vdd, "v_yas", "Yaş Problemleri", 3, 1, "Yaş Problemleri")
            for book in (orj, fen, vdd):
                sbs[book.id] = StudentBook(student_id=st.id, book_id=book.id)
                db.add(sbs[book.id])
            db.flush()
            used = {k: 0 for k in secs}

            def task(d, items):
                t = Task(student_id=st.id, date=d, type=TaskType.TEST, title="x", is_draft=False)
                db.add(t)
                db.flush()
                for key, n in items:
                    sec = secs[key]
                    db.add(TaskBookItem(task_id=t.id, book_id=sec.book_id,
                                        book_section_id=sec.id, planned_count=n))
                    used[key] += n
                    db.flush()
                return t

            # Problem rutini (Orijinal, günde 2): Oran 2+2 · Yaş 2+2 · PD 2+2+2 → PD'de 1 kaldı
            prob_plan = ["o_oran", "o_oran", "o_yas", "o_yas", "o_pd", "o_pd", "o_pd"]
            for i, d in enumerate(hist_days):
                task(d, [(prob_plan[i], 2)])
                # Konu hattı: Orijinal Fonksiyon (0, 2, 4. gün) — 4 test, biter
                if i in (0, 2, 4):
                    task(d, [("o_fonk", 2 if i == 4 else 1)])
                # 2. soru bankasından konu görevi (Temel Kavramlar)
                if i == 1:
                    task(d, [("f_temel", 2)])
            for key, n in used.items():
                if n:
                    sec = secs[key]
                    db.add(SectionProgress(student_book_id=sbs[sec.book_id].id,
                                           book_section_id=sec.id, completed_count=n,
                                           reserved_count=0))
            ids.update(coach=coach.id, st=st.id, mat=mat.id, orj=orj.id, fen=fen.id, vdd=vdd.id,
                       secs={k: v.id for k, v in secs.items()},
                       books=[orj.id, fen.id, vdd.id], sbs=[s.id for s in sbs.values()],
                       topics=[t.id for t in topics.values()])
            db.commit()

        S = ids["secs"]

        # 1 — problem bölümleri (servis)
        with SessionLocal() as db:
            ctx = sks._load_ctx(db, student=db.get(User, ids["st"]), coach_id=ids["coach"],
                                start=today, end=today)
            prob = ctx.problem_secs
        want = {S["o_oran"], S["o_yas"], S["o_pd"], S["f_oran"], S["f_yas"]}
        check("1a. problem bölümleri: Oran-Orantı + Yaş + Problem Denemeleri (iki kitap)",
              want <= prob, str(want - prob))
        check("1b. ÖSYM çıkmış · blok içi konu bölümü · bloktan önceki 'problem' konulu bölüm HARİÇ",
              not ({S["o_osym1"], S["o_osym2"], S["f_bir"], S["o_ozel"],
                    S["o_fonk"], S["o_pol"]} & prob))
        check("1c. video destekli defter soru bankası sayılmaz",
              ids["vdd"] not in ctx.bank_books and ids["orj"] in ctx.bank_books)

        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        base = f"/api/v2/teacher/students/{ids['st']}/skeleton"

        # 2 — bu haftadan iskelet
        r2 = c.post(f"{base}/from-week", json={"start": hist_days[0].isoformat(),
                                               "end": hist_days[-1].isoformat()})
        check("2. from-week 200", r2.status_code == 200, r2.text[:300])
        skel = r2.json()["data"]
        tw = today.weekday()
        day_slots = [s for s in skel["slots"] if s["weekday"] == tw]
        prob_slot = next((s for s in day_slots if s["is_routine"]), None)
        topic_slot = next((s for s in day_slots if not s["is_routine"]), None)
        check("2a. problem görevleri → rutin · kapsam 'problems' · sirali · adet 2 · kitap Orijinal",
              bool(prob_slot and prob_slot["routine_scope"] == "problems"
                   and prob_slot["routine_mode"] == "sirali" and prob_slot["default_count"] == 2
                   and prob_slot["book_id"] == ids["orj"]), str(prob_slot))
        check("2b. konu satırı rutin değil · 2. kaynak = Fen Bilimleri (soru bankası)",
              bool(topic_slot and topic_slot["book_id"] == ids["orj"]
                   and topic_slot["second_book_id"] == ids["fen"]
                   and "Fen Bilimleri" in (topic_slot["second_book_name"] or "")), str(topic_slot))

        # 3 — problem rutini hayaleti
        rg = c.get(f"{base}/ghosts", params={"start": today.isoformat(), "end": today.isoformat()})
        ghosts = rg.json()["days"][0]["ghosts"] if rg.json()["days"] else []
        pg = next((g for g in ghosts if g["is_routine"]), None)
        tg = next((g for g in ghosts if not g["is_routine"]), None)
        chip = (pg or {}).get("chips", [{}])[0] if pg and pg["chips"] else {}
        its = chip.get("items") or []
        its_ids = [it["section_id"] for it in its]
        check("3a. rutin: Orijinal son problem testi + Fen Bilimleri Oran-Orantı",
              its_ids == [S["o_pd"], S["f_oran"]] and [it["count"] for it in its] == [1, 1],
              str(its))
        check("3b. rutin gerekçesi kaynak geçişini söyler",
              "problemleri bu gün bitiyor" in chip.get("reason", "")
              and "Fen Bilimleri" in chip.get("reason", ""), chip.get("reason"))
        check("3c. video defter yok · Polinomlar/Fonksiyon yok",
              not ({S["v_oran"], S["v_yas"], S["o_pol"], S["o_fonk"], S["f_fonk"]} & set(its_ids)))
        check("3d. hayalet kapsamı döner", (pg or {}).get("routine_scope") == "problems")

        # 4 — konu satırı
        tchips = (tg or {}).get("chips", [])
        tsecs = [c_["section_id"] for c_ in tchips]
        check("4a. konu satırında problem bölümü önerilmez",
              not (set(tsecs) & (want | {S["o_pd"]})), str(tsecs))
        second = next((c_ for c_ in tchips if c_["kind"] == "second"), None)
        nxt = next((c_ for c_ in tchips if c_["kind"] == "next"), None)
        check("4b. 1. kaynakta konu bitti → 2. kaynakta aynı konu İLK öneri (otomatik)",
              bool(second and second["section_id"] == S["f_fonk"] and not second.get("source_choice")
                   and tchips and tchips[0]["kind"] == "second"
                   and "2. kaynakta" in second["reason"]), str(second))
        check("4c. kitapta sıradaki konu (Orijinal · Polinomlar) yalnız alternatif",
              bool(nxt and nxt["section_id"] == S["o_pol"] and not nxt.get("source_choice")
                   and tsecs.index(S["o_pol"]) > tsecs.index(S["f_fonk"])), str(nxt))
        check("4d. hayalette seçim uyarısı YOK · 2. kaynak adı var",
              bool(tg and not tg["source_choice"] and "Fen Bilimleri" in (tg["second_book_name"] or "")))

        # 5 — rutin kabul: kaynaklar arası → kitap başına ayrı görev
        ra = c.post(f"{base}/ghosts/accept", json={
            "slot_id": pg["slot_id"], "date": today.isoformat(),
            "items": [{"section_id": it["section_id"], "count": it["count"]} for it in its],
            "chip_rank": 1, "chip_kind": "routine", "chip_count": 1,
        })
        created = ra.json().get("data", {}).get("created") if ra.status_code == 200 else None
        check("5a. kabul 200 · iki kitap → iki görev", created == 2, ra.text[:300])
        with SessionLocal() as db:
            tids = ra.json()["data"]["task_ids"] if created else []
            books_per_task = [
                {it.book_id for it in db.get(Task, t).book_items} for t in tids
            ]
        check("5b. her görev tek kitap", all(len(b) == 1 for b in books_per_task), str(books_per_task))
        rg2 = c.get(f"{base}/ghosts", params={"start": today.isoformat(), "end": today.isoformat()})
        g2 = rg2.json()["days"][0]["ghosts"] if rg2.json()["days"] else []
        check("5c. problem rutini hayaleti doldu · konu satırı hayaleti kaldı",
              not any(g["is_routine"] for g in g2) and any(not g["is_routine"] for g in g2),
              str([(g["is_routine"], g["book_id"]) for g in g2]))

        # 6 — ertesi gün yeni kaynakta devam
        tm = today + timedelta(days=1)
        rg3 = c.get(f"{base}/ghosts", params={"start": tm.isoformat(), "end": tm.isoformat()})
        g3 = rg3.json()["days"][0]["ghosts"] if rg3.json()["days"] else []
        p3 = next((g for g in g3 if g["is_routine"]), None)
        c3 = p3["chips"][0] if p3 and p3["chips"] else {}
        ids3 = [it["section_id"] for it in (c3.get("items") or [])]
        check("6. ertesi gün: Fen Bilimleri Oran-Orantı'dan sırayla (2 test)",
              ids3 == [S["f_oran"]] and c3.get("count") == 2, str(c3.get("items")))

        # 7 — kitap seçenekleri
        rs = c.get(base)
        books = {b["id"]: b for b in rs.json()["books"]}
        check("7. soru bankası / problem kaynağı işaretleri",
              books[ids["orj"]]["is_bank"] and books[ids["orj"]]["has_problems"]
              and books[ids["fen"]]["has_problems"]
              and not books[ids["vdd"]]["is_bank"] and not books[ids["vdd"]]["has_problems"],
              str({k: (v["is_bank"], v["has_problems"]) for k, v in books.items()}))

        # 8 — doğrulama
        def save(slot_over):
            slots = []
            for s in rs.json()["slots"]:
                row = {k: s[k] for k in ("weekday", "period", "subject_id", "position", "is_routine",
                                         "default_count", "book_id", "label", "routine_mode",
                                         "is_anchor", "routine_scope", "second_book_id")}
                if s["id"] == topic_slot["id"]:
                    row.update(slot_over)
                slots.append(row)
            return c.post(base, json={"skeleton_id": rs.json()["id"], "slots": slots})

        r8a = save({"second_book_id": ids["vdd"]})
        r8b = save({"second_book_id": ids["orj"]})
        r8c = save({"is_routine": True, "routine_scope": "hepsi"})
        check("8. 2. kaynak video defter 422 · aynı kitap 422 · kapsam 422",
              r8a.status_code == 422 and r8a.json()["detail"]["code"] == "second_not_bank"
              and r8b.status_code == 422 and r8b.json()["detail"]["code"] == "second_same_book"
              and r8c.status_code == 422 and r8c.json()["detail"]["code"] == "bad_routine_scope",
              f"{r8a.status_code} {r8b.status_code} {r8c.status_code}")

        # 9 — kaydet/oku
        r9 = save({"second_book_id": ids["fen"]})
        s9 = r9.json()["data"]["slots"] if r9.status_code == 200 else []
        t9 = next((s for s in s9 if s["weekday"] == tw and not s["is_routine"]), {})
        p9 = next((s for s in s9 if s["weekday"] == tw and s["is_routine"]), {})
        check("9. kaydet: 2. kaynak + kapsam korunur",
              t9.get("second_book_id") == ids["fen"] and p9.get("routine_scope") == "problems",
              f"{r9.status_code} {t9} {p9}")
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
                db.execute(sa_delete(Subject).where(Subject.id == ids["mat"]))
                db.execute(sa_delete(User).where(User.id.in_([ids["st"], ids["coach"]])))
                db.commit()
    print(f"\n=== {passed}/{passed + len(failed)} geçti ===")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
