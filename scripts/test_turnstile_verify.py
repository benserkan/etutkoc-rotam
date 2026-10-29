"""Turnstile doğrulama kuralları (siteverify taklit edilir, ağ yok)."""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services import turnstile as t

os.environ.update(TURNSTILE_SITE_KEY="site", TURNSTILE_SECRET_KEY="sec", TURNSTILE_ENABLED="1")
passed = failed = 0
def check(name, cond):
    global passed, failed
    if cond: passed += 1; print("  ✓", name)
    else: failed += 1; print("  ✗", name)

calls = []
def fake(resp):
    def _f(payload):
        calls.append(payload); return resp
    return _f

t._siteverify = fake({"success": True, "action": "login", "hostname": "rotam.etutkoc.com"})
check("1 başarılı token", t.verify_token("tok", ip="1.2.3.4", action="login"))
check("1b remoteip + idempotency gönderildi", calls[-1].get("remoteip") == "1.2.3.4" and calls[-1].get("idempotency_key"))
check("2 başka formun token'ı reddedilir", not t.verify_token("tok", action="signup"))
t._siteverify = fake({"success": True, "action": "", "hostname": "rotam.etutkoc.com"})
check("3 eski (action'sız) istemci kabul", t.verify_token("tok", action="login"))
t._siteverify = fake({"success": False, "error-codes": ["timeout-or-duplicate"]})
check("4 süresi dolmuş/tekrar kullanılan token reddedilir", not t.verify_token("tok", action="login"))
check("5 boş token reddedilir", not t.verify_token("", action="login"))
check("6 2048+ karakter reddedilir", not t.verify_token("x" * 3000, action="login"))
os.environ["TURNSTILE_ALLOWED_HOSTNAMES"] = "rotam.etutkoc.com"
t._siteverify = fake({"success": True, "action": "login", "hostname": "evil.example"})
check("7 başka alan adında üretilen token reddedilir", not t.verify_token("tok", action="login"))
t._siteverify = fake({"success": True, "action": "login", "hostname": "rotam.etutkoc.com"})
check("8 izinli alan adı kabul", t.verify_token("tok", action="login"))
t._siteverify = fake(None)
check("9 Cloudflare'e ulaşılamazsa varsayılan geç", t.verify_token("tok", action="login"))
os.environ["TURNSTILE_FAIL_CLOSED"] = "1"
check("10 FAIL_CLOSED=1 iken reddet", not t.verify_token("tok", action="login"))
os.environ["TURNSTILE_ENABLED"] = "0"
check("11 kapalıyken her zaman geçer", t.verify_token(None))
print(f"\n{passed}/{passed+failed} passed")
sys.exit(1 if failed else 0)
