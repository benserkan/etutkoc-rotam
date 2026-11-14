# -*- coding: utf-8 -*-
"""Kurum yöneticisi "Koçlara mesajlar" smoke — 2026-11-14."""
from __future__ import annotations

import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.database import SessionLocal
from app.main import app
from app.models import Institution, User, UserRole
from app.models.message_suggestion import MessageSuggestionAction
from app.models.whatsapp_dispatch_log import WhatsAppDispatchLog
from app.services import message_suggestions as ms
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"imsg_{secrets.token_hex(3)}"
PWD = "InstMsg!2345"
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
        i1 = Institution(name=f"{PFX} Kurum", slug=f"{PFX}-k1", plan="etut_standart", is_active=True)
        i2 = Institution(name=f"{PFX} Diğer", slug=f"{PFX}-k2", plan="etut_standart", is_active=True)
        db.add_all([i1, i2]); db.flush()

        def u(tag, role, **kw):
            x = User(email=f"{PFX}_{tag}@test.invalid", password_hash=pwd, full_name=f"Ayşe {tag}",
                     role=role, is_active=True, password_changed_at=now, must_change_password=False,
                     created_at=now - timedelta(days=60), **kw)
            db.add(x); db.flush(); return x
        a = u("a", UserRole.INSTITUTION_ADMIN, institution_id=i1.id)
        c = u("c", UserRole.TEACHER, institution_id=i1.id, phone="905321220001")
        c2 = u("c2", UserRole.TEACHER, institution_id=i2.id)
        s1 = u("s1", UserRole.STUDENT, teacher_id=c.id, institution_id=i1.id, grade_level=8)
        s2 = u("s2", UserRole.STUDENT, teacher_id=c.id, institution_id=i1.id, grade_level=8)
        db.commit()
        return {"i1": i1.id, "i2": i2.id, "a": a.id, "c": c.id, "c2": c2.id, "s": [s1.id, s2.id]}


def cleanup(d):
    with SessionLocal() as db:
        db.execute(delete(MessageSuggestionAction).where(MessageSuggestionAction.coach_id == d["a"]))
        db.execute(delete(WhatsAppDispatchLog).where(WhatsAppDispatchLog.sender_user_id == d["a"]))
        db.execute(delete(User).where(User.id.in_([d["a"], d["c"], d["c2"], *d["s"]])))
        db.execute(delete(Institution).where(Institution.id.in_([d["i1"], d["i2"]])))
        db.commit()
    ms._CACHE.clear()


def login(c, tag):
    get_login_limiter().reset()
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{tag}@test.invalid", "password": PWD})
    assert r.status_code == 200, r.text


def main():
    d = seed()
    try:
        cl = TestClient(app)
        login(cl, "a")
        r = cl.get("/api/v2/institution/message-suggestions")
        check("1 liste 200", r.status_code == 200, r.text[:200])
        items = r.json().get("items", [])
        mine = [i for i in items if i["group_id"] == d["c"]]
        emp = next((i for i in mine if i["key"].startswith("inst_empty")), None)
        check("2 programsız öğrenciler önerisi", emp is not None, str([i["key"] for i in mine]))
        check("3 koça sohbet açan metin", emp and "Hocam" in emp["text"] and "?" in emp["text"], emp and emp["text"])
        check("4 alıcı koç, telefonlu", emp and emp["targets"][0]["user_id"] == d["c"] and emp["targets"][0]["can_message"])
        check("5 başka kurum koçu listede yok", not any(i["group_id"] == d["c2"] for i in items))
        r = cl.post("/api/v2/institution/message-suggestions/send",
                    json={"coach_id": d["c"], "key": emp["key"], "text": emp["text"]})
        check("6 gönder 200", r.status_code == 200, r.text[:200])
        check("7 koçun numarasıyla wa.me", "wa.me/905321220001" in r.json().get("wa_url", ""))
        check("8 sayaç 1", r.json().get("sent_today") == 1)
        after = cl.get("/api/v2/institution/message-suggestions").json()["items"]
        check("9 gönderilen düştü", not any(i["key"] == emp["key"] and i["group_id"] == d["c"] for i in after))
        r = cl.post("/api/v2/institution/message-suggestions/send",
                    json={"coach_id": d["c2"], "key": "inst_empty:x", "text": "x"})
        check("10 başka kurum koçu 404", r.status_code == 404, str(r.status_code))
        r = cl.post("/api/v2/institution/message-suggestions/send",
                    json={"coach_id": d["c"], "key": "yok", "text": "x"})
        check("11 geçersiz öneri 409", r.status_code == 409, str(r.status_code))
        r = cl.post("/api/v2/institution/message-suggestions/skip", json={"coach_id": d["c2"], "key": "x"})
        check("12 başka kurum atla 404", r.status_code == 404, str(r.status_code))
        ct = TestClient(app)
        login(ct, "c")
        r = ct.get("/api/v2/institution/message-suggestions")
        check("13 koç kurum ucuna giremez", r.status_code in (401, 403), str(r.status_code))
    finally:
        cleanup(d)
    print(f"\n{passed} geçti, {len(failed)} kaldı")
    for f in failed:
        print("  -", f)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
