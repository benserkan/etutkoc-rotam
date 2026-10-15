"""Haftalık görev havuzu — rehber uçları smoke (Adım 2, 2026-10-12).

  1. Gün-gün öğrencide havuz paketi: mod gun_gun, dönem yok, dersler listelenir
  2. Moda geç → havuz · dönem aç · ikinci açılış 409
  3. K25: 12. sınıf alan boş → AYT dersleri kilitli listede, AYT kalemi 422 track_required
  4. Kalem ekleme: kitap+bölüm · yalnız konu · etkinlik · serbest metin; miktar yok → 422
  5. Paket: kalemler ders adıyla, kalan, kaynak türü; K24 eksik ders şeridi; hacim ipucu
  6. Konu listesi (K27): SON işareti + kalan + kaynaklar + şube konumu
  7. Serbest metin ayrıştırma (K28): taslak çıkar / belirsizde uyarı, yazmaz
  8. Sil (iz) · beklenen gün değiştir · dönem kapat · kapalıyken kalem 404 no_open_period
  9. Şube: konu konumu + ders programı; şubesiz öğrencide 422
 10. Başka koçun öğrencisi → 404
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
    Book, BookSection, BookType, ClassGroup, PoolItem, SectionProgress, StudentBook, StudyPeriod,
    Subject, Task, TaskBookItem, Topic, Track, User, UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"pe_{secrets.token_hex(3)}"
PWD = "Havuz!234567xy"
today = date.today()
passed = 0
failed: list[str] = []
ids: dict = {"users": [], "subjects": [], "books": []}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Havuz Rehber", role=UserRole.TEACHER, is_active=True)
        other = User(email=f"{PFX}_o@test.invalid", password_hash=hash_password(PWD),
                     full_name="Başka Koç", role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other])
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Havuz Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12, class_group="12-A")
        st2 = User(email=f"{PFX}_s2@test.invalid", password_hash=hash_password(PWD),
                   full_name="Şubesiz", role=UserRole.STUDENT, is_active=True,
                   teacher_id=coach.id, grade_level=12, program_mode="havuz")
        db.add_all([st, st2])
        db.flush()
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        # Alan filtresi kanonik ada bakar ("AYT Fizik" ∈ TRACK_AYT_SUBJECTS[SAYISAL]) → ad önek almaz
        ayt = Subject(name="AYT Fizik", teacher_id=coach.id, exam_section=ExamSection.AYT_SAY)
        db.add_all([tyt, ayt])
        db.flush()
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        t2 = Topic(subject_id=tyt.id, name="Köklü Sayılar", order=2, teacher_id=coach.id)
        db.add_all([t1, t2])
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal TYT Mat",
                 type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        s1 = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=8, order=1, topic_id=t1.id)
        s2 = BookSection(book_id=b.id, label="Köklü Sayılar", test_count=6, order=2, topic_id=t2.id)
        db.add_all([s1, s2])
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=b.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=s1.id, reserved_count=0, completed_count=2))
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=s2.id, reserved_count=0, completed_count=0))
        db.commit()
        ids["users"] += [coach.id, other.id, st.id, st2.id]
        ids["subjects"] += [tyt.id, ayt.id]
        ids["books"].append(b.id)
        return {"coach": coach.id, "st": st.id, "st2": st2.id, "tyt": tyt.id, "ayt": ayt.id,
                "t1": t1.id, "t2": t2.id, "book": b.id, "s1": s1.id, "s2": s2.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
        db.execute(sa_delete(Topic).where(Topic.subject_id.in_(ids["subjects"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(ClassGroup).where(ClassGroup.scope_key == f"coach:{ids['users'][0]}"))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def main() -> int:
    get_login_limiter().reset()
    d = seed()
    print(f"\n=== havuz rehber uçları smoke — {PFX} ===\n")
    try:
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        base = f"/api/v2/teacher/students/{d['st']}"

        # 1
        r = c.get(f"{base}/pool")
        check("1a gün-gün öğrencide paket 200 · mod gun_gun · dönem yok",
              r.status_code == 200 and r.json()["student"]["program_mode"] == "gun_gun"
              and r.json()["period"] is None, r.text[:200])
        names = [s["name"] for s in r.json()["subjects"]]
        check("1b TYT dersi listede, AYT alan boş → kilitli listede",
              any("TYT Matematik" in n for n in names) and r.json()["ayt_locked"]
              and any("AYT Fizik" in n for n in r.json()["locked_ayt_names"]), str(names))

        # 2
        r = c.post(f"{base}/program-mode", json={"mode": "havuz"})
        check("2a moda geçiş 200 + öğrenci öneki bayatlatıldı",
              r.status_code == 200 and r.json()["data"]["student"]["program_mode"] == "havuz"
              and f"teacher:{d['coach']}:students:{d['st']}" in r.json()["invalidate"], r.text[:200])
        r = c.post(f"{base}/pool/periods", json={"opened_on": today.isoformat(),
                                                  "expected_next_on": (today + timedelta(days=7)).isoformat()})
        check("2b dönem açıldı", r.status_code == 200 and r.json()["data"]["period"]["status"] == "acik", r.text[:200])
        pid = r.json()["data"]["period"]["id"]
        r = c.post(f"{base}/pool/periods", json={"opened_on": today.isoformat()})
        check("2c ikinci açık dönem 409", r.status_code == 409 and r.json()["detail"]["code"] == "already_open")
        r = c.post(f"{base}/program-mode", json={"mode": "gun_gun"})
        check("2d açık dönemde mod değişmez 409", r.status_code == 409)

        # 3
        r = c.post(f"{base}/pool/items", json={"subject_id": d["ayt"], "quantity": 2, "unit": "test",
                                               "label": "Optik"})
        check("3a K25 alan boş → AYT kalemi 422 track_required",
              r.status_code == 422 and r.json()["detail"]["code"] == "track_required", r.text[:200])
        with SessionLocal() as db:
            db.get(User, d["st"]).track = Track.SAYISAL
            db.commit()
        r = c.get(f"{base}/pool")
        check("3b alan dolu → AYT dersi açıldı", not r.json()["ayt_locked"]
              and any("AYT Fizik" in s["name"] for s in r.json()["subjects"]))

        # 4
        r = c.post(f"{base}/pool/items", json={"subject_id": d["tyt"], "unit": "test", "topic_id": d["t1"]})
        check("4a miktarsız test kalemi 422 quantity_required",
              r.status_code == 422 and r.json()["detail"]["code"] == "quantity_required")
        r = c.post(f"{base}/pool/items", json={"subject_id": d["tyt"], "quantity": 4, "unit": "test",
                                               "book_id": d["book"], "section_id": d["s1"]})
        check("4b kitap+bölüm kalemi", r.status_code == 200, r.text[:200])
        it_book = next(i for i in r.json()["data"]["period"]["items"] if i["book_id"] == d["book"])
        check("4c kalem konuyu bölümden aldı, kalan 4, kaynak rehber",
              it_book["topic_id"] == d["t1"] and it_book["remaining"] == 4 and it_book["source"] == "rehber")
        r = c.post(f"{base}/pool/items", json={"subject_id": d["tyt"], "quantity": 3, "unit": "test",
                                               "topic_id": d["t2"], "teacher_homework": True})
        check("4d yalnız konulu kalem + öğretmen ödevi işareti", r.status_code == 200
              and any(i["teacher_homework"] for i in r.json()["data"]["period"]["items"]))
        r = c.post(f"{base}/pool/items", json={"subject_id": d["ayt"], "unit": "etkinlik", "label": "Optik videosu",
                                               "day_hint": (today + timedelta(days=2)).isoformat()})
        check("4e etkinlik kalemi miktarsız → 1, gün etiketi", r.status_code == 200
              and any(i["unit"] == "etkinlik" and i["quantity"] == 1 and i["day_hint"]
                      for i in r.json()["data"]["period"]["items"]), r.text[:200])
        r = c.post(f"{base}/pool/items", json={"subject_id": d["tyt"], "quantity": 2, "unit": "test"})
        # 2026-10-14: test birimli kalemde önce konu zorunluluğu söylenir
        check("4f konu/kaynak/metin yok → 422 topic_required (test birimi konu ister)",
              r.status_code == 422 and r.json()["detail"]["code"] == "topic_required")
        with SessionLocal() as db:
            sp = db.query(SectionProgress).filter_by(book_section_id=d["s1"]).one()
            check("4g kalem eklenince rezerv açılmadı", sp.reserved_count == 0)

        # 5
        r = c.get(f"{base}/pool")
        j = r.json()
        check("5a özet: 4+3+1 = 8 birim, %0, 7 gün, günde 1.1",
              j["period"]["summary"]["total_units"] == 8 and j["period"]["summary"]["days_left"] == 7
              and j["period"]["summary"]["per_day_needed"] == 1.1, str(j["period"]["summary"]))
        tyt_name = next(s["name"] for s in j["subjects"] if s["id"] == d["tyt"])
        check("5b K24 kontrol şeridi: TYT ve AYT kalemli → eksikte değil",
              tyt_name not in j["missing_subjects"], str(j["missing_subjects"]))
        check("5c kalem ders/kitap/bölüm adlarıyla gelir",
              it_book["subject_name"] == tyt_name and it_book["book_name"].endswith("Orijinal TYT Mat")
              and it_book["section_label"] == "Üslü Sayılar")
        check("5d hacim ipucu: geçmiş dönem yok → ortalama None, mevcut 8",
              j["volume"]["avg_done_last3"] is None and j["volume"]["current_total"] == 8)

        # 6
        r = c.get(f"{base}/pool/topics", params={"subject_id": d["tyt"]})
        check("6a konu listesi 200", r.status_code == 200, r.text[:200])
        tops = {t["topic_id"]: t for t in r.json()["topics"]}
        check("6b Üslü: kalan 6 (8−2 çözülmüş), kaynak var, SON işaretli",
              tops[d["t1"]]["remaining"] == 6 and tops[d["t1"]]["sources"]
              and tops[d["t1"]]["last_assigned_on"] == today.isoformat(), str(tops[d["t1"]]))
        check("6c Köklü: kaynak kalan 6, konulu kalemden SON var", tops[d["t2"]]["remaining"] == 6
              and tops[d["t2"]]["last_assigned_on"] == today.isoformat())
        r = c.get(f"{base}/pool/topics", params={"subject_id": 999999})
        check("6d yabancı ders 404", r.status_code == 404)

        # 7
        r = c.post(f"{base}/pool/parse", json={"text": "Orijinal · Köklü Sayılar · 4 test"})
        pj = r.json()
        check("7a tam metin → taslak (ders, kitap, konu, bölüm, 4 test)",
              pj["draft"] and pj["draft"]["subject_id"] == d["tyt"] and pj["draft"]["book_id"] == d["book"]
              and pj["draft"]["topic_id"] == d["t2"] and pj["draft"]["section_id"] == d["s2"]
              and pj["draft"]["quantity"] == 4 and pj["draft"]["unit"] == "test", str(pj)[:300])
        r = c.post(f"{base}/pool/parse", json={"text": "Üslü 3", "subject_id": d["tyt"]})
        pj = r.json()
        check("7b kısmi konu adı → tahmin + uyarı, birim test varsayılan",
              pj["draft"] and pj["draft"]["topic_id"] == d["t1"] and pj["draft"]["quantity"] == 3
              and pj["warning"] and "tahmin" in pj["warning"].lower(), str(pj)[:300])
        r = c.post(f"{base}/pool/parse", json={"text": "biraz paragraf çöz"})
        pj = r.json()
        check("7c ders anlaşılmazsa taslak yok + uyarı (sessizce yazmaz)",
              pj["draft"] is None and pj["warning"], str(pj)[:200])
        r = c.post(f"{base}/pool/parse", json={"text": "orijinal köklü sayılar 4 test"})
        pj = r.json()
        check("7e AYRAÇSIZ doğal metin → kitap + konu + bölüm + 4 test (2026-10-13 saha)",
              pj["draft"] and pj["draft"]["book_id"] == d["book"] and pj["draft"]["topic_id"] == d["t2"]
              and pj["draft"]["section_id"] == d["s2"] and pj["draft"]["quantity"] == 4, str(pj)[:300])
        r = c.post(f"{base}/pool/parse", json={"text": "orijinal sayılar 3test"})
        pj = r.json()
        check("7f iki konuya uyan kısmi metin → taslak YOK, 'Bunu mu demek istedin?' seçenekleri (Üslü + Köklü) + 3 test",
              pj["draft"] is None and {o["topic_id"] for o in pj["options"]} >= {d["t1"], d["t2"]}
              and pj["base"]["quantity"] == 3 and all(o["book_id"] == d["book"] for o in pj["options"]), str(pj)[:400])
        with SessionLocal() as db:
            check("7d ayrıştırma hiçbir kalem yazmadı",
                  db.query(PoolItem).filter(PoolItem.student_id == d["st"]).count() == 3)

        # 8
        r = c.post(f"{base}/pool/items/{it_book['id']}/delete")
        check("8a kalem silindi (listeden düştü)", r.status_code == 200
              and all(i["id"] != it_book["id"] for i in r.json()["data"]["period"]["items"]))
        with SessionLocal() as db:
            check("8b silinen kalem iz bıraktı", db.get(PoolItem, it_book["id"]).removed_at is not None)
        r = c.post(f"{base}/pool/periods/{pid}/expected",
                   json={"opened_on": today.isoformat(), "expected_next_on": (today + timedelta(days=3)).isoformat()})
        check("8c beklenen gün değişti → kalan gün 3", r.status_code == 200
              and r.json()["data"]["period"]["summary"]["days_left"] == 3, r.text[:200])
        r = c.post(f"{base}/pool/periods/{pid}/close", json={"closed_on": today.isoformat()})
        check("8d dönem kapandı, paket dönem=None, geçmişte 1 dönem",
              r.status_code == 200 and r.json()["data"]["period"] is None
              and len(r.json()["data"]["periods"]) == 1 and r.json()["data"]["periods"][0]["status"] == "kapandi")
        r = c.post(f"{base}/pool/items", json={"subject_id": d["tyt"], "quantity": 1, "unit": "test", "topic_id": d["t1"]})
        check("8e açık dönem yokken kalem 404 no_open_period",
              r.status_code == 404 and r.json()["detail"]["code"] == "no_open_period")
        r = c.post(f"{base}/pool/periods/{pid}/close", json={"closed_on": today.isoformat()})
        check("8f kapalı dönem yeniden kapanmaz 409", r.status_code == 409)

        # 9
        r = c.post(f"{base}/pool/class-group/position", json={"subject_id": d["tyt"], "topic_id": d["t2"]})
        check("9a şube konu konumu yazıldı", r.status_code == 200
              and r.json()["data"]["class_group"]["positions"][str(d["tyt"])]["topic_name"] == "Köklü Sayılar",
              r.text[:300])
        r = c.get(f"{base}/pool/topics", params={"subject_id": d["tyt"]})
        tops = {t["topic_id"]: t for t in r.json()["topics"]}
        check("9b konu listesinde şube konumu işaretli", tops[d["t2"]]["is_class_position"]
              and not tops[d["t1"]]["is_class_position"])
        r = c.post(f"{base}/pool/class-group/lesson-days", json={"lessons": {"0": [d["tyt"]], "3": [d["ayt"]]}})
        check("9c ders programı yazıldı", r.status_code == 200
              and r.json()["data"]["class_group"]["lesson_days"]["3"] == [d["ayt"]], r.text[:200])
        r = c.post(f"/api/v2/teacher/students/{d['st2']}/pool/class-group/position",
                   json={"subject_id": d["tyt"], "topic_id": d["t1"]})
        check("9d şubesiz öğrencide konum 422 no_class_group", r.status_code == 422)

        # 10
        c2 = TestClient(app)
        r = c2.post("/api/v2/auth/login", json={"email": f"{PFX}_o@test.invalid", "password": PWD})
        assert r.status_code == 200
        r = c2.get(f"{base}/pool")
        check("10a başka koçun öğrencisi 404", r.status_code == 404)
        r = c2.post(f"{base}/pool/items", json={"subject_id": d["tyt"], "quantity": 1, "unit": "test", "topic_id": d["t1"]})
        check("10b başka koç kalem ekleyemez 404", r.status_code == 404)
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    if failed:
        print("Başarısız:", failed)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
