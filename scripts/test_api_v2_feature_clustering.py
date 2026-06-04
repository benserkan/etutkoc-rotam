"""Vitrin AI temalı gruplama (feature_clustering, A2) smoke.

Gemini monkeypatch ile (gerçek çağrı yok):
  1. keşif adayları (kesif-mig-*) DRAFT oluştur
  2. teacher → 403
  3. süper admin ai-cluster → 200 + themes_created + candidates_grouped
  4. üretilen temalı kart(lar): slug tema-*, DRAFT, benefits dolu
     4b. AI'ın seçtiği geçerli mockup aynen; geçersiz mockup → generic fallback
  5. gruplanan kaynak adaylar manual_hide=True (kuyruktan çıktı)
  6. tekrar çağır → gruplanacak aday yok (0 tema)
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import FeatureCard, User, UserRole
from app.models.feature_card import FeatureStatus
from app.services import feature_catalog as fc
from app.services import gemini
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
from app.models.suspicious_ip import SuspiciousIp

PFX = f"clt_{secrets.token_hex(3)}"
PWD = hash_password("Cluster!23")
PWDH = "Cluster!23"
now = datetime.now(timezone.utc)
ctx: dict = {}
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        admin = User(email=f"{PFX}_admin@test.invalid", password_hash=PWD,
                     full_name=f"{PFX} Admin", role=UserRole.SUPER_ADMIN, is_active=True,
                     password_changed_at=now, must_change_password=False)
        coach = User(email=f"{PFX}_coach@test.invalid", password_hash=PWD,
                     full_name=f"{PFX} Koç", role=UserRole.TEACHER, institution_id=None,
                     is_active=True, plan="solo_free", password_changed_at=now,
                     must_change_password=False)
        db.add(admin); db.add(coach); db.flush()
        ctx.update(admin=admin.id, coach=coach.id)
        # 3 keşif adayı (kesif-mig-*)
        slugs = []
        for i, (t, dom) in enumerate([
            ("WhatsApp toplu gönderim altyapısı", "genel"),
            ("WhatsApp şablon yönetimi", "genel"),
            ("Yapay zeka koçluk içgörüsü", "genel"),
        ]):
            s = f"kesif-mig-{PFX}{i}-{_slug(t)}"
            card = fc.create(db, actor_id=admin.id, slug=s, title=t, tagline="(otomatik)",
                             domain=dom, status=FeatureStatus.DRAFT.value, strategic_priority=2)
            slugs.append(card.slug)  # fc.create slug'ı normalize edebilir
        ctx["cand_slugs"] = slugs
        db.commit()


def _slug(s):
    import re
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:30]


def login(suffix):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login",
               json={"email": f"{PFX}_{suffix}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {suffix}: {r.status_code}")
    return c


def main() -> int:
    print(f"\n=== VİTRİN AI TEMALI GRUPLAMA — {PFX} ===\n")
    setup()
    cand = ctx["cand_slugs"]

    # Gemini monkeypatch — 1 WhatsApp + 1 AI teması döndür
    fake = {
        "themes": [
            {
                "title": "WhatsApp ile Hızlı İletişim",
                "tagline": "Veli ve öğrenciye tek tıkla ulaş.",
                "category_label": "İletişim", "category_icon": "💬",
                "domain": "genel", "target_roles": ["teacher"],
                "commercial_weight": 5,
                "benefits": ["Toplu duyuru", "Hazır şablonlar", "Tek tık gönderim"],
                "mockup": "whatsapp_chat",  # geçerli → aynen kullanılır
                "source_slugs": [cand[0], cand[1]],
            },
            {
                "title": "Yapay Zeka Koçluk Asistanı",
                "tagline": "Bir sonraki seansa hazır gel.",
                "category_label": "Yapay Zeka", "category_icon": "🤖",
                "domain": "genel", "target_roles": ["teacher"],
                "commercial_weight": 4,
                "benefits": ["Seans özeti", "Gündem önerisi"],
                "mockup": "uydurma_gecersiz",  # geçersiz → generic'e düşmeli
                "source_slugs": [cand[2]],
            },
        ]
    }
    orig = gemini.generate
    gemini.generate = lambda *a, **k: json.dumps(fake)  # type: ignore[assignment]
    try:
        coach = login("coach")
        r = coach.post("/api/v2/admin/feature-catalog/discovery-queue/ai-cluster")
        check("2. teacher → 403", r.status_code == 403, f"{r.status_code}")

        admin = login("admin")
        r = admin.post("/api/v2/admin/feature-catalog/discovery-queue/ai-cluster")
        ok = r.status_code == 200
        data = r.json()["data"] if ok else {}
        check("3. ai-cluster → 200 + 2 tema + 3 aday gruplandı",
              ok and data.get("themes_created") == 2 and data.get("candidates_grouped") == 3,
              f"{r.status_code} {r.text[:160]}")

        with SessionLocal() as db:
            themed = db.query(FeatureCard).filter(
                FeatureCard.slug.like("tema-%"),
                FeatureCard.created_by == ctx["admin"]).all()
            by_title = {c.title: c for c in themed}
            check("4. temalı kart üretildi (DRAFT + benefits dolu)",
                  len(themed) == 2 and all(
                      c.status == "draft" and len(c.benefits or []) > 0 for c in themed),
                  f"{[(c.slug, c.status, c.mockup_type, len(c.benefits or [])) for c in themed]}")
            # 4b: AI'ın seçtiği geçerli mockup aynen; geçersiz → generic fallback
            wa = by_title.get("WhatsApp ile Hızlı İletişim")
            ai = by_title.get("Yapay Zeka Koçluk Asistanı")
            check("4b. geçerli mockup aynen (whatsapp_chat) · geçersiz → generic",
                  wa is not None and wa.mockup_type == "whatsapp_chat"
                  and ai is not None and ai.mockup_type == "generic",
                  f"wa={getattr(wa, 'mockup_type', None)} ai={getattr(ai, 'mockup_type', None)}")

            hidden = db.query(FeatureCard).filter(
                FeatureCard.slug.in_(cand), FeatureCard.manual_hide.is_(True)).count()
            check("5. 3 kaynak aday gizlendi (kuyruktan çıktı)", hidden == 3, f"hidden={hidden}")

        # 6. tekrar → bizim 3 adayımız gizli kalır, tekrar gruplanmaz (idempotent)
        r = admin.post("/api/v2/admin/feature-catalog/discovery-queue/ai-cluster")
        with SessionLocal() as db:
            still_hidden = db.query(FeatureCard).filter(
                FeatureCard.slug.in_(cand), FeatureCard.manual_hide.is_(True)).count()
        check("6. tekrar → 200 + bizim 3 aday hâlâ gizli (tekrar gruplanmadı)",
              r.status_code == 200 and still_hidden == 3, f"{r.status_code} hidden={still_hidden}")
    finally:
        gemini.generate = orig  # type: ignore[assignment]
        with SessionLocal() as db:
            db.execute(sa_delete(FeatureCard).where(FeatureCard.created_by == ctx.get("admin")))
            ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if ids:
                db.execute(sa_delete(User).where(User.id.in_(ids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
