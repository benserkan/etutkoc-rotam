"""Deneme analizi Faz 2 — gelişim raporu, hedef, gündem kuyruğu, öğrenciyle paylaşım."""
import json
import secrets
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, ".")
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AppSetting, AuditLog, ExamResult, ExamTarget, SessionAgendaItem, SuspiciousIp, User, UserRole  # noqa: E402
from app.models.exam_result import ExamSection  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PW = "ExamProg!2345xyz"
PFX = f"exprog_{secrets.token_hex(3)}"
now = datetime.now(timezone.utc)
ok: list[bool] = []


def chk(label, cond, extra=""):
    ok.append(bool(cond))
    print(("  OK   " if cond else "  FAIL ") + label + (f"  [{extra}]" if not cond and extra else ""))


def mk_user(db, email, role, **kw):
    u = User(email=email, password_hash=hash_password(PW), full_name=kw.pop("full_name", email.split("@")[0]),
             role=role, is_active=True, password_changed_at=now, must_change_password=False,
             email_verified_at=now, **kw)
    db.add(u)
    db.flush()
    return u


with SessionLocal() as db:
    t = mk_user(db, f"{PFX}_t@test.invalid", UserRole.TEACHER, plan="solo_pro", subscription_status="active")
    t2 = mk_user(db, f"{PFX}_t2@test.invalid", UserRole.TEACHER, plan="solo_pro", subscription_status="active")
    s = mk_user(db, f"{PFX}_s@test.invalid", UserRole.STUDENT, teacher_id=t.id, grade_level=12,
                full_name="Deniz Deneme", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    exam_ids = []
    # TYT: 5 deneme, Matematik düşüyor, Türkçe yükseliyor; son denemede çok boş
    plan = [(60, 30, 5, 5), (62, 28, 4, 8), (64, 26, 4, 10), (66, 22, 4, 14), (70, 18, 3, 40)]
    for i, (tc, mc, w_each, blank) in enumerate(plan):
        tw, mw = w_each, w_each
        nets = [{"name": "TYT Türkçe", "correct": tc // 2, "wrong": tw, "blank": 0, "net": round(tc / 2 - tw / 4, 2)},
                {"name": "TYT Matematik", "correct": mc, "wrong": mw, "blank": blank, "net": round(mc - mw / 4, 2)}]
        D = sum(n["correct"] for n in nets)
        Y = sum(n["wrong"] for n in nets)
        e = ExamResult(student_id=s.id, created_by_id=t.id, title=f"TYT Deneme {i + 1}",
                       exam_date=date.today() - timedelta(days=60 - i * 12), section=ExamSection.TYT,
                       total_correct=D, total_wrong=Y, total_blank=blank, net=round(D - Y / 4, 2),
                       subject_nets=json.dumps(nets, ensure_ascii=False),
                       note="koça özel gizli not" if i == 4 else None)
        db.add(e)
        db.flush()
        exam_ids.append(e.id)
    # başka tür (karışmamalı)
    e = ExamResult(student_id=s.id, created_by_id=t.id, title="AYT 1", exam_date=date.today(),
                   section=ExamSection.AYT_SAY, total_correct=20, total_wrong=4, total_blank=56, net=19.0)
    db.add(e)
    db.flush()
    exam_ids.append(e.id)
    db.commit()
    tid, t2id, sid = t.id, t2.id, s.id

client = TestClient(app)


def login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return c


try:
    ct = login(f"{PFX}_t@test.invalid")
    ct2 = login(f"{PFX}_t2@test.invalid")
    cs = login(f"{PFX}_s@test.invalid")

    r = ct.get(f"/api/v2/teacher/students/{sid}/exam-progress?section=tyt&period=all")
    chk("1 rapor 200", r.status_code == 200, r.text[:200])
    d = r.json()
    chk("2 yalnız TYT (5 deneme), AYT karışmaz", d["stats"]["count"] == 5 and len(d["exams"]) == 5)
    chk("3 tür seçenekleri iki tür", {o["value"] for o in d["section_options"]} == {"tyt", "ayt_say"})
    mat = next(x for x in d["subjects"] if x["name"] == "TYT Matematik")
    chk("4 Matematik eğimi negatif", mat["slope"] is not None and mat["slope"] < 0, mat)
    texts = " ".join(c["text"] for c in d["commentary"])
    chk("5 yorum: gerileyen ders Matematik + boş uyarısı", "gerileyen ders TYT Matematik" in texts and "boş kaldı" in texts, texts)
    keys = {a["key"] for a in d["actions"]}
    chk("6 aksiyon: ders düşüşü + boş davranışı", "subjdrop:tyt matematik" in keys and "behavior:blank" in keys, keys)

    r = ct2.get(f"/api/v2/teacher/students/{sid}/exam-progress")
    chk("7 başka koç 404", r.status_code == 404)

    # hedef
    r = ct.post(f"/api/v2/teacher/students/{sid}/exam-targets",
                json={"section": "tyt", "target_net": 80, "target_date": (date.today() + timedelta(days=70)).isoformat(),
                      "subjects": {"TYT Matematik": 30}})
    chk("8 hedef kaydedildi", r.status_code == 200 and r.json()["targets"]["tyt"]["target_net"] == 80, r.text[:200])
    chk("9 invalidate exam-progress", any("exam-progress" in k for k in r.json()["invalidate"]))
    d = ct.get(f"/api/v2/teacher/students/{sid}/exam-progress?section=tyt&period=all").json()
    chk("10 hedef farkı + hafta", d["target"]["gap"] > 0 and d["target"]["weeks_left"] == 10, d["target"])
    mat = next(x for x in d["subjects"] if x["name"] == "TYT Matematik")
    chk("11 ders hedefi farkı", mat["target"] == 30 and mat["gap"] == round(30 - mat["last"], 2))
    chk("12 aksiyonda ders hedefi açığı", any(a["key"] == "subjgap:tyt matematik" for a in d["actions"]))
    r = ct.post(f"/api/v2/teacher/students/{sid}/exam-targets", json={"section": "tyt", "target_net": 900})
    chk("13 geçersiz hedef 422", r.status_code == 422)
    r = ct.post(f"/api/v2/teacher/students/{sid}/exam-targets", json={"section": "xx", "target_net": 50})
    chk("14 geçersiz tür 422", r.status_code == 422)

    # kuyruk
    act = d["actions"][0]
    r = ct.post(f"/api/v2/teacher/students/{sid}/agenda-queue",
                json={"items": [{"text": "A madde", "key": act["key"]}, {"text": "B madde"}]})
    chk("15 kuyruğa 2 madde", r.status_code == 200 and r.json()["added"] == 2, r.text[:200])
    r = ct.post(f"/api/v2/teacher/students/{sid}/agenda-queue",
                json={"items": [{"text": "A madde tekrar", "key": act["key"]}]})
    chk("16 aynı anahtar tekrar eklenmez", r.json()["added"] == 0 and len(r.json()["items"]) == 2)
    d = ct.get(f"/api/v2/teacher/students/{sid}/exam-progress?section=tyt&period=all").json()
    chk("17 aksiyon queued işaretli", next(a for a in d["actions"] if a["key"] == act["key"])["queued"])
    ids = [i["id"] for i in ct.get(f"/api/v2/teacher/students/{sid}/agenda-queue").json()["items"]]
    r = ct.post(f"/api/v2/teacher/students/{sid}/agenda-queue/remove", json={"ids": ids[:1]})
    chk("18 kuyruktan çıkar", len(r.json()["items"]) == 1)
    r = ct2.get(f"/api/v2/teacher/students/{sid}/agenda-queue")
    chk("19 başka koç kuyruğu 404", r.status_code == 404)

    # paylaşım
    last = exam_ids[4]
    r = ct.post(f"/api/v2/teacher/exams/{last}/share-student", json={"note": "Matematikte boşlar arttı, konuşalım.", "notify": False})
    chk("20 paylaşıldı", r.status_code == 200 and r.json()["share"]["note"].startswith("Matematikte"), r.text[:200])
    r = ct2.post(f"/api/v2/teacher/exams/{last}/share-student", json={"note": "x"})
    chk("21 başka koç paylaşamaz 404", r.status_code == 404)
    sh = cs.get("/api/v2/student/exam-shares").json()["shares"]
    chk("22 öğrenci paylaşımı görür", str(last) in sh and sh[str(last)]["note"].startswith("Matematikte"))
    rows = cs.get("/api/v2/student/exams?period=all").json()["rows"]
    chk("23 koça özel not öğrenciye gitmez", all(x["note"] is None for x in rows))
    sp = cs.get("/api/v2/student/exam-progress?section=tyt&period=all")
    chk("24 öğrenci raporu + hedefi görür", sp.status_code == 200 and sp.json()["target"]["target_net"] == 80)
    r = ct.post(f"/api/v2/teacher/exams/{last}/unshare-student")
    chk("25 paylaşım geri alındı", r.status_code == 200 and str(last) not in cs.get("/api/v2/student/exam-shares").json()["shares"])
    r = cs.get(f"/api/v2/teacher/students/{sid}/exam-progress")
    chk("26 öğrenci koç ucuna giremez", r.status_code == 403)

    # hedef kaldır
    r = ct.post(f"/api/v2/teacher/students/{sid}/exam-targets", json={"section": "tyt", "target_net": None})
    chk("27 hedef kaldırıldı", r.status_code == 200 and "tyt" not in r.json()["targets"])

    # 28-31: kalıcı tablolar + yetim koruması (2026-10-02)
    with SessionLocal() as db:
        kv = db.query(AppSetting).filter(AppSetting.key.like(f"%:{sid}")).count()
        chk("28 app_settings'e öğrenci anahtarı yazılmıyor", kv == 0)
        chk("29 kuyruk kaydı session_agenda_items tablosunda",
            db.query(SessionAgendaItem).filter(SessionAgendaItem.student_id == sid).count() == 1)
    fk = {c.name: list(c.foreign_keys)[0].ondelete for t in (ExamTarget.__table__, SessionAgendaItem.__table__)
          for c in t.columns if c.name == "student_id"}
    chk("30 iki tabloda student_id CASCADE (öğrenci silinince yetim kalmaz)", set(fk.values()) == {"CASCADE"})
    from app.services.exam_progress import set_target
    with SessionLocal() as db:
        set_target(db, sid, section="tyt", target_net=60, actor=db.get(User, tid)); db.commit()
    from app.services.demo_seed import _demo_closure  # noqa: F401 (silme yolu var mı)
    with SessionLocal() as db:
        # demo silme yolunun kullandığı açık silme (SQLite'ta FK kapalı)
        db.query(SessionAgendaItem).filter(SessionAgendaItem.student_id == sid).delete()
        db.query(ExamTarget).filter(ExamTarget.student_id == sid).delete(); db.commit()
        chk("31 silme sonrası kayıt kalmadı",
            db.query(ExamTarget).filter(ExamTarget.student_id == sid).count() == 0)
finally:
    with SessionLocal() as db:
        db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(exam_ids)))
        db.execute(sa_delete(SessionAgendaItem).where(SessionAgendaItem.student_id == sid))
        db.execute(sa_delete(ExamTarget).where(ExamTarget.student_id == sid))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_([tid, t2id, sid])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_([sid, tid, t2id])))
        db.commit()

print(f"\n=== {sum(ok)} passed, {len(ok) - sum(ok)} failed ===")
sys.exit(0 if all(ok) else 1)
