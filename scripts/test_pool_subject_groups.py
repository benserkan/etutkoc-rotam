"""Havuz ders grupları + müfredat modeli — saha regresyonu (2026-10-13, öğrenci #415).

VAKA: akademik yılı atanmamış 11. sınıf öğrencisi (2026-2027'de 9-10-11 Maarif, yalnız 12 Klasik) için
müfredat modeli türetilemiyordu (None) → havuzda okul (Maarif) Fizik hiç yoktu, yalnız AYT/TYT Fizik
vardı ve AYT Fizik konuları klasik 11 içeriğiyle aynı olduğundan "Maarif öğrencisine klasik konular"
görünüyordu.

KURAL: akademik yıl yoksa model bugünün öğretim yılından türetilir · Maarif 11 okul omurgasını izler ·
havuz Klasik 11+/mezunda TYT/AYT derslerini AYRI grup (sinav) olarak sunar; MAARIF 11'de eski TYT/AYT YOK —
yerine "TYT (Maarif)" = TYT karşılığı olan Maarif okul dersleri (konular 9-10. sınıf; 2026-10-13 kullanıcı
kararı), AYT ayrı grup yok (11. sınıf müfredatı zaten AYT Maarif'i kapsar) · eksik ders şeridi yalnız
omurgaya bakar · konu listesi sınıf bilgisi taşır, öğrencinin sınıfını aşmaz.

Çalıştır: PYTHONPATH=. python scripts/test_pool_subject_groups.py
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import PoolItem, StudyPeriod, Track, User, UserRole  # noqa: E402
from app.models.curriculum import CurriculumModel, current_school_year_start  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import pool_mode as pm  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"psg_{secrets.token_hex(3)}"
PWD = "Groups!234567xy"
now = datetime.now(timezone.utc)
passed = 0
failed: list[str] = []
uids: list[int] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def _user(db, tag, role, **kw):
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD), full_name=f"PSG {tag}",
             role=role, is_active=True, created_at=now - timedelta(days=30), **kw)
    db.add(u)
    db.flush()
    uids.append(u.id)
    return u


def main() -> int:
    get_login_limiter().reset()
    with SessionLocal() as db:
        coach = _user(db, "coach", UserRole.TEACHER)
        s11 = _user(db, "s11", UserRole.STUDENT, teacher_id=coach.id, grade_level=11, track=Track.SAYISAL,
                    program_mode="havuz")
        s12 = _user(db, "s12", UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                    program_mode="havuz")
        s9 = _user(db, "s9", UserRole.STUDENT, teacher_id=coach.id, grade_level=9, program_mode="havuz")
        s10 = _user(db, "s10", UserRole.STUDENT, teacher_id=coach.id, grade_level=10, program_mode="havuz")
        for st in (s11, s12, s9, s10):
            pm.open_period(db, student=st, coach=coach, opened_on=now.date())
        db.commit()
        ids = {"s11": s11.id, "s12": s12.id, "s9": s9.id, "s10": s10.id}
    try:
        # ---- birim: öğretim yılı + model türetme
        from datetime import date
        check("Y1 öğretim yılı Eylül sınırı: 2026-10 → 2026 · 2027-03 → 2026 · 2026-08 → 2025",
              current_school_year_start(date(2026, 10, 13)) == 2026 and current_school_year_start(date(2027, 3, 1)) == 2026
              and current_school_year_start(date(2026, 8, 31)) == 2025)
        with SessionLocal() as db:
            a = db.get(User, ids["s11"])
            b = db.get(User, ids["s12"])
            yr = current_school_year_start()
            exp11 = CurriculumModel.MAARIF_LISE if yr - 2 >= 2024 else CurriculumModel.KLASIK_LISE
            check("Y2 akademik yılsız 11 → model türetildi (2026-2027'de MAARIF)", a.effective_curriculum_model == exp11,
                  str(a.effective_curriculum_model))
            check("Y3 akademik yılsız 12 → KLASIK (2026-2027)", yr != 2026 or b.effective_curriculum_model == CurriculumModel.KLASIK_LISE,
                  str(b.effective_curriculum_model))

        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_coach@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text

        # ---- Maarif 11 havuzu
        j = c.get(f"/api/v2/teacher/students/{ids['s11']}/pool").json()
        okul = [s for s in j["subjects"] if s["group"] == "okul"]
        sinav = [s for s in j["subjects"] if s["group"] == "sinav"]
        check("G1 okul grubu Maarif dersleri (Fizik, Matematik) · başlık 'Maarif müfredatı · 11. sınıf'",
              any(s["name"] == "Fizik" for s in okul) and any(s["name"] == "Matematik" for s in okul)
              and (j["curriculum_label"] or "").startswith("Maarif") and "11. sınıf" in (j["curriculum_label"] or ""),
              f"{[s['name'] for s in okul]} {j['curriculum_label']}")
        check("G2 Maarif 11: eski TYT/AYT sınav dersi YOK (kitabı yok), AYT kilit notu yok",
              not sinav and not j["ayt_locked"], str([s["name"] for s in sinav]))
        tyt_ids = set(j.get("tyt_maarif_subject_ids") or [])
        tyt_names = {s["name"] for s in okul if s["id"] in tyt_ids}
        check("G3 TYT (Maarif) = TYT karşılığı olan Maarif dersleri (Fizik, Matematik, TDE), İngilizce YOK · max_grade 10",
              {"Fizik", "Matematik", "Türk Dili ve Edebiyatı"} <= tyt_names and "İngilizce" not in tyt_names
              and j.get("tyt_maarif_max_grade") == 10, str(sorted(tyt_names)))
        check("G4 eksik ders şeridi yalnız omurga (TYT/AYT yok)",
              "Fizik" in j["missing_subjects"] and not any(n.startswith(("TYT", "AYT")) for n in j["missing_subjects"]),
              str(j["missing_subjects"]))
        fiz = next(s for s in okul if s["name"] == "Fizik")
        t = c.get(f"/api/v2/teacher/students/{ids['s11']}/pool/topics?subject_id={fiz['id']}").json()
        grades = {x["grade_level"] for x in t["topics"]}
        names = {x["name"] for x in t["topics"]}
        check("K1 Maarif Fizik konuları sınıf taşır, 11'i aşmaz (9/10/11)", grades and grades <= {9, 10, 11} and 11 in grades,
              str(grades))
        check("K2 Maarif 11 konusu var (Limit Hız / Çembersel Hareket), klasik 'Basit Makineler' yok",
              ({"Limit Hız", "Çembersel Hareket"} & names) and "Basit Makineler" not in names, str(sorted(names))[:200])
        check("K3 TYT (Maarif) kapsamı için 9-10. sınıf Maarif Fizik konuları mevcut",
              bool({9, 10} & grades), str(grades))

        # ---- Klasik 12 havuzu (regresyon: sınav omurgası)
        j = c.get(f"/api/v2/teacher/students/{ids['s12']}/pool").json()
        names12 = {s["name"] for s in j["subjects"]}
        check("R1 Klasik 12: TYT/AYT Fizik var, okul 'Fizik' YOK (sınav omurgası korunur)",
              {"TYT Fizik", "AYT Fizik"} <= names12 and "Fizik" not in names12, str(sorted(names12)))
        check("R3 Klasik 12: TYT (Maarif) grubu yok", not j.get("tyt_maarif_subject_ids"), str(j.get("tyt_maarif_subject_ids")))
        check("R4 Klasik 12: kitabı olmayan sınav-karşılıksız okul dersi (İnkılap, İngilizce) YOK",
              not ({"İngilizce", "T.C. İnkılap Tarihi ve Atatürkçülük"} & names12) and all(s["group"] == "sinav" for s in j["subjects"]),
              str(sorted(names12)))
        check("R2 Klasik 12 başlığı 'Klasik müfredatı · 12. sınıf'", (j["curriculum_label"] or "").startswith("Klasik"),
              str(j["curriculum_label"]))
        # ---- Maarif 9 / 10: yalnız kendi okul müfredatı (sınav grubu, TYT (Maarif), AYT kilidi YOK); konular kümülatif
        for key, g in (("s9", 9), ("s10", 10)):
            j = c.get(f"/api/v2/teacher/students/{ids[key]}/pool").json()
            subs = j["subjects"]
            check(f"M{g}a {g}. sınıf: tüm dersler okul (Maarif), sınav/TYT (Maarif) grubu ve AYT kilidi yok",
                  subs and all(s["group"] == "okul" for s in subs) and not j.get("tyt_maarif_subject_ids")
                  and not j["ayt_locked"] and (j["curriculum_label"] or "").startswith("Maarif")
                  and f"{g}. sınıf" in (j["curriculum_label"] or ""), f"{[s['name'] for s in subs]} {j['curriculum_label']}")
            names_g = {s["name"] for s in subs}
            check(f"M{g}b {g}. sınıf ders seti: Matematik + Fizik + Türk Dili ve Edebiyatı var",
                  {"Matematik", "Fizik", "Türk Dili ve Edebiyatı"} <= names_g, str(sorted(names_g)))
            mat = next(s for s in subs if s["name"] == "Matematik")
            tg = {x["grade_level"] for x in c.get(f"/api/v2/teacher/students/{ids[key]}/pool/topics?subject_id={mat['id']}").json()["topics"]}
            check(f"M{g}c {g}. sınıf Matematik konuları kümülatif 9..{g}, üst sınıf yok",
                  g in tg and max(x for x in tg if x is not None) == g and min(x for x in tg if x is not None) == 9, str(tg))
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(uids)))
            db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(uids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
            db.execute(sa_delete(User).where(User.id.in_(uids)))
            db.commit()
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
