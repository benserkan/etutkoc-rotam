# -*- coding: utf-8 -*-
"""Veli haftalık rapor e-postası v2 smoke (2026-11-12).

- payload: hafta = son tamamlanmış Pzt–Paz, sayılar Haftalık Rapor ekranıyla aynı
- konu: tamlayan eki (Emir'in / Ayşe'nin), görev uyumu
- şablon render: marka başlığı, emoji yok, deneme serisi, branş grubu, gelecek hafta
- cron parent_weekly_report: kuyruğa yazar, aynı gün ikinci çalışmada tekrar yazmaz
- weekly_backstop kapalı, on_task_completed tetiklemez
"""
from __future__ import annotations

import json
import re
import secrets
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookType, ParentRelation, ParentStudentLink,
    Subject, Task, TaskBookItem, TaskStatus, TaskType, User, UserRole,
)
from app.models.curriculum import ExamSection
from app.models.exam_result import ExamResult
from app.models.parent import NotificationKind, NotificationLog
from app.services import cron_jobs, email_service, event_triggers
from app.services.parent_weekly_mail import build_mail_payload, genitive, report_week
from app.services.security import hash_password

PFX = f"pwm2_{secrets.token_hex(3)}"
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


def seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password("PwmTest!2345")
    today = date.today()
    mon = report_week(today)
    with SessionLocal() as db:
        t = User(email=f"{PFX}_t@test.invalid", password_hash=pwd, full_name=f"{PFX} Koç",
                 role=UserRole.TEACHER, is_active=True)
        db.add(t); db.flush()
        s = User(email=f"{PFX}_s@test.invalid", password_hash=pwd, full_name="Ayşe Deneme",
                 role=UserRole.STUDENT, teacher_id=t.id, grade_level=12, is_active=True,
                 created_at=now - timedelta(days=150))
        p = User(email=f"{PFX}_p@test.invalid", password_hash=pwd, full_name=f"{PFX} Veli",
                 role=UserRole.PARENT, is_active=True)
        db.add_all([s, p]); db.flush()
        db.add(ParentStudentLink(parent_id=p.id, student_id=s.id, relation=ParentRelation.ANNE,
                                 is_primary=True))
        subj = Subject(teacher_id=t.id, name="Matematik", order=1)
        db.add(subj); db.flush()
        b = Book(teacher_id=t.id, name="Mat SB", type=BookType.SORU_BANKASI, subject_id=subj.id)
        db.add(b); db.flush()
        sec = BookSection(book_id=b.id, label="Türev", order=1, test_count=900)
        db.add(sec); db.flush()

        def task(d, planned, done):
            tk = Task(student_id=s.id, date=d, type=TaskType.TEST, title="G", is_draft=False,
                      status=TaskStatus.COMPLETED if done >= planned else TaskStatus.PARTIAL)
            db.add(tk); db.flush()
            db.add(TaskBookItem(task_id=tk.id, book_id=b.id, book_section_id=sec.id,
                                planned_count=planned, completed_count=done))

        # 8 önceki hafta: her hafta 5 görev, 4'ü tamam (olağan %80 civarı)
        for w in range(1, 9):
            wm = mon - timedelta(days=7 * w)
            for d in range(5):
                task(wm + timedelta(days=d), 3, 3 if d < 4 else 0)
        # rapor haftası: 5 görev, 5'i tamam
        for d in range(5):
            task(mon + timedelta(days=d), 3, 3)
        # gelecek hafta programı
        task(mon + timedelta(days=7), 3, 0)
        # deneme: 2 tam TYT + 1 branş
        db.add(ExamResult(student_id=s.id, created_by_id=t.id, title="TYT Genel 1",
                          exam_date=mon - timedelta(days=10), section=ExamSection.TYT,
                          total_correct=80, total_wrong=20, total_blank=20, net=75.0))
        db.add(ExamResult(student_id=s.id, created_by_id=t.id, title="TYT Genel 2",
                          exam_date=mon + timedelta(days=2), section=ExamSection.TYT,
                          total_correct=88, total_wrong=16, total_blank=16, net=84.0))
        db.commit()
        return {"t": t.id, "s": s.id, "p": p.id, "mon": mon}


def cleanup(d):
    from sqlalchemy import delete
    with SessionLocal() as db:
        tids = [x for (x,) in db.query(Task.id).filter(Task.student_id == d["s"]).all()]
        if tids:
            db.execute(delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(delete(Task).where(Task.student_id == d["s"]))
        db.execute(delete(ExamResult).where(ExamResult.student_id == d["s"]))
        db.execute(delete(NotificationLog).where(NotificationLog.parent_id == d["p"]))
        db.execute(delete(ParentStudentLink).where(ParentStudentLink.parent_id == d["p"]))
        for b in db.query(Book).filter(Book.teacher_id == d["t"]).all():
            db.execute(delete(BookSection).where(BookSection.book_id == b.id))
        db.execute(delete(Book).where(Book.teacher_id == d["t"]))
        db.execute(delete(Subject).where(Subject.teacher_id == d["t"]))
        db.execute(delete(User).where(User.id.in_([d["s"], d["p"], d["t"]])))
        db.commit()


def main() -> int:
    print("== genitive / report_week")
    check("Emir → Emir'in", genitive("Emir") == "Emir'in")
    check("Ayşe → Ayşe'nin", genitive("Ayşe") == "Ayşe'nin")
    check("Umut → Umut'un", genitive("Umut") == "Umut'un")
    check("Ali → Ali'nin", genitive("Ali") == "Ali'nin")
    check("Doğa → Doğa'nın", genitive("Doğa") == "Doğa'nın")
    check("report_week(Pazartesi 16 Kas) = 9 Kas", report_week(date(2026, 11, 16)) == date(2026, 11, 9))
    check("report_week(Perşembe 12 Kas) = 2 Kas", report_week(date(2026, 11, 12)) == date(2026, 11, 2))

    d = seed()
    try:
        with SessionLocal() as db:
            p = db.get(User, d["p"]); s = db.get(User, d["s"])
            pl = build_mail_payload(db, p, s)
            print("== payload")
            check("hafta Pzt–Paz", pl["week_start"] == d["mon"].isoformat()
                  and pl["week_end"] == (d["mon"] + timedelta(days=6)).isoformat(), str(pl["week_start"]))
            check("görev 5/5 · %100", pl["gorev_done"] == 5 and pl["gorev_total"] == 5
                  and pl["completion_pct"] == 100, f"{pl['gorev_done']}/{pl['gorev_total']} {pl['completion_pct']}")
            check("olağan aralık hesaplandı", pl["normal"]["pct_low"] is not None, str(pl["normal"]))
            check("geçmiş 8 hafta + bu hafta", len(pl["history"]) == 9, str(len(pl["history"])))
            check("verdict metni olağan aralığı anar", "olağan" in (pl["verdict_text"] or ""), pl["verdict_text"])
            check("TYT serisi: son net 84, öncekine göre +9",
                  pl["series"] and pl["series"][0]["last_net"] == "84"
                  and "+9" in (pl["series"][0]["diff_text"] or ""), str(pl["series"]))
            check("gelecek hafta 1 görev", pl["next_week"] and pl["next_week"]["tasks"] == 1, str(pl["next_week"]))
            check("student_gen = Ayşe'nin", pl["student_gen"] == "Ayşe'nin")

            print("== şablon")
            r = email_service.render_template_safe("parent_weekly_report", {**pl, "unsubscribe_token": "x"})
            check("render edildi", r is not None)
            subj, html = (r[0], r[1]) if r else ("", "")
            check("konu: Ayşe'nin haftası · görev uyumu %100",
                  subj.startswith("Ayşe'nin haftası") and "%100" in subj, subj)
            check("konu kaçışlı değil (&#39; yok)", "&#39;" not in subj, subj)
            check("emoji yok", not re.search("[\U0001F300-\U0001FAFF☀-➿]", html))
            check("deneme bölümü var", "Denemeler" in html and "84" in html)
            check("gelecek hafta kutusu var", "Gelecek hafta" in html)
            check("abonelikten çık bağlantısı", "unsubscribe" in html or "tek tıkla" in html)

            print("== cron")
            today = date.today()
            mon_now = today - timedelta(days=today.weekday())
            run_at = datetime(mon_now.year, mon_now.month, mon_now.day, 16, 0, tzinfo=timezone.utc)
            cron_jobs.parent_weekly_report(db, now=run_at)
            db.commit()
            logs = db.query(NotificationLog).filter(NotificationLog.parent_id == d["p"],
                                                     NotificationLog.kind == NotificationKind.WEEKLY_REPORT).all()
            check("cron kuyruğa yazdı (1 e-posta)", len(logs) == 1, str(len(logs)))
            if logs:
                pj = json.loads(logs[0].payload_json or "{}")
                check("payload sürüm 2", pj.get("version") == 2, str(pj.get("version")))
            cron_jobs.parent_weekly_report(db, now=run_at + timedelta(hours=1))
            db.commit()
            n2 = db.query(NotificationLog).filter(NotificationLog.parent_id == d["p"],
                                                   NotificationLog.kind == NotificationKind.WEEKLY_REPORT).count()
            check("aynı gün ikinci çalışma tekrar yazmaz", n2 == 1, str(n2))
            bs = cron_jobs.weekly_backstop(db, now=run_at)
            check("weekly_backstop kapalı", isinstance(bs, dict) and "disabled" in bs, str(bs))
            ev = event_triggers.on_task_completed(db, s)
            check("görev tamamlama tetiği rapor üretmez", ev["fired_for_parents"] == 0, str(ev))
    finally:
        cleanup(d)

    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
