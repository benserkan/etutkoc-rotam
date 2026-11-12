# -*- coding: utf-8 -*-
"""Rapor paylaşımı (PDF + WhatsApp) smoke — /messaging/share-targets + /share-link (2026-11-12)."""
from __future__ import annotations

import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import ParentRelation, ParentStudentLink, User, UserRole, WhatsAppDispatchLog
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"shr_{secrets.token_hex(3)}"
PWD = "ShareRep!2345"
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


def seed():
    now = datetime.now(timezone.utc)
    pwd = hash_password(PWD)
    with SessionLocal() as db:
        def u(tag, role, **kw):
            x = User(email=f"{PFX}_{tag}@test.invalid", password_hash=pwd, full_name=f"{PFX} {tag}",
                     role=role, is_active=True, password_changed_at=now, must_change_password=False, **kw)
            db.add(x); db.flush(); return x
        t = u("t", UserRole.TEACHER)
        t2 = u("t2", UserRole.TEACHER)
        s = u("s", UserRole.STUDENT, teacher_id=t.id, grade_level=12)
        s2 = u("s2", UserRole.STUDENT, teacher_id=t2.id, grade_level=12)
        pa = u("pa", UserRole.PARENT, phone="905321112233")
        pb = u("pb", UserRole.PARENT)  # numarasız
        par = u("par", UserRole.PARENT)
        db.add(ParentStudentLink(parent_id=pa.id, student_id=s.id, relation=ParentRelation.ANNE, is_primary=True))
        db.add(ParentStudentLink(parent_id=pb.id, student_id=s.id, relation=ParentRelation.BABA, is_primary=False))
        db.commit()
        return {k: v.id for k, v in dict(t=t, t2=t2, s=s, s2=s2, pa=pa, pb=pb, par=par).items()}


def cleanup(d):
    from sqlalchemy import delete
    with SessionLocal() as db:
        db.execute(delete(WhatsAppDispatchLog).where(WhatsAppDispatchLog.sender_user_id.in_([d["t"], d["t2"]])))
        db.execute(delete(ParentStudentLink).where(ParentStudentLink.student_id.in_([d["s"], d["s2"]])))
        db.execute(delete(User).where(User.id.in_(list(d.values()))))
        db.commit()


def login(tag):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{tag}@test.invalid", "password": PWD})
    assert r.status_code == 200, r.text
    return c


def main():
    d = seed()
    try:
        c = login("t")
        r = c.get(f"/api/v2/messaging/share-targets?student_id={d['s']}")
        check("1 kişiler 200", r.status_code == 200, r.text[:200])
        tg = r.json().get("targets", [])
        labels = [x["relation_label"] for x in tg]
        check("2 anne önce, baba, sonra öğrencinin kendisi",
              labels == ["Annesi", "Babası", "Öğrencinin kendisi"], str(labels))
        check("3 numarası olan anne gönderilebilir, numarasız baba gönderilemez",
              tg[0]["can_message"] and not tg[1]["can_message"], str(tg))
        check("4 telefon maskeli", tg[0]["phone_masked"] and "***" in tg[0]["phone_masked"], str(tg[0]))

        body = {"student_id": d["s"], "kind": "exam_card", "text": "Merhaba, karne ekte.",
                "target_user_id": d["pa"], "ref_id": 77}
        r = c.post("/api/v2/messaging/share-link", json=body)
        check("5 anneye bağlantı 200", r.status_code == 200, r.text[:200])
        j = r.json()
        check("6 wa.me numaralı + metin kodlu", j["wa_url"].startswith("https://wa.me/905321112233?text=Merhaba"), j.get("wa_url"))
        with SessionLocal() as db:
            log = db.get(WhatsAppDispatchLog, j["log_id"])
            pj = json.loads(log.params_json)
            check("7 denetim kaydı: pdf_share:exam_card, hedef anne, öğrenci+ref",
                  log.template_key == "pdf_share:exam_card" and log.target_user_id == d["pa"]
                  and pj["student_id"] == d["s"] and pj["ref_id"] == 77, f"{log.template_key} {pj}")

        r = c.post("/api/v2/messaging/share-link", json={**body, "target_user_id": d["pb"]})
        check("8 numarasız babaya 400 target_phone_missing", r.status_code == 400
              and r.json()["detail"]["code"] == "target_phone_missing", r.text[:200])
        r = c.post("/api/v2/messaging/share-link", json={**body, "target_user_id": None})
        check("9 kişisiz: wa.me/?text, kayıt hedefsiz", r.status_code == 200
              and r.json()["wa_url"].startswith("https://wa.me/?text="), r.text[:200])
        r = c.post("/api/v2/messaging/share-link", json={**body, "target_user_id": d["par"]})
        check("10 öğrenciye bağlı olmayan veli → 404", r.status_code == 404, r.text[:200])
        r = c.post("/api/v2/messaging/share-link", json={**body, "kind": "baska"})
        check("11 geçersiz tür → 422", r.status_code == 422, r.text[:200])
        r = c.get(f"/api/v2/messaging/share-targets?student_id={d['s2']}")
        check("12 başka koçun öğrencisi → 404", r.status_code == 404, r.text[:200])

        cp = login("pa")
        r = cp.get(f"/api/v2/messaging/share-targets?student_id={d['s']}")
        check("13 veli rolü → 403", r.status_code == 403, r.text[:200])
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
