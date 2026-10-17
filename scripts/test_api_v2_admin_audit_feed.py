"""/admin/audit/feed — birleşik denetim akışı smoke.

Kurulum: koç + öğrenci; koçun girişi (audit) + deneme karnesi (exam_results, PDF) +
öğrenci başarısız giriş + kilitlenme. Kontroller: Türkçe başlıklar, kategori/önem,
aktör süzgeci + gezilen sayfalar, kategori süzgeci, kritik süzgeci, kişi araması
(e-posta denemesi dahil), yetki 403.
"""
from __future__ import annotations

import json
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
from app.models import ExamResult, User, UserRole
from app.models.audit_log import AuditAction, AuditLog
from app.models.exam_result import ExamSection
from app.models.panel_behavior import PanelVisitEvent
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"aud{secrets.token_hex(3)}"
PWD = "AuditFeed!23456x"
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
        print(f"  [FAIL] {label}  ({str(detail)[:300]})")


def mk(db, tag, role, **kw):
    u = User(email=f"{PFX}-{tag}@test.invalid", password_hash=hash_password(PWD), full_name=f"{PFX} {tag}",
             role=role, is_active=True, must_change_password=False, created_at=now - timedelta(days=20), **kw)
    db.add(u)
    db.flush()
    return u


def main() -> int:
    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        admin = mk(db, "admin", UserRole.SUPER_ADMIN)
        coach = mk(db, "koc", UserRole.TEACHER)
        stu = mk(db, "ogr", UserRole.STUDENT, teacher_id=coach.id, grade_level=12)
        stu.created_at = now - timedelta(hours=2)
        db.add_all([
            AuditLog(actor_id=coach.id, action=AuditAction.LOGIN_SUCCESS, user_agent="Mozilla/5.0 (Windows NT 10.0) Chrome/150",
                     ip_address="1.2.3.4", details_json=json.dumps({"role": "teacher", "channel": "api_v2"}),
                     created_at=now - timedelta(minutes=30)),
            AuditLog(actor_id=None, email_attempted=f"{PFX}-ogr@test.invalid", action=AuditAction.LOGIN_FAILED,
                     details_json=json.dumps({"reason": "wrong_password", "failed_count": 2}), created_at=now - timedelta(minutes=20)),
            AuditLog(actor_id=stu.id, action=AuditAction.LOGIN_LOCKED,
                     details_json=json.dumps({"reason": "wrong_password", "failed_count": 5, "triggered_lock": True}),
                     created_at=now - timedelta(minutes=10)),
            ExamResult(student_id=stu.id, created_by_id=coach.id, title=f"{PFX} TYT-3", exam_date=date.today(),
                       section=ExamSection.TYT, total_correct=60, total_wrong=8, total_blank=52, net=58.0,
                       import_source="pdf_import", created_at=now - timedelta(minutes=25)),
            PanelVisitEvent(user_id=coach.id, role="teacher", route_key="teacher.student_exams" , dwell_ms=90000,
                            source="web", created_at=now - timedelta(minutes=24)),
        ])
        db.commit()
        ids = {"admin": admin.id, "coach": coach.id, "stu": stu.id}

    try:
        c = TestClient(app)
        assert c.post("/api/v2/auth/login", json={"email": f"{PFX}-admin@test.invalid", "password": PWD}).status_code == 200
        r = c.get(f"/api/v2/admin/audit/feed?days=1&actor_id={ids['coach']}")
        chk("200", r.status_code == 200, r.text[:200])
        d = r.json()
        titles = [i["title"] for i in d["items"]]
        chk("koç girişi Türkçe + cihaz", any(i["title"] == "Giriş yaptı" and i["device"] == "Chrome · Windows" and i["ip"] == "1.2.3.4"
                                          for i in d["items"]), d["items"][:2])
        ex = next((i for i in d["items"] if i["title"].startswith("Deneme karnesini PDF")), None)
        chk("deneme karnesi olayı (alan tablosundan) + hedef öğrenci",
            ex is not None and ex["target_name"] == f"{PFX} ogr" and ex["category"] == "coaching", titles)
        chk("deneme ayrıntıları Türkçe (Net 58,00)",
            ex is not None and {"label": "Net", "value": "58,00"} in ex["details"], ex and ex["details"])
        chk("giriş satırında 'Rol' tekrarı yok",
            all(x["label"] != "Rol" for i in d["items"] if i["title"] == "Giriş yaptı" for x in i["details"]))
        f = d["focus"]
        chk("kişi odağı + gezilen sayfa", f and f["name"] == f"{PFX} koc" and f["pages"]
            and f["pages"][0]["minutes"] == 1.5, f)
        r = c.get(f"/api/v2/admin/audit/feed?days=1&q={PFX}-ogr")
        t = [i["title"] for i in r.json()["items"]]
        chk("kişi araması e-posta denemesini de bulur", any("Giriş denemesi başarısız" in x for x in t)
            and any("Hesap kilitlendi" in x for x in t), t)
        r = c.get(f"/api/v2/admin/audit/feed?days=1&q={PFX}&severity=critical").json()
        chk("kritik süzgeci yalnız kilitlenme", [i["title"] for i in r["items"]] == ["Hesap kilitlendi (çok sayıda yanlış şifre)"],
            [i["title"] for i in r["items"]])
        r = c.get(f"/api/v2/admin/audit/feed?days=1&q={PFX}&category=coaching").json()
        chk("kategori süzgeci (koçluk)", r["items"] and all(i["category"] == "coaching" for i in r["items"]), r["items"])
        chk("sayımlar kategori bazında", r["counts"]["categories"]["security"] >= 3, r["counts"])
        ck = TestClient(app)
        ck.post("/api/v2/auth/login", json={"email": f"{PFX}-koc@test.invalid", "password": PWD})
        chk("koç erişemez 403", ck.get("/api/v2/admin/audit/feed").status_code == 403)
    finally:
        with SessionLocal() as db:
            uids = list(ids.values())
            db.execute(delete(PanelVisitEvent).where(PanelVisitEvent.user_id.in_(uids)))
            db.execute(delete(ExamResult).where(ExamResult.student_id.in_(uids)))
            db.execute(delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
            db.execute(delete(AuditLog).where(AuditLog.email_attempted.like(f"{PFX}%")))
            db.execute(delete(User).where(User.id.in_(uids)))
            db.commit()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
