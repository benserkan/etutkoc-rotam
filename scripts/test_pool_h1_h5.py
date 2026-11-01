"""Havuz H1–H5 düzeltmeleri — Taha #84 vakasının birebir kurgusu (2026-11-01).

Kurgu: 11 günlük dönem (beklenen seans 7. gün, 3 gün geç kapandı). Öğrenci yalnız 3 gün kap kurdu,
son 4 gün hiç dokunmadı; bir günde 5 görevi saniyeler içinde işaretledi; D/Y girmedi; Fizik kalemine
hiç dokunmadı. Seans bitirildi, kalanlar devretti.

  H1  görev bazlı ölçüler havuzda %100'e yapışmaz: tutarlılık havuz günü, tutturma dönem yüzdesi,
      detay/liste dönem durumu, analitik dönem noktası + takvimde havuz günü planlı, haftalık
      ilerleme grafiğinde dönem değeri birimle
  H2  kapanışta bayraklar saklanır; koç geçmişinde görünür, öğrenciye görünmez; yeni dönemin ilk
      günlerinde "Geçen dönem uyarıyla kapandı" kartı
  H3  ders dengesi havuz kalemleriyle: bırakılan ders Fizik; önlem /pool'a gider
  H4  öğrenci temposu: yeni dönemin ilk günü "geride" değil; takvimin gerisi "geride"
  H5  "Talep ve devir" havuz devrini sayar
"""
from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import date, datetime, time, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, CoachingSession, PoolItem, SectionProgress, StudentBook, StudyPeriod,
    Subject, Task, TaskBookItem, Topic, Track, User, UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.models.task import TaskStatus  # noqa: E402
from app.routes.api_v2.pool_student import _pace  # noqa: E402
from app.services import pool_mode as pm  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"h15_{secrets.token_hex(3)}"
PWD = "Havuz!234567xy"
today = date.today()
OPEN = today - timedelta(days=10)          # dönem başı
passed = 0
failed: list[str] = []
ids: dict = {"users": [], "subjects": [], "books": []}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def utc(d: date, h: int, m: int = 0, s: int = 0) -> datetime:
    return datetime.combine(d, time(h, m, s), tzinfo=timezone.utc)


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="H Rehber", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="H Öğrenci", role=UserRole.STUDENT, is_active=True, teacher_id=coach.id,
                  grade_level=12, track=Track.SAYISAL, program_mode="havuz",
                  created_at=utc(today - timedelta(days=60), 9))
        db.add(st)
        db.flush()
        subs, books, secs = {}, {}, {}
        for key, nm in (("mat", "TYT Matematik"), ("fiz", "TYT Fizik"), ("tur", "TYT Türkçe")):
            s = Subject(name=f"{PFX} {nm}", teacher_id=coach.id, exam_section=ExamSection.TYT)
            db.add(s)
            db.flush()
            tp = Topic(subject_id=s.id, name=f"{nm} konu", order=1, teacher_id=coach.id)
            db.add(tp)
            db.flush()
            b = Book(teacher_id=coach.id, subject_id=s.id, name=f"{PFX} {nm} SB", type=BookType.SORU_BANKASI)
            db.add(b)
            db.flush()
            sec = BookSection(book_id=b.id, label=f"{nm} bölüm", test_count=20, order=1, topic_id=tp.id)
            db.add(sec)
            db.flush()
            sb = StudentBook(student_id=st.id, book_id=b.id)
            db.add(sb)
            db.flush()
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
            subs[key], books[key], secs[key] = s.id, b.id, sec.id
            ids["subjects"].append(s.id)
            ids["books"].append(b.id)
        db.commit()
        ids["users"] += [coach.id, st.id]
        return {"coach": coach.id, "st": st.id, "subs": subs, "books": books, "secs": secs}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(CoachingSession).where(CoachingSession.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
        db.execute(sa_delete(Topic).where(Topic.subject_id.in_(ids["subjects"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def cup_done(db, item, day: date, count: int, at: datetime):
    t = pm.put_in_cup(db, item=item, day=day, count=count)
    t.status = TaskStatus.COMPLETED
    t.completed_at = at
    for bi in t.book_items:
        bi.completed_count = bi.planned_count
    db.flush()
    pm.sync_item_progress(db, item)
    return t


def main() -> int:
    get_login_limiter().reset()
    d = seed()
    print(f"\n=== havuz H1–H5 — {PFX} ===\n")
    try:
        with SessionLocal() as db:
            st = db.get(User, d["st"])
            coach = db.get(User, d["coach"])
            p = pm.open_period(db, student=st, coach=coach, opened_on=OPEN, expected_next_on=OPEN + timedelta(days=7))
            items = {}
            for key, qty in (("mat", 12), ("fiz", 10), ("tur", 8)):
                items[key] = pm.add_item(db, period=p, student=st, subject=db.get(Subject, d["subs"][key]),
                                         quantity=qty, unit="test", book=db.get(Book, d["books"][key]),
                                         section=db.get(BookSection, d["secs"][key]))
                items[key].created_at = utc(OPEN, 9)
            # 3. gün: 5 görev saniyeler içinde (toplu işaretleme) · 4. gün · 6. gün; son 4 gün boş
            d3 = OPEN + timedelta(days=3)
            for i, (key, n) in enumerate((("tur", 4), ("tur", 4), ("mat", 3), ("mat", 3), ("mat", 2))):
                cup_done(db, items[key], d3, n, utc(d3, 9, 38, i * 2))
            cup_done(db, items["mat"], OPEN + timedelta(days=4), 1, utc(OPEN + timedelta(days=4), 19))
            cup_done(db, items["mat"], OPEN + timedelta(days=6), 1, utc(OPEN + timedelta(days=6), 10))
            db.commit()
            ids["pid"] = p.id
            ids["items"] = {k: v.id for k, v in items.items()}
            sm = pm.period_summary(db, p, today)
            check("0 kurgu: 30 birimin 18'i yapıldı (%60)", (sm.done_units, sm.total_units, sm.pct) == (18, 30, 60),
                  (sm.done_units, sm.total_units, sm.pct))

        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        base = f"/api/v2/teacher/students/{d['st']}"

        # ------------------------------------------------ H1 (dönem açıkken)
        j = c.get(base).json()
        ps = j["program_summary"]
        check("H1a detay: pool durumu dolu, dönem %60", ps.get("pool") and ps["pool"]["pct"] == 60, ps.get("pool"))
        check("H1b detay: son 3 gün (bugün hariç) dokunmadı → idle_streak 3", ps["pool"]["idle_streak"] == 3, ps["pool"])
        check("H1c tutarlılık %100'e yapışmıyor (son 7 havuz gününün 2'sinde işaret)",
              ps["consistency_7d"] < 0.5, ps["consistency_7d"])
        check("H1d tutturma = dönem yüzdesi (0.6), görev bazlı 1.0 değil", abs(ps["hit_rate_7d"] - 0.6) < 0.01,
              ps["hit_rate_7d"])
        lst = c.get("/api/v2/teacher/students?status=aktif").json()
        row = next(x for x in lst["items"] if x["id"] == d["st"])
        check("H1e liste satırı dönem yüzdesini taşır", row.get("pool") and row["pool"]["pct"] == 60, row.get("pool"))
        an = c.get(f"{base}/analytics").json()
        pts = [w for w in an["weekly_trend"] if w.get("kind") == "donem"]
        check("H1f analitik: dönem noktası %60 (birim), hafta noktası değil",
              len(pts) == 1 and pts[0]["pct"] == 60 and pts[0]["planned"] == 30, an["weekly_trend"][-3:])
        cal = {x["date"]: x for x in an["activity_calendar"]}
        empty_day = (today - timedelta(days=2)).isoformat()
        check("H1g ritim takvimi: işaretsiz havuz günü 'planlı ama yapılmadı'",
              cal[empty_day]["has_plan"] and not cal[empty_day]["active"], cal.get(empty_day))
        check("H1h analitik tutarlılık %100 değil", an["summary"]["consistency_7d_pct"] < 50, an["summary"])

        # ------------------------------------------------ seans bitir (3 gün geç, bugün)
        r = c.post(f"{base}/pool/session/finish", json={
            "closed_on": today.isoformat(), "expected_next_on": (today + timedelta(days=7)).isoformat(),
            "carry": [{"item_id": ids["items"]["mat"]}, {"item_id": ids["items"]["fiz"]}],
            "record_session": False})
        check("S seans bitti", r.status_code == 200, r.text[:300])

        with SessionLocal() as db:
            p_old = db.get(StudyPeriod, ids["pid"])
            snap = json.loads(p_old.closing_flags_json or "[]")
            codes = {f["code"] for f in snap}
        check("H2a kapanış anlık görüntüsü saklandı", len(snap) > 0, p_old.closing_flags_json)
        check("H2b dokunmama + toplu işaretleme + D/Y yok + kaçınma + gecikme yakalandı",
              {"pool_idle_streak", "pool_bulk_mark", "pool_dy_missing", "pool_avoided", "pool_session_late"} <= codes,
              codes)
        hist = c.get(f"{base}/pool/periods").json()["rows"]
        old_row = next(x for x in hist if x["id"] == ids["pid"])
        check("H2c koç dönem geçmişinde kapanış uyarıları", len(old_row["closing_flags"]) == len(snap), old_row["closing_flags"])
        det = c.get(f"{base}/pool/periods/{ids['pid']}").json()
        check("H2d koç dönem penceresinde kapanış uyarıları", len(det["period"]["closing_flags"]) > 0)
        j2 = c.get(base).json()
        all_codes = [w["code"] for w in j2["warning_items"] + j2["extra_items"]]
        check("H2e yeni dönem 0. gün: 'Geçen dönem uyarıyla kapandı' kartı (yeşil yolunda değil)",
              "pool_prev_period" in all_codes and j2["worst_warning_level"] == "amber", (all_codes, j2["worst_warning_level"]))

        cs = TestClient(app)
        r = cs.post("/api/v2/auth/login", json={"email": f"{PFX}_s@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        sp = cs.get("/api/v2/student/pool").json()
        check("H2f öğrenciye geçen dönem kartı gitmez", all(h["code"] != "pool_prev_period" for h in sp["hints"]), sp["hints"])
        sh = cs.get("/api/v2/student/program-history").json()
        per_rows = [e["period"] for e in sh["entries"] if e["kind"] == "period"]
        check("H2g öğrenci program geçmişinde kapanış uyarısı yok", all(not x["closing_flags"] for x in per_rows))
        check("H4a öğrenci yeni dönemin ilk günü 'geride' görmez", sp["summary"]["pace"] == "yolunda", sp["summary"])

        # ------------------------------------------------ H3 + H5 (haftalık ilerleme, yeni dönem)
        wp = c.get(f"{base}/weekly-progress").json()
        by = {x["key"]: x for x in wp["cards"]}
        check("H3a ders dengesi: bırakılan ders TYT Fizik %0", "TYT Fizik" in by["balance"]["value_label"]
              and by["balance"]["status"] == "below", by["balance"])
        act = next((a for a in wp["actions"] if a["key"] == "avoid"), None)
        check("H3b önlem havuza gider", act is not None and act["cta_href"].endswith("/pool"), act)
        check("H5 talep ve devir: 2 kalem devirle geldi", "2 kalem devirle geldi" in by["requests"]["value_label"],
              by["requests"]["value_label"])
        chart = {x["label"]: x for x in wp["chart"]}
        old_pt = next((x for x in wp["chart"] if not x["current"]), None)
        check("H1i haftalık ilerleme grafiği: kapanan dönem %60 (görev bazlı %100 değil)",
              old_pt is not None and old_pt["value"] == 60.0, wp["chart"])
        check("H1j havuz tamamlama kartı adı", by["gorev_pct"]["name"] == "Havuz tamamlama", by["gorev_pct"]["name"])

        # ------------------------------------------------ H4 birim kuralları
        S = pm.PeriodSummary
        check("H4b takvime uygun → yolunda", _pace(S(28, 12, 43, 3, 1, 0, 4, 4.0, None), 3)[0] == "yolunda")
        check("H4c takvimin çok gerisi → geride", _pace(S(77, 0, 0, 14, 0, 0, 4, 19.3, None), 3)[0] == "geride")
        check("H4d takvimin önü → önde", _pace(S(28, 20, 71, 3, 2, 0, 4, 2.0, None), 3)[0] == "onde")
        check("H4e alışkanlık varsa koçun kuralı (gereken > alışkanlık×1,5)",
              _pace(S(30, 0, 0, 3, 0, 0, 6, 5.0, None), 1, baseline=3.0)[0] == "geride"
              and _pace(S(30, 0, 0, 3, 0, 0, 6, 5.0, None), 1, baseline=4.0)[0] == "yolunda")
    finally:
        cleanup()

    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
