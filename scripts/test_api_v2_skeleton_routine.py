"""Haftalık İskelet F2-1 — kitaba bağlı rutin + satır kaynağı (smoke, 2026-09-26).

Saha: Zeynep Ela paragrafı KARIŞIK çözüyor (her gün farklı bölümlerden birer
test); Taha'nın Problemler rutini SIRALI; bazı rutinler kitapsız serbest metin
("345 Sıfır Risk Paragraf 2 Test"). Aynı derste birden çok satır varken hangisinin
rutin olduğu okunabilmeli.

Senaryolar:
   1. Bu haftadan iskelet: karma paragraf rutini (kitap + karma + adet 3) ·
      sıralı problem rutini (kitap + sirali + adet 2) · kitapsız rutin (label) ·
      konu satırı rutin DEĞİL ama kitabını taşır
   2. Hayalet: karma çip kaldığı yerden döner (3 farklı bölüm, birer test)
   3. Hayalet: sıralı çip kalınan bölümden 2 test
   4. Kitapsız rutin hayaletinin çipi yok, etiketi var
   5. Konu satırında satırın kitabının çipi önde
   6. Haftanın rutinleri (3 gün): her gün karma/sıralı/etkinlik görevi; ertesi gün
      karma sonraki bölümlerden devam eder; çok kalemli başlık kalemlerden
   7. Kaynak eşleştirme: rutin görevi konu satırını "doldurmaz"
   8. Doğrulama: kitaplık dışı kitap 422 · ders uyuşmazlığı 422 · biçim 422
   9. Etiketli satır → etkinlik olarak yaz
  10. Kaydet/oku: kitap adı · etiket · biçim döner
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

PFX = f"skr_{secrets.token_hex(3)}"
PWD = "SkelR!234567xy"
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
    print(f"\n=== iskelet rutin smoke — {PFX} ===\n")
    get_login_limiter().reset()
    today = date.today()
    hist_days = [today - timedelta(days=i) for i in range(7, 0, -1)]  # 7 gün geçmiş
    ids: dict = {}
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                         full_name="Rutin Koç", role=UserRole.TEACHER, is_active=True)
            db.add(coach)
            db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                      full_name="Rutin Öğrenci", role=UserRole.STUDENT, is_active=True,
                      teacher_id=coach.id, grade_level=12)
            db.add(st)
            db.flush()
            tur = Subject(name=f"{PFX} Türkçe", teacher_id=coach.id, order=1)
            mat = Subject(name=f"{PFX} Matematik", teacher_id=coach.id, order=2)
            db.add_all([tur, mat])
            db.flush()
            tmat = Topic(subject_id=mat.id, name="Üslü", order=1, teacher_id=coach.id)
            tmat2 = Topic(subject_id=mat.id, name="Köklü", order=2, teacher_id=coach.id)
            db.add_all([tmat, tmat2])
            db.flush()
            par = Book(name=f"{PFX} Mor Paragraf", teacher_id=coach.id, subject_id=tur.id,
                       type=BookType.SORU_BANKASI)
            prob = Book(name=f"{PFX} Problemler", teacher_id=coach.id, subject_id=mat.id,
                        type=BookType.SORU_BANKASI)
            konu = Book(name=f"{PFX} Mat Konu", teacher_id=coach.id, subject_id=mat.id,
                        type=BookType.SORU_BANKASI)
            other = Book(name=f"{PFX} Yabancı", teacher_id=coach.id, subject_id=tur.id,
                         type=BookType.SORU_BANKASI)  # öğrenciye ATANMAZ
            db.add_all([par, prob, konu, other])
            db.flush()
            secs: dict = {}
            sbs: dict = {}

            def add_sec(book, key, label, total, order, topic=None):
                sec = BookSection(book_id=book.id, label=label, order=order,
                                  test_count=total, topic_id=topic.id if topic else None)
                db.add(sec)
                db.flush()
                secs[key] = sec
                return sec

            for i, n in enumerate(["Sözcükte Anlam", "Cümlede Anlam", "Paragrafta Yapı",
                                   "Ana Düşünce", "Yardımcı Düşünce"]):
                add_sec(par, f"p{i}", n, 20, i + 1)
            for i in range(4):
                add_sec(prob, f"r{i}", f"Karma Test {i + 1}", 10, i + 1)
            add_sec(konu, "k1", "Üslü Testleri", 10, 1, tmat)
            add_sec(konu, "k2", "Köklü Testleri", 10, 2, tmat2)
            for book in (par, prob, konu):
                sbs[book.id] = StudentBook(student_id=st.id, book_id=book.id)
                db.add(sbs[book.id])
            db.flush()
            used = {k: 0 for k in secs}

            def task(d, items, title="x", ttype=TaskType.TEST):
                t = Task(student_id=st.id, date=d, type=ttype, title=title, is_draft=False)
                db.add(t)
                db.flush()
                for key, n in items:
                    sec = secs[key]
                    db.add(TaskBookItem(task_id=t.id, book_id=sec.book_id,
                                        book_section_id=sec.id, planned_count=n))
                    used[key] += n
                    db.flush()
                return t

            ring = [f"p{i}" for i in range(5)]
            pos = 0
            for i, d in enumerate(hist_days):
                # karma paragraf: 3 farklı bölümden birer test, dönen halka
                picks = [ring[(pos + j) % 5] for j in range(3)]
                pos = (pos + 3) % 5
                task(d, [(k, 1) for k in picks])
                # sıralı problem: 2 test (bölüm dolunca sıradaki)
                r = "r0" if used["r0"] < 10 else "r1"
                task(d, [(r, 2)])
                # kitapsız rutin
                task(d, [], title=f"{PFX} Türkçe · 345 Sıfır Risk Paragraf 2 Test",
                     ttype=TaskType.OTHER)
                # konu görevi yalnız iki günde (rutin değil)
                if i in (0, 3):
                    task(d, [("k1", 2)])
            for key, n in used.items():
                sec = secs[key]
                db.add(SectionProgress(student_book_id=sbs[sec.book_id].id,
                                       book_section_id=sec.id, completed_count=n,
                                       reserved_count=0))
            ids.update(coach=coach.id, st=st.id, tur=tur.id, mat=mat.id, par=par.id,
                       prob=prob.id, konu=konu.id, other=other.id,
                       secs={k: v.id for k, v in secs.items()},
                       sec_label={v.id: v.label for v in secs.values()},
                       books=[par.id, prob.id, konu.id, other.id],
                       sbs=[s.id for s in sbs.values()], topics=[tmat.id, tmat2.id],
                       last_picks=picks, next_pos=pos)
            db.commit()

        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        base = f"/api/v2/teacher/students/{ids['st']}/skeleton"
        S = ids["secs"]

        # 1
        r1 = c.post(f"{base}/from-week", json={"start": hist_days[0].isoformat(),
                                               "end": hist_days[-1].isoformat()})
        sk = r1.json()["data"]
        slots = sk["slots"]
        tw = today.weekday()
        day_slots = [s for s in slots if s["weekday"] == tw]
        par_slot = next((s for s in day_slots if s["book_id"] == ids["par"]), None)
        prob_slot = next((s for s in day_slots if s["book_id"] == ids["prob"]), None)
        lab_slot = next((s for s in day_slots if s["label"]), None)
        check("1a. karma paragraf rutini: kitap + karma + adet 3",
              bool(par_slot and par_slot["is_routine"] and par_slot["routine_mode"] == "karma"
                   and par_slot["default_count"] == 3 and "Mor Paragraf" in (par_slot["book_name"] or "")),
              str(par_slot))
        check("1b. sıralı problem rutini: kitap + sirali + adet 2",
              bool(prob_slot and prob_slot["is_routine"] and prob_slot["routine_mode"] == "sirali"
                   and prob_slot["default_count"] == 2), str(prob_slot))
        check("1c. kitapsız rutin: etiket = başlık (ders öneki atılmış), kitap yok",
              bool(lab_slot and lab_slot["is_routine"] and lab_slot["book_id"] is None
                   and lab_slot["label"] == "345 Sıfır Risk Paragraf 2 Test"), str(lab_slot))
        konu_slots = [s for s in slots if s["book_id"] == ids["konu"]]
        check("1d. konu satırı rutin değil ama kitabını taşır",
              bool(konu_slots) and not any(s["is_routine"] for s in konu_slots),
              str(konu_slots))

        # 2-5 — bugünün hayaletleri (bugün hiç görev yok)
        g = c.get(f"{base}/ghosts", params={"start": today.isoformat(),
                                            "end": today.isoformat()}).json()
        ghosts = g["days"][0]["ghosts"] if g["days"] else []
        gp = next((x for x in ghosts if x["book_id"] == ids["par"]), None)
        items = (gp["chips"][0].get("items") or []) if gp and gp["chips"] else []
        exp = [S[f"p{(ids['next_pos'] + j) % 5}"] for j in range(3)]
        check("2. karma çip kaldığı yerden döner: 3 farklı bölüm, birer test",
              [it["section_id"] for it in items] == exp and all(it["count"] == 1 for it in items)
              and gp["chips"][0]["kind"] == "routine",
              f"{[it['section_id'] for it in items]} != {exp}")
        gr = next((x for x in ghosts if x["book_id"] == ids["prob"]), None)
        ritems = (gr["chips"][0].get("items") or []) if gr and gr["chips"] else []
        check("3. sıralı çip: kalınan bölümden 2 test",
              sum(it["count"] for it in ritems) == 2 and ritems[0]["section_id"] == S["r1"],
              str(ritems))
        gl = next((x for x in ghosts if x["label"]), None)
        check("4. kitapsız rutin hayaleti: çip yok, etiket var",
              bool(gl and gl["chips"] == [] and gl["label"] == "345 Sıfır Risk Paragraf 2 Test"),
              str(gl))

        # 5 — konu satırının olduğu bir gün (hist gün 0 ve 3'ün hafta günleri)
        kd = next(d for d in (today + timedelta(days=i) for i in range(1, 8))
                  if d.weekday() in (hist_days[0].weekday(), hist_days[3].weekday()))
        g5 = c.get(f"{base}/ghosts", params={"start": kd.isoformat(), "end": kd.isoformat()}).json()
        gk = next((x for x in g5["days"][0]["ghosts"] if x["book_id"] == ids["konu"]), None)
        check("5. konu satırında satırın kitabının çipi önde",
              bool(gk and gk["chips"] and gk["chips"][0]["book_id"] == ids["konu"]), str(gk)[:300])

        # 6 — üç günün rutinleri tek istekte
        d1, d3 = today, today + timedelta(days=2)
        r6 = c.post(f"{base}/ghosts/accept-routine",
                    json={"date": d1.isoformat(), "end": d3.isoformat()})
        with SessionLocal() as db:
            new = (db.query(Task).filter(Task.student_id == ids["st"], Task.date >= d1,
                                         Task.date <= d3).order_by(Task.date, Task.id).all())
            by_day = {}
            for t in new:
                its = sorted(t.book_items, key=lambda x: x.id)
                by_day.setdefault(t.date, []).append(
                    (t.type.value if hasattr(t.type, "value") else t.type, t.title,
                     [(i.book_section_id, i.planned_count) for i in its],
                     {i.book_id for i in its}))
        ok_days = all(len(v) == 3 for v in by_day.values()) and len(by_day) == 3
        check("6a. 3 gün × 3 rutin görevi (karma · sıralı · etkinlik)",
              r6.status_code == 200 and ok_days, f"{r6.status_code} {by_day}")
        par_seq = [
            [sid for sid, _n in items_] for day in sorted(by_day)
            for _ty, _ti, items_, bks in by_day[day] if ids["par"] in bks
        ]
        flat = [x for day in par_seq for x in day]
        exp_flat = [S[f"p{(ids['next_pos'] + j) % 5}"] for j in range(9)]
        check("6b. karma ertesi gün sonraki bölümlerden devam (dönen halka)",
              flat == exp_flat, f"{flat} != {exp_flat}")
        par_titles = [ti for day in by_day.values() for _ty, ti, _i, bks in day if ids["par"] in bks]
        check("6c. çok kalemli başlık kalemlerden ('·' ile bölümler)",
              bool(par_titles) and all(" · " in t and "Mor Paragraf" in t for t in par_titles),
              str(par_titles[:1]))
        acts = [ti for day in by_day.values() for ty, ti, _i, _b in day if ty == "other"]
        check("6d. kitapsız rutin → etkinlik görevi 'Ders · etiket'",
              len(acts) == 3 and all(t.endswith("· 345 Sıfır Risk Paragraf 2 Test") for t in acts),
              str(acts[:1]))

        # 7 — kaynak eşleştirme: bugün rutinler yazıldı; konu satırı (varsa) hâlâ hayalet
        g7 = c.get(f"{base}/ghosts", params={"start": kd.isoformat(), "end": kd.isoformat()}).json()
        gh7 = g7["days"][0]["ghosts"]
        check("7. rutin görevleri konu satırını 'doldurmaz' (konu hayaleti kalır)",
              any(x["book_id"] == ids["konu"] for x in gh7)
              and not any(x["is_routine"] for x in gh7) if kd <= d3 else
              any(x["book_id"] == ids["konu"] for x in gh7),
              str([(x["book_id"], x["is_routine"]) for x in gh7]))

        # 8 — doğrulama
        base_row = {"weekday": 0, "period": None, "subject_id": ids["tur"], "position": 0,
                    "is_routine": True, "default_count": 3}
        r8a = c.post(base, json={"slots": [dict(base_row, book_id=ids["other"])]})
        r8b = c.post(base, json={"slots": [dict(base_row, book_id=ids["prob"])]})
        r8c = c.post(base, json={"slots": [dict(base_row, book_id=ids["par"], routine_mode="x")]})
        check("8. kitaplık dışı 422 · ders uyuşmazlığı 422 · biçim 422",
              [r8a.status_code, r8b.status_code, r8c.status_code] == [422, 422, 422]
              and r8a.json()["detail"]["code"] == "book_not_allowed"
              and r8b.json()["detail"]["code"] == "book_subject_mismatch",
              f"{r8a.status_code} {r8b.status_code} {r8c.status_code}")

        # 10 — kaydet/oku (9'dan önce: iskeleti tek etiketli satıra indir)
        wd9 = (today + timedelta(days=5)).weekday()
        r10 = c.post(base, json={"slots": [
            {"weekday": wd9, "period": "evening", "subject_id": ids["tur"], "position": 0,
             "is_routine": False, "default_count": None, "label": "Mor Yayınları 3 Test Paragraf"},
            {"weekday": wd9, "period": None, "subject_id": ids["tur"], "position": 1,
             "is_routine": True, "default_count": 3, "book_id": ids["par"],
             "routine_mode": "karma"},
        ]})
        got = r10.json()["data"]["slots"]
        check("10. kaydet/oku: etiket · kitap adı · biçim",
              r10.status_code == 200 and got[0]["label"] == "Mor Yayınları 3 Test Paragraf"
              and got[1]["book_name"].endswith("Mor Paragraf") and got[1]["routine_mode"] == "karma"
              and any(b["id"] == ids["par"] for b in r10.json()["data"]["books"]),
              str(got))

        # 9 — etiketli satır → etkinlik
        d9 = today + timedelta(days=5)
        g9 = c.get(f"{base}/ghosts", params={"start": d9.isoformat(), "end": d9.isoformat()}).json()
        gl9 = next(x for x in g9["days"][0]["ghosts"] if x["label"])
        r9 = c.post(f"{base}/ghosts/accept", json={"slot_id": gl9["slot_id"], "date": d9.isoformat(),
                                                    "as_activity": True})
        with SessionLocal() as db:
            t9 = db.get(Task, r9.json()["data"]["task_ids"][0]) if r9.status_code == 200 else None
            ok9 = t9 is not None and t9.title.endswith("· Mor Yayınları 3 Test Paragraf") \
                and (t9.period.value if hasattr(t9.period, "value") else t9.period) == "evening"
        check("9. etiketli satır → etkinlik görevi (periyot satırdan)", ok9,
              f"{r9.status_code} {r9.text[:200]}")
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
                db.execute(sa_delete(Subject).where(Subject.id.in_([ids["tur"], ids["mat"]])))
                db.execute(sa_delete(User).where(User.id.in_([ids["st"], ids["coach"]])))
                db.commit()
    print(f"\n=== {passed}/{passed + len(failed)} geçti ===")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
