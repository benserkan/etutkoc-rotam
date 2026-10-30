"""Smoke — konusuz test görevleri → müfredat konusu (2026-10-16, Açı Seçkin Kurs saha bulgusu).

Koç "Diğer" etkinliğine "AÇI 2 TEST" yazınca görevdeki testler hiçbir tabloya
girmiyordu. Doğrulananlar:
  · test sayısı + konu önerisi (kısa yazım, tema → alt konu, TYT karşılığı)
  · koçun konusuz görev listesi (yalnız test sayısı yazılmış etkinlikler)
  · dönüştürme: tamamlanmış görev çözülmüş test sayılır, tema/yabancı/çift dönüşüm reddedilir
  · dönüşen görev kurum kohort tablosuna ve müfredata yansır
  · kohort görev sayıları + konusuz görev sayacı, koç rozeti

  python scripts/test_task_topic_link.py
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Institution, Subject, Task, TaskBookItem, TaskStatus, TaskType, Topic, User, UserRole,
)
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import task_topic_link as ttl  # noqa: E402
from app.services.cohort_analysis import (  # noqa: E402
    cohort_by_curriculum, cohort_by_exam_target, cohort_by_grade, cohort_by_track,
)
from app.services.curriculum_progress import compute_curriculum_progress  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"ttl_{secrets.token_hex(3)}"
PWD = "Koc!234567xyQwe"
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


def _subj(db, name, model):
    return (db.query(Subject).filter(Subject.name == name, Subject.is_builtin.is_(True),
                                     Subject.curriculum_model == model).first())


def seed() -> dict:
    from app.models.curriculum import CurriculumModel

    today = date.today()
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} Kurs", slug=f"{PFX}-kurs", plan="dershane_pro", is_active=True)
        db.add(inst)
        db.flush()
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Rehber Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False, institution_id=inst.id)
        other = User(email=f"{PFX}_o@test.invalid", password_hash=hash_password(PWD), full_name="Başka Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add_all([coach, other])
        db.flush()
        s8 = User(email=f"{PFX}_s8@test.invalid", password_hash=hash_password(PWD), full_name="LGS Öğrenci",
                  role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                  institution_id=inst.id, grade_level=8)
        s10 = User(email=f"{PFX}_s10@test.invalid", password_hash=hash_password(PWD), full_name="Maarif Öğrenci",
                   role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                   institution_id=inst.id, grade_level=10)
        so = User(email=f"{PFX}_so@test.invalid", password_hash=hash_password(PWD), full_name="Yabancı Öğrenci",
                  role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=other.id,
                  grade_level=8)
        db.add_all([s8, s10, so])
        db.flush()

        def task(st, title, notes, *, typ=TaskType.OTHER, done=False, d=today, items=None):
            t = Task(student_id=st.id, date=d, type=typ, title=title, notes=notes, is_draft=False,
                     status=TaskStatus.COMPLETED if done else TaskStatus.PENDING, book_items=items or [])
            db.add(t)
            db.flush()
            return t.id

        ids = {
            "ebob_done": task(s8, "Matematik · ebob ekok", "fenomen 2 test", done=True, d=today - timedelta(days=1)),
            "anlam": task(s8, "Türkçe · sözcükte anlam", "AÇI 3 TEST"),
            "no_count": task(s8, "Türkçe · paragraf", "kitaptan oku"),
            "video": task(s8, "Fen Bilimleri · dna", "2 test", typ=TaskType.VIDEO),
            "enerji": task(s10, "Biyoloji · ENERJİ", "AÇI 2 TEST", done=True),
            "foreign": task(so, "Matematik · ebob ekok", "2 test"),
        }
        db.commit()
        return {"inst": inst.id, "coach": coach.id, "other": other.id, "s8": s8.id, "s10": s10.id,
                "so": so.id, **ids}


def cleanup(d):
    with SessionLocal() as db:
        u = [d["s8"], d["s10"], d["so"], d["coach"], d["other"]]
        tids = [t.id for t in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.execute(sa_delete(Institution).where(Institution.id == d["inst"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def main() -> int:
    get_login_limiter().reset()
    d = seed()
    print(f"\n=== konusuz test görevleri → konu — {PFX} ===\n")
    try:
        check("1 test sayısı: 'AÇI 2 TEST' / '3 adet test' / '2 yaprak test' / 'test yok'",
              ttl.extract_test_count("AÇI 2 TEST") == 2 and ttl.extract_test_count("3 adet test") == 3
              and ttl.extract_test_count("2 yaprak test") == 2 and ttl.extract_test_count("kitaptan oku") is None)
        check("1b birim: '30 soru' → soru · '4 sayfa' → sayfa · '2 test (30 soru)' → test · '40 soruluk deneme' → yok",
              ttl.extract_count("30 soru") == (30, "soru") and ttl.extract_count("4 sayfa") == (4, "sayfa")
              and ttl.extract_count("2 test (30 soru)") == (2, "test")
              and ttl.extract_count("40 soruluk deneme") is None
              and ttl.extract_count("Paragraf 12 sf") == (12, "sayfa"))

        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text

        with SessionLocal() as db:
            mat8 = ttl.resolve_subject(db, db.get(User, d["s8"]), "Matematik")
            bio10 = ttl.resolve_subject(db, db.get(User, d["s10"]), "Biyoloji")
        r = c.post(f"/api/v2/teacher/students/{d['s8']}/task-topic-suggest",
                   json={"subject_id": mat8.id, "text": "ebob ekok", "notes": "fenomen 2 test"})
        js = r.json()
        check("2 öneri: 'ebob ekok' → Çarpanlar ve Katlar (kesin) + 2 test",
              r.status_code == 200 and js["confident"] and js["topic"]["name"] == "Çarpanlar ve Katlar"
              and js["test_count"] == 2, str(js)[:300])
        r = c.post(f"/api/v2/teacher/students/{d['s10']}/task-topic-suggest",
                   json={"subject_id": bio10.id, "text": "ENERJİ", "notes": "AÇI 2 TEST"})
        js = r.json()
        names = [o["name"] for o in js["options"]]
        check("3 tema yazılmış ('Enerji') → kesin öneri yok, alt konular seçenek (Fotosentez dahil)",
              js["topic"] is None and "Fotosentez" in names, str(js)[:300])
        r = c.post(f"/api/v2/teacher/students/{d['so']}/task-topic-suggest",
                   json={"subject_id": mat8.id, "text": "ebob", "notes": ""})
        check("4 başka koçun öğrencisi → 404", r.status_code == 404, str(r.status_code))

        r = c.get(f"/api/v2/teacher/students/{d['s10']}/subject-topics", params={"subject_id": bio10.id})
        tps = r.json()["topics"]
        with SessionLocal() as db:
            parent_ids = {t.parent_id for t in db.query(Topic).filter(Topic.subject_id == bio10.id) if t.parent_id}
        check("5 dersin konu listesi yalnız alt konular", r.status_code == 200 and tps
              and not any(t["topic_id"] in parent_ids for t in tps), str(len(tps)))

        r = c.get("/api/v2/teacher/unlinked-test-tasks")
        lst = r.json()
        got = {i["task_id"] for i in lst["items"]}
        check("6 liste: 3 konusuz test görevi (sayısız/video/yabancı yok)",
              got == {d["ebob_done"], d["anlam"], d["enerji"]} and lst["completed"] == 2, str(lst)[:300])

        b = c.get("/api/v2/teacher/badges").json()
        check("7 koç rozeti: unlinked_test_tasks = 3", b.get("unlinked_test_tasks") == 3, str(b))

        with SessionLocal() as db:
            cs = {x.cohort_key: x for x in cohort_by_grade(db, institution_id=d["inst"])}
            c8 = cs.get("8")
        check("8 kohort öncesi: 8. sınıf planlanan test 0, görev 1/4 (video da görev), konusuz 2",
              c8 and c8.weekly_planned == 0 and (c8.gorev_done, c8.gorev_total) == (1, 4)
              and c8.unlinked_test_tasks == 2, str(c8))

        with SessionLocal() as db:
            ebob = db.query(Topic).filter(Topic.subject_id == mat8.id, Topic.name == "Çarpanlar ve Katlar",
                                          Topic.grade_level == 8).first()
            fot = db.query(Topic).filter(Topic.subject_id == bio10.id, Topic.name == "Fotosentez").first()
            theme = db.get(Topic, fot.parent_id)
        r = c.post("/api/v2/teacher/unlinked-test-tasks/convert", json={"items": [
            {"task_id": d["ebob_done"], "topic_id": ebob.id, "planned_count": 2},
            {"task_id": d["enerji"], "topic_id": theme.id, "planned_count": 2},
            {"task_id": d["foreign"], "topic_id": ebob.id, "planned_count": 2},
        ]})
        res = {x["task_id"]: x for x in r.json()["data"]["results"]}
        check("9 dönüştürme: 1 başarılı, temaya bağlama 'topic_is_theme', yabancı görev 'task_not_found'",
              r.status_code == 200 and res[d["ebob_done"]]["ok"]
              and res[d["enerji"]]["code"] == "topic_is_theme" and res[d["foreign"]]["code"] == "task_not_found",
              str(r.json())[:400])

        with SessionLocal() as db:
            t = db.get(Task, d["ebob_done"])
            it = t.book_items[0] if t.book_items else None
            foreign_clean = not db.get(Task, d["foreign"]).book_items
            enerji_clean = not db.get(Task, d["enerji"]).book_items
        check("10 tamamlanmış görev → TEST, kalem konu bağlı 2/2, başlık+not korunur",
              t.type == TaskType.TEST and it and it.topic_id == ebob.id and it.planned_count == 2
              and it.completed_count == 2 and t.title == "Matematik · ebob ekok" and t.notes == "fenomen 2 test"
              and t.status == TaskStatus.COMPLETED)
        check("11 yabancı ve tema reddi hiçbir şey yazmadı",
              foreign_clean and enerji_clean)

        r = c.post("/api/v2/teacher/unlinked-test-tasks/convert", json={"items": [
            {"task_id": d["ebob_done"], "topic_id": ebob.id, "planned_count": 2}]})
        check("12 aynı görevi ikinci kez bağlama → already_linked",
              r.json()["data"]["results"][0]["code"] == "already_linked", r.text[:200])

        r = c.post("/api/v2/teacher/unlinked-test-tasks/convert", json={"items": [
            {"task_id": d["enerji"], "topic_id": fot.id, "planned_count": 2}]})
        with SessionLocal() as db:
            et_done = db.get(Task, d["enerji"]).book_items[0].completed_count
        check("13 tema yerine alt konu (Fotosentez) → bağlandı, 2/2 çözülmüş",
              r.json()["data"]["converted"] == 1 and et_done == 2, r.text[:200])

        with SessionLocal() as db:
            cs = {x.cohort_key: x for x in cohort_by_grade(db, institution_id=d["inst"])}
            c8, c10 = cs.get("8"), cs.get("10")
        check("14 kohort sonrası: 8. sınıf 2/2 test, %100; 10. sınıf 2/2; konusuz 8'de 1",
              c8.weekly_planned == 2 and c8.weekly_completed == 2 and c8.weekly_rate_pct == 100
              and c10.weekly_planned == 2 and c8.unlinked_test_tasks == 1, f"{c8} | {c10}")

        with SessionLocal() as db:
            st = db.get(User, d["s8"])
            cp = compute_curriculum_progress(db, st, d["coach"])
            status = next((tp.status for sp in cp.subjects for tp in sp.topics if tp.topic_id == ebob.id), None)
        check("15 müfredat: Çarpanlar ve Katlar artık başlanmış (devam/tamamlandı)",
              status in ("devam", "tamamlandi"), str(status))

        b = c.get("/api/v2/teacher/badges").json()
        check("16 rozet 3 → 1", b.get("unlinked_test_tasks") == 1, str(b))

        errs = []
        with SessionLocal() as db:
            for fn in (cohort_by_grade, cohort_by_track, cohort_by_curriculum, cohort_by_exam_target):
                try:
                    fn(db, institution_id=d["inst"])
                except Exception as e:  # noqa: BLE001
                    errs.append(f"{fn.__name__}: {e}")
        check("16b kohort 4 sekmenin hepsi hatasız (sınıf/alan/müfredat/hedef sınav)", not errs, str(errs))

        # ---- 2026-10-16 ek: sezgisel arama + ders listesi + kaynaksız görevin dersi
        r = c.get(f"/api/v2/teacher/students/{d['s8']}/task-picker", params={"q": "milli desten"})
        names = [i["topic_name"] for g in r.json()["groups"] for i in g["items"]]
        check("18 arama: 'milli desten' (yazım hatası + araya giren sözcük) → Millî Bir Destan ilk sırada",
              r.status_code == 200 and names and names[0].startswith("Millî Bir Destan"), str(names[:3]))
        r = c.get(f"/api/v2/teacher/students/{d['s10']}/task-picker", params={"q": "sözün ezgisi"})
        its = [i for g in r.json()["groups"] for i in g["items"]]
        check("19 arama: tema adı ('sözün ezgisi') → alt konuları + tema adı yanıtta",
              its and all(i.get("theme_name") and "Sözün Ezgisi" in i["theme_name"] for i in its[:3]), str(its[:2])[:300])
        r = c.get(f"/api/v2/teacher/students/{d['s10']}/task-picker", params={"q": "fotosnetez"})
        names = [i["topic_name"] for g in r.json()["groups"] for i in g["items"]]
        check("20 arama: harf yer değiştirmesi ('fotosnetez') → Fotosentez", "Fotosentez" in names[:2], str(names[:3]))
        r = c.get(f"/api/v2/teacher/students/{d['s10']}/all-subjects")
        snames = [x["name"] for x in r.json()["items"]]
        check("21 10. sınıf (Maarif, kitapsız) ders listesinde TYT dersi YOK, okul dersleri var",
              r.status_code == 200 and "Matematik" in snames and not any(n.startswith("TYT") for n in snames),
              str(snames))
        r = c.get(f"/api/v2/teacher/students/{d['s8']}/week", params={"start": (date.today() - timedelta(days=1)).isoformat()})
        wk = r.json()
        item = next((it for day in wk.get("days", []) for t in day.get("tasks", []) if t["id"] == d["ebob_done"]
                     for it in t["items"]), None)
        check("22 kaynaksız görev kalemi: ders = Matematik, konu = Çarpanlar ve Katlar (Diğer değil)",
              item and item.get("subject_name") == "Matematik" and item.get("topic_name") == "Çarpanlar ve Katlar",
              str(item)[:300])

        r = c.post(f"/api/v2/teacher/students/{d['s8']}/tasks", json={
            "date": date.today().isoformat(), "type": "test", "title": "Türkçe · cümlede anlam",
            "notes": "AÇI 2 TEST", "items": [{"book_id": None, "section_id": None,
                                               "topic_id": ebob.id, "planned_count": 2}]})
        check("17 formdan 'konuya bağlı test' oluşturma (kaynaksız konu kalemi) → 200", r.status_code == 200,
              r.text[:200])
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
