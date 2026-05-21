"""GERÇEK API anahtarıyla uçtan uca AI maliyet simülasyonu (Paket D).

GÜVENLİ: Gemini ücretli anahtarı YOKSA gerçek çağrı yapmaz — yalnız ücretli paket
kapısını (free=403, maliyetsiz) doğrular ve "anahtarı süper adminden gir" der.
Anahtar VARSA (süper admin → AI Ayarları veya .env) paid koç için GERÇEK
coaching-insight (Gemini) + opsiyonel foto (PIL sentetik görsel → Gemini vision)
çağrısı yapar; kredi before/after + AI çıktısı + maliyet özeti raporlar.

Geçici test kullanıcıları oluşturur, sonunda hepsini temizler — gerçek hesaplara
DOKUNMAZ (kullanıcının kırmızı çizgisi).

Çalıştırma:  PYTHONPATH=. python scripts/simulate_ai_real.py
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import base64
import io
import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    CoachingInsight, CoachingSession, CreditAccount, Institution, User, UserRole,
)
from app.models.suspicious_ip import SuspiciousIp
from app.models.usage import UsageEvent, UsageKind, UsageOwnerType
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"sim{secrets.token_hex(3)}"
PASSWORD = "SimPass1!@xyz"


def line(c="─"):
    print(c * 64)


def _mk(db, key, plan):
    t = User(email=f"{PFX}_{key}@s.invalid", password_hash=hash_password(PASSWORD),
             full_name=f"{PFX} {key}", role=UserRole.TEACHER, is_active=True, plan=plan)
    db.add(t); db.flush()
    s = User(email=f"{PFX}_{key}_s@s.invalid", password_hash=hash_password(PASSWORD),
             full_name="Ahmet Yılmaz", role=UserRole.STUDENT, is_active=True,
             grade_level=8, teacher_id=t.id)
    db.add(s); db.flush()
    return t.id, s.id


def _seed():
    with SessionLocal() as db:
        from app.services.credits import CreditOwner, get_or_create_account
        paid_t, paid_s = _mk(db, "paid", "solo_pro")
        free_t, free_s = _mk(db, "free", "solo_free")
        acc = get_or_create_account(db, owner=CreditOwner.for_user(db.get(User, paid_t)))
        get_or_create_account(db, owner=CreditOwner.for_user(db.get(User, free_t)))
        out = {"paid_t": paid_t, "paid_s": paid_s, "free_t": free_t, "free_s": free_s,
               "alloc": acc.total_allocated}
        db.commit()
        return out


def _cleanup(seed):
    with SessionLocal() as db:
        sids = [seed["paid_s"], seed["free_s"]]
        uids = [seed["paid_t"], seed["free_t"], *sids]
        db.execute(sa_delete(CoachingInsight).where(CoachingInsight.student_id.in_(sids)))
        db.execute(sa_delete(CoachingSession).where(CoachingSession.student_id.in_(sids)))
        db.execute(sa_delete(UsageEvent).where(UsageEvent.owner_id.in_(uids)))
        db.execute(sa_delete(CreditAccount).where(CreditAccount.owner_id.in_(uids)))
        try:
            from app.models import PlanChangeHistory, PlanOwnerType
            db.execute(sa_delete(PlanChangeHistory).where(
                PlanChangeHistory.owner_type == PlanOwnerType.USER,
                PlanChangeHistory.owner_id.in_(uids)))
        except Exception:
            pass
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(key):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{key}@s.invalid", "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {r.status_code} {r.text[:120]}")
    return c


def _used_credits(owner_id):
    with SessionLocal() as db:
        acc = (db.query(CreditAccount)
               .filter(CreditAccount.owner_type == UsageOwnerType.USER,
                       CreditAccount.owner_id == owner_id)
               .order_by(CreditAccount.period_year_month.desc()).first())
        return acc.used_credits if acc else 0


def _synthetic_form_png() -> tuple[str, str] | None:
    """PIL varsa basit bir 'koçluk görüşme formu' görseli üretir (base64, media_type)."""
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    img = Image.new("RGB", (700, 460), "white")
    d = ImageDraw.Draw(img)
    lines = [
        "HAFTALIK KOCLUK GORUSME FORMU",
        "Ogrenci: Ahmet Yilmaz   Tarih: 21.05.2026",
        "",
        "Bu hafta: Matematik tamamlama dusuk (%45).",
        "Ogrenci sinav kaygisi yasiyor, motivasyonu kirik.",
        "",
        "Gundem: Kaygi yonetimi + matematik rutini",
        "Gelecek hafta degisecek: Gunluk 20 soru matematik",
        "Ruh hali: 2/5",
        "Etiketler: kaygi, matematik, motivasyon",
    ]
    y = 24
    for ln in lines:
        d.text((28, y), ln, fill="black")
        y += 38
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii"), "image/png"


def main():
    print("\n" + "=" * 64)
    print("  GERÇEK API MALİYET SİMÜLASYONU — Bağımsız Koç AI")
    print("=" * 64)
    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient")); db.commit()

    from app.services.system_secrets import get_gemini_free_keys, get_gemini_model, get_gemini_paid_key
    anthropic = get_gemini_paid_key()   # öğrenci verili işler için ücretli Gemini key
    free_keys = get_gemini_free_keys()
    openai = bool(free_keys)
    print(f"\n  Gemini ÜCRETLİ anahtar : {'VAR ✓' if anthropic else 'YOK ✗'}  (model: {get_gemini_model(paid=True)})")
    print(f"  Gemini ÜCRETSİZ anahtar: {('VAR ✓ x' + str(len(free_keys))) if free_keys else 'YOK ✗'}  (model: {get_gemini_model(paid=False)})")

    seed = _seed()
    try:
        paid = _login("paid")
        free = _login("free")
        paid_s, free_s = seed["paid_s"], seed["free_s"]

        # Rıza
        paid.post("/api/v2/teacher/ai-consent")
        free.post("/api/v2/teacher/ai-consent")

        line()
        print("  1) ÜCRETLİ PAKET KAPISI (maliyetsiz doğrulama)")
        line()
        # free koça seans ekle (gate yine de 403)
        free.post(f"/api/v2/teacher/students/{free_s}/sessions", json={
            "session_date": "2026-05-20", "status": "done", "agenda": "Genel"})
        r = free.post(f"/api/v2/teacher/students/{free_s}/coaching-insight")
        print(f"  free koç (solo_free) içgörü → HTTP {r.status_code} "
              f"({r.json().get('detail', {}).get('code') if r.status_code != 200 else 'AÇIK'})")
        print(f"    beklenen: 403 plan_upgrade_required  → {'DOĞRU ✓' if r.status_code == 403 else 'HATA ✗'}")

        # paid koça 2 seans ekle
        paid.post(f"/api/v2/teacher/students/{paid_s}/sessions", json={
            "session_date": "2026-05-14", "status": "done",
            "agenda": "Matematik kaygısı", "coach_note": "Öğrenci son denemede zorlandı, morali bozuk.",
            "mood": 2, "tags": ["kaygı", "matematik"]})
        paid.post(f"/api/v2/teacher/students/{paid_s}/sessions", json={
            "session_date": "2026-05-21", "status": "done",
            "agenda": "Rutin takibi", "coach_note": "Hafta sonu çalışma planına uydu, biraz toparladı.",
            "mood": 3, "tags": ["motivasyon"]})

        line()
        print("  2) GERÇEK AI ÇAĞRISI — Koçluk İçgörüsü (paid koç)")
        line()
        if not anthropic:
            print("  ⚠ Gemini ücretli anahtarı yok — gerçek çağrı ATLANDI.")
            print("    Süper admin → AI Ayarları'na anahtar girip tekrar çalıştırın.")
        else:
            before = _used_credits(seed["paid_t"])
            r = paid.post(f"/api/v2/teacher/students/{paid_s}/coaching-insight")
            after = _used_credits(seed["paid_t"])
            if r.status_code == 200:
                ins = r.json()["insight"]
                print(f"  HTTP 200 ✓  | Kredi: {before} → {after} (Δ {after - before})")
                print(f"  Tahsis (aylık): {seed['alloc']} kredi | Kalan: {seed['alloc'] - after}")
                print(f"\n  ÖZET: {ins['summary']}")
                print("  GÜNDEM:")
                for a in ins["agenda_suggestions"]:
                    print(f"    • {a}")
                print("  İPUÇLARI:")
                for t in ins["psychological_tips"]:
                    print(f"    • {t}")
                if ins["watch_outs"]:
                    print("  DİKKAT:")
                    for w in ins["watch_outs"]:
                        print(f"    • {w}")
                # 2. GET → kredi DÜŞMEZ (cache)
                g_before = _used_credits(seed["paid_t"])
                paid.get(f"/api/v2/teacher/students/{paid_s}/coaching-insight")
                g_after = _used_credits(seed["paid_t"])
                print(f"\n  Cache okuma (GET): kredi {g_before} → {g_after} "
                      f"({'ÜCRETSIZ ✓' if g_before == g_after else 'HATA ✗'})")
            else:
                print(f"  HTTP {r.status_code} ✗  {r.text[:200]}")

        line()
        print("  3) GERÇEK AI ÇAĞRISI — Fotoğraftan yakalama (paid koç)")
        line()
        photo = _synthetic_form_png()
        if not anthropic:
            print("  ⚠ Gemini ücretli anahtarı yok — ATLANDI.")
        elif photo is None:
            print("  ⚠ PIL (Pillow) yok — sentetik görsel üretilemedi, ATLANDI.")
            print("    (Fotoğraf akışını canlı UI'dan gerçek bir formla test edebilirsiniz.)")
        else:
            img_b64, mt = photo
            before = _used_credits(seed["paid_t"])
            r = paid.post(f"/api/v2/teacher/students/{paid_s}/sessions/parse-photo",
                          json={"image_base64": img_b64, "media_type": mt})
            after = _used_credits(seed["paid_t"])
            if r.status_code == 200:
                d = r.json()
                print(f"  HTTP 200 ✓  | Kredi: {before} → {after} (Δ {after - before})")
                print(f"  Okunan gündem : {d['agenda']}")
                print(f"  Okunan not    : {d['coach_note'][:120]}")
                print(f"  Ruh hali      : {d['mood']} | Etiketler: {d['tags']}")
            else:
                print(f"  HTTP {r.status_code}  {r.text[:200]}")

        line()
        print("  4) SES (Gemini)")
        line()
        print("  Ses gerçek bir kayıt gerektirir (sentetik üretilemez).")
        print(f"  Ses artık Gemini (ücretli key) ile tek çağrıda. "
              f"{'Ücretli key VAR — UI → öğrenci → Seanslar → Sesle doldur ile test edin.' if anthropic else 'Ücretli key YOK — süper adminden girin.'}")

        line()
        print("  MALİYET ÖZETİ (kredi)")
        line()
        print("  AI_COACHING_INSIGHT = 6 · AI_SESSION_CAPTURE(foto) = 5 · AI_SESSION_VOICE(ses) = 8")
        print(f"  solo_free aylık tahsis örn: ücretsiz planda AI KAPALI (kapı 403).")
        print(f"  solo_pro koç bu simülasyonda {_used_credits(seed['paid_t'])} kredi tüketti.")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()
        print("\n  (geçici test kullanıcıları temizlendi)")

    print("=" * 64 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
