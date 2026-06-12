# -*- coding: utf-8 -*-
"""Anket sistemi (Faz 1) smoke testi.

Senaryolar:
  1.  anon → 401
  2.  rol kapıları: öğrenci koç ucuna 403, koç öğrenci ucuna 403
  3.  koç katalog → 11 anket + 4 kategori
  4.  koç kendi öğrencisine anket atar → 200 + listede görünür
  5.  aynı şablonu tekrar atama → 409 survey_already_assigned
  6.  yabancı koç atayamaz → 404 student_not_found (sızıntı yok)
  7.  öğrenci listesinde atama 'pending' görünür
  8.  doldurma görünümü → sorular + disclaimer
  9.  kısmi kaydet → in_progress + cevap sayısı korunur
  10. eksikle tamamla → ok=False + missing_question_ids
  11. tam tamamla → completed + boyut skorları hesaplanır
  12. koç sonucu görür → boyut etiketleri + level + yorum
  13. yaşam çarkı (wheel) → dilim skorları + açık uç cevaplar raporda
  14. SWOT (qualitative) → kadran blokları
  15. iptal akışı: bekleyeni iptal OK · tamamlananı iptal 400
  16. yabancı koç atamayı göremez → 404
  17. başka öğrenci atamayı göremez/dolduramaz → 404
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

from app.database import SessionLocal
from app.main import app
from app.models import SurveyAssignment, SurveyTemplate, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"srv_{secrets.token_hex(3)}"
PWD = hash_password("Survey!234")
PWDH = "Survey!234"
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


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        def user(suffix, role, teacher_id=None):
            u = User(email=f"{PFX}_{suffix}@test.invalid", password_hash=PWD,
                     full_name=f"{PFX} {suffix}", role=role,
                     teacher_id=teacher_id, institution_id=None,
                     grade_level=8 if role == UserRole.STUDENT else None,
                     is_active=True, plan="solo_pro",
                     password_changed_at=now, must_change_password=False)
            db.add(u)
            db.flush()
            return u
        c1 = user("c1", UserRole.TEACHER)
        c2 = user("c2", UserRole.TEACHER)
        s1 = user("s1", UserRole.STUDENT, teacher_id=c1.id)
        s2 = user("s2", UserRole.STUDENT, teacher_id=c2.id)
        db.commit()
        ctx.update(c1=c1.id, c2=c2.id, s1=s1.id, s2=s2.id)
        # şablon id'leri (seed'den)
        for code in ("ogrenme-stilleri", "yasam-carki", "swot", "coklu-zeka"):
            t = db.query(SurveyTemplate).filter(SurveyTemplate.code == code).first()
            if not t:
                raise RuntimeError(f"seed eksik: {code} — önce scripts/seed_surveys.py çalıştır")
            ctx[f"t_{code}"] = t.id


def login(suffix):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login",
               json={"email": f"{PFX}_{suffix}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {suffix}: {r.status_code} {r.text[:200]}")
    return c


def cleanup():
    with SessionLocal() as db:
        uids = [ctx.get(k) for k in ("c1", "c2", "s1", "s2") if ctx.get(k)]
        if uids:
            db.query(SurveyAssignment).filter(
                SurveyAssignment.student_id.in_(uids)
            ).delete(synchronize_session=False)
            db.query(SuspiciousIp).filter(SuspiciousIp.ip == "testclient").delete(
                synchronize_session=False
            )
            db.query(User).filter(User.id.in_(uids)).delete(synchronize_session=False)
        db.commit()


def main() -> int:
    print(f"\n=== ANKET SİSTEMİ SMOKE — {PFX} ===\n")
    setup()
    s1 = ctx["s1"]
    try:
        # 1. anon
        anon = TestClient(app)
        r = anon.get("/api/v2/teacher/surveys/catalog")
        check("1. anon katalog → 401", r.status_code == 401, r.status_code)

        coach = login("c1")
        student = login("s1")

        # 2. rol kapıları
        r = student.get("/api/v2/teacher/surveys/catalog")
        check("2a. öğrenci koç ucuna → 403", r.status_code == 403, r.status_code)
        r = coach.get("/api/v2/student/surveys")
        check("2b. koç öğrenci ucuna → 403", r.status_code == 403, r.status_code)

        # 3. katalog
        r = coach.get("/api/v2/teacher/surveys/catalog")
        cat = r.json()
        check("3. katalog 11 anket + 4 kategori",
              r.status_code == 200 and len(cat["items"]) >= 11
              and len(cat["categories"]) == 4,
              f"{r.status_code} n={len(cat.get('items', []))}")

        # 4. atama
        tid = ctx["t_ogrenme-stilleri"]
        r = coach.post(f"/api/v2/teacher/students/{s1}/surveys",
                       json={"template_id": tid, "note": "İlk görüşme öncesi doldur"})
        ok4 = r.status_code == 200
        aid = r.json()["data"]["assignment_id"] if ok4 else None
        lst = coach.get(f"/api/v2/teacher/students/{s1}/surveys").json()
        check("4. koç atar + listede görünür",
              ok4 and any(a["id"] == aid for a in lst["assignments"]),
              f"{r.status_code}")

        # 5. mükerrer
        r = coach.post(f"/api/v2/teacher/students/{s1}/surveys",
                       json={"template_id": tid})
        check("5. mükerrer atama → 409", r.status_code == 409
              and _code(r) == "survey_already_assigned", f"{r.status_code} {_code(r)}")

        # 6. yabancı koç
        coach2 = login("c2")
        r = coach2.post(f"/api/v2/teacher/students/{s1}/surveys",
                        json={"template_id": tid})
        check("6. yabancı koç atayamaz → 404", r.status_code == 404, r.status_code)

        # 7. öğrenci listesi
        r = student.get("/api/v2/student/surveys")
        body = r.json()
        check("7. öğrencide pending görünür",
              r.status_code == 200
              and any(a["id"] == aid for a in body["pending"]),
              f"{r.status_code}")

        # 8. doldurma görünümü
        r = student.get(f"/api/v2/student/surveys/{aid}")
        fill = r.json()
        qids = [q["id"] for q in fill.get("questions", [])]
        check("8. sorular + disclaimer",
              r.status_code == 200 and len(qids) == 18
              and "psikolojik test değildir" in fill.get("disclaimer", ""),
              f"{r.status_code} n={len(qids)}")

        # 9. kısmi kaydet
        partial = {str(q): 4 for q in qids[:5]}
        r = student.post(f"/api/v2/student/surveys/{aid}/answers",
                         json={"answers": partial, "complete": False})
        d = r.json()["data"]
        r2 = student.get(f"/api/v2/student/surveys/{aid}")
        check("9. kısmi kaydet → in_progress + 5 cevap",
              r.status_code == 200 and d["status"] == "in_progress"
              and len(r2.json()["answers"]) == 5,
              f"{r.status_code} {d}")

        # 10. eksikle tamamla
        r = student.post(f"/api/v2/student/surveys/{aid}/answers",
                         json={"answers": {}, "complete": True})
        d = r.json()["data"]
        check("10. eksikle tamamla → ok=False + missing",
              r.status_code == 200 and d["ok"] is False
              and len(d["missing_question_ids"]) == 13,
              f"{r.status_code} {d.get('missing_question_ids') and len(d['missing_question_ids'])}")

        # 11. tam tamamla (görsel maddelere 5, diğerlerine 2 → görsel baskın)
        full = {}
        for q in fill["questions"]:
            full[str(q["id"])] = 5 if q["dimension_key"] == "gorsel" else 2
        r = student.post(f"/api/v2/student/surveys/{aid}/answers",
                         json={"answers": full, "complete": True})
        d = r.json()["data"]
        check("11. tam tamamla → completed", r.status_code == 200
              and d["completed"] is True and d["status"] == "completed",
              f"{r.status_code} {d}")

        # 12. koç sonucu
        r = coach.get(f"/api/v2/teacher/surveys/assignments/{aid}")
        det = r.json()
        res = det.get("result") or {}
        dims = {x["key"]: x for x in res.get("dimensions", [])}
        check("12. koç sonuç: görsel=100 high + etiket + yorum",
              r.status_code == 200
              and dims.get("gorsel", {}).get("score_pct") == 100
              and dims["gorsel"]["level"] == "high"
              and dims["gorsel"]["label"] == "Görsel"
              and dims["gorsel"]["comment"] != ""
              and res.get("top_dimensions", [None])[0] == "gorsel",
              f"{r.status_code} {dims.get('gorsel')}")

        # 13. yaşam çarkı (wheel)
        tid_w = ctx["t_yasam-carki"]
        r = coach.post(f"/api/v2/teacher/students/{s1}/surveys",
                       json={"template_id": tid_w})
        aid_w = r.json()["data"]["assignment_id"]
        fill_w = student.get(f"/api/v2/student/surveys/{aid_w}").json()
        ans_w = {}
        for q in fill_w["questions"]:
            if q["qtype"] == "slider10":
                ans_w[str(q["id"])] = 3 if q["dimension_key"] == "dersler" else 8
            else:
                ans_w[str(q["id"])] = "Derslerimde daha planlı olmak isterdim."
        r = student.post(f"/api/v2/student/surveys/{aid_w}/answers",
                         json={"answers": ans_w, "complete": True})
        det_w = coach.get(f"/api/v2/teacher/surveys/assignments/{aid_w}").json()
        res_w = det_w.get("result") or {}
        dims_w = {x["key"]: x for x in res_w.get("dimensions", [])}
        check("13. çark: 8 dilim + düşük dilim + açık uç raporda",
              len(dims_w) == 8
              and dims_w.get("dersler", {}).get("level") == "low"
              and len(res_w.get("open_answers", [])) == 2,
              f"dims={len(dims_w)} open={len(res_w.get('open_answers', []))}")

        # 14. SWOT (qualitative)
        tid_s = ctx["t_swot"]
        r = coach.post(f"/api/v2/teacher/students/{s1}/surveys",
                       json={"template_id": tid_s})
        aid_s = r.json()["data"]["assignment_id"]
        fill_s = student.get(f"/api/v2/student/surveys/{aid_s}").json()
        ans_s = {str(q["id"]): f"Cevap {i}" for i, q in enumerate(fill_s["questions"])}
        student.post(f"/api/v2/student/surveys/{aid_s}/answers",
                     json={"answers": ans_s, "complete": True})
        det_s = coach.get(f"/api/v2/teacher/surveys/assignments/{aid_s}").json()
        res_s = det_s.get("result") or {}
        blocks = {b["key"]: b for b in res_s.get("qualitative", [])}
        check("14. SWOT: 4 kadran + cevaplar",
              len(blocks) == 4 and len(blocks.get("guclu", {}).get("entries", [])) == 2
              and blocks["guclu"]["entries"][0]["answer"] != "",
              f"blocks={list(blocks.keys())}")

        # 15. iptal akışı
        tid_c = ctx["t_coklu-zeka"]
        r = coach.post(f"/api/v2/teacher/students/{s1}/surveys",
                       json={"template_id": tid_c})
        aid_c = r.json()["data"]["assignment_id"]
        r = coach.post(f"/api/v2/teacher/surveys/assignments/{aid_c}/cancel")
        ok_cancel = r.status_code == 200
        r2 = coach.post(f"/api/v2/teacher/surveys/assignments/{aid}/cancel")
        check("15. bekleyeni iptal OK · tamamlananı iptal 400",
              ok_cancel and r2.status_code == 400
              and _code(r2) == "survey_completed",
              f"{r.status_code}/{r2.status_code}")

        # 16. yabancı koç sonucu göremez
        r = coach2.get(f"/api/v2/teacher/surveys/assignments/{aid}")
        check("16. yabancı koç atama → 404", r.status_code == 404, r.status_code)

        # 17. başka öğrenci dolduramaz
        student2 = login("s2")
        r = student2.get(f"/api/v2/student/surveys/{aid_w}")
        r2 = student2.post(f"/api/v2/student/surveys/{aid_w}/answers",
                           json={"answers": {}, "complete": False})
        check("17. başka öğrenci → 404",
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
