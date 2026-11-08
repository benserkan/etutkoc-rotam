"""Genel sekmesi üst sırası — Özet (yalnız koç) + 1. gün geçen hafta + branş önlemi (2026-11-09).

Öğrenciler (hepsinde bugün yeni hafta başlıyor → k=0; 7 geçmiş program haftası, günde 3 test görevi):
  toplu  : her günün 3 görevini ertesi sabah 09:00'da AYNI saniyede işaretler, D/Y girmez
           → "bulk" (sarı) + ertesi gün notu metinde · "results" sarı · deneme eğilimi aşağı ·
             hedef gerçekçi değil · branş denemesi önlemi · Gelişim Raporu'nda data:bulk
  ertesi : ertesi sabah 09:00'dan başlayıp 20'şer dakika arayla işaretler, D/Y girer
           → "next_day" (bilgi) · "results" ok · deneme yok · hedef yok
  gununde: aynı gün 18:00'den 30'ar dakika arayla işaretler → "marking_ok"
  + 1. gün: last_week dolu, geçen haftanın kartlarında kıyas var; bu haftanın kartları "insufficient"
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, time, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Task, TaskBookItem, Topic, User, UserRole, WeeklyProgram  # noqa: E402
from app.models.exam_progress import ExamTarget  # noqa: E402
from app.models.exam_result import ExamResult, ExamSection  # noqa: E402
from app.models.student_period import StudentGradePeriod  # noqa: E402
from app.models.task import TaskStatus, TaskType  # noqa: E402
from app.services import development_report  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from app.services.weekly_progress import build_weekly_progress  # noqa: E402

PFX = f"sov_{secrets.token_hex(3)}"
today = date.today()
passed = 0
failed: list[str] = []
uids: list[int] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def utc(d: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(d, time(hour)) + timedelta(minutes=minute) - timedelta(hours=3)


def seed(db, topic_id: int):
    coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password("x"), full_name="Koç",
                 role=UserRole.TEACHER, is_active=True)
    db.add(coach); db.flush()
    uids.append(coach.id)

    def student(tag: str) -> User:
        s = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password("x"), full_name=tag,
                 role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                 must_change_password=False, created_at=utc(today - timedelta(days=120), 10))
        db.add(s); db.flush()
        uids.append(s.id)
        return s

    toplu, ertesi, gununde = student("toplu"), student("ertesi"), student("gununde")

    def stamp(style: str, d: date, j: int) -> datetime:
        if style == "toplu":
            return utc(d + timedelta(days=1), 9)
        if style == "ertesi":
            return utc(d + timedelta(days=1), 9, 20 * j)
        return utc(d, 18, 30 * j)

    def week(st: User, start: date, cur: bool, style: str, dy: bool):
        db.add(WeeklyProgram(student_id=st.id, coach_id=coach.id, start_date=start,
                             end_date=start + timedelta(days=6)))
        for day in range(7):
            d = start + timedelta(days=day)
            for j in range(3):
                done = not (cur and d >= today)
                t = Task(student_id=st.id, date=d, title=f"Konu testi {day}-{j}", type=TaskType.TEST,
                         status=TaskStatus.COMPLETED if done else TaskStatus.PENDING, is_draft=False,
                         order=j, completed_at=stamp(style, d, j) if done else None)
                t.book_items = [TaskBookItem(topic_id=topic_id, planned_count=5,
                                             completed_count=5 if done else 0,
                                             correct_count=(40 if (done and dy) else None),
                                             wrong_count=(5 if (done and dy) else None))]
                db.add(t)

    for st, style, dy in ((toplu, "toplu", False), (ertesi, "ertesi", True), (gununde, "gununde", True)):
        for i in range(7, 0, -1):
            week(st, today - timedelta(days=7 * i), False, style, dy)
        week(st, today, True, style, dy)

    # toplu: 5 TYT genel deneme (son deneme +10 ama eğilim aşağı) + gerçekçi olmayan hedef
    for i, net in enumerate([100, 96, 92, 88, 98]):
        db.add(ExamResult(student_id=toplu.id, created_by_id=coach.id, title=f"TYT Deneme {i + 1}",
                          exam_date=today - timedelta(days=7 * (5 - i)), section=ExamSection.TYT,
                          total_correct=100, total_wrong=15, total_blank=5, net=net))
    db.add(ExamTarget(student_id=toplu.id, section="tyt", target_net=105,
                      target_date=today + timedelta(days=14), set_by_id=coach.id))
    # toplu: son 4 haftada 4 branş denemesi verildi, 1 çözüldü
    for i in range(4):
        d = today - timedelta(days=3 + i)
        t = Task(student_id=toplu.id, date=d, title=f"Branş denemesi {i}", type=TaskType.OTHER,
                 status=TaskStatus.COMPLETED if i == 0 else TaskStatus.PENDING, is_draft=False, order=9,
                 completed_at=utc(d + timedelta(days=1), 9) if i == 0 else None)
        t.book_items = [TaskBookItem(label="Matematik branş", planned_count=1, completed_count=1 if i == 0 else 0,
                                     exam_kind="brans", question_count=40)]
        db.add(t)
    db.commit()
    return toplu, ertesi, gununde


def cleanup():
    if not uids:
        return
    with SessionLocal() as db:
        tids = [t for (t,) in db.query(Task.id).filter(Task.student_id.in_(uids)).all()]
        if tids:
            db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(uids)))
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(uids)))
        db.execute(sa_delete(ExamTarget).where(ExamTarget.student_id.in_(uids)))
        db.execute(sa_delete(WeeklyProgram).where(WeeklyProgram.student_id.in_(uids)))
        db.execute(sa_delete(StudentGradePeriod).where(StudentGradePeriod.student_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def rel(wp: dict) -> dict:
    return {i["key"]: i for i in wp["overview"]["reliability"]}


def main():
    with SessionLocal() as db:
        topic = db.query(Topic).filter(Topic.is_builtin.is_(True)).first()
        toplu, ertesi, gununde = seed(db, topic.id)

        print("— 1. Veri güvenilirliği")
        wt = build_weekly_progress(db, toplu, today=today)
        r = rel(wt)
        check("toplu: 'bulk' sarı", r.get("bulk", {}).get("tone") == "warn", r)
        check("toplu: örnek '3 görev 0 saniyede'", "3 görev 0 saniyede" in r.get("bulk", {}).get("text", ""),
              r.get("bulk", {}).get("text"))
        check("toplu: ertesi gün bilgisi metinde", "ertesi gün" in r.get("bulk", {}).get("text", ""))
        check("toplu: seansa ekle metni var", bool(r.get("bulk", {}).get("agenda")))
        check("toplu: D/Y girilmiyor sarı", r.get("results", {}).get("tone") == "warn", r.get("results"))
        check("toplu: sayılar test cinsinden (son 4 hafta 28 gün × 15 test = 420)",
              "çözülen 420 testin yalnız 0 tanesinde" in r.get("results", {}).get("text", ""),
              r.get("results", {}).get("text"))

        we = build_weekly_progress(db, ertesi, today=today)
        r2 = rel(we)
        check("ertesi: toplu DEĞİL, ertesi gün bilgi notu", "bulk" not in r2
              and r2.get("next_day", {}).get("tone") == "info", r2)
        check("ertesi: D/Y giriliyor (ok)", r2.get("results", {}).get("tone") == "ok", r2.get("results"))

        wg = build_weekly_progress(db, gununde, today=today)
        r3 = rel(wg)
        check("gününde: işaretleme olağan", "marking_ok" in r3 and "bulk" not in r3 and "next_day" not in r3, r3)

        print("— 2. Deneme gidişatı")
        ex = wt["overview"]["exam"]
        check("son deneme 98, önceki 88, fark +10", ex and ex["last_net"] == 98 and ex["diff"] == 10, ex)
        check("eğilim deneme başına −1,2 → sarı", ex and ex["slope"] == -1.2 and ex["tone"] == "warn", ex)
        check("metin 'ama ... eğilimi aşağı' der", ex and "ama son 5 denemenin eğilimi aşağı" in ex["text"],
              ex and ex["text"])
        check("son 3 ortalama 92,67", ex and ex["avg_last3"] == 92.67, ex)
        check("denemesiz öğrencide exam None", we["overview"]["exam"] is None)

        print("— 3. Hedef gerçekçiliği")
        tg = wt["overview"]["target"]
        check("açık 12,33 net, 2 hafta, haftada +6,17", tg and tg["gap"] == 12.33 and tg["weeks_left"] == 2
              and tg["per_week_needed"] == 6.17, tg)
        check("tempo haftada −1,2 (haftada 1 deneme)", tg and tg["pace_per_week"] == -1.2, tg)
        check("gerçekçi değil → sarı + seansa ekle", tg and tg["realistic"] is False and tg["tone"] == "warn"
              and tg["agenda"], tg)
        check("hedefsiz öğrencide target None", we["overview"]["target"] is None)

        print("— 4. Önlemler: branş denemesi")
        ak = {a["key"]: a for a in wt["actions"]}
        check("branş önlemi (4 verildi, 1 çözüldü)", "brans" in ak and "4 branş denemesi kondu, 1 tanesi çözüldü"
              in ak["brans"]["why"], ak.get("brans"))
        check("branş verilmeyen öğrencide önlem yok", "brans" not in {a["key"] for a in we["actions"]})

        print("— 5. Haftanın 1. günü: geçen hafta")
        lw = wt.get("last_week")
        check("last_week dolu", lw is not None and lw["cards"], lw and lw.get("label"))
        if lw:
            lwc = {c["key"]: c for c in lw["cards"]}
            check("geçen hafta test kartı kıyaslı (cetvel dolu)", lwc["test_done"]["status"] != "insufficient"
                  and len(lwc["test_done"]["baseline"]) >= 4, lwc["test_done"]["status"])
            check("geçen hafta test değeri tam hafta (21 görev × 5 = 105)", lwc["test_done"]["value"] == 105,
                  lwc["test_done"]["value"])
            check("geçen hafta metni 'bu hafta' demiyor", all("Bu hafta" not in c["verdict"] for c in lw["cards"]),
                  [c["verdict"] for c in lw["cards"] if "Bu hafta" in c["verdict"]])
        cur = {c["key"]: c for c in wt["cards"]}
        check("bu haftanın test kartı kıyassız", cur["test_done"]["status"] == "insufficient")
        w2 = build_weekly_progress(db, toplu, today=today + timedelta(days=1))
        check("2. gün: last_week yok", w2.get("last_week") is None)

        print("— 6. Gelişim Raporu ile tutarlılık")
        rep = development_report.build_development_report(db, toplu, today=today)
        rk = {x["key"]: x for x in rep["risks"]}
        ak2 = {a["key"] for a in rep["actions"]}
        check("raporda data:bulk riski", "data:bulk" in rk, list(rk))
        check("raporda D/Y metni Genel ile aynı", rk.get("data:results", {}).get("text") == r["results"]["text"],
              rk.get("data:results", {}).get("text"))
        check("raporda branş önlemi tek (act:data:brans, wp:brans yok)",
              "act:data:brans" in ak2 and "wp:brans" not in ak2, sorted(ak2))


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    if failed:
        sys.exit(1)
