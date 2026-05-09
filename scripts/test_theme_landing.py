"""Theme + Landing page smoke test (Stage 11+ tema sistemi).

Senaryolar:
1. / anonim → 200 + landing render (hero + bento + pricing + footer)
2. / logged-in user → role-bazlı dashboard redirect
3. /login → modern split-screen render
4. /signup/teacher → modern split-screen + 14g trial CTA
5. /pricing → tema güncellenmiş hero
6. Tema sistemi: Plus Jakarta Sans + Inter + JetBrains Mono Google Fonts CDN'de
7. Alpine.js CDN'de
8. Role-bazlı body data-attribute logged-in user için
9. Reveal scroll-trigger script base.html'de
10. Bento grid + counter-animate + tab switcher class'ları landing'de
11. CTA → /signup/teacher path doğru
12. Footer KVKK / Gizlilik linkleri
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import joinedload
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user
from app.main import app
from app.models import User, UserRole


PFX = f"_th_{secrets.token_hex(3)}"
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


def main() -> int:
    now = datetime.now(timezone.utc)
    client = TestClient(app)

    # ============ STEP 1: / anonim landing ============
    print("\n=== STEP 1: / anonim → landing ===")
    app.dependency_overrides.clear()
    r = client.get("/", follow_redirects=False)
    check("anonim → 200 (landing)", r.status_code == 200, f"got {r.status_code}")
    body = r.text
    check("Hero başlık 'dijital omurgası'",
          "dijital omurgası" in body)
    check("Hero CTA 14 Gün Ücretsiz",
          "14 Gün Ücretsiz Başla" in body)
    check("Kurum pilotu CTA", "Kurum Pilotu" in body)
    check("Sosyal proof counter (3500)",
          'data-target="3500"' in body)
    check("Bento grid section başlığı",
          "Her ihtiyaca özel parça" in body)
    check("5 rol tab section",
          "5 rol, 1 platform" in body)
    check("Pricing 3 plan kartı",
          "Solo Free" in body and "Solo Pro" in body and "Etüt Standart" in body)
    check("FAQ accordion",
          "Karar vermenize yardımcı" in body)
    check("Final CTA section", "14 günde fark hissedeceksiniz" in body)
    check("Footer KVKK link", '/kvkk' in body)

    # ============ STEP 2: / logged-in redirect ============
    print("\n=== STEP 2: / logged-in → dashboard redirect ===")
    with SessionLocal() as db:
        teacher = User(
            email=f"{PFX}_t@test.invalid", password_hash="x" * 60,
            full_name="Theme Teacher", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now,
        )
        student = User(
            email=f"{PFX}_s@test.invalid", password_hash="x" * 60,
            full_name="Theme Student", role=UserRole.STUDENT,
            is_active=True, password_changed_at=now,
        )
        db.add_all([teacher, student]); db.commit()
        teacher_id, student_id = teacher.id, student.id

    def make_user_override(uid: int):
        def _ov():
            with SessionLocal() as _db:
                u = (
                    _db.query(User)
                    .options(joinedload(User.institution))
                    .filter(User.id == uid)
                    .first()
                )
                if u is not None:
                    if u.institution is not None:
                        _db.expunge(u.institution)
                    _db.expunge(u)
                return u
        return _ov

    app.dependency_overrides[get_current_user] = make_user_override(teacher_id)
    r = client.get("/", follow_redirects=False)
    check("teacher / → 303",
          r.status_code in (302, 303), f"got {r.status_code}")
    check("teacher / redirect → /teacher",
          r.headers.get("location", "") == "/teacher")
    app.dependency_overrides.clear()

    app.dependency_overrides[get_current_user] = make_user_override(student_id)
    r = client.get("/", follow_redirects=False)
    check("student / redirect → /student",
          r.headers.get("location", "") == "/student")
    app.dependency_overrides.clear()

    # ============ STEP 3: /login modern ============
    print("\n=== STEP 3: /login modern split-screen ===")
    r = client.get("/login")
    check("/login 200", r.status_code == 200)
    body = r.text
    check("Login 'Hoş geldiniz' display başlık",
          "Hoş geldiniz" in body)
    check("Login sağ panel sosyal kanıt",
          "3.5K+" in body or "Türk eğitim takvimine" in body)

    # ============ STEP 4: /signup/teacher modern ============
    print("\n=== STEP 4: /signup/teacher modern ===")
    r = client.get("/signup/teacher")
    check("/signup/teacher 200", r.status_code == 200)
    body = r.text
    check("Signup '14 Gün Ücretsiz Pro Deneme' badge",
          "14 Gün Ücretsiz" in body)
    check("Signup sağ panel '14 günde neler açık'",
          "14 günde neler açık" in body)
    check("KVKK + Gizlilik checkbox link",
          "KVKK Aydınlatma" in body)

    # ============ STEP 5: /pricing modernize ============
    print("\n=== STEP 5: /pricing aurora-deep hero ===")
    r = client.get("/pricing")
    check("/pricing 200", r.status_code == 200)
    body = r.text
    check("aurora-deep class kullanımı",
          "bg-aurora-deep" in body or "aurora" in body)
    check("text-display-lg font-display class",
          "text-display-lg" in body)

    # ============ STEP 6: Tema altyapısı kontrol ============
    print("\n=== STEP 6: Tema altyapısı ===")
    r = client.get("/")
    body = r.text
    check("Plus Jakarta Sans Google Font",
          "Plus+Jakarta+Sans" in body)
    check("Inter Google Font", "Inter:wght" in body)
    check("JetBrains Mono Google Font",
          "JetBrains+Mono" in body)
    check("Alpine.js CDN", "alpinejs" in body)
    check("HTMX CDN", "htmx.org" in body)
    check("Tailwind CDN", "cdn.tailwindcss.com" in body)
    check("Font preconnect",
          'rel="preconnect"' in body and "fonts.gstatic.com" in body)

    # ============ STEP 7: Role data-attribute ============
    print("\n=== STEP 7: body data-role logged-in ===")
    app.dependency_overrides[get_current_user] = make_user_override(teacher_id)
    # /teacher veya başka role-aware sayfaya bakalım — / redirect ediyor, başka public sayfa lazım
    # Login pagesi hâlâ render ederse oradan görelim — ama login user yokken render edilmesi gerek
    # Yerine /me sayfası rol-aware olmalı
    r = client.get("/me")
    check("/me logged-in 200", r.status_code == 200)
    check("body data-role='teacher'",
          'data-role="teacher"' in r.text)
    app.dependency_overrides.clear()

    # ============ STEP 8: Bento grid + counter ============
    print("\n=== STEP 8: Landing bileşenleri ===")
    r = client.get("/")
    body = r.text
    check("bento-grid sınıfı kullanılıyor",
          "bento-grid" in body)
    check("counter-animate scroll-trigger",
          "counter-animate" in body)
    check("reveal scroll-trigger sınıfı",
          'class="' + "reveal" in body or "reveal-stagger" in body)
    check("Alpine x-data tab switcher",
          "x-data" in body and "tab" in body)
    check("CTA → /signup/teacher",
          "/signup/teacher" in body)

    # ============ STEP 9: Reveal IntersectionObserver script ============
    print("\n=== STEP 9: Tema script'leri ===")
    check("IntersectionObserver scroll-reveal",
          "IntersectionObserver" in body and "reveal-now" in body)
    check("Counter animation tick fn",
          "counter-animate" in body and "requestAnimationFrame" in body)

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        db.execute(delete(User).where(User.id.in_([teacher_id, student_id])))
        db.commit()
    print("  cleanup OK")

    print(f"\n=== SONUÇ ===\nPASS: {passed}\nFAIL: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
