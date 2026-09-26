"""Haftalık İskelet — smoke (F1, 2026-09-25).

Senaryolar:
   1. İskelet kaydet (aynı gün aynı derse 2 satır) → GET döner
   2. Görevsiz günde iskelet satırı başına bir hayalet (iki satır → iki hayalet)
   3. Geçmiş gün için hayalet YOK
   4. Çip sırası iplik modeli: dünkü bölüm devam ('thread', son adet) →
      biten bölümün kitabında sıradaki konu ('next') → yeni konu → tekrar
   5. KAPATILMIŞ konu hiçbir çipte yok
   6. İkinci hayaletin çipleri kaydırılmış (iki iplik iki satıra dağılır)
   7. Rozetler BİLGİ taşır: denemede yanlış sayısı Müfredat panosuyla AYNI
   8. Hayalet rezerv TUTMAZ (GET sonrası sayaçlar değişmez)
   9. Kabul → görev (periyot iskeletten) + rezerv + o gün hayalet sayısı düşer
  10. CANLI yeniden hesap: ertesi günün çipinde kalan azalır, gerekçe "devamı"
  11. Başka dersin bölümü → 422 · yanlış hafta günü → 422
  12. Kaldır → hayalet gizli · geri getir → döner
  13. Haftadan iskelet (from-week) · kabul raporu
  14. Başka koçun öğrencisi → 404
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
    ExamResult,
    ExamSection,
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
from app.models.exam_result import ExamResultQuestion
from app.models.suspicious_ip import SuspiciousIp
from app.models.weekly_skeleton import SkeletonGhostAction, WeeklySkeleton
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"skel_{secrets.token_hex(3)}"
PWD = "Skel!234567xy"
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
    print(f"\n=== haftalık iskelet smoke — {PFX} ===\n")
    get_login_limiter().reset()
    today = date.today()
    d0, d1, d2 = today - timedelta(days=1), today + timedelta(days=1), today + timedelta(days=2)
    ids: dict = {}
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                         full_name="İskelet Koç", role=UserRole.TEACHER, is_active=True)
            other = User(email=f"{PFX}_o@test.invalid", password_hash=hash_password(PWD),
                         full_name="Diğer Koç", role=UserRole.TEACHER, is_active=True)
            db.add_all([coach, other])
            db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                      full_name="İskelet Öğrenci", role=UserRole.STUDENT, is_active=True,
                      teacher_id=coach.id, grade_level=12)
            fst = User(email=f"{PFX}_f@test.invalid", password_hash=hash_password(PWD),
                       full_name="Yabancı", role=UserRole.STUDENT, is_active=True,
                       teacher_id=other.id, grade_level=12)
            db.add_all([st, fst])
            db.flush()
            mat = Subject(name=f"{PFX} Matematik", teacher_id=coach.id, order=1)
            fiz = Subject(name=f"{PFX} Fizik", teacher_id=coach.id, order=2)
            db.add_all([mat, fiz])
            db.flush()
            tp = {}
            for i, n in enumerate(["Üslü", "Köklü", "Kapalı Konu", "Çarpanlar",
                                   "Oran", "Problemler"], start=1):
                tp[n] = Topic(subject_id=mat.id, name=n, order=i, teacher_id=coach.id)
                db.add(tp[n])
            tf = Topic(subject_id=fiz.id, name="Kuvvet", order=1, teacher_id=coach.id)
            db.add(tf)
            db.flush()

            ba = Book(name=f"{PFX} Mat SB", teacher_id=coach.id, subject_id=mat.id,
                      type=BookType.SORU_BANKASI)
            bb = Book(name=f"{PFX} Problem SB", teacher_id=coach.id, subject_id=mat.id,
                      type=BookType.SORU_BANKASI)
            bf = Book(name=f"{PFX} Fizik SB", teacher_id=coach.id, subject_id=fiz.id,
                      type=BookType.SORU_BANKASI)
            db.add_all([ba, bb, bf])
            db.flush()
            # A kitabı: s1 Üslü 10 test (3 rezervli dünden) · s2 Köklü 4/4 bitmiş ·
            # s3 KAPALI konu · s4 Çarpanlar (s2'nin sıradakisi) · s5 Oran başlanmamış
            spec = [("s1", ba, "Üslü", 10, 0, 3), ("s2", ba, "Köklü", 4, 4, 0),
                    ("s3", ba, "Kapalı Konu", 10, 0, 0), ("s4", ba, "Çarpanlar", 10, 0, 0),
                    ("s5", ba, "Oran", 10, 0, 0), ("b1", bb, "Problemler", 10, 2, 0),
                    ("f1", bf, "Kuvvet", 10, 0, 0)]
            secs = {}
            sbs = {}
            for key, book, tname, total, comp, res in spec:
                topic = tf if tname == "Kuvvet" else tp[tname]
                sec = BookSection(book_id=book.id, label=f"{tname} Testleri",
                                  order=len([k for k in secs if secs[k].book_id == book.id]) + 1,
                                  test_count=total, topic_id=topic.id)
                db.add(sec)
                db.flush()
                if book.id not in sbs:
                    sbs[book.id] = StudentBook(student_id=st.id, book_id=book.id)
                    db.add(sbs[book.id])
                    db.flush()
                db.add(SectionProgress(student_book_id=sbs[book.id].id, book_section_id=sec.id,
                                       completed_count=comp, reserved_count=res))
                secs[key] = sec
            db.flush()

            def task(d, sec, planned, done=0):
                t = Task(student_id=st.id, date=d, type=TaskType.TEST, title="x", is_draft=False)
                db.add(t)
                db.flush()
                db.add(TaskBookItem(task_id=t.id, book_id=sec.book_id, book_section_id=sec.id,
                                    planned_count=planned, completed_count=done))
                db.flush()

            task(d0, secs["s2"], 2, done=2)  # dün Köklü — bölüm bitti
            task(d0, secs["s1"], 3)          # dün (sonra) Üslü 3 test — en yeni iplik
            db.add(TopicClosure(student_id=st.id, topic_id=tp["Kapalı Konu"].id,
                                closed_by_id=coach.id))
            ex = ExamResult(student_id=st.id, title="Deneme", exam_date=today,
                            section=ExamSection.TYT, total_correct=40, total_wrong=10,
                            total_blank=0, net=37.5, created_by_id=coach.id)
            db.add(ex)
            db.flush()
            for tname, n in (("Çarpanlar", 2), ("Problemler", 3), ("Kapalı Konu", 4)):
                for _ in range(n):
                    db.add(ExamResultQuestion(exam_result_id=ex.id, topic_id=tp[tname].id,
                                              result="yanlis"))
            ids.update(coach=coach.id, other=other.id, st=st.id, fst=fst.id, mat=mat.id,
                       fiz=fiz.id, books=[ba.id, bb.id, bf.id],
                       secs={k: v.id for k, v in secs.items()},
                       closed_topic=tp["Kapalı Konu"].id, t_carp=tp["Çarpanlar"].id)
            db.commit()

        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        base = f"/api/v2/teacher/students/{ids['st']}/skeleton"
        S = ids["secs"]

        # 1
        slots = [
            {"weekday": d1.weekday(), "period": "morning", "subject_id": ids["mat"], "position": 0},
            {"weekday": d1.weekday(), "period": "evening", "subject_id": ids["mat"], "position": 1},
            {"weekday": d2.weekday(), "period": None, "subject_id": ids["mat"], "position": 0},
            {"weekday": d0.weekday(), "period": None, "subject_id": ids["mat"], "position": 0},
        ]
        r1 = c.post(base, json={"slots": slots})
        g1 = c.get(base).json()
        check("1. iskelet kaydedildi (4 satır)", r1.status_code == 200 and len(g1["slots"]) == 4,
              f"{r1.status_code} {r1.text[:200]}")

        def ghosts(start, end):
            return c.get(f"{base}/ghosts", params={"start": start.isoformat(),
                                                   "end": end.isoformat()}).json()

        def day_ghosts(data, d):
            for day in data["days"]:
                if day["date"] == d.isoformat():
                    return day["ghosts"]
            return []

        with SessionLocal() as db:
            before = {k: db.query(SectionProgress.reserved_count)
                      .filter(SectionProgress.book_section_id == v).scalar() for k, v in S.items()}
        data = ghosts(d0, d2)
        gd1 = day_ghosts(data, d1)
        check("2. d1'de iki satır → iki hayalet", len(gd1) == 2, str(len(gd1)))
        check("3. geçmiş gün (dün) için hayalet YOK",
              not any(day["date"] == d0.isoformat() for day in data["days"]), str(data["days"][:1]))

        chips = gd1[0]["chips"] if gd1 else []
        kinds = [(ch["kind"], ch["section_id"]) for ch in chips]
        check("4a. 1. çip = dünün ipliği Üslü (thread, son adet 3)",
              chips and chips[0]["kind"] == "thread" and chips[0]["section_id"] == S["s1"]
              and chips[0]["count"] == 3, str(kinds))
        check("4b. biten Köklü → kitapta sıradaki Çarpanlar ('next'; kapalı konu atlandı)",
              ("next", S["s4"]) in kinds, str(kinds))
        check("4c. yeni konu çipi Oran", ("new", S["s5"]) in kinds, str(kinds))
        check("4d. tekrar çipi Problemler (denemede 3 yanlış)",
              ("weak", S["b1"]) in kinds, str(kinds))
        all_sections = {ch["section_id"] for day in data["days"] for g in day["ghosts"] for ch in g["chips"]}
        check("5. kapatılmış konu hiçbir çipte yok", S["s3"] not in all_sections, str(all_sections))
        check("5b. başka dersin bölümü çipe girmez", S["f1"] not in all_sections)
        check("6. ikinci hayaletin ilk çipi farklı (iplikler satırlara dağılır)",
              len(gd1) == 2 and gd1[1]["chips"] and gd1[1]["chips"][0]["section_id"] != chips[0]["section_id"],
              str([g["chips"][0]["section_id"] for g in gd1 if g["chips"]]))

        carp = next((ch for ch in chips if ch["section_id"] == S["s4"]), None)
        board = c.get(f"/api/v2/teacher/students/{ids['st']}/topic-board",
                      params={"subject_id": ids["mat"]}).json()
        bt = next((t for s in board.get("subjects", []) for t in s.get("topics", [])
                   if t.get("topic_id") == ids["t_carp"]), {})
        badge = next((b for b in (carp or {}).get("badges", []) if b["code"] == "exam_wrong"), None)
        check("7. rozet 'denemede N yanlış' Müfredat panosuyla aynı sayı",
              badge is not None and badge["label"] == f"denemede {bt.get('exam_wrong')} yanlış",
              f"{badge} board={bt.get('exam_wrong')}")
        check("7b. çipin gerekçe cümlesi var", all(ch["reason"] for ch in chips))

        with SessionLocal() as db:
            after = {k: db.query(SectionProgress.reserved_count)
                     .filter(SectionProgress.book_section_id == v).scalar() for k, v in S.items()}
        check("8. hayalet rezerv tutmaz", before == after, f"{before} vs {after}")

        # 9 kabul
        r9 = c.post(f"{base}/ghosts/accept", json={
            "slot_id": gd1[0]["slot_id"], "date": d1.isoformat(), "section_id": S["s1"],
            "count": 3, "chip_rank": 1, "chip_kind": "thread", "chip_count": len(chips)})
        check("9a. kabul 200", r9.status_code == 200, r9.text[:300])
        tid = (r9.json().get("data") or {}).get("task_ids", [None])[0] if r9.status_code == 200 else None
        with SessionLocal() as db:
            t = db.get(Task, tid) if tid else None
            res = db.query(SectionProgress.reserved_count).filter(
                SectionProgress.book_section_id == S["s1"]).scalar()
        check("9b. görev oluştu, periyot iskeletten (sabah)", t is not None and t.period == "morning",
              f"{t and t.period}")
        check("9c. rezerv açıldı (3 → 6)", res == 6, str(res))
        check("9d. invalidate iskelet anahtarını içerir",
              any(k.endswith(":skeleton") for k in r9.json().get("invalidate", [])))
        data2 = ghosts(d1, d2)
        gd1b = day_ghosts(data2, d1)
        check("9e. d1'de hayalet sayısı 2 → 1", len(gd1b) == 1, str(len(gd1b)))
        check("9f. kalan hayaletin çiplerinde bugün verilen Üslü yok",
              gd1b and all(ch["section_id"] != S["s1"] for ch in gd1b[0]["chips"]))

        gd2 = day_ghosts(data2, d2)
        u = next((ch for ch in (gd2[0]["chips"] if gd2 else []) if ch["section_id"] == S["s1"]), None)
        check("10. CANLI: ertesi gün Üslü çipi kalan 4 + 'devamı' gerekçesi",
              u is not None and u["remaining"] == 4 and "devamı" in u["reason"], str(u))

        # 11
        r11 = c.post(f"{base}/ghosts/accept", json={
            "slot_id": gd1b[0]["slot_id"], "date": d1.isoformat(), "section_id": S["f1"], "count": 2})
        check("11a. başka dersin bölümü → 422", r11.status_code == 422, str(r11.status_code))
        r11b = c.post(f"{base}/ghosts/accept", json={
            "slot_id": gd1b[0]["slot_id"], "date": d2.isoformat(), "section_id": S["s4"], "count": 2})
        check("11b. yanlış hafta günü → 422", r11b.status_code == 422, str(r11b.status_code))

        # 12
        c.post(f"{base}/ghosts/action", json={"slot_id": gd1b[0]["slot_id"],
                                              "date": d1.isoformat(), "action": "dismissed"})
        check("12a. kaldırılan hayalet gizli", len(day_ghosts(ghosts(d1, d1), d1)) == 0)
        c.post(f"{base}/ghosts/action", json={"slot_id": gd1b[0]["slot_id"],
                                              "date": d1.isoformat(), "action": "restore"})
        check("12b. geri getirilen hayalet döner", len(day_ghosts(ghosts(d1, d1), d1)) == 1)

        # 13
        rep = c.get("/api/v2/teacher/skeleton/acceptance").json()
        check("13a. kabul raporu: 1 kabul, 1. çipten", rep.get("accepted") == 1
              and rep.get("by_rank", {}).get("1") == 1, str(rep))
        r13 = c.post(f"{base}/from-week", json={"start": d0.isoformat(), "end": d1.isoformat()})
        fw = r13.json().get("data", {}) if r13.status_code == 200 else {}
        check("13b. haftadan iskelet: dün 2 görev + d1 1 görev → 3 satır",
              r13.status_code == 200 and fw.get("source") == "from_week" and len(fw.get("slots", [])) == 3,
              r13.text[:300])

        # 14
        r14 = c.get(f"/api/v2/teacher/students/{ids['fst']}/skeleton/ghosts",
                    params={"start": d1.isoformat(), "end": d2.isoformat()})
        check("14. başka koçun öğrencisi → 404", r14.status_code == 404, str(r14.status_code))
    finally:
        with SessionLocal() as db:
            uid = [ids[k] for k in ("coach", "other", "st", "fst") if ids.get(k)]
            if uid:
                db.execute(sa_delete(SkeletonGhostAction).where(SkeletonGhostAction.student_id.in_(uid)))
                for skel in db.query(WeeklySkeleton).filter(WeeklySkeleton.student_id.in_(uid)):
                    db.delete(skel)
                db.execute(sa_delete(TopicClosure).where(TopicClosure.student_id.in_(uid)))
                exids = [r[0] for r in db.query(ExamResult.id).filter(ExamResult.student_id.in_(uid))]
                if exids:
                    db.execute(sa_delete(ExamResultQuestion)
                               .where(ExamResultQuestion.exam_result_id.in_(exids)))
                    db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(exids)))
                tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(uid))]
                if tids:
                    db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
                    db.execute(sa_delete(Task).where(Task.id.in_(tids)))
            bids = ids.get("books") or []
            if bids:
                sbids = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.book_id.in_(bids))]
                if sbids:
                    db.execute(sa_delete(SectionProgress)
                               .where(SectionProgress.student_book_id.in_(sbids)))
                    db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sbids)))
                db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(bids)))
                db.execute(sa_delete(Book).where(Book.id.in_(bids)))
            for k in ("mat", "fiz"):
                if ids.get(k):
                    db.execute(sa_delete(Topic).where(Topic.subject_id == ids[k]))
                    db.execute(sa_delete(Subject).where(Subject.id == ids[k]))
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
