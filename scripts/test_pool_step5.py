"""Havuz modu Adım 5 smoke — K53 veli seans özeti · cron susturma · K54/K55 kurum panosu ·
K56 Rota paketi · K48/K50 rehber günlük liste · K52 veli salt-okuma (2026-10-12).

Çalıştır: PYTHONPATH=. python scripts/test_pool_step5.py
"""
from __future__ import annotations

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
    Book, BookSection, BookType, Institution, NotificationLog, NotificationStatus, ParentNotificationPref,
    ParentStudentLink, PoolItem, SectionProgress, StudentBook, StudyPeriod, Subject, Task, TaskBookItem,
    TaskStatus, Topic, Track, User, UserRole, WarningState,
)
from app.models.appointment import APPT_STATUS_SCHEDULED, CoachingAppointment  # noqa: E402
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.exam_result import EQ_RESULT_YANLIS, ExamResult, ExamResultQuestion  # noqa: E402
from app.models.parent import ParentRelation  # noqa: E402
from app.models.pool import PERIOD_CLOSED, SOURCE_STUDENT  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import analytics, cron_jobs, email_service, event_triggers, parent_chat, parent_commentary  # noqa: E402
from app.services import pool_coach_day, pool_mode as pm, pool_parent_summary as pps  # noqa: E402
from app.services.institution_pool import build_overview  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"p5_{secrets.token_hex(3)}"
PWD = "Step5!234567xy"
today = date.today()
now = datetime.now(timezone.utc)
analytics._tr_now = lambda: datetime.combine(today, time(12, 0), tzinfo=timezone.utc)
passed = 0
failed: list[str] = []
ids: dict = {"users": [], "subjects": [], "books": [], "exams": [], "inst": []}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def _user(db, tag, role, **kw):
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD), full_name=f"P5 {tag}",
             role=role, is_active=True, created_at=now - timedelta(days=60), **kw)
    db.add(u)
    db.flush()
    ids["users"].append(u.id)
    return u


def _cup_done(db, item, day, count, correct=None, wrong=None):
    t = pm.put_in_cup(db, item=item, day=day, count=count)
    for bi in t.book_items:
        bi.completed_count, bi.correct_count, bi.wrong_count = count, correct, wrong
    t.status = TaskStatus.COMPLETED
    t.completed_at = datetime.combine(day, time(20, 0), tzinfo=timezone.utc)
    db.flush()
    pm.sync_item_progress(db, item)
    return t


def seed() -> dict:
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} Kurum", slug=f"{PFX}-k", contact_email=f"{PFX}@t.invalid",
                           plan="etut_standart", is_active=True)
        db.add(inst)
        db.flush()
        ids["inst"].append(inst.id)
        admin = _user(db, "admin", UserRole.INSTITUTION_ADMIN, institution_id=inst.id)
        coach = _user(db, "coach", UserRole.TEACHER, institution_id=inst.id)
        coach2 = _user(db, "coach2", UserRole.TEACHER, institution_id=inst.id)
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(tyt)
        db.flush()
        ids["subjects"].append(tyt.id)
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        t2 = Topic(subject_id=tyt.id, name="Köklü Sayılar", order=2, teacher_id=coach.id)
        db.add_all([t1, t2])
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        ids["books"].append(b.id)
        sec = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=100, order=1, topic_id=t1.id)
        db.add(sec)
        db.flush()

        def mk_student(tag, cg, last_seen_h=20):
            s = _user(db, tag, UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                      program_mode="havuz", class_group=cg, last_seen_at=now - timedelta(hours=last_seen_h))
            sb = StudentBook(student_id=s.id, book_id=b.id)
            db.add(sb)
            db.flush()
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
            return s

        # s_main: kapanmış dönem (yüzde 50 + devir + deneme) + açık dönem
        s_main = mk_student("main", "12-A")
        p_old = pm.open_period(db, student=s_main, coach=coach, opened_on=today - timedelta(days=10),
                               expected_next_on=today - timedelta(days=3))
        i_a = pm.add_item(db, period=p_old, student=s_main, subject=tyt, quantity=10, unit="test", book=b, section=sec)
        i_b = pm.add_item(db, period=p_old, student=s_main, subject=tyt, quantity=4, unit="test", topic=t2, teacher_homework=True)
        _cup_done(db, i_a, today - timedelta(days=6), 6, correct=50, wrong=10)
        i_c = pm.add_item(db, period=p_old, student=s_main, subject=tyt, quantity=5, unit="test", topic=t2, source=SOURCE_STUDENT, created_by=s_main)
        e = ExamResult(student_id=s_main.id, created_by_id=coach.id, title=f"{PFX} TYT Deneme", exam_date=today - timedelta(days=5),
                       section=ExamSection.TYT, total_correct=50, total_wrong=10, total_blank=60, net=40.0)
        db.add(e)
        db.flush()
        ids["exams"].append(e.id)
        db.add(ExamResultQuestion(exam_result_id=e.id, question_no=1, subject_id=tyt.id, topic_id=t1.id, result=EQ_RESULT_YANLIS))
        new_p, _ = pm.finish_session(db, student=s_main, coach=coach, period=p_old, closed_on=today - timedelta(days=3),
                                     expected_next_on=today + timedelta(days=4), carry=[(i_a.id, None), (i_b.id, None)],
                                     record_session=True, agenda="Seans", coach_note="GİZLİ NOT", next_change=None, mood=3)
        i_new = pm.add_item(db, period=new_p, student=s_main, subject=tyt, quantity=8, unit="test", book=b, section=sec)
        _cup_done(db, i_new, today, 2, correct=15, wrong=5)
        # s_late: 12-B, seans gecikti (beklenen 4 gün önce), yarı dolu
        s_late = mk_student("late", "12-B")
        p_l = pm.open_period(db, student=s_late, coach=coach, opened_on=today - timedelta(days=9),
                             expected_next_on=today - timedelta(days=4))
        i_l = pm.add_item(db, period=p_l, student=s_late, subject=tyt, quantity=10, unit="test", book=b, section=sec)
        _cup_done(db, i_l, today - timedelta(days=1), 5, correct=40, wrong=10)
        # s_today: bugün randevusu var
        s_today = mk_student("today", "12-A")
        pm.open_period(db, student=s_today, coach=coach, opened_on=today - timedelta(days=2))
        db.add(CoachingAppointment(coach_id=coach.id, student_id=s_today.id, date=today, start_time="16:00",
                                   duration_min=40, status=APPT_STATUS_SCHEDULED))
        # gün-gün öğrenci (kontrol)
        s_gun = _user(db, "gun", UserRole.STUDENT, teacher_id=coach.id, grade_level=12, program_mode="gun_gun")
        # veliler
        parent = _user(db, "veli", UserRole.PARENT)
        parent2 = _user(db, "veli2", UserRole.PARENT)
        db.add(ParentStudentLink(parent_id=parent.id, student_id=s_main.id, relation=ParentRelation.ANNE, is_primary=True))
        db.add(ParentStudentLink(parent_id=parent.id, student_id=s_gun.id, relation=ParentRelation.ANNE, is_primary=True))
        db.add(ParentStudentLink(parent_id=parent2.id, student_id=s_late.id, relation=ParentRelation.BABA, is_primary=True))
        db.add(ParentNotificationPref(parent_id=parent.id, unsubscribe_token=f"ut{PFX}"))
        db.commit()
        return {"inst": inst.id, "admin": admin.id, "coach": coach.id, "coach2": coach2.id, "main": s_main.id,
                "late": s_late.id, "today": s_today.id, "gun": s_gun.id, "parent": parent.id, "parent2": parent2.id,
                "p_old": p_old.id, "p_new": new_p.id, "tyt": tyt.id, "exam": e.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(CoachingAppointment).where(CoachingAppointment.student_id.in_(u)))
        from app.models import CoachingSession
        from app.models.exam_progress import SessionAgendaItem
        from app.models.self_study import SelfStudyEntry
        db.execute(sa_delete(CoachingSession).where(CoachingSession.student_id.in_(u)))
        db.execute(sa_delete(SessionAgendaItem).where(SessionAgendaItem.student_id.in_(u)))
        db.execute(sa_delete(NotificationLog).where(NotificationLog.parent_id.in_(u)))
        db.execute(sa_delete(ParentNotificationPref).where(ParentNotificationPref.parent_id.in_(u)))
        db.execute(sa_delete(ParentStudentLink).where(ParentStudentLink.student_id.in_(u)))
        db.execute(sa_delete(WarningState).where(WarningState.student_id.in_(u)))
        db.execute(sa_delete(ExamResultQuestion).where(ExamResultQuestion.exam_result_id.in_(ids["exams"])))
        db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(ids["exams"])))
        db.execute(sa_delete(SelfStudyEntry).where(SelfStudyEntry.student_id.in_(u)))
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
        db.execute(sa_delete(Institution).where(Institution.id.in_(ids["inst"])))
        db.commit()


def main() -> int:
    get_login_limiter().reset()
    d = seed()
    try:
        with SessionLocal() as db:
            S = {k: db.get(User, d[k]) for k in ("main", "late", "today", "gun", "parent", "parent2", "coach", "admin")}

            # ---- (a) cron susturma
            pairs = cron_jobs._all_parent_student_pairs(db)
            sids = {s.id for _, s, _ in pairs}
            check("A1 veli cron çiftleri: havuz öğrencisi ATLANIR, gün-gün öğrenci kalır",
                  d["main"] not in sids and d["late"] not in sids and d["gun"] in sids, str(sids & {d['main'], d['gun']}))
            pairs2 = cron_jobs._all_parent_student_pairs(db, include_havuz=True)
            check("A2 include_havuz=True (sınav yaklaşıyor) havuz öğrencisini kapsar",
                  d["main"] in {s.id for _, s, _ in pairs2})
            r = event_triggers.on_task_completed(db, S["main"])
            check("A3 görev tamamlanınca haftalık rapor tetiği havuz öğrencisinde susar", r["fired_for_parents"] == 0, str(r))

            # ---- (b) K53 özet
            p_old = db.get(StudyPeriod, d["p_old"])
            sm = pps.build_summary(db, p_old, today)
            check("B1 özet: yüzde 43 (6/14 birim; onaysız öğrenci kalemi sayılmaz), 7 gün",
                  sm["pct"] == 43 and sm["total_units"] == 14 and sm["done_units"] == 6 and sm["days"] == 7, f"{sm['pct']} {sm['done_units']}/{sm['total_units']} {sm['days']}")
            check("B2 devredilen 2 kalem listelendi", len(sm["carried"]) == 2, str(sm["carried"]))
            check("B3 dönem içi deneme özete girdi (net 40)", sm["exam"] and sm["exam"]["net"] == 40.0, str(sm["exam"]))
            txt = " ".join(sm["narrative"])
            check("B4 cümleler veli dilinde: yüzde + devir normal + evde destek; rehber notu YOK",
                  "yüzde 43" in txt and "ceza değil" in txt and "Evde" in txt and "GİZLİ NOT" not in txt, txt[:200])
            check("B5 öğretmen ödevi kalemi işaretli, onaysız öğrenci kalemi listede değil",
                  any(i["teacher_homework"] for i in sm["items"]) and len(sm["items"]) == 2, str(sm["items"]))
            ctx = pps.build_email_context(db, p_old, narrative=["Özel cümle."], include_items=False)
            rendered = email_service.render_template_safe("parent_pool_session_summary", {**ctx, "unsubscribe_token": "x"})
            html = rendered[1] if rendered else ""
            check("B6 e-posta şablonu render edilir; koçun cümlesi var, kalem listesi yok, yüzde var",
                  rendered is not None and "Özel cümle." in html and "Havuzdaki kalemler" not in html and "%43" in html, (html[:200] if html else "render None"))
            res = pps.send_summary(db, period=p_old, actor=S["coach"], narrative=["Özel cümle."], include_items=True)
            db.commit()
            logs = db.query(NotificationLog).filter(NotificationLog.student_id == d["main"]).all()
            check("B7 gönder: 1 veliye kuyruğa girdi (QUEUED), özel şablon, dönem damgalandı",
                  res["queued"] == 1 and len(logs) == 1 and logs[0].status == NotificationStatus.QUEUED
                  and db.get(StudyPeriod, d["p_old"]).parent_summary_sent_at is not None, str(res))
            snap = pps.sent_snapshot(db.get(StudyPeriod, d["p_old"]))
            check("B8 gönderilen hâl saklandı (yeniden açma/PDF aynı)", snap and snap["narrative"] == ["Özel cümle."], str(snap and snap.get("narrative")))

            # ---- (c) K54/K55 kurum
            ov = build_overview(db, institution_id=d["inst"], today=today)
            g = {r["class_group"]: r for r in ov.groups}
            check("C1 kurum panosu: 3 havuz öğrencisi, 2 şube", ov.students == 3 and set(g) == {"12-A", "12-B"}, str(list(g)))
            check("C2 12-A son kapanmış dönem ortalaması %43 (tek kapanmış dönem)", g["12-A"]["last_pct"] == 43, str(g["12-A"]))
            check("C3 seansı geciken: s_late (beklenen 4 gün geçti) sarı", ov.late_sessions == 1 and ov.late[0]["student_id"] == d["late"]
                  and ov.late[0]["level"] == "amber" and ov.late[0]["late_days"] == 4, str(ov.late))
            cr = {r["coach_id"]: r for r in ov.coach_rows}
            check("C4 K55 rehber yükü: koç1 bugün 1 görüşme + 1 geciken seans; koç2 0",
                  cr[d["coach"]]["today_sessions"] == 1 and cr[d["coach"]]["late_sessions"] == 1 and cr[d["coach"]]["load"] >= 2
                  and cr[d["coach2"]]["load"] == 0, str(cr))

            # ---- (d) K56 Rota
            bundle = parent_commentary.build_bundle(db, S["parent"], S["main"], "program", today)
            check("D1 Rota program paketi havuz modelinde: dönem + kalemler + kap günleri, 'GİZLİ NOT' yok",
                  bundle.get("model") == "havuz" and bundle["period"]["total_units"] == 16 and len(bundle["items"]) == 3
                  and "GİZLİ NOT" not in str(bundle), str(bundle.get("period")))
            prompt = parent_commentary._build_prompt("program", bundle)
            check("D2 istem havuz modelini anlatır ('bu dönem')", "HAVUZU" in prompt and "bu dönem" in prompt)
            sig = parent_commentary.compute_signature(db, d["main"], "program", today)
            check("D3 bayatlık imzası dönem bazlı", sig.get("period") == d["p_new"] and sig["total"] == 16, str(sig))
            gr = parent_chat.build_greeting(db, S["main"], today)
            check("D4 Rota karşılaması: 'havuzundan 1 kalem aldı, 1 tanesini işaretledi' + dönem yüzdesi",
                  "havuzundan 1 kalem aldı" in gr["text"] and "1 tanesini işaretledi" in gr["text"] and any(c["id"] == "havuz" for c in gr["chips"]), gr["text"])
            gg = parent_chat.build_greeting(db, S["gun"], today)
            check("D5 gün-gün öğrencide karşılama değişmedi", "havuz" not in gg["text"].lower())

            # ---- (e) K48 günlük liste
            dl = pool_coach_day.build_daily_list(db, coach=S["coach"], today=today, now=now)
            order = [r["student_id"] for r in dl["rows"]]
            check("E1 bugünkü randevu ÜSTTE, sonra sinyal şiddeti", order[0] == d["today"] and dl["counts"]["sessions_today"] == 1, str(order))
            check("E2 gün-gün öğrenci listede değil; satırda 1 ana + ek sinyaller + yüzde",
                  d["gun"] not in order and all(("primary" in r and "extra" in r) for r in dl["rows"]), str(order))
            db.rollback()

        # ---- HTTP
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_coach@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        base = f"/api/v2/teacher/students/{d['main']}"
        r = c.get(f"{base}/pool/periods/{d['p_old']}/parent-summary")
        j = r.json()
        check("H1 önizleme: gönderilmiş snapshot + alıcı listesi (1 veli, gönderilir)",
              r.status_code == 200 and j["is_sent_snapshot"] and j["narrative"] == ["Özel cümle."]
              and len(j["recipients"]) == 1 and j["recipients"][0]["will_send"], r.text[:200])
        r = c.post(f"{base}/pool/periods/{d['p_old']}/parent-summary/send", json={"narrative": ["x"]})
        check("H2 ikinci gönderim 409 already_sent", r.status_code == 409 and r.json()["detail"]["code"] == "already_sent", r.text[:150])
        r = c.post(f"{base}/pool/periods/{d['p_new']}/parent-summary/send", json={})
        check("H3 açık dönem gönderilemez 409 period_open", r.status_code == 409 and r.json()["detail"]["code"] == "period_open", r.text[:150])
        r = c.get(f"{base}/pool")
        briefs = {p["id"]: p for p in r.json()["periods"]}
        check("H4 editör paketi: eski dönemde parent_summary_sent_at dolu, yenide boş",
              briefs[d["p_old"]]["parent_summary_sent_at"] and briefs[d["p_new"]]["parent_summary_sent_at"] is None)
        r = c.get(f"/api/v2/teacher/students/{d['late']}/pool/periods/{d['p_old']}/parent-summary")
        check("H5 başka öğrencinin dönemi 404", r.status_code == 404)
        r = c.get("/api/v2/teacher/pool/daily")
        j = r.json()
        check("H6 günlük liste ucu: 3 satır, ilk satır bugünkü randevu 16:00",
              r.status_code == 200 and j["counts"]["students"] == 3 and j["rows"][0]["appointment_time"] == "16:00", r.text[:200])
        # Gördüm/Ertele günlük listede
        code = next((x["primary"]["code"] for x in j["rows"] if x["student_id"] == d["late"] and x["primary"]), None)
        if code:
            c.post("/api/v2/teacher/dashboard/warnings/ack", json={"student_id": d["late"], "code": code, "snooze_days": 3})
            r = c.get("/api/v2/teacher/pool/daily")
            row = next(x for x in r.json()["rows"] if x["student_id"] == d["late"])
            check("H7 K50 Gördüm: günlük listede ana sinyal ertelenmiş işaretli, sayım düştü",
                  row["primary_snoozed"] and r.json()["counts"]["snoozed"] == 1, str(row["primary_snoozed"]))
        else:
            check("H7 K50 Gördüm (s_late'in ana sinyali yok?)", False, str(j["rows"]))
        c.cookies.clear()
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_admin@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        r = c.get("/api/v2/institution/pool-overview")
        j = r.json()
        check("H8 kurum ucu: şube satırları + geciken seans + rehber yükü",
              r.status_code == 200 and len(j["groups"]) == 2 and len(j["late"]) == 1 and j["coaches_rows"][0]["load"] >= 2, r.text[:200])
        c.cookies.clear()
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_veli@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        r = c.get(f"/api/v2/parent/students/{d['main']}/pool")
        j = r.json()
        check("H9 K52 veli salt-okuma: havuz %, 3 kalem, bugünün kabı 1, önceki dönem listesi",
              r.status_code == 200 and j["summary"]["total_units"] == 16 and len(j["items"]) == 3 and len(j["cup"]) == 1
              and len(j["previous"]) == 1, r.text[:300])
        r = c.get(f"/api/v2/parent/students/{d['late']}/pool")
        check("H10 bağ olmayan çocuk 404", r.status_code == 404)
        r = c.get(f"/api/v2/parent/students/{d['gun']}/pool")
        check("H11 gün-gün çocukta mode gun_gun, dönem yok", r.status_code == 200 and r.json()["mode"] == "gun_gun" and r.json()["period_id"] is None)
        r = c.get(f"/api/v2/parent/students/{d['main']}/chat")
        check("H12 Rota sohbet karşılaması havuz dilinde (veli ucu)", r.status_code == 200 and "havuz" in r.json()["greeting"]["text"].lower(), r.text[:200])
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    if failed:
        print("Başarısız:", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
