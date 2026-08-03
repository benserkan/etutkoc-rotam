"""AI erişim kontrolleri — koç/kurum müdahale mekanizması (2026-08-03).

Kapsam:
- Koç, öğrenci bazında AI'ı kapatır: öğrencinin kendi tetiklemesi (YSA
  ai-tag) 403 `ai_disabled_by_coach`; KOÇUN kendi tetiklemesi SÜRER.
- Koç, veli AI'ını öğrenci bazında kapatır: veli gate'i available=False +
  "kapatmış" gerekçesi; açınca geri gelir.
- Sahiplik: yabancı koç toggle → 404. Veli/öğrenci rolü toggle → 403/404.
- Koç AI onayını GERİ ALIR: tüm AI consent_required'a döner; yeniden verince
  çalışır.
- Kurum yöneticisi koçun AI'ını kapatır: koçun kendi AI'ı 403
  `ai_disabled_by_institution` + öğrenci tetiklemesi + veli gate'i kapanır;
  yabancı kurum yöneticisi → 404.
- Kullanım dökümü GET /teacher/ai-usage: tür + kişi kırılımı; kurum koçu
  yalnız KENDİ alt-ağacını görür (meslektaş olayı sızmaz); anon 401.
- Kurum /institution/usage yanıtında person_breakdown.

Gemini monkeypatch — gerçek AI çağrısı YOK.
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
    Institution,
    SuspiciousIp,
    UsageEvent,
    User,
    UserRole,
)
from app.models.parent import ParentStudentLink
from app.models.usage import UsageKind, UsageOwnerType
from app.services import ai_wrong_question as aiwq
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"aictl{secrets.token_hex(3)}"
PASSWORD = "AiCtrl!2026X"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 300
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


def mk_user(db, key, role, **kw):
    u = User(email=f"{PFX}-{key}@t.invalid", password_hash=hash_password(PASSWORD),
             full_name=f"{PFX} {key}", role=role, is_active=True,
             must_change_password=False, **kw)
    db.add(u)
    db.flush()
    return u


def client(key) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login",
               json={"email": f"{PFX}-{key}@t.invalid", "password": PASSWORD})
    assert r.status_code == 200, f"login {key}: {r.text[:200]}"
    return c


def main() -> int:
    print(f"\n=== AI erişim kontrolleri smoke — {PFX} ===\n")
    now = datetime.now(timezone.utc)
    ids: dict = {}
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} Kurum", slug=f"{PFX}-k",
                           plan="etut_standart", is_active=True)
        inst2 = Institution(name=f"{PFX} Kurum2", slug=f"{PFX}-k2",
                            plan="etut_standart", is_active=True)
        db.add_all([inst, inst2])
        db.flush()
        coach = mk_user(db, "c", UserRole.TEACHER, plan="solo_pro",
                        ai_capture_consent_at=now)
        coach2 = mk_user(db, "c2", UserRole.TEACHER, plan="solo_pro",
                         ai_capture_consent_at=now)
        s = mk_user(db, "s", UserRole.STUDENT, grade_level=8)
        s.teacher_id = coach.id
        p = mk_user(db, "p", UserRole.PARENT)
        db.add(ParentStudentLink(parent_id=p.id, student_id=s.id, is_primary=True))
        ia = mk_user(db, "ia", UserRole.INSTITUTION_ADMIN, institution_id=inst.id)
        ia2 = mk_user(db, "ia2", UserRole.INSTITUTION_ADMIN, institution_id=inst2.id)
        t1 = mk_user(db, "t1", UserRole.TEACHER, institution_id=inst.id,
                     ai_capture_consent_at=now)
        t2 = mk_user(db, "t2", UserRole.TEACHER, institution_id=inst.id,
                     ai_capture_consent_at=now)
        st = mk_user(db, "st", UserRole.STUDENT, grade_level=8,
                     institution_id=inst.id)
        st.teacher_id = t1.id
        pt = mk_user(db, "pt", UserRole.PARENT)
        db.add(ParentStudentLink(parent_id=pt.id, student_id=st.id, is_primary=True))
        db.commit()
        ids = {k: v.id for k, v in {
            "coach": coach, "coach2": coach2, "s": s, "p": p, "ia": ia,
            "ia2": ia2, "t1": t1, "t2": t2, "st": st, "pt": pt}.items()}
        ids["inst"] = inst.id

    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        # id-reuse savunması: bu id'lere ait eski kullanım olayları temizlenir
        db.execute(sa_delete(UsageEvent).where(
            UsageEvent.actor_user_id.in_(list(ids.values()))))
        db.commit()

    def fake_tag(image_base64, media_type, *, candidates, timeout=45.0):
        return {"question_text": "test", "topic_id": None,
                "difficulty": "orta", "hint": "ipucu"}

    orig = aiwq.tag_wrong_question_photo
    aiwq.tag_wrong_question_photo = fake_tag

    try:
        cs = client("s")          # bağımsız koçun öğrencisi
        cc = client("c")          # bağımsız koç
        cc2 = client("c2")        # yabancı koç
        cp = client("p")          # veli
        cia = client("ia")        # kurum yöneticisi
        cia2 = client("ia2")      # yabancı kurum yöneticisi
        cst = client("st")        # kurum koçunun öğrencisi
        cpt = client("pt")        # kurum velisi

        # Fotoğraflı yanlış (öğrenci) — ai-tag hedefi
        r = cs.post("/api/v2/student/wrong-questions",
                    files=[("photos", ("q.png", PNG, "image/png"))])
        wq = r.json()["data"]["id"]

        print("1) Varsayılan durum + koç toggle okuma")
        r = cc.get(f"/api/v2/teacher/students/{ids['s']}/ai-toggles")
        d = r.json()
        check("varsayılan: ikisi de açık",
              r.status_code == 200 and d["student_ai_enabled"] and d["parent_ai_enabled"],
              r.text[:150])

        print("\n2) Öğrenci AI kapatılır — öğrenci 403, koç tetiklemesi sürer")
        r = cc.post(f"/api/v2/teacher/students/{ids['s']}/ai-toggles",
                    json={"student_ai_enabled": False})
        check("kapatma 200", r.status_code == 200
              and r.json()["data"]["student_ai_enabled"] is False, r.text[:150])
        r = cs.post(f"/api/v2/student/wrong-questions/{wq}/ai-tag")
        check("öğrenci ai-tag 403 ai_disabled_by_coach",
              r.status_code == 403
              and r.json()["detail"]["code"] == "ai_disabled_by_coach", r.text[:150])
        r = cc.post(f"/api/v2/teacher/wrong-questions/{wq}/ai-tag")
        check("koçun kendi tetiklemesi SÜRER (200)", r.status_code == 200, r.text[:200])
        r = cc.post(f"/api/v2/teacher/students/{ids['s']}/ai-toggles",
                    json={"student_ai_enabled": True})
        check("geri açma 200", r.status_code == 200
              and r.json()["data"]["student_ai_enabled"] is True, r.text[:150])
        r = cs.post(f"/api/v2/student/wrong-questions/{wq}/ai-tag")
        check("açınca öğrenci tetiklemesi geri geldi", r.status_code == 200, r.text[:150])

        print("\n3) Veli AI kapatılır — gate kapanır, açınca döner")
        r = cp.get(f"/api/v2/parent/students/{ids['s']}/insight")
        check("önce: veli gate açık", r.json()["ai_available"] is True, r.text[:150])
        cc.post(f"/api/v2/teacher/students/{ids['s']}/ai-toggles",
                json={"parent_ai_enabled": False})
        r = cp.get(f"/api/v2/parent/students/{ids['s']}/insight")
        d = r.json()
        check("kapalı: available=False + 'kapatmış' gerekçesi",
              d["ai_available"] is False and "kapatmış" in (d["unavailable_reason"] or ""),
              r.text[:200])
        cc.post(f"/api/v2/teacher/students/{ids['s']}/ai-toggles",
                json={"parent_ai_enabled": True})
        r = cp.get(f"/api/v2/parent/students/{ids['s']}/insight")
        check("açınca veli gate döndü", r.json()["ai_available"] is True, r.text[:150])

        print("\n4) Sahiplik + rol kapıları")
        r = cc2.post(f"/api/v2/teacher/students/{ids['s']}/ai-toggles",
                     json={"student_ai_enabled": False})
        check("yabancı koç → 404", r.status_code == 404, str(r.status_code))
        r = cp.get(f"/api/v2/teacher/students/{ids['s']}/ai-toggles")
        check("veli rolü → 403", r.status_code == 403, str(r.status_code))
        r = TestClient(app).get("/api/v2/teacher/ai-usage")
        check("anon ai-usage → 401", r.status_code == 401, str(r.status_code))

        print("\n5) Koç onayı geri alma (toptan kapatma)")
        r = cc.post("/api/v2/teacher/ai-consent/revoke")
        check("revoke 200 + consented=False",
              r.status_code == 200 and r.json()["data"]["consented"] is False,
              r.text[:150])
        r = cs.post(f"/api/v2/student/wrong-questions/{wq}/ai-tag")
        check("revoke sonrası öğrenci ai-tag 403 consent_required",
              r.status_code == 403
              and r.json()["detail"]["code"] == "consent_required", r.text[:150])
        r = cp.get(f"/api/v2/parent/students/{ids['s']}/insight")
        check("revoke sonrası veli gate kapalı", r.json()["ai_available"] is False)
        r = cc.post("/api/v2/teacher/ai-consent")
        check("yeniden onay 200", r.status_code == 200
              and r.json()["data"]["consented"] is True, r.text[:150])
        r = cs.post(f"/api/v2/student/wrong-questions/{wq}/ai-tag")
        check("onay sonrası tekrar çalışır", r.status_code == 200, r.text[:150])

        print("\n6) Kurum yöneticisi koçun AI'ını kapatır")
        r = cia.post(f"/api/v2/institution/teachers/{ids['t1']}/ai-toggle",
                     json={"enabled": False})
        check("kurum kapatma 200", r.status_code == 200
              and r.json()["data"]["ai_enabled"] is False, r.text[:150])
        r = cia.get(f"/api/v2/institution/teachers/{ids['t1']}")
        check("öğretmen kartında ai_enabled=False",
              r.json()["ai_enabled"] is False, r.text[:150])
        # Koçun kendi AI'ı (merkezî assert_ai_premium)
        ct1 = client("t1")
        r = ct1.post(f"/api/v2/teacher/students/{ids['st']}/coaching-insight")
        check("koçun kendi AI'ı 403 ai_disabled_by_institution",
              r.status_code == 403
              and r.json()["detail"]["code"] == "ai_disabled_by_institution",
              r.text[:200])
        # Öğrenci tetiklemesi (kurum koçunun öğrencisi)
        r = cst.post("/api/v2/student/wrong-questions",
                     files=[("photos", ("q.png", PNG, "image/png"))])
        wq_st = r.json()["data"]["id"]
        r = cst.post(f"/api/v2/student/wrong-questions/{wq_st}/ai-tag")
        check("öğrenci tetiklemesi 403 ai_disabled_by_institution",
              r.status_code == 403
              and r.json()["detail"]["code"] == "ai_disabled_by_institution",
              r.text[:150])
        # Veli gate
        r = cpt.get(f"/api/v2/parent/students/{ids['st']}/insight")
        check("veli gate 'kurum' gerekçesiyle kapalı",
              r.json()["ai_available"] is False
              and "kurum" in (r.json()["unavailable_reason"] or ""), r.text[:200])
        # Yabancı kurum yöneticisi
        r = cia2.post(f"/api/v2/institution/teachers/{ids['t1']}/ai-toggle",
                      json={"enabled": True})
        check("yabancı kurum yöneticisi → 404", r.status_code == 404,
              str(r.status_code))
        # Geri aç
        r = cia.post(f"/api/v2/institution/teachers/{ids['t1']}/ai-toggle",
                     json={"enabled": True})
        check("kurum geri açma 200", r.status_code == 200
              and r.json()["data"]["ai_enabled"] is True, r.text[:150])

        print("\n7) Kullanım dökümü — bağımsız koç")
        with SessionLocal() as db:
            db.add_all([
                UsageEvent(owner_type=UsageOwnerType.USER, owner_id=ids["coach"],
                           kind=UsageKind.AI_WRONG_TAG, credits=2,
                           period_year_month=now.strftime("%Y-%m"),
                           actor_user_id=ids["s"]),
                UsageEvent(owner_type=UsageOwnerType.USER, owner_id=ids["coach"],
                           kind=UsageKind.AI_PARENT_CHAT, credits=3,
                           period_year_month=now.strftime("%Y-%m"),
                           actor_user_id=ids["p"]),
                UsageEvent(owner_type=UsageOwnerType.USER, owner_id=ids["coach"],
                           kind=UsageKind.AI_COACHING_INSIGHT, credits=6,
                           period_year_month=now.strftime("%Y-%m"),
                           actor_user_id=ids["coach"]),
            ])
            db.commit()
        r = cc.get("/api/v2/teacher/ai-usage?days=30")
        d = r.json()
        # ai-tag testleri de gerçek event üretti (2 kredi/koşu) — >= ile bak
        check("toplamlar dolu", r.status_code == 200 and d["total_credits"] >= 11
              and d["total_count"] >= 3, r.text[:200])
        roles = {p_["role_label"] for p_ in d["persons"]}
        check("kişi kırılımı: Öğrenci + Veli + Koç (sen)",
              {"Öğrenci", "Veli", "Koç (sen)"} <= roles, str(roles))
        kinds = {k["kind"] for k in d["kinds"]}
        check("tür kırılımında veli sohbeti var", "ai_parent_chat" in kinds, str(kinds))
        check("olay listesi dolu + aktör adlı",
              len(d["events"]) >= 3 and all(e["actor_name"] for e in d["events"]),
              str(d["events"][:2]))

        print("\n8) Kullanım dökümü — kurum koçu yalnız KENDİ alt-ağacı")
        with SessionLocal() as db:
            db.add_all([
                UsageEvent(owner_type=UsageOwnerType.INSTITUTION, owner_id=ids["inst"],
                           kind=UsageKind.AI_WRONG_TAG, credits=2,
                           period_year_month=now.strftime("%Y-%m"),
                           actor_user_id=ids["st"]),
                # Meslektaşın (t2) olayı — t1'in dökümüne SIZMAMALI
                UsageEvent(owner_type=UsageOwnerType.INSTITUTION, owner_id=ids["inst"],
                           kind=UsageKind.AI_COACHING_INSIGHT, credits=6,
                           period_year_month=now.strftime("%Y-%m"),
                           actor_user_id=ids["t2"]),
            ])
            db.commit()
        r = ct1.get("/api/v2/teacher/ai-usage?days=30")
        d = r.json()
        actor_ids = {p_["user_id"] for p_ in d["persons"]}
        check("kendi öğrencisinin olayı görünür", ids["st"] in actor_ids, str(actor_ids))
        check("meslektaşın olayı SIZMAZ", ids["t2"] not in actor_ids, str(actor_ids))

        print("\n9) Kurum kullanım sayfası kişi kırılımı")
        r = cia.get("/api/v2/institution/usage")
        d = r.json()
        pb = d.get("person_breakdown", [])
        check("person_breakdown dolu", r.status_code == 200 and len(pb) >= 2,
              str(pb)[:200])
        check("rol etiketleri anlamlı",
              {row["role_label"] for row in pb} <= {"Koç", "Öğrenci", "Veli",
                                                    "Yönetici", "Sistem",
                                                    "Silinmiş kullanıcı", "Diğer"},
              str(pb)[:200])
    finally:
        aiwq.tag_wrong_question_photo = orig
        with SessionLocal() as db:
            db.execute(sa_delete(UsageEvent).where(
                UsageEvent.actor_user_id.in_(list(ids.values()))))
            db.execute(sa_delete(ParentStudentLink).where(
                ParentStudentLink.parent_id.in_([ids["p"], ids["pt"]])))
            from app.models import WrongQuestion, WrongQuestionImage
            wq_ids = [w.id for w in db.query(WrongQuestion).filter(
                WrongQuestion.student_id.in_([ids["s"], ids["st"]])).all()]
            if wq_ids:
                db.execute(sa_delete(WrongQuestionImage).where(
                    WrongQuestionImage.wrong_question_id.in_(wq_ids)))
                db.execute(sa_delete(WrongQuestion).where(
                    WrongQuestion.id.in_(wq_ids)))
            db.execute(sa_delete(User).where(User.email.like(f"{PFX}-%")))
            db.execute(sa_delete(Institution).where(
                Institution.slug.in_([f"{PFX}-k", f"{PFX}-k2"])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f_ in failed:
        print("  FAIL:", f_)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
