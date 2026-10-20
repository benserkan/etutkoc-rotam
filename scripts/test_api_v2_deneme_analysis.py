"""D4 — program denemesi analizi smoke (2026-10-20).

   1. TYT Matematik branş: 6 sonuçlu deneme (net düşüyor) + 1 sonuç bekleyen
      → tek branş serisi, net %, doğruluk, boş oranı, soru başı dakika
   2. Normal aralık (çeyrekler arası) + son deneme "altında" + üst üste düşüş 5 + eğilim aşağı
      + 4 deneme sonrası tahmini net % (0–100 arası, sondan düşük)
   3. Kıyas: konulu test kalemlerinden test doğruluğu · karne genel denemesinden ders doğruluğu
   4. İşaretler: decline + below_normal + test_gap
   5. Karne denemesi seri olarak GİRMEZ (yalnız kıyas) · sonuç bekleyen sayılır
   6. Başka koç 404 · öğrenci 403
"""
from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ExamResult, Subject, Task, TaskBookItem, Track, User, UserRole  # noqa: E402
from app.models.curriculum import ExamSection, Topic  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.models.task import TaskStatus, TaskType  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"dan_{secrets.token_hex(3)}"
PWD = "DenemeAn!2345x"
today = date.today()
passed = 0
failed: list[str] = []
ids: dict = {"users": []}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def login(email: str) -> TestClient:
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return c


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Koç",
                     role=UserRole.TEACHER, is_active=True)
        other = User(email=f"{PFX}_o@test.invalid", password_hash=hash_password(PWD), full_name="Öbür Koç",
                     role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other]); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Öğrenci",
                  role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                  track=Track.SAYISAL, must_change_password=False)
        db.add(st); db.flush()
        mat = Subject(name="TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(mat); db.flush()
        top = Topic(subject_id=mat.id, name="Problemler", order=1, teacher_id=coach.id)
        db.add(top); db.flush()
        # Konulu (kaynaksız) test kalemi: 50D 10Y → test doğruluğu %83,3
        t = Task(student_id=st.id, date=today, title="Matematik · Problemler", type=TaskType.TEST,
                 status=TaskStatus.COMPLETED, is_draft=False)
        db.add(t); db.flush()
        db.add(TaskBookItem(task_id=t.id, topic_id=top.id, planned_count=3, completed_count=3,
                            correct_count=50, wrong_count=10, blank_count=0))
        # Karne genel denemesi (elle) — Matematik 30D 5Y → %85,7
        db.add(ExamResult(student_id=st.id, created_by_id=coach.id, title="Özdebir TYT-3",
                          exam_date=today, section=ExamSection.TYT, total_correct=90, total_wrong=20,
                          total_blank=10, net=85.0,
                          subject_nets=json.dumps([{"name": "Matematik", "correct": 30, "wrong": 5, "blank": 5,
                                                    "net": 28.75}])))
        db.commit()
        ids["users"] += [coach.id, other.id, st.id]
        ids["topic"] = top.id
        return {"coach": coach.id, "st": st.id, "mat": mat.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(u)))
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        if ids.get("topic"):
            db.execute(sa_delete(Topic).where(Topic.id == ids["topic"]))
        db.execute(sa_delete(Subject).where(Subject.teacher_id.in_(u)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def main() -> int:
    d = seed()
    print(f"\n=== deneme analizi D4 — {PFX} ===\n")
    try:
        c = login(f"{PFX}_t@test.invalid")
        s = login(f"{PFX}_s@test.invalid")
        sid = d["st"]
        r = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": today.isoformat(), "kind": "brans", "subject_id": d["mat"], "count": 7,
                         "question_count": 20, "name": "Branş mat", "is_draft": False})
        assert r.status_code == 200, r.text
        tid = r.json()["data"]["id"]
        items = sorted(x["id"] for x in r.json()["data"]["items"])
        # 6 sonuçlu, net düşüyor: D 14..9, Y 6 → net 12.5, 11.5, ... 7.5 ; 7. çözüldü sonuç yok
        rows = [{"item_id": iid, "solved": True, "correct": 14 - k, "wrong": 6,
                 "duration_minutes": 40 if k < 3 else None}
                for k, iid in enumerate(items[:6])]
        rows.append({"item_id": items[6], "solved": True})
        r = s.post(f"/api/v2/student/tasks/{tid}/deneme-results", json={"rows": rows})
        check("0 sonuç kaydı 200", r.status_code == 200, r.text[:200])
        inv = r.json().get("invalidate", [])
        check("0b invalidate deneme-analysis", any(k.endswith(f"students:{sid}:deneme-analysis") for k in inv), str(inv))

        r = c.get(f"/api/v2/teacher/students/{sid}/deneme-analysis")
        check("1a 200", r.status_code == 200, r.text[:300])
        a = r.json()
        sm = a["summary"]
        check("1b özet: 6 sonuçlu · 1 bekleyen", sm["with_result"] == 6 and sm["pending"] == 1, str(sm))
        check("5a karne denemesi seri değil (tek seri)", sm["series_count"] == 1 and sm["branch_series"] == 1,
              str([x["key"] for x in a["series"]]))
        ser = a["series"][0] if a["series"] else {}
        check("1c seri tyt~matematik branş", ser.get("key") == "tyt~matematik" and ser.get("kind") == "brans",
              str(ser.get("key")))
        pts = ser.get("points", [])
        check("1d 6 nokta, ilk net 12.5 · %62.5", len(pts) == 6 and pts[0]["net"] == 12.5
              and pts[0]["net_pct"] == 62.5, str(pts[:1]))
        check("1e doğruluk 69/(69+36)=%65.7", ser.get("accuracy_pct") == 65.7, str(ser.get("accuracy_pct")))
        # boş: her denemede 20-D-6 → 0..5 → 15 / 120
        check("1f boş oranı %12.5", ser.get("blank_rate_pct") == 12.5, str(ser.get("blank_rate_pct")))
        check("1g soru başı 2 dk (3 süreli deneme)", ser.get("min_per_question") == 2.0
              and ser.get("timed_count") == 3, str(ser.get("min_per_question")))
        check("5b sonuç bekleyen derse yazıldı", ser.get("pending") == 1, str(ser.get("pending")))

        check("2a normal aralık var", ser.get("normal_low") is not None
              and ser["normal_low"] <= ser["normal_high"], f"{ser.get('normal_low')} {ser.get('normal_high')}")
        check("2b son deneme normal aralığın altında", ser.get("last_position") == "below", str(ser.get("last_position")))
        check("2c üst üste düşüş 5", ser.get("decline_run") == 5, str(ser.get("decline_run")))
        check("2d eğilim aşağı", ser.get("direction") == "down" and (ser.get("slope") or 0) < 0, str(ser.get("slope")))
        proj = ser.get("projected_net_pct")
        check("2e tahmin 0–100 ve son değerin altında", proj is not None and 0 <= proj < pts[-1]["net_pct"],
              f"{proj} vs {pts[-1]['net_pct']}")

        check("3a test doğruluğu %83.3", ser.get("test_accuracy_pct") == 83.3, str(ser.get("test_accuracy_pct")))
        check("3b karne genel denemesinde ders doğruluğu %85.7", ser.get("genel_accuracy_pct") == 85.7
              and ser.get("genel_exams") == 1, str(ser.get("genel_accuracy_pct")))

        codes = {f["code"] for f in a["flags"]}
        check("4 işaretler decline + below_normal + test_gap", {"decline", "below_normal", "test_gap"} <= codes,
              str(codes))

        # 7 — ek açılar (2026-10-20): net % 62.5 → 37.5, her denemede −5 (düz doğru)
        check("7a en iyi/en düşük", ser.get("best_net_pct") == 62.5 and ser.get("worst_net_pct") == 37.5,
              f"{ser.get('best_net_pct')} {ser.get('worst_net_pct')}")
        check("7b düz doğru → düzenli (sapma 0)", ser.get("stdev_net_pct") == 0 and ser.get("consistency") == "high",
              f"{ser.get('stdev_net_pct')} {ser.get('consistency')}")
        check("7c ivme son 3 − önceki 3 = −15", ser.get("momentum") == -15.0 and ser.get("momentum_window") == 3,
              str(ser.get("momentum")))
        check("7d kaçan net: yanlış 6×1.25=7.5 · boş 2.5", ser.get("lost_wrong_per_exam") == 7.5
              and ser.get("lost_blank_per_exam") == 2.5 and ser.get("penalty") == 4,
              f"{ser.get('lost_wrong_per_exam')} {ser.get('lost_blank_per_exam')}")
        check("7e ortalama net 10 · 20 soru", ser.get("avg_net") == 10.0 and ser.get("avg_questions") == 20.0,
              f"{ser.get('avg_net')} {ser.get('avg_questions')}")
        check("7f son deneme bugün", ser.get("days_since_last") == 0 and ser.get("last_date") == today.isoformat(),
              str(ser.get("days_since_last")))
        ov = a.get("overview") or {}
        check("7g kuşbakışı 6 deneme · 1 ders · 120 soru", ov.get("exams") == 6 and ov.get("subjects") == 1
              and ov.get("questions") == 120, str({k: ov.get(k) for k in ("exams", "subjects", "questions")}))
        check("7h tek derste 'en zayıf' yok, 'gerileyen' var", ov.get("weakest") is None
              and (ov.get("falling") or {}).get("key") == "tyt~matematik", str(ov.get("falling")))
        check("7i haftalık ritim 8 hafta, bu hafta 6", len(ov.get("weeks", [])) == 8
              and ov["weeks"][-1]["count"] == 6, str(ov.get("weeks", [])[-1:]))

        o = login(f"{PFX}_o@test.invalid")
        check("6a başka koç 404", o.get(f"/api/v2/teacher/students/{sid}/deneme-analysis").status_code == 404)
        check("6b öğrenci 403", s.get(f"/api/v2/teacher/students/{sid}/deneme-analysis").status_code == 403)
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
