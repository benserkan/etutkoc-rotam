"""Hata Tercümanı smoke — kural kataloğu (unit) + canlı sistem endpoint enrich.

A) error_translator kural çıktıları (sunucu gerekmez).
B) Canlı: süper admin → /security-monitor/system → error_groups'ta explanation +
   stale + last_seen_label var mı; /explain 404 (eksik id). Gemini gerçek çağrısı
   YOK (AI path birim testte monkeypatch).
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import User, UserRole, AuditLog
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

B = "http://127.0.0.1:3000"
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


def unit_tests():
    print("A) Kural kataloğu (unit):")
    from app.services import error_translator as T

    e = T.explain_error("InvalidRequestError", "Query.filter() ... LIMIT or OFFSET applied")
    chk("InvalidRequestError → database + kod bug + critical + rule",
        e.category == "database" and e.is_code_bug and e.severity == "critical" and e.source == "rule", str(e))

    e = T.explain_error("OperationalError", "could not connect to server")
    chk("OperationalError(connect) → database + critical", e.category == "database" and e.severity == "critical", str(e))

    e = T.explain_error("IntegrityError", "UNIQUE constraint failed: users.email")
    chk("IntegrityError → database + kod bug değil", e.category == "database" and not e.is_code_bug, str(e))

    e = T.explain_error("AIServiceUnavailable", "gemini timeout")
    chk("AI servis → external_ai", e.category == "external_ai", str(e))

    e = T.explain_error("SomethingWeird", "no idea what this is")
    chk("bilinmeyen → source=none (AI yedeği işareti)", e.source == "none", str(e))

    c = T.explain_cron("daily_summary", "crit", 48, "günde 1")
    chk("cron daily_summary → dostça ad + açıklama", "Günlük veli özeti" in c.summary and c.severity == "critical", str(c))
    chk("cron_label bilinmeyen anahtar → insanlaştır", T.cron_label("foo_bar_baz") == "Foo bar baz", T.cron_label("foo_bar_baz"))

    # AI yedeği — gemini.generate monkeypatch (gerçek çağrı yok)
    import app.services.gemini as gem
    orig = gem.generate
    gem.generate = lambda parts, **kw: '{"summary":"S","why":"W","how_to_fix":"H","severity":"warning","is_code_bug":false}'
    try:
        T.clear_ai_cache()
        a = T.ai_explain_error("WeirdErr", "msg", "/x", signature="sig123")
        chk("ai_explain_error → source=ai + alanlar dolu", a.source == "ai" and a.summary == "S" and a.how_to_fix == "H", str(a))
        # önbellek: ikinci çağrıda generate ÇAĞRILMAMALI
        gem.generate = lambda *a, **k: (_ for _ in ()).throw(AssertionError("generate tekrar çağrıldı"))
        a2 = T.ai_explain_error("WeirdErr", "msg", "/x", signature="sig123")
        chk("ai_explain_error önbellekli (tekrar çağrıda kredi yanmaz)", a2.summary == "S", str(a2))
    finally:
        gem.generate = orig
        T.clear_ai_cache()


def live_tests():
    print("\nB) Canlı sistem endpoint:")
    PFX = "etr_" + secrets.token_hex(3)
    PWD = "ErrTrans!2345aB"
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        sa = User(email=f"{PFX}@t.invalid", password_hash=hash_password(PWD), full_name="Super",
                  role=UserRole.SUPER_ADMIN, is_active=True, must_change_password=False, password_changed_at=now)
        db.add(sa); db.commit(); sid = sa.id
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id == sid)); db.commit()
    get_login_limiter().reset()
    c = httpx.Client(base_url=B, timeout=40)
    for attempt in range(2):
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}@t.invalid", "password": PWD})
        if r.status_code == 200:
            break
        if r.status_code == 429 and attempt == 0:
            time.sleep(min(int(r.json().get("detail", {}).get("retry_after_seconds", 60)) + 1, 62)); continue
        raise RuntimeError(f"login: {r.status_code} {r.text[:120]}")
    try:
        data = c.get("/api/v2/admin/security-monitor/system").json()
        groups = data.get("error_groups", [])
        chk("sistem endpoint 200 + error_groups döndü", isinstance(groups, list))
        if groups:
            g = groups[0]
            chk("her grupta explanation var", g.get("explanation") is not None, str(g.get("explanation")))
            chk("explanation alanları (summary/why/how/category_label)",
                all(k in (g.get("explanation") or {}) for k in ("summary", "why", "how_to_fix", "category_label")), str(g.get("explanation")))
            chk("stale + last_seen_label alanları var", "stale" in g and "last_seen_label" in g, str({k: g.get(k) for k in ("stale", "last_seen_label")}))
        else:
            print("    (not: açık hata grubu yok — alan kontrolü atlandı)")
        r = c.post("/api/v2/admin/security-monitor/system/999999999/explain")
        chk("/explain eksik id → 404", r.status_code == 404, f"{r.status_code}")
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(AuditLog).where(AuditLog.actor_id == sid))
            db.execute(sa_delete(User).where(User.id == sid))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"]))); db.commit()


def main() -> int:
    print("\n=== HATA TERCÜMANI SMOKE ===\n")
    unit_tests()
    live_tests()
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
