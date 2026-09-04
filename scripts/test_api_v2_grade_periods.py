"""Sınıf dönemi damgası — smoke (P2, 2026-09-04).

SAHA VAKASI: Yiğit Eren 8'den 9'a geçti; geçen yılın 607 görevi + 3 LGS
denemesi "bu yıl" ile karışıyordu. Dönem sınırı bunu ayırır — veri YERİNDE
kalır, yalnız hangi döneme ait olduğu kaydedilir.

Senaryolar:
  A. SINIR FORMÜLÜ (servis düzeyi, tarih kontrollü)
     1. Geç yükseltme (10 Ekim)  → sınır 1 Eylül'e ÇEKİLİR
     2. Erken yükseltme (15 Tem) → sınır 15 Temmuz KALIR (yaz kampı)
     3. Aynı dönemde ikinci yükseltme → sıfır uzunlukta dönem oluşmaz
     4. Kapanan dönem ESKİ sınıfı taşır, yeni dönem yeni sınıfı
  B. DAMGA AYRIMI (HTTP)
     5. Sınıf Yükseltme (promote) → YENİ dönem açar
     6. Profil Düzenle'den sınıf değişimi → yeni dönem AÇMAZ, düzeltir
  C. YİĞİT SENARYOSU
     7. Sınır öncesi tüm görev/denemeler ÖNCEKİ döneme, güncel dönem boş
  D. KOÇ DÜZELTMELERİ
     8. Başlangıç değiştir → komşu dönemin bitişi birlikte kayar
     9. Geçersiz tarih (önceki dönemden önce) → 422
     10. Dönem sil → aralık komşuya geçer, GÖREVLER SİLİNMEZ
     11. Tek dönem silinemez → 422
  E. KAPILAR
     12. Yabancı öğrenci 404 · yabancı dönem 404
     13. period_for_date doğru dönemi bulur
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    ExamResult,
    ExamSection,
    StudentGradePeriod,
    SuspiciousIp,
    Task,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services import grade_period_service as gp
from app.services.security import hash_password

PFX = f"gp_{secrets.token_hex(3)}"
PWD = "TestPass123!@xyz"
passed = 0
failed: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="GP Koç", role=UserRole.TEACHER, is_active=True)
        other = User(email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PWD),
                     full_name="GP Koç2", role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other])
        db.flush()
        # Yiğit benzeri: 8. sınıf, geçen öğretim yılında açılmış hesap
        yigit = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                     full_name="Dönem Öğrenci", role=UserRole.STUDENT, is_active=True,
                     teacher_id=coach.id, grade_level=8)
        srv = User(email=f"{PFX}_srv@test.invalid", password_hash=hash_password(PWD),
                   full_name="Servis Öğrenci", role=UserRole.STUDENT, is_active=True,
                   teacher_id=coach.id, grade_level=8)
        foreign = User(email=f"{PFX}_f@test.invalid", password_hash=hash_password(PWD),
                       full_name="Yabancı Öğrenci", role=UserRole.STUDENT,
                       is_active=True, teacher_id=other.id, grade_level=9)
        # GERÇEK DESEN: hesaplar geçen öğretim yılında açıldı (Yiğit 2026-04-23).
        # Bugün açılmış hesabın 1 Eylül'de başlayan geçmiş dönemi OLAMAZ —
        # seed bunu yansıtmazsa sınır testi yanlış negatif verir.
        opened = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
        for u in (yigit, srv, foreign):
            u.created_at = opened
        db.add_all([yigit, srv, foreign])
        db.flush()

        # Geçen öğretim yılına ait veri (Nisan-Mayıs) — Yiğit'in gerçek deseni
        for i in range(6):
            db.add(Task(student_id=yigit.id, date=date(2026, 5, 4 + i),
                        type=TaskType.TEST, title=f"Geçen yıl görev {i}",
                        status=TaskStatus.COMPLETED, is_draft=False))
        db.add(ExamResult(student_id=yigit.id, title="LGS Deneme",
                          exam_date=date(2026, 5, 9), section=ExamSection.LGS,
                          total_correct=60, total_wrong=15, total_blank=15, net=55.0))
        # SAHA BOSLUGU (prod 2026-09-04): kocun GECMISE DONUK girdigi deneme
        # hesabin acilisindan (20 Nisan) ONCE tarihli. Ilk donem hesap
        # tarihinde baslarsa bu kayit hicbir doneme dusmez ve KAYBOLUR.
        db.add(ExamResult(student_id=yigit.id, title="Eski LGS Deneme",
                          exam_date=date(2026, 2, 4), section=ExamSection.LGS,
                          total_correct=50, total_wrong=20, total_blank=20, net=45.0))
        # DEV SQLite hijyeni: FK CASCADE kapali oldugundan silinmis
        # ogrencilerin donem satirlari yetim kalir ve id yeniden kullanilinca
        # yeni ogrenciye miras gecer (prod PG'de CASCADE var, sorun degil).
        db.execute(sa_delete(StudentGradePeriod).where(
            StudentGradePeriod.student_id.in_([yigit.id, srv.id, foreign.id])))
        db.commit()
        return {"coach_id": coach.id, "other_id": other.id,
                "yigit": yigit.id, "srv": srv.id, "foreign": foreign.id}


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        ids = [s["coach_id"], s["other_id"], s["yigit"], s["srv"], s["foreign"]]
        db.execute(sa_delete(StudentGradePeriod).where(
            StudentGradePeriod.student_id.in_(ids)))
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(ids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(ids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


def periods(student_id: int) -> list[StudentGradePeriod]:
    with SessionLocal() as db:
        rows = gp.list_periods(db, student_id)
        for r in rows:
            db.expunge(r)
        return rows


def main() -> int:
    s = seed()
    print(f"\n=== Sınıf dönemi damgası (öğrenci #{s['yigit']}) ===\n")
    try:
        # ---------------------------------------------------------------- A
        with SessionLocal() as db:
            st = db.get(User, s["srv"])
            prev = gp.snapshot_of(st)
            st.grade_level = 9
            db.flush()
            gp.stamp_advance(db, st, previous_snapshot=prev,
                             advance_date=date(2026, 10, 10))
            db.commit()
        rows = sorted(periods(s["srv"]), key=lambda p: p.started_on)
        check("1. geç yükseltme (10 Ekim) → sınır 1 Eylül'e çekildi",
              len(rows) == 2 and rows[1].started_on == date(2026, 9, 1)
              and rows[0].ended_on == date(2026, 8, 31),
              f"{[(p.grade_level, p.started_on, p.ended_on) for p in rows]}")
        check("2. kapanan dönem ESKİ sınıfı, yeni dönem YENİ sınıfı taşıyor",
              len(rows) == 2 and rows[0].grade_level == 8 and rows[1].grade_level == 9,
              f"{[p.grade_level for p in rows]}")

        # aynı dönemde ikinci yükseltme → sıfır uzunlukta dönem yok
        with SessionLocal() as db:
            st = db.get(User, s["srv"])
            prev = gp.snapshot_of(st)
            st.grade_level = 10
            db.flush()
            gp.stamp_advance(db, st, previous_snapshot=prev,
                             advance_date=date(2026, 10, 20))
            db.commit()
        rows = sorted(periods(s["srv"]), key=lambda p: p.started_on)
        check("3. aynı dönemde ikinci yükseltme → sıfır uzunlukta dönem oluşmaz",
              len(rows) == 3 and rows[2].started_on == date(2026, 9, 2)
              and rows[1].ended_on == date(2026, 9, 1),
              f"{[(p.grade_level, p.started_on, p.ended_on) for p in rows]}")

        # erken yükseltme (yaz kampı) — temiz öğrenci üzerinde
        with SessionLocal() as db:
            st = db.get(User, s["foreign"])
            prev = gp.snapshot_of(st)
            st.grade_level = 10
            db.flush()
            gp.stamp_advance(db, st, previous_snapshot=prev,
                             advance_date=date(2026, 7, 15))
            db.commit()
        rows_f = sorted(periods(s["foreign"]), key=lambda p: p.started_on)
        check("4. erken yükseltme (15 Tem yaz kampı) → sınır 15 Temmuz KALIR",
              len(rows_f) == 2 and rows_f[1].started_on == date(2026, 7, 15),
              f"{[(p.grade_level, p.started_on) for p in rows_f]}")

        # ---------------------------------------------------------------- B
        c = TestClient(app)
        from app.services.rate_limit import get_login_limiter
        get_login_limiter().reset()
        r = c.post("/api/v2/auth/login",
                   json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text

        sid = s["yigit"]
        # GET → lazy backfill (dönemi olmayan öğrenci)
        r = c.get(f"/api/v2/teacher/students/{sid}/grade-periods")
        body = r.json() if r.text else {}
        check("5. GET dönem listesi → lazy backfill 2 dönem üretti",
              r.status_code == 200 and len(body.get("periods", [])) == 2,
              f"status={r.status_code} {str(body)[:200]}")

        # C — Yiğit senaryosu: sınır öncesi tüm veri ÖNCEKİ döneme
        pl = sorted(body.get("periods", []), key=lambda p: p["started_on"])
        check("6. sınır öncesi görev+denemeler (GEÇMİŞE DÖNÜK dahil) ÖNCEKİ döneme",
              len(pl) == 2
              and pl[0]["task_count"] == 6 and pl[0]["exam_count"] == 2
              and pl[1]["task_count"] == 0 and pl[1]["exam_count"] == 0,
              f"{[(p['grade_label'], p['task_count'], p['exam_count']) for p in pl]}")

        before = len(periods(sid))
        # 7. Profil düzenleme → yeni dönem AÇMAZ
        r = c.patch(f"/api/v2/teacher/students/{sid}",
                    json={"grade_level": 9})
        after_rows = periods(sid)
        cur = [p for p in after_rows if p.ended_on is None]
        check("7. profil düzenlemeden sınıf değişimi → YENİ DÖNEM AÇMAZ, düzeltir",
              r.status_code == 200 and len(after_rows) == before
              and len(cur) == 1 and cur[0].grade_level == 9,
              f"status={r.status_code} önce={before} sonra={len(after_rows)} "
              f"guncel={[p.grade_level for p in cur]}")

        # 8. Sınıf Yükseltme (promote) → YENİ dönem
        r = c.post(f"/api/v2/teacher/students/{sid}/promote",
                   json={"grade": "10"})
        after2 = periods(sid)
        check("8. Sınıf Yükseltme (promote) → YENİ dönem açar",
              r.status_code == 200 and len(after2) == before + 1,
              f"status={r.status_code} {r.text[:160]} sayı={len(after2)}")

        # ---------------------------------------------------------------- D
        rows_y = sorted(periods(sid), key=lambda p: p.started_on)
        # Hareket alanı olan dönemi hedefle: ard arda aynı gün açılmış iki dönem
        # arasında tarih kaydırmak zaten (doğru şekilde) reddedilir.
        idx = 1 if len(rows_y) >= 3 else len(rows_y) - 1
        target = rows_y[idx]
        new_start = target.started_on - timedelta(days=10)
        r = c.post(f"/api/v2/teacher/students/{sid}/grade-periods/{target.id}",
                   json={"started_on": new_start.isoformat()})
        rows_y2 = sorted(periods(sid), key=lambda p: p.started_on)
        check("9. başlangıç düzeltildi + komşu dönemin bitişi birlikte kaydı",
              r.status_code == 200
              and rows_y2[idx].started_on == new_start
              and rows_y2[idx - 1].ended_on == new_start - timedelta(days=1),
              f"status={r.status_code} {[(p.started_on, p.ended_on) for p in rows_y2]}")

        r = c.post(f"/api/v2/teacher/students/{sid}/grade-periods/{target.id}",
                   json={"started_on": "2020-01-01"})
        check("10. önceki dönemden önceye çekme → 422 start_before_previous",
              r.status_code == 422
              and r.json().get("detail", {}).get("code") == "start_before_previous",
              f"status={r.status_code} {r.text[:160]}")

        # 11. dönem sil → görevler SİLİNMEZ
        with SessionLocal() as db:
            tasks_before = db.query(Task).filter(Task.student_id == sid).count()
        r = c.post(f"/api/v2/teacher/students/{sid}/grade-periods/{target.id}/delete")
        with SessionLocal() as db:
            tasks_after = db.query(Task).filter(Task.student_id == sid).count()
        rows_y3 = periods(sid)
        check("11. dönem silindi → görevler SİLİNMEDİ, aralık komşuya geçti",
              r.status_code == 200 and tasks_before == tasks_after == 6
              and len(rows_y3) == len(rows_y2) - 1
              and any(p.ended_on is None for p in rows_y3),
              f"status={r.status_code} görev {tasks_before}→{tasks_after} "
              f"dönem {len(rows_y2)}→{len(rows_y3)}")

        # 12. tek döneme inene kadar sil, sonuncusu silinemesin
        for p in sorted(periods(sid), key=lambda x: x.started_on)[1:]:
            c.post(f"/api/v2/teacher/students/{sid}/grade-periods/{p.id}/delete")
        last = periods(sid)
        r = c.post(f"/api/v2/teacher/students/{sid}/grade-periods/{last[0].id}/delete")
        check("12. tek dönem silinemez → 422 last_period",
              len(last) == 1 and r.status_code == 422
              and r.json().get("detail", {}).get("code") == "last_period",
              f"kalan={len(last)} status={r.status_code} {r.text[:120]}")

        # ---------------------------------------------------------------- E
        r1 = c.get(f"/api/v2/teacher/students/{s['foreign']}/grade-periods")
        foreign_p = periods(s["foreign"])[0]
        r2 = c.post(
            f"/api/v2/teacher/students/{sid}/grade-periods/{foreign_p.id}",
            json={"started_on": date.today().isoformat()})
        check("13. yabancı öğrenci 404 + başka öğrencinin dönemi 404",
              r1.status_code == 404 and r2.status_code == 404,
              f"{r1.status_code}/{r2.status_code}")

        # 15. ilk dönem, hesap açılışından ÖNCEKİ kaydı kapsıyor mu
        first = sorted(periods(sid), key=lambda p: p.started_on)[0]
        check("15. ilk dönem, hesap açılışından ÖNCEKİ kaydı kapsıyor",
              first.started_on <= date(2026, 2, 4),
              f"ilk dönem başlangıcı={first.started_on} (deneme 2026-02-04)")

        # 14. period_for_date
        with SessionLocal() as db:
            p_old = gp.period_for_date(db, s["srv"], date(2026, 5, 20))
            p_new = gp.period_for_date(db, s["srv"], date(2026, 9, 15))
            check("14. period_for_date → tarih doğru döneme düşüyor",
                  p_old is not None and p_new is not None
                  and p_old.grade_level == 8 and p_new.grade_level == 10,
                  f"{getattr(p_old,'grade_level',None)} / {getattr(p_new,'grade_level',None)}")
    finally:
        cleanup(s)

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===\n")
    if failed:
        for f in failed:
            print("  -", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
