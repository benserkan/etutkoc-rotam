# -*- coding: utf-8 -*-
"""Veli deneme analiz raporu (bağlantı + ses + PDF) smoke — 2026-11-13."""
from __future__ import annotations

import json
import secrets
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User, UserRole
from app.models.curriculum import ExamSection
from app.models.exam_parent_report import ExamParentReport
from app.models.exam_result import ExamResult
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"epr_{secrets.token_hex(3)}"
PWD = "ExamRep!2345"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def seed():
    now = datetime.now(timezone.utc)
    pwd = hash_password(PWD)
    with SessionLocal() as db:
        def u(tag, role, **kw):
            x = User(email=f"{PFX}_{tag}@test.invalid", password_hash=pwd, full_name=f"Ece {tag}",
                     role=role, is_active=True, password_changed_at=now, must_change_password=False, **kw)
            db.add(x); db.flush(); return x
        t = u("t", UserRole.TEACHER)
        t2 = u("t2", UserRole.TEACHER)
        s = u("s", UserRole.STUDENT, teacher_id=t.id, grade_level=12)
        nets = [
            {"name": "Türkçe", "correct": 30, "wrong": 6, "blank": 4, "net": 28.5},
            {"name": "Matematik", "correct": 15, "wrong": 10, "blank": 15, "net": 12.5},
        ]
        e1 = ExamResult(student_id=s.id, created_by_id=t.id, title="TYT Deneme 1", exam_date=date(2026, 10, 1),
                        section=ExamSection.TYT, total_correct=40, total_wrong=20, total_blank=20, net=35.0,
                        subject_nets=json.dumps(nets))
        e2 = ExamResult(student_id=s.id, created_by_id=t.id, title="TYT Deneme 2", exam_date=date(2026, 11, 1),
                        section=ExamSection.TYT, total_correct=45, total_wrong=16, total_blank=19, net=41.0,
                        subject_nets=json.dumps(nets))
        db.add_all([e1, e2]); db.commit()
        return {"t": t.id, "t2": t2.id, "s": s.id, "e2": e2.id, "e1": e1.id}


def cleanup(d):
    from sqlalchemy import delete
    with SessionLocal() as db:
        from app.models import UsageEvent, CreditAccount
        db.execute(delete(ExamParentReport).where(ExamParentReport.student_id == d["s"]))
        db.execute(delete(UsageEvent).where(UsageEvent.owner_id == d["t"]))
        db.execute(delete(CreditAccount).where(CreditAccount.owner_id == d["t"]))
        db.execute(delete(ExamResult).where(ExamResult.student_id == d["s"]))
        db.execute(delete(User).where(User.id.in_([d["t"], d["t2"], d["s"]])))
        db.commit()


def login(tag):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{tag}@test.invalid", "password": PWD})
    assert r.status_code == 200, r.text
    return c


def main():
    d = seed()
    try:
        c = login("t")
        r = c.post(f"/api/v2/teacher/exams/{d['e2']}/parent-report")
        check("1 bağlantı oluştu", r.status_code == 200 and r.json()["created"], r.text[:200])
        tok = r.json()["token"]
        check("2 adres /rapor/{token}", r.json()["url"].endswith(f"/rapor/{tok}"), r.json()["url"])
        r2 = c.post(f"/api/v2/teacher/exams/{d['e2']}/parent-report")
        check("3 ikinci istek aynı bağlantı", r2.json()["token"] == tok and not r2.json()["created"])

        anon = TestClient(app)
        v = anon.get(f"/api/v2/public/exam-report/{tok}")
        check("4 veli girişsiz açar", v.status_code == 200, v.text[:200])
        j = v.json()
        check("5 başlık + artış", "80 sorunun 45 tanesini" in j["hero"]["headline"] and j["hero"]["trend_dir"] == "up", str(j["hero"]))
        levels = next(sx for sx in j["sections"] if sx["type"] == "levels")["items"]
        lv = {s["name"]: s["level"] for s in levels}
        check("6 ders seviyeleri", lv.get("Türkçe") == "strong" and lv.get("Matematik") == "support", str(lv))
        tips = next(sx for sx in j["sections"] if sx["type"] == "tips")["items"]
        check("7 ev önerileri + seslendirme metni", 1 <= len(tips) <= 3 and "Rota" in j["speech_text"]
              and "T Y T" in j["speech_text"])
        check("8 ücretsiz koçta Rota sesi yok (cihaz sesi)", j["voice_available"] is False)
        vv = anon.post(f"/api/v2/public/exam-report/{tok}/voice")
        check("9 ses isteği cihaz sesine düşer", vv.status_code == 200 and vv.json()["fallback"] is True, vv.text)
        with SessionLocal() as db:
            check("10 görüntülenme sayıldı", db.query(ExamParentReport).filter_by(token=tok).one().view_count == 1)

        p = anon.get(f"/api/v2/public/exam-report/{tok}/pdf")
        check("11 PDF", p.status_code == 200 and p.content[:4] == b"%PDF"
              and p.headers["content-type"] == "application/pdf", p.status_code)
        tp = c.post(f"/api/v2/teacher/exams/{d['e2']}/parent-report.pdf", json={"narrative": ["Koçun cümlesi."]})
        check("12 koç PDF (düzenlemeli)", tp.status_code == 200 and tp.content[:4] == b"%PDF")

        c2 = login("t2")
        check("13 başka koç bağlantı alamaz", c2.post(f"/api/v2/teacher/exams/{d['e2']}/parent-report").status_code == 404)
        check("14 uydurma token 404", anon.get("/api/v2/public/exam-report/yok-boyle-bir-sey").status_code == 404)

        # --- ücretli koç: Rota sesi bir kez üretilir, sonra önbellek
        import app.services.tts as tts_mod
        calls = {"n": 0}
        def fake_tts(text, **kw):
            calls["n"] += 1
            return b"ID3fakeaudio", "audio/mpeg"
        orig = tts_mod.synthesize_speech
        tts_mod.synthesize_speech = fake_tts
        try:
            with SessionLocal() as db:
                t = db.get(User, d["t"])
                t.plan = "solo_pro"; t.subscription_status = "active"
                t.ai_capture_consent_at = datetime.now(timezone.utc)
                db.commit()
            j2 = anon.get(f"/api/v2/public/exam-report/{tok}").json()
            check("9a ücretli koçta Rota sesi kullanılabilir", j2["voice_available"] and not j2["voice_ready"])
            a1 = anon.post(f"/api/v2/public/exam-report/{tok}/voice").json()
            a2 = anon.post(f"/api/v2/public/exam-report/{tok}/voice").json()
            check("9b ses bir kez üretildi, ikincisi önbellek", a1["ready"] and a2["ready"] and calls["n"] == 1, f"{a1} {a2} {calls}")
            au = anon.get(f"/api/v2/public/exam-report/{tok}/audio")
            check("9c ses akışı", au.status_code == 200 and au.content == b"ID3fakeaudio")
            check("9d sayfa sesi hazır görür", anon.get(f"/api/v2/public/exam-report/{tok}").json()["voice_ready"])
        finally:
            tts_mod.synthesize_speech = orig

        # --- gelişim + haftalık bağlantıları (2026-11-14)
        sid = d["s"]
        g1 = c.post(f"/api/v2/teacher/students/{sid}/parent-report-link", json={"kind": "progress"})
        g2 = c.post(f"/api/v2/teacher/students/{sid}/parent-report-link", json={"kind": "progress"})
        check("18 gelişim bağlantısı + aynı bağlantı", g1.status_code == 200 and g1.json()["token"] == g2.json()["token"], g1.text[:200])
        gv = anon.get(f"/api/v2/public/exam-report/{g1.json()['token']}").json()
        check("19 gelişim raporu: 2 deneme, 35 → 41", gv.get("kind") == "progress" and "35" in gv["hero"]["headline"]
              and "41" in gv["hero"]["headline"] and any(sx["type"] == "bars" for sx in gv["sections"]), str(gv.get("hero")))
        w1 = c.post(f"/api/v2/teacher/students/{sid}/parent-report-link", json={"kind": "weekly", "week_start": "2026-11-04"})
        w2 = c.post(f"/api/v2/teacher/students/{sid}/parent-report-link", json={"kind": "weekly", "week_start": "2026-11-02"})
        check("20 haftalık bağlantı Pazartesi'ye çekilir (aynı hafta = aynı bağlantı)", w1.status_code == 200
              and w1.json()["token"] == w2.json()["token"], w1.text[:200])
        wv = anon.get(f"/api/v2/public/exam-report/{w1.json()['token']}").json()
        check("21 haftalık rapor açılır", wv.get("kind") == "weekly" and "Kasım" in wv["subtitle"], str(wv.get("subtitle")))
        wp = c.post(f"/api/v2/teacher/students/{sid}/parent-report.pdf", json={"kind": "weekly"})
        gp = anon.get(f"/api/v2/public/exam-report/{g1.json()['token']}/pdf")
        check("22 haftalık + gelişim PDF", wp.content[:4] == b"%PDF" and gp.content[:4] == b"%PDF")
        check("23 başka koç gelişim bağlantısı alamaz",
              c2.post(f"/api/v2/teacher/students/{sid}/parent-report-link", json={"kind": "progress"}).status_code == 404)
        check("24 geçersiz tür 422",
              c.post(f"/api/v2/teacher/students/{sid}/parent-report-link", json={"kind": "baska"}).status_code == 422)

        rv = c.post(f"/api/v2/teacher/exams/{d['e2']}/parent-report/revoke")
        check("15 iptal", rv.status_code == 200)
        check("16 iptal sonrası açılmaz", anon.get(f"/api/v2/public/exam-report/{tok}").status_code == 404)
        r3 = c.post(f"/api/v2/teacher/exams/{d['e2']}/parent-report")
        check("17 iptalden sonra yeni bağlantı", r3.json()["created"] and r3.json()["token"] != tok)
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
