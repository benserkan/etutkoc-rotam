"""/admin/people — rol sekmeleri + aktivite kümeleri + bağlantılar smoke.

Senaryo: 1 kurum + koç (kurumlu) + bağımsız koç; 3 öğrenci (bugün aktif / 3 gün
önce / hiç girmedi) + 1 veli (kurumlu öğrenciye bağlı). Kontroller: rol sayıları,
aktivite kümeleri, veli → çocuk (koç + kurum) + kurum adı çocuktan, öğrenci → koç
+ son 7 gün görev, koç → öğrenci sayısı + paket durumu, kurum süzgeci veliyi de
yakalar, sayfalama, set-active (kendi/süper admin 403), yetki 403.
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.database import SessionLocal
from app.main import app
from app.models import Institution, User, UserRole
from app.models.parent import ParentStudentLink
from app.models.suspicious_ip import SuspiciousIp
from app.models.task import Task, TaskBookItem, TaskStatus, TaskType
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"ppl{secrets.token_hex(3)}"
PWD = "People!234567xy"
now = datetime.now(timezone.utc)
passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def mk(db, tag, role, **kw):
    u = User(email=f"{PFX}-{tag}@test.invalid", password_hash=hash_password(PWD),
             full_name=f"{PFX} {tag}", role=role, is_active=True, must_change_password=False,
             created_at=now - timedelta(days=30), **kw)
    db.add(u)
    db.flush()
    return u


def login(email):
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return c


def main() -> int:
    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        inst = Institution(name=f"{PFX} Kurum", slug=f"{PFX}-k", plan="etut_standart", is_active=True)
        db.add(inst)
        db.flush()
        admin = mk(db, "admin", UserRole.SUPER_ADMIN)
        coach = mk(db, "koc", UserRole.TEACHER, institution_id=inst.id)
        solo = mk(db, "solo", UserRole.TEACHER, plan="solo_free", post_trial_plan="solo_pro")
        trial = mk(db, "trial", UserRole.TEACHER, plan="solo_trial", trial_ends_at=now + timedelta(days=5),
                   post_trial_plan="solo_pro")
        s1 = mk(db, "s1", UserRole.STUDENT, teacher_id=coach.id, institution_id=inst.id,
                grade_level=9, last_seen_at=now - timedelta(minutes=5))
        s2 = mk(db, "s2", UserRole.STUDENT, teacher_id=coach.id, institution_id=inst.id,
                grade_level=10, last_login_at=now - timedelta(days=3))
        s3 = mk(db, "s3", UserRole.STUDENT, teacher_id=solo.id, grade_level=12)
        par = mk(db, "veli", UserRole.PARENT)
        db.add(ParentStudentLink(parent_id=par.id, student_id=s1.id))
        t = Task(student_id=s1.id, date=date.today() - timedelta(days=1), type=TaskType.TEST,
                 title="x", status=TaskStatus.COMPLETED, is_draft=False)
        t.book_items = [TaskBookItem(label="x", planned_count=2, completed_count=2)]
        db.add(t)
        db.commit()
        ids = {k: v.id for k, v in dict(admin=admin, coach=coach, solo=solo, trial=trial, s1=s1, s2=s2, s3=s3, par=par).items()}
        inst_id = inst.id

    try:
        c = login(f"{PFX}-admin@test.invalid")
        q = f"&q={PFX}"
        r = c.get(f"/api/v2/admin/people?role=student{q}")
        chk("200", r.status_code == 200, r.text[:200])
        d = r.json()
        chk("rol sayıları (3 koç · 3 öğrenci · 1 veli)",
            d["role_counts"]["teacher"] == 3 and d["role_counts"]["student"] == 3 and d["role_counts"]["parent"] == 1,
            d["role_counts"])
        ac = d["activity_counts"]
        chk("aktivite kümeleri bugün 1 · hafta 1 · hiç 1", (ac["today"], ac["week"], ac["never"]) == (1, 1, 1), ac)
        chk("varsayılan sıra son aktivite (bugünkü önde, hiç girmeyen sonda)",
            [i["id"] for i in d["items"]] == [ids["s1"], ids["s2"], ids["s3"]], [i["full_name"] for i in d["items"]])
        s1r = next(i for i in d["items"] if i["id"] == ids["s1"])
        chk("öğrenci → koç + sınıf + 7g görev 1/1",
            s1r["coach"]["id"] == ids["coach"] and s1r["grade_label"] == "9. sınıf"
            and (s1r["gorev_7d_done"], s1r["gorev_7d_total"]) == (1, 1), s1r)
        r = c.get(f"/api/v2/admin/people?role=student&activity=never{q}")
        chk("activity=never süzgeci", [i["id"] for i in r.json()["items"]] == [ids["s3"]])
        p = c.get(f"/api/v2/admin/people?role=parent{q}").json()["items"][0]
        chk("veli → çocuk + koç + kurum adı çocuktan",
            p["children"] and p["children"][0]["id"] == ids["s1"] and p["children"][0]["coach_name"]
            and p["institution_name"] == f"{PFX} Kurum", p)
        tch = {i["id"]: i for i in c.get(f"/api/v2/admin/people?role=teacher{q}").json()["items"]}
        chk("koç öğrenci sayısı (kurumlu 2 · bağımsız 1)",
            tch[ids["coach"]]["student_count"] == 2 and tch[ids["solo"]]["student_count"] == 1, tch)
        chk("bağımsız koç paket durumu: ödeme bekleniyor",
            tch[ids["solo"]]["plan_state"] == "payment_pending", tch[ids["solo"]])
        chk("kurumlu koç plan_state=institution", tch[ids["coach"]]["plan_state"] == "institution")
        ind = c.get(f"/api/v2/admin/people?role=teacher&independent=true{q}").json()
        chk("bağımsız görünüm kurumlu koçu dışlar (2)", ind["total"] == 2, ind["total"])
        pc = ind["plan_counts"]
        chk("paket sayıları: deneme 1 · ödeme bekliyor 1 · ücretsiz 0",
            (pc["trial"], pc["payment_pending"], pc["free"]) == (1, 1, 0), pc)
        r = c.get(f"/api/v2/admin/people?role=teacher&independent=true&plan=trial{q}").json()
        chk("plan=trial süzgeci + satır durumu trial",
            [i["id"] for i in r["items"]] == [ids["trial"]] and r["items"][0]["plan_state"] == "trial", r["items"])
        r = c.get(f"/api/v2/admin/people?role=teacher&independent=true&plan=payment_pending{q}").json()
        chk("plan=payment_pending → yalnız deneme bitmiş koç", [i["id"] for i in r["items"]] == [ids["solo"]], r["items"])
        r = c.get(f"/api/v2/admin/people?role=parent&institution_id={inst_id}{q}")
        chk("kurum süzgeci veliyi çocuğu üzerinden yakalar", r.json()["total"] == 1, r.json()["total"])
        r = c.get(f"/api/v2/admin/people?role=student&page_size=10&page=2{q}")
        chk("sayfalama: 2. sayfa boş, total 3", r.json()["total"] == 3 and r.json()["items"] == [])
        chk("geçersiz rol 422", c.get("/api/v2/admin/people?role=xx").status_code == 422)
        r = c.post(f"/api/v2/admin/users/{ids['s3']}/set-active", json={"is_active": False})
        chk("set-active pasife alır", r.status_code == 200 and r.json()["data"]["is_active"] is False, r.text[:200])
        with SessionLocal() as db:
            chk("DB'de pasif + kurum alanı korunur", db.get(User, ids["s3"]).is_active is False)
            chk("kurumlu öğrencinin kurumu dokunulmadı", db.get(User, ids["s1"]).institution_id == inst_id)
        chk("kendi hesabı 403",
            c.post(f"/api/v2/admin/users/{ids['admin']}/set-active", json={"is_active": False}).status_code == 403)
        cc = login(f"{PFX}-koc@test.invalid")
        chk("koç erişemez 403", cc.get("/api/v2/admin/people").status_code == 403)
    finally:
        with SessionLocal() as db:
            uids = list(ids.values())
            db.execute(delete(ParentStudentLink).where(ParentStudentLink.parent_id.in_(uids)))
            for tk in db.query(Task).filter(Task.student_id.in_(uids)).all():
                db.delete(tk)
            db.flush()
            db.execute(delete(User).where(User.id.in_(uids)))
            db.execute(delete(Institution).where(Institution.id == inst_id))
            db.commit()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
