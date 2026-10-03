"""Paket asistanı + ödeme sorunu görünürlüğü smoke (2026-10-03)."""
import json
import secrets
import sys
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, ".")
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Institution, SuspiciousIp, UsageEvent, User, UserRole  # noqa: E402
from app.models.payment_transaction import PaymentTransaction  # noqa: E402
from app.models.support_request import SupportRequest, SupportRequestMessage  # noqa: E402
from app.services import gemini, plan_assistant  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"pas_{secrets.token_hex(3)}"
PW = "PlanAsist2026!x"
passed = 0
failed: list[str] = []


def check(label, cond, extra=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {extra}")


def mk(db, tag, **kw):
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PW), full_name=f"Koç {tag}",
             role=kw.pop("role", UserRole.TEACHER), is_active=True, must_change_password=False,
             password_changed_at=datetime.utcnow(), **kw)
    db.add(u)
    db.flush()
    return u


def login(tag) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{tag}@test.invalid", "password": PW})
    assert r.status_code == 200, r.text
    return c


orig_generate = gemini.generate
ids: list[int] = []
inst_id = None
try:
    with SessionLocal() as db:
        now = datetime.utcnow()
        trial = mk(db, "trial", plan="solo_trial", trial_ends_at=now + timedelta(days=5),
                   post_trial_plan="solo_elite")
        for i in range(12):
            mk(db, f"trial_s{i}", role=UserRole.STUDENT, teacher_id=trial.id, grade_level=12)
        active = mk(db, "active", plan="solo_pro", subscription_status="active",
                    subscription_period_end=now + timedelta(days=4), subscription_cycle="monthly",
                    subscription_platform="iyzico")
        failpay = mk(db, "fail", plan="solo_free")
        abandon = mk(db, "aband", plan="solo_free")
        inst = Institution(name=f"{PFX} kurum", slug=f"{PFX}-kurum", plan="etut_standart", is_active=True)
        db.add(inst)
        db.flush()
        inst_id = inst.id
        mk(db, "inst", institution_id=inst.id)
        db.add(PaymentTransaction(user_id=failpay.id, provider="iyzico", amount=Decimal("2500"),
                                  plan_code="solo_pro", cycle="monthly", status="failed",
                                  status_reason="Kart limiti yetersiz, yetersiz bakiye",
                                  created_at=now - timedelta(hours=1)))
        db.add(PaymentTransaction(user_id=abandon.id, provider="iyzico", amount=Decimal("5000"),
                                  plan_code="solo_elite", cycle="annual", status="3ds_pending",
                                  created_at=now - timedelta(hours=2)))
        db.commit()
        ids = [u.id for u in db.query(User).filter(User.email.like(f"{PFX}_%")).all()]

    get_login_limiter().reset()
    ct, ca, cf, cb, ci = (login(t) for t in ("trial", "active", "fail", "aband", "inst"))

    # 1 — plan yanıtı: ödeme sorunu + yenileme günü
    p = cf.get("/api/v2/teacher/plan").json()
    i = p.get("last_payment_issue") or {}
    check("1a başarısız ödeme sade dille (limit)", i.get("kind") == "failed" and "limit" in i.get("title", "").lower()
          and i.get("plan_label") == "Patika", str(i))
    p = cb.get("/api/v2/teacher/plan").json()
    i = p.get("last_payment_issue") or {}
    check("1b yarım kalan 3D ödeme = abandoned + akademik yıl", i.get("kind") == "abandoned"
          and i.get("cycle") == "academic_year" and i.get("plan_label") == "Rota", str(i))
    p = ca.get("/api/v2/teacher/plan").json()
    check("1c aktif abonede yenileme günü 4 + sorun yok", p.get("renewal_days_left") == 4
          and p.get("last_payment_issue") is None, str(p.get("renewal_days_left")))

    # 2 — karşılama + çipler duruma göre
    s = ct.get("/api/v2/teacher/plan-assistant").json()
    chips = [c["id"] for c in s["chips"]]
    check("2a deneme: 'Deneme bitince' çipi + öneri Rota (12 öğrenci)", "trial_end" in chips
          and s["suggested_plan"] == "solo_elite" and "5 gün" in s["greeting"], json.dumps(s, ensure_ascii=False)[:300])
    s = cf.get("/api/v2/teacher/plan-assistant").json()
    check("2b ödeme hatası: ilk çip 'Ödemem neden geçmedi?' + karşılamada sorun",
          s["chips"][0]["id"] == "payment_failed" and "sorun" in s["greeting"], str(s["chips"][:2]))
    s = ci.get("/api/v2/teacher/plan-assistant").json()
    check("2c kurum öğretmeni: yönetilen paket çipleri", [c["id"] for c in s["chips"]] == ["managed", "human"],
          str(s["chips"]))

    # 3 — hazır cevaplar (yapay zekâ çağrılmaz)
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise RuntimeError("gemini kapalı")

    gemini.generate = boom
    r = ct.post("/api/v2/teacher/plan-assistant/ask", json={"chip": "which"}).json()
    check("3a 'Hangi paket?': 12 öğrenci → Rota + fiyat + select_plan", "Rota" in r["answer"] and "5.000 ₺" in r["answer"]
          and (r.get("action") or {}).get("plan") == "solo_elite" and r["source"] == "rule", str(r)[:300])
    r = ca.post("/api/v2/teacher/plan-assistant/ask", json={"chip": "renew"}).json()
    check("3b yenileme: erken ödeme gün yakmaz bilgisi", "yanmaz" in r["answer"], r["answer"][:200])
    r = cf.post("/api/v2/teacher/plan-assistant/ask", json={"chip": "payment_failed"}).json()
    check("3c ödeme hatası cevabı: ne yapmalı + paketi seç eylemi", "başka bir kart" in r["answer"].lower()
          and (r.get("action") or {}).get("type") == "select_plan", r["answer"][:200])
    check("3d hazır cevaplarda Gemini çağrılmadı", calls["n"] == 0, str(calls))

    # 4 — serbest soru: Gemini yoksa anahtar kelimeyle hazır cevaba düşer
    r = ca.post("/api/v2/teacher/plan-assistant/ask", json={"question": "Aboneliği iptal edersem ne olur?"}).json()
    check("4a Gemini hatası → fallback (iptal cevabı)", r["source"] == "fallback" and "iptal" in r["answer"].lower(),
          str(r)[:200])

    # 5 — Gemini cevabı + uydurma eylem temizlenir
    def fake(parts, **k):
        assert "BİLGİ PAKETİ" in parts[0]["text"] and "Patika" in parts[0]["text"]
        return json.dumps({"answer": "Rota sana uygun.", "action": {"type": "select_plan", "plan": "solo_pro"}})

    gemini.generate = fake
    r = ct.post("/api/v2/teacher/plan-assistant/ask",
                json={"question": "Bana hangisi?", "history": [{"role": "user", "text": "merhaba"}]}).json()
    check("5a AI cevabı geldi + 12 öğrenciye YETMEYEN Patika eylemi düşürüldü",
          r["source"] == "ai" and r["answer"] == "Rota sana uygun." and r.get("action") is None, str(r))
    s = ct.get("/api/v2/teacher/plan-assistant").json()
    check("5b serbest soru hakkı 1 azaldı", s["daily_left"] == plan_assistant.PA_DAILY_LIMIT - 1, str(s["daily_left"]))

    # 6 — günlük tavan
    with SessionLocal() as db:
        u = db.get(User, ids[0])
        for _ in range(plan_assistant.PA_DAILY_LIMIT):
            plan_assistant.record_ask(db, u, source="test")
        db.commit()
    r = ct.post("/api/v2/teacher/plan-assistant/ask", json={"question": "kredi nedir"}).json()
    check("6 tavan dolunca yapay zekâ yerine hazır cevap", r["source"] == "fallback" and r["daily_left"] == 0
          and "kredi" in r["answer"].lower(), str(r)[:200])

    # 7 — insana aktar
    r = cf.post("/api/v2/teacher/plan-assistant/handoff",
                json={"message": "Kartım reddediliyor, yardım eder misiniz?",
                      "transcript": [{"role": "user", "text": "ödemem neden geçmedi"},
                                     {"role": "assistant", "text": "limit yetersiz"}]})
    d = r.json()
    with SessionLocal() as db:
        req = db.get(SupportRequest, d.get("request_id") or 0)
        body = " ".join(m.body for m in req.messages) if req else ""
    check("7 destek talebi: üyelik kategorisi + durum + konuşma dökümü",
          r.status_code == 200 and req is not None and req.category == "billing"
          and "Son ödeme" in body and "Konuşma" in body, f"{r.status_code} {r.text[:200]}")

    # 9 — uygulama kanalı: web ödemesinden hiç söz edilmez (App Store 3.1.1)
    s = cf.get("/api/v2/teacher/plan-assistant?channel=ios").json()
    ids_ = [c["id"] for c in s["chips"]]
    check("9a iOS: ödeme hatası/kartla öde çipleri yok, 'Paketi nasıl alırım?' var",
          "payment_failed" not in ids_ and "pay_safe" not in ids_ and "buy_app" in ids_, str(ids_))
    banned = ("kart", "iyzico", "web")
    texts = [s["greeting"]]
    for chip in ids_:
        if chip == "human":
            continue
        texts.append(cf.post("/api/v2/teacher/plan-assistant/ask",
                             json={"chip": chip, "channel": "ios"}).json()["answer"])
    leak = [t for t in texts if any(b in t.lower() for b in banned)]
    check("9b iOS cevaplarında kart/iyzico/web geçmiyor", not leak, str(leak)[:300])
    r = ca.post("/api/v2/teacher/plan-assistant/ask", json={"chip": "renew", "channel": "android"}).json()
    check("9c Android: web aboneliği 'web hesabından yönetiliyor' (bağlantısız)",
          "web hesabın" in r["answer"] and r.get("action") is None, str(r)[:200])

    r = ct.post("/api/v2/teacher/plan-assistant/ask", json={}).json()
    check("8 boş soru → 422", r.get("code") == "question_required" or "question_required" in json.dumps(r), str(r))
finally:
    gemini.generate = orig_generate
    with SessionLocal() as db:
        if ids:
            rq = [r[0] for r in db.query(SupportRequest.id).filter(SupportRequest.requester_id.in_(ids)).all()]
            if rq:
                db.execute(sa_delete(SupportRequestMessage).where(SupportRequestMessage.request_id.in_(rq)))
                db.execute(sa_delete(SupportRequest).where(SupportRequest.id.in_(rq)))
            db.execute(sa_delete(UsageEvent).where(UsageEvent.actor_user_id.in_(ids)))
            db.execute(sa_delete(PaymentTransaction).where(PaymentTransaction.user_id.in_(ids)))
            db.execute(sa_delete(User).where(User.id.in_(ids)))
        if inst_id:
            db.execute(sa_delete(Institution).where(Institution.id == inst_id))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

print(f"\n=== {passed} passed, {len(failed)} failed ===")
sys.exit(0 if not failed else 1)
