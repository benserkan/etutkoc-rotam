"""API v2 sosyal kanıt (testimonials) smoke.

Senaryolar:
   1. public GET /api/v2/testimonials → 200 (başlangıçta bizimkiler yok)
   2. super admin POST /admin/testimonials (published) → 200 + data
   3. public GET → yayınlanan kayıt görünür + counts.review>=1
   4. öğrenci POST /testimonials/submit → 200 + pending (public'te GÖRÜNMEZ)
   5. öğrenci tekrar submit → already_pending=True (tek bekleyen)
   6. veli submit → 200 (rol kapısı geçer)
   7. super admin GET /admin/testimonials → pending + published görünür + counts
   8. super admin status=published (pending kaydı yayınla) → public'te görünür
   9. super admin update (content/featured) → 200 + değişti
  10. super admin status=hidden (yayını gizle) → public'ten DÜŞER
  11. super admin delete → 200 + kayıt gider
  12. kind filtresi (public) çalışır
  13. teacher GET /admin/testimonials → 403
  14. anonim GET /admin/testimonials → 401
  15. anonim POST /testimonials/submit → 401
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete
from sqlalchemy import or_

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, Testimonial, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2testi_{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
STUDENT_EMAIL = f"{PFX}_student@test.invalid"
PARENT_EMAIL = f"{PFX}_parent@test.invalid"
OLDSTU_EMAIL = f"{PFX}_oldstu@test.invalid"
PASSWORD = "TestPassTesti!23"

passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        rows = {
            "super": User(email=SUPER_EMAIL, password_hash=pwd, full_name=f"{PFX} Super",
                          role=UserRole.SUPER_ADMIN, is_active=True,
                          password_changed_at=now, must_change_password=False),
            "teacher": User(email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} Teacher",
                            role=UserRole.TEACHER, institution_id=None, is_active=True,
                            password_changed_at=now, must_change_password=False),
            "student": User(email=STUDENT_EMAIL, password_hash=pwd, full_name=f"{PFX} Student",
                            role=UserRole.STUDENT, is_active=True,
                            password_changed_at=now, must_change_password=False),
            "parent": User(email=PARENT_EMAIL, password_hash=pwd, full_name=f"{PFX} Parent",
                           role=UserRole.PARENT, is_active=True,
                           password_changed_at=now, must_change_password=False),
            # 30 gün önce açılmış öğrenci → prompt yaş kapısını geçer
            "oldstu": User(email=OLDSTU_EMAIL, password_hash=pwd, full_name=f"{PFX} Eski Ogrenci",
                           role=UserRole.STUDENT, is_active=True,
                           created_at=now - timedelta(days=30),
                           password_changed_at=now, must_change_password=False),
        }
        db.add_all(list(rows.values()))
        db.commit()
        return {k: u.id for k, u in rows.items()}


def _cleanup(seed: dict) -> None:
    ids = list(seed.values())
    with SessionLocal() as db:
        db.execute(sa_delete(Testimonial).where(
            or_(
                Testimonial.submitted_by_id.in_(ids),
                Testimonial.author_name.like(f"{PFX}%"),
            )
        ))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(ids)))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 testimonials smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    try:
        anon = TestClient(app)

        # 1. public GET (boş/diğer kayıtlar olabilir, 200 yeterli)
        r = anon.get("/api/v2/testimonials")
        check("1. public GET → 200", r.status_code == 200, f"status={r.status_code}")

        super_client = _login(SUPER_EMAIL)
        teacher_client = _login(TEACHER_EMAIL)
        student_client = _login(STUDENT_EMAIL)
        parent_client = _login(PARENT_EMAIL)

        # 2. super admin manuel oluştur (kurum referansı, yayında)
        r = super_client.post("/api/v2/admin/testimonials", json={
            "kind": "institution_ref",
            "author_name": f"{PFX} Demir Dershanesi",
            "author_role": "institution_admin",
            "author_title": "Kurum Müdürü",
            "institution_name": f"{PFX} Demir Dershanesi",
            "rating": 5,
            "content": "ETÜTKOÇ ile koçlarımızın verimi gözle görülür arttı.",
            "status": "published",
            "consent_public": True,
            "featured": True,
        })
        manual_id = r.json().get("data", {}).get("id") if r.status_code == 200 else 0
        check("2. super POST manuel (published) → 200",
              r.status_code == 200 and manual_id
              and r.json()["data"]["status"] == "published"
              and "testimonials:public" in r.json().get("invalidate", []),
              f"status={r.status_code} body={r.text[:200]}")

        # 3. public'te görünür + counts
        r = anon.get("/api/v2/testimonials")
        j = r.json() if r.status_code == 200 else {}
        pub_ids = [it["id"] for it in j.get("items", [])]
        check("3. public GET → manuel kayıt görünür + counts.institution_ref>=1",
              manual_id in pub_ids and j.get("counts", {}).get("institution_ref", 0) >= 1,
              f"pub_ids={pub_ids[:10]} counts={j.get('counts')}")

        # 4. öğrenci submit → pending (public'te görünmez)
        r = student_client.post("/api/v2/testimonials/submit", json={
            "content": "Bu sistem sayesinde günlük programımı kolayca takip ediyorum.",
            "rating": 5,
            "author_name": f"{PFX} Zeynep A.",
            "consent_public": True,
        })
        ok4 = r.status_code == 200 and r.json().get("ok") and not r.json().get("already_pending")
        # public'te görünmemeli
        rp = anon.get("/api/v2/testimonials")
        names = [it["author_name"] for it in rp.json().get("items", [])]
        check("4. öğrenci submit → pending (public'te YOK)",
              ok4 and f"{PFX} Zeynep A." not in names,
              f"status={r.status_code} names={names[:10]}")

        # 5. öğrenci tekrar submit → already_pending
        r = student_client.post("/api/v2/testimonials/submit", json={
            "content": "İkinci kez yorum göndermeye çalışıyorum, engellenmeli.",
            "author_name": f"{PFX} Zeynep A.",
        })
        check("5. öğrenci tekrar submit → already_pending=True",
              r.status_code == 200 and r.json().get("already_pending") is True,
              f"status={r.status_code} body={r.text[:200]}")

        # 6. veli submit → 200 (rol kapısı geçer)
        r = parent_client.post("/api/v2/testimonials/submit", json={
            "content": "Çocuğumun gelişimini veli panelinden net görebiliyorum.",
            "rating": 4,
            "author_name": f"{PFX} Bir Veli",
        })
        check("6. veli submit → 200", r.status_code == 200 and r.json().get("ok"),
              f"status={r.status_code} body={r.text[:200]}")

        # 7. super admin liste — pending + published + counts
        r = super_client.get("/api/v2/admin/testimonials")
        j = r.json() if r.status_code == 200 else {}
        items = j.get("items", [])
        mine = [it for it in items if str(it.get("author_name", "")).startswith(PFX)]
        pendings = [it for it in mine if it["status"] == "pending"]
        student_pending = next((it for it in pendings if "Zeynep" in it["author_name"]), None)
        check("7. super GET list → pending+published + counts + labels",
              r.status_code == 200 and len(mine) >= 3 and len(pendings) >= 2
              and j.get("counts", {}).get("pending", 0) >= 2
              and any(it.get("source_label") == "Uygulama içi gönderim" for it in pendings)
              and any(it.get("kind_label") == "Kurum referansı" for it in mine),
              f"mine={len(mine)} pendings={len(pendings)} counts={j.get('counts')}")

        # 8. pending → published (öğrenci yorumunu yayınla)
        sp_id = student_pending["id"] if student_pending else 0
        r = super_client.post(f"/api/v2/admin/testimonials/{sp_id}/status",
                              json={"status": "published"})
        ok8a = r.status_code == 200 and r.json()["data"]["status"] == "published"
        rp = anon.get("/api/v2/testimonials")
        names = [it["author_name"] for it in rp.json().get("items", [])]
        check("8. pending→published → public'te görünür",
              ok8a and f"{PFX} Zeynep A." in names,
              f"status={r.status_code} names={names[:10]}")

        # 9. update (içerik + featured)
        r = super_client.post(f"/api/v2/admin/testimonials/{sp_id}", json={
            "content": "Güncellenmiş yorum metni — koçumla iletişimim çok kolay.",
            "featured": True,
        })
        check("9. update → 200 + içerik değişti",
              r.status_code == 200 and r.json()["data"]["featured"] is True
              and "Güncellenmiş" in r.json()["data"]["content"],
              f"status={r.status_code} body={r.text[:200]}")

        # 10. published → hidden (public'ten düşer)
        r = super_client.post(f"/api/v2/admin/testimonials/{sp_id}/status",
                              json={"status": "hidden"})
        rp = anon.get("/api/v2/testimonials")
        names = [it["author_name"] for it in rp.json().get("items", [])]
        check("10. published→hidden → public'ten DÜŞER",
              r.status_code == 200 and f"{PFX} Zeynep A." not in names,
              f"status={r.status_code} names={names[:10]}")

        # 11. delete
        r = super_client.post(f"/api/v2/admin/testimonials/{sp_id}/delete", json={})
        ok11a = r.status_code == 200
        r2 = super_client.get("/api/v2/admin/testimonials")
        still = [it for it in r2.json().get("items", []) if it["id"] == sp_id]
        check("11. delete → 200 + kayıt gider", ok11a and not still,
              f"status={r.status_code} still={still}")

        # 12. kind filtresi (public)
        r = anon.get("/api/v2/testimonials", params={"kind": "institution_ref"})
        ok12 = r.status_code == 200 and all(
            it["kind"] == "institution_ref" for it in r.json().get("items", [])
        )
        check("12. public kind=institution_ref filtresi", ok12, f"status={r.status_code}")

        # 13. teacher admin list → 403
        r = teacher_client.get("/api/v2/admin/testimonials")
        check("13. teacher admin list → 403", r.status_code == 403, f"status={r.status_code}")

        # 14. anonim admin list → 401
        r = anon.get("/api/v2/admin/testimonials")
        check("14. anonim admin list → 401", r.status_code == 401, f"status={r.status_code}")

        # 15. anonim submit → 401
        r = anon.post("/api/v2/testimonials/submit", json={
            "content": "Anonim gönderim engellenmeli kesinlikle.",
            "author_name": "Anonim",
        })
        check("15. anonim submit → 401", r.status_code == 401, f"status={r.status_code}")

        # 16. anonim prompt → 401
        r = anon.get("/api/v2/testimonials/prompt")
        check("16. anonim prompt → 401", r.status_code == 401, f"status={r.status_code}")

        # 17. yeni öğrenci (hesap yaşı 0) prompt → eligible False (yaş kapısı)
        r = student_client.get("/api/v2/testimonials/prompt")
        check("17. yeni öğrenci prompt → eligible False (yaş)",
              r.status_code == 200 and r.json().get("eligible") is False,
              f"status={r.status_code} body={r.text[:200]}")

        # 18. eski öğrenci (30 gün, gönderim yok) prompt → eligible True + default_name
        old_client = _login(OLDSTU_EMAIL)
        r = old_client.get("/api/v2/testimonials/prompt")
        check("18. eski öğrenci prompt → eligible True + default_name",
              r.status_code == 200 and r.json().get("eligible") is True
              and r.json().get("default_name") == f"{PFX} Eski Ogrenci",
              f"status={r.status_code} body={r.text[:200]}")

        # 19. eski öğrenci gönderir → prompt artık eligible False (gönderim var)
        r = old_client.post("/api/v2/testimonials/submit", json={
            "content": "Uzun süredir kullanıyorum, programımı düzene soktu.",
            "rating": 5, "author_name": f"{PFX} Eski Ogrenci", "consent_public": True,
        })
        ok19a = r.status_code == 200 and r.json().get("ok")
        r2 = old_client.get("/api/v2/testimonials/prompt")
        check("19. gönderim sonrası prompt → eligible False",
              ok19a and r2.status_code == 200 and r2.json().get("eligible") is False,
              f"submit={r.status_code} prompt={r2.text[:200]}")

    finally:
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
