# -*- coding: utf-8 -*-
"""AI Kariyer Sentezi smoke (KS4 kredi deseni — cache'li).

Gerçek Gemini çağrısı YAPILMAZ — generate_career_synthesis monkeypatch'lenir.

Senaryolar:
   1. anon → 401
   2. GET (anket yok) → ready=False + 2 eksik anket adı (kredi yok)
   3. POST (anket yok) → 422 not_enough_data + missing_surveys
   4. öğrenci RIASEC + Beceri Seti'ni tamamlar → GET ready=True, insight=None
   5. POST rıza yok → 403 consent_required
   6. rıza ver + POST → sentez üretildi + öneriler + kredi=1
   7. GET → cache, KREDİ DÜŞMEZ (hâlâ 1) + is_stale=False
   8. kariyer setinden anket yeniden tamamlanır → GET is_stale=True
   9. POST yenile → is_stale=False + kredi=2
  10. free plan koç → 403 plan_upgrade_required
  11. yabancı koç → 404 (GET + POST)
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    CareerInsight,
    CreditAccount,
    SurveyAssignment,
    SurveyTemplate,
    User,
    UserRole,
)
from app.models.suspicious_ip import SuspiciousIp
from app.models.usage import UsageEvent, UsageKind
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
import app.services.ai_career_synthesis as ai_career

PFX = f"crs_{secrets.token_hex(3)}"
PWD = hash_password("Career!234")
PWDH = "Career!234"
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


def _code(r):
    try:
        return (r.json().get("detail", {}) or {}).get("code")
    except Exception:
        return None


FAKE_SYNTHESIS = {
    "summary": "Sosyal becerileri ve sözel ifadesi güçlü; eşit ağırlık profili belirgin.",
    "career_suggestions": [
        {"title": "Psikoloji", "field": "Eşit Ağırlık",
         "why": "Sosyal boyut yüksek + empati güçlü.",
         "example_departments": ["Psikoloji", "PDR"]},
        {"title": "Hukuk", "field": "Eşit Ağırlık",
         "why": "İkna ve sözel ifade güçlü.",
         "example_departments": ["Hukuk"]},
    ],
    "strengths": ["Empati", "Sözel ifade"],
    "agenda": ["Psikoloji mesleğini araştırma görevi ver"],
    "watch_outs": ["Matematik temposu hedefin gerisinde"],
}


def setup():
    get_login_limiter().reset()
    # Gerçek Gemini çağrısı yok
    ai_career.generate_career_synthesis = (  # type: ignore[assignment]
        lambda *a, **k: dict(FAKE_SYNTHESIS)
    )
    with SessionLocal() as db:
        def user(suffix, role, teacher_id=None, plan="solo_pro", consent=None):
            u = User(email=f"{PFX}_{suffix}@test.invalid", password_hash=PWD,
                     full_name=f"{PFX} {suffix}", role=role,
                     teacher_id=teacher_id, institution_id=None,
                     grade_level=11 if role == UserRole.STUDENT else None,
                     is_active=True, plan=plan,
                     password_changed_at=now, must_change_password=False)
            if consent:
                u.ai_capture_consent_at = consent
            db.add(u)
            db.flush()
            return u
        c1 = user("c1", UserRole.TEACHER)            # ücretli, rıza sonra verilir
        c2 = user("c2", UserRole.TEACHER)            # yabancı koç
        cf = user("cf", UserRole.TEACHER, plan="solo_free")  # ücretsiz
        s1 = user("s1", UserRole.STUDENT, teacher_id=c1.id)
        sf = user("sf", UserRole.STUDENT, teacher_id=cf.id)
        db.commit()
        ctx.update(c1=c1.id, c2=c2.id, cf=cf.id, s1=s1.id, sf=sf.id)
        for code in ("mesleki-ilgi", "beceri-seti", "akademik-benlik"):
            t = db.query(SurveyTemplate).filter(SurveyTemplate.code == code).first()
            if not t:
                raise RuntimeError(f"seed eksik: {code}")
            ctx[f"t_{code}"] = t.id


def login(suffix):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login",
               json={"email": f"{PFX}_{suffix}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {suffix}: {r.status_code}")
    return c


def complete_survey(coach, student, sid, template_id):
    """Koç atar, öğrenci tüm sorulara 4 verip tamamlar."""
    r = coach.post(f"/api/v2/teacher/students/{sid}/surveys",
                   json={"template_id": template_id})
    aid = r.json()["data"]["assignment_id"]
    fill = student.get(f"/api/v2/student/surveys/{aid}").json()
    answers = {
        str(q["id"]): (4 if q["qtype"] in ("likert5",) else 6 if q["qtype"] == "slider10" else "cevap")
        for q in fill["questions"]
    }
    r = student.post(f"/api/v2/student/surveys/{aid}/answers",
                     json={"answers": answers, "complete": True})
    assert r.json()["data"]["completed"], f"anket tamamlanamadı: {r.text[:200]}"
    return aid


def credit_count():
    with SessionLocal() as db:
        return (
            db.query(UsageEvent)
            .filter(UsageEvent.owner_id == ctx["c1"],
                    UsageEvent.kind == UsageKind.AI_CAREER_SYNTHESIS)
            .count()
        )


def cleanup():
    with SessionLocal() as db:
        uids = [ctx.get(k) for k in ("c1", "c2", "cf", "s1", "sf") if ctx.get(k)]
        if uids:
            db.execute(sa_delete(CareerInsight).where(CareerInsight.student_id.in_(uids)))
            db.execute(sa_delete(SurveyAssignment).where(SurveyAssignment.student_id.in_(uids)))
            db.execute(sa_delete(UsageEvent).where(UsageEvent.owner_id.in_(uids)))
            db.execute(sa_delete(CreditAccount).where(CreditAccount.owner_id.in_(uids)))
            db.query(SuspiciousIp).filter(SuspiciousIp.ip == "testclient").delete(
                synchronize_session=False)
            db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def main() -> int:
    print(f"\n=== AI KARİYER SENTEZİ SMOKE — {PFX} ===\n")
    setup()
    s1 = ctx["s1"]
    try:
        # 1. anon
        anon = TestClient(app)
        r = anon.get(f"/api/v2/teacher/students/{s1}/career-synthesis")
        check("1. anon → 401", r.status_code == 401, r.status_code)

        coach = login("c1")
        student = login("s1")

        # 2. GET anket yok
        r = coach.get(f"/api/v2/teacher/students/{s1}/career-synthesis")
        b = r.json()
        check("2. GET: ready=False + 2 eksik anket",
              r.status_code == 200 and b["ready"] is False
              and len(b["missing_surveys"]) == 2 and b["insight"] is None,
              f"{r.status_code} {b.get('missing_surveys')}")

        # 3. POST anket yok → 422 (rıza/paket kapısından önce veri kontrolü değil —
        #    kapı önce; c1 ücretli ama rızasız → consent 403 gelir. Önce rıza verelim mi?
        #    Sıra: premium → consent → readiness. c1 ücretli + rızasız → 403 beklenir;
        #    bu adımda yalnız readiness'i test etmek için geçici rıza verip geri alırız.
        with SessionLocal() as db:
            u = db.query(User).get(ctx["c1"])
            u.ai_capture_consent_at = now
            db.commit()
        r = coach.post(f"/api/v2/teacher/students/{s1}/career-synthesis")
        det = r.json().get("detail", {})
        check("3. POST anket yok → 422 not_enough_data",
              r.status_code == 422 and det.get("code") == "not_enough_data"
              and len((det.get("details") or {}).get("missing_surveys", [])) == 2,
              f"{r.status_code} {det}")
        with SessionLocal() as db:
            u = db.query(User).get(ctx["c1"])
            u.ai_capture_consent_at = None
            db.commit()

        # 4. zorunlu iki anketi tamamla
        complete_survey(coach, student, s1, ctx["t_mesleki-ilgi"])
        complete_survey(coach, student, s1, ctx["t_beceri-seti"])
        r = coach.get(f"/api/v2/teacher/students/{s1}/career-synthesis")
        b = r.json()
        check("4. anketler tamam → ready=True, insight=None",
              b["ready"] is True and b["missing_surveys"] == [] and b["insight"] is None,
              f"{b.get('ready')} {b.get('missing_surveys')}")

        # 5. POST rıza yok → 403
        r = coach.post(f"/api/v2/teacher/students/{s1}/career-synthesis")
        check("5. rıza yok → 403 consent_required",
              r.status_code == 403 and _code(r) == "consent_required",
              f"{r.status_code} {_code(r)}")

        # 6. rıza ver + üret
        with SessionLocal() as db:
            u = db.query(User).get(ctx["c1"])
            u.ai_capture_consent_at = now
            db.commit()
        r = coach.post(f"/api/v2/teacher/students/{s1}/career-synthesis")
        b = r.json()
        ins = b.get("insight") or {}
        check("6. POST → sentez + öneriler + kredi=1",
              r.status_code == 200 and ins.get("summary")
              and len(ins.get("career_suggestions", [])) == 2
              and ins["career_suggestions"][0]["title"] == "Psikoloji"
              and len(ins.get("based_on_surveys", [])) == 2
              and credit_count() == 1,
              f"{r.status_code} kredi={credit_count()}")

        # 7. GET ücretsiz
        r = coach.get(f"/api/v2/teacher/students/{s1}/career-synthesis")
        b = r.json()
        check("7. GET cache → kredi hâlâ 1 + is_stale=False",
              r.status_code == 200 and (b.get("insight") or {}).get("summary")
              and b["is_stale"] is False and credit_count() == 1,
              f"{r.status_code} kredi={credit_count()}")

        # 8. kariyer setinden yeni anket tamamlanır → stale
        complete_survey(coach, student, s1, ctx["t_akademik-benlik"])
        r = coach.get(f"/api/v2/teacher/students/{s1}/career-synthesis")
        check("8. yeni anket → is_stale=True",
              r.json()["is_stale"] is True, r.text[:150])

        # 9. yenile
        r = coach.post(f"/api/v2/teacher/students/{s1}/career-synthesis")
        b = r.json()
        check("9. POST yenile → is_stale=False + kredi=2 + 3 anket",
              r.status_code == 200 and b["is_stale"] is False
              and len((b.get("insight") or {}).get("based_on_surveys", [])) == 3
              and credit_count() == 2,
              f"{r.status_code} kredi={credit_count()}")

        # 10. free plan koç → 403 plan_upgrade_required
        coach_f = login("cf")
        r = coach_f.post(f"/api/v2/teacher/students/{ctx['sf']}/career-synthesis")
        check("10. free plan → 403 plan_upgrade_required",
              r.status_code == 403 and _code(r) == "plan_upgrade_required",
              f"{r.status_code} {_code(r)}")

        # 11. yabancı koç → 404
        coach2 = login("c2")
        r = coach2.get(f"/api/v2/teacher/students/{s1}/career-synthesis")
        r2 = coach2.post(f"/api/v2/teacher/students/{s1}/career-synthesis")
        check("11. yabancı koç → 404 (GET+POST)",
              r.status_code == 404 and r2.status_code == 404,
              f"{r.status_code}/{r2.status_code}")

    finally:
        cleanup()

    print(f"\n=== SONUÇ: {passed} PASS / {len(failed)} FAIL ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
