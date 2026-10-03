"""Koyu (ve açık) tema okunurluk denetimi — TÜM rol sayfaları, gerçek tarayıcı (2026-10-03).

Her rolün her sayfası açılır; sayfadaki her yaprak metnin zemine karşı kontrastı
`lib_live_contrast` ile ölçülür (OKLCH + yarı saydam zemin doğru hesaplanır).
Eşik altı metinler sayfa + sınıf imzasına göre raporlanır.

Kullanım (dev sunucuları açık: :3000 + :8081):
    python scripts/audit_dark_theme_pages.py [--light] [--role teacher] [--min 3.0]
Çıktı: .shots/contrast_report_<tema>.json + özet.
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys
import time
from datetime import datetime

sys.path.insert(0, ".")
from playwright.sync_api import sync_playwright  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import User, UserRole  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import CONTRAST_JS  # noqa: E402

BASE = "http://localhost:3000"
SA_EMAIL, SA_PW = "audit_superadmin@test.invalid", "AuditSa2026!x"
JS = CONTRAST_JS.replace("worst.slice(0, 8)", "worst.slice(0, 400)")

STUDENT_ID = 228
ROLES = {
    "teacher": ("rehber-koc@etutkoc.demo", "RehberDemo2026!", [
        "/teacher/dashboard", "/teacher/students", f"/teacher/students/{STUDENT_ID}",
        f"/teacher/students/{STUDENT_ID}#analytics", f"/teacher/students/{STUDENT_ID}#curriculum",
        f"/teacher/students/{STUDENT_ID}#books", f"/teacher/students/{STUDENT_ID}#exams",
        f"/teacher/students/{STUDENT_ID}#topics", f"/teacher/students/{STUDENT_ID}#wrongs",
        f"/teacher/students/{STUDENT_ID}#sessions", f"/teacher/students/{STUDENT_ID}#surveys",
        f"/teacher/students/{STUDENT_ID}#dev", f"/teacher/students/{STUDENT_ID}#parents",
        f"/teacher/students/{STUDENT_ID}/week", f"/teacher/students/{STUDENT_ID}/day",
        f"/teacher/students/{STUDENT_ID}/dna", f"/teacher/students/{STUDENT_ID}/focus",
        f"/teacher/students/{STUDENT_ID}/goals", f"/teacher/students/{STUDENT_ID}/review",
        f"/teacher/students/{STUDENT_ID}/promote", "/teacher/students/import",
        "/teacher/academic-years", "/teacher/appointments", "/teacher/billing", "/teacher/bulk-wa",
        "/teacher/burnout", "/teacher/grade-advance", "/teacher/guide", "/teacher/insights",
        "/teacher/library", "/teacher/library/book-sets", "/teacher/library/new",
        "/teacher/library/task-templates", "/teacher/library/templates", "/teacher/plan",
        "/teacher/requests", "/teacher/review", "/teacher/settings", "/teacher/support",
        "/teacher/support-inbox", "/teacher/usage", "/me/account",
    ]),
    "student": ("rehber-elif@etutkoc.demo", "RehberDemo2026!", [
        "/student/day", "/student/week", "/student/books", "/student/exams", "/student/topics",
        "/student/wrong-questions", "/student/review", "/student/dna", "/student/focus",
        "/student/goals", "/student/requests", "/student/surveys", "/student/appointments",
        "/student/guide", "/me/account",
    ]),
    "parent": ("rehber-veli@etutkoc.demo", "RehberDemo2026!", [
        "/parent", f"/parent/students/{STUDENT_ID}", f"/parent/students/{STUDENT_ID}/week",
        f"/parent/students/{STUDENT_ID}/report", f"/parent/students/{STUDENT_ID}/exams",
        f"/parent/students/{STUDENT_ID}/topics", f"/parent/students/{STUDENT_ID}/sessions",
        "/parent/notifications", "/parent/settings", "/parent/support", "/parent/guide", "/me/account",
    ]),
    "institution": ("marhan-yonetici@etutkoc.demo", "MarhanDemo2026!", [
        "/institution", "/institution/teachers", "/institution/teachers/267", "/institution/roster",
        "/institution/invitations", "/institution/compliance", "/institution/academic",
        "/institution/action-center", "/institution/at-risk", "/institution/cohorts",
        "/institution/activity-heatmap", "/institution/burnout", "/institution/teacher-scorecard",
        "/institution/goals", "/institution/admin-digest", "/institution/parent-trust",
        "/institution/self-study", "/institution/activity-stream", "/institution/bulk-wa",
        "/institution/subscription", "/institution/quota", "/institution/usage",
        "/institution/support", "/institution/support-inbox",
    ]),
    "admin": (SA_EMAIL, SA_PW, [
        "/admin", "/admin/institutions", "/admin/institutions/24", "/admin/users", "/admin/users/227",
        "/admin/independent-teachers", "/admin/audit", "/admin/kvkk", "/admin/system-health",
        "/admin/announcements", "/admin/usage", "/admin/quota", "/admin/feature-flags",
        "/admin/feature-catalog", "/admin/feature-catalog/dashboard", "/admin/feature-catalog/discovery-queue",
        "/admin/feature-catalog/experiments", "/admin/revenue/action-center", "/admin/revenue/forecast",
        "/admin/revenue/cohort", "/admin/revenue/campaigns", "/admin/revenue/action-templates",
        "/admin/revenue/users/227", "/admin/revenue/institutions/24", "/admin/security-monitor",
        "/admin/security-monitor/revenue", "/admin/security-monitor/revenue/invoices",
        "/admin/security-monitor/activity", "/admin/security-monitor/sessions",
        "/admin/security-monitor/live", "/admin/security-monitor/alarms", "/admin/security-monitor/abuse",
        "/admin/security-monitor/integrity", "/admin/security-monitor/system",
        "/admin/security-monitor/notifications", "/admin/support", "/admin/contact-requests",
        "/admin/settings", "/admin/pricing", "/admin/whatsapp-templates", "/admin/whatsapp-dispatch-log",
        "/admin/payment-links", "/admin/membership-offers", "/admin/prospects", "/admin/campaign-links",
        "/admin/testimonials", "/admin/conversion", "/admin/activity-stream", "/admin/book-catalog",
        "/admin/communication-health", "/admin/demo-sessions",
    ]),
}


def ensure_superadmin():
    with SessionLocal() as db:
        if db.query(User).filter(User.email == SA_EMAIL).first():
            return
        now = datetime.utcnow()
        db.add(User(email=SA_EMAIL, password_hash=hash_password(SA_PW), full_name="Denetim Yönetici",
                    role=UserRole.SUPER_ADMIN, is_active=True, must_change_password=False,
                    email_verified_at=now, password_changed_at=now))
        db.commit()


def drop_superadmin():
    with SessionLocal() as db:
        db.execute(sa_delete(User).where(User.email == SA_EMAIL))
        db.commit()


def login(page, email, pw):
    for attempt in range(3):
        page.context.clear_cookies()
        page.goto(f"{BASE}/login")
        page.wait_for_selector("input[type=email]")
        time.sleep(1.2)
        page.fill("input[type=email]", email)
        page.fill("input[type=password]", pw)
        page.click("button[type=submit]")
        try:
            page.wait_for_url(lambda u: "/login" not in u, timeout=15000)
            return True
        except Exception:
            time.sleep(62)
    return False


def dismiss(page):
    for name in ("Daha sonra", "Kapat"):
        b = page.get_by_role("button", name=name)
        try:
            if b.count() and b.first.is_visible():
                b.first.click()
                time.sleep(0.6)
        except Exception:
            pass


SIG_RE = re.compile(r"\b(?:dark:)?(?:text|bg)-[a-z]+-\d{2,3}(?:/\d+)?\b")


def main():
    light = "--light" in sys.argv
    only = sys.argv[sys.argv.index("--role") + 1] if "--role" in sys.argv else None
    min_ratio = float(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 3.0
    theme = "light" if light else "dark"
    ensure_superadmin()
    report: dict[str, list[str]] = {}
    sig = collections.Counter()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome")
            for role, (email, pw, paths) in ROLES.items():
                if only and role != only:
                    continue
                ctx = b.new_context(viewport={"width": 1366, "height": 900}, color_scheme=theme)
                page = ctx.new_page()
                if not login(page, email, pw):
                    print(f"[{role}] GİRİŞ OLMADI")
                    continue
                for path in paths:
                    try:
                        page.goto(BASE + path, wait_until="domcontentloaded", timeout=60000)
                        time.sleep(4.5)
                        dismiss(page)
                        res = page.evaluate(JS, {"selector": "body", "minRatio": min_ratio})
                    except Exception as e:  # noqa: BLE001
                        print(f"  ! {path}: {str(e)[:80]}")
                        continue
                    items = [w for w in res["worst"] if "nextjs" not in w and "tsqd" not in w]
                    report[f"{role} {path}"] = items
                    for w in items:
                        cls = w.split(" :: ")[-1]
                        key = " ".join(sorted(set(SIG_RE.findall(cls)))) or cls[:60]
                        sig[key] += 1
                    print(f"[{role}] {path}: {len(items)}", flush=True)
                ctx.close()
            b.close()
    finally:
        drop_superadmin()
    os.makedirs(".shots", exist_ok=True)
    out = f".shots/contrast_report_{theme}.json"
    json.dump({"pages": report, "signatures": sig.most_common()}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    total = sum(len(v) for v in report.values())
    bad_pages = sum(1 for v in report.values() if v)
    print(f"\nTEMA {theme} · eşik {min_ratio} · {len(report)} sayfa · sorunlu sayfa {bad_pages} · okunmaz metin {total}")
    print("En sık sınıf imzaları:")
    for k, n in sig.most_common(25):
        print(f"  {n:4d}  {k}")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
