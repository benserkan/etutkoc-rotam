"""Rehber (onboarding guide) API smoke — coach_onboarding.

Senaryolar:
  1.  Anonim GET → 401
  2.  Öğrenci rolü → 404 guide_not_found (rehber koça ait, varlık ifşası yok)
  3.  Koç ilk GET → not_started + chapters listesi + checklist tümü False
  4.  start → in_progress + current_chapter=hosgeldin
  5.  chapter_done (hosgeldin) → done listesinde + current=kitap-ekle
  6.  Kitap eklenince (start SONRASI) checklist['kitap-ekle'] True (taze eylem)
  7.  Öğrenci + kitap ataması → checklist['ogrenci-ata'] True
  8.  Program + yayınlanmış görev → program-kur & yayinla-duyur & hafta-takip True
  9.  Deneme girilince → deneme-gir True
  10. Tüm bölümler chapter_done → status=completed
  11. dismiss → dismissed; start → yeniden in_progress (kaldığı bölüm korunur)
  12. reset → chapters_done boş + current=hosgeldin + TABAN SIFIRLANIR
      (eski kitap artık taze değil → checklist False + preexisting True)
  13. Geçersiz action → 422 / chapter'sız chapter_done → 422
  14. İzolasyon: başka koçun durumu not_started kalır
  15. ÖNCEDEN VAR: coach_b'nin rehber ÖNCESİ kitabı → checklist False +
      preexisting True (yanlış 'harika' YOK)
  16. coach_b start SONRASI yeni kitap → checklist True (taze eylem tanınır)
  17. watch: adım izleme SUNUCUDA kalıcı (yeni oturum/GET aynı listeyi döner;
      mükerrer adım tekrarlanmaz; invalidate boş — churn yok)
  18. watch chapter/step'siz → 422
  19. ÖĞRENCİ REHBERİ: öğrenci student_onboarding'i açar (ogr-* bölümleri),
      koç student_onboarding'e 404 (rol izolasyonu iki yönlü)
  20. öğrenci chapter_done akışı ogr sırasında ilerler + watch kalıcı
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import secrets
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    ExamResult,
    StudentBook,
    Subject,
    Task,
    User,
    UserGuideState,
    UserRole,
    WeeklyProgram,
)
from app.models.book import BookType
from app.models.exam_result import ExamSection
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"gd_{secrets.token_hex(3)}"
PWD = "GuideTest!23"
PWD_HASH = hash_password(PWD)
now = datetime.now(timezone.utc)

passed = 0
failed: list[str] = []
ctx: dict = {}

GK = "coach_onboarding"
BASE = f"/api/v2/me/guide/{GK}"


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _user(db, key, role, **kw):
    u = User(
        email=f"{PFX}_{key}@test.invalid",
        password_hash=PWD_HASH,
        full_name=f"{PFX} {key}",
        role=role,
        is_active=True,
        password_changed_at=now,
        must_change_password=False,
        **kw,
    )
    db.add(u)
    db.flush()
    return u


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        coach = _user(db, "coach", UserRole.TEACHER, plan="solo_pro")
        coach_b = _user(db, "coach_b", UserRole.TEACHER, plan="solo_pro")
        student = _user(db, "s1", UserRole.STUDENT, teacher_id=coach.id, grade_level=8)
        db.commit()
        ctx.update(coach=coach.id, coach_b=coach_b.id, s1=student.id)


def login(key):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post(
        "/api/v2/auth/login",
        json={"email": f"{PFX}_{key}@test.invalid", "password": PWD},
    )
    if r.status_code != 200:
        raise RuntimeError(f"login {key}: {r.status_code} {r.text}")
    return c


def backdate_start(user_id: int, seconds: int = 10):
    """SQLite saniye çözünürlüğü: start ile hemen ardından yaratılan kayıt aynı
    saniyeye düşerse tazelik karşılaştırması flake olur → taban geriye alınır."""
    from datetime import timedelta

    from app.models import UserGuideState

    with SessionLocal() as db:
        st = db.query(UserGuideState).filter_by(user_id=user_id, guide_key=GK).one()
        st.started_at = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        db.commit()


def main() -> int:
    print(f"\n=== REHBER API SMOKE — {PFX} ===\n")
    setup()
    try:
        anon = TestClient(app)
        r = anon.get(BASE)
        check("1. anonim GET → 401", r.status_code == 401, f"{r.status_code}")

        st = login("s1")
        r = st.get(BASE)
        check("2. öğrenci → 404", r.status_code == 404, f"{r.status_code}")

        c = login("coach")
        r = c.get(BASE)
        ok = r.status_code == 200
        data = r.json() if ok else {}
        check(
            "3. koç ilk GET → not_started + chapters + checklist False",
            ok
            and data["state"]["status"] == "not_started"
            and data["chapters"][0] == "hosgeldin"
            and data["checklist"].get("kitap-ekle") is False
            and data["checklist"].get("deneme-gir") is False,
            f"{r.status_code} {data}",
        )

        r = c.post(f"{BASE}/progress", json={"action": "start"})
        d = r.json() if r.status_code == 200 else {}
        check(
            "4. start → in_progress + hosgeldin",
            r.status_code == 200
            and d["state"]["status"] == "in_progress"
            and d["state"]["current_chapter"] == "hosgeldin"
            and "me:guide" in d.get("invalidate", []),
            f"{r.status_code} {d}",
        )
        backdate_start(ctx["coach"])

        r = c.post(f"{BASE}/progress", json={"action": "chapter_done", "chapter": "hosgeldin"})
        d = r.json() if r.status_code == 200 else {}
        check(
            "5. chapter_done → done + current=kitap-ekle",
            r.status_code == 200
            and "hosgeldin" in d["state"]["chapters_done"]
            and d["state"]["current_chapter"] == "kitap-ekle",
            f"{r.status_code} {d}",
        )

        # 6. gerçek veri: kitap
        with SessionLocal() as db:
            subj = Subject(name=f"{PFX} Matematik", teacher_id=ctx["coach"])
            db.add(subj)
            db.flush()
            book = Book(
                teacher_id=ctx["coach"], subject_id=subj.id,
                name=f"{PFX} Soru Bankası", type=BookType.SORU_BANKASI,
            )
            db.add(book)
            db.commit()
            ctx["book"] = book.id
        r = c.get(BASE)
        d = r.json()
        check(
            "6. kitap eklenince checklist['kitap-ekle'] True",
            d["checklist"]["kitap-ekle"] is True and d["checklist"]["ogrenci-ata"] is False,
            f"{d['checklist']}",
        )

        # 7. atama
        with SessionLocal() as db:
            db.add(StudentBook(student_id=ctx["s1"], book_id=ctx["book"]))
            db.commit()
        r = c.get(BASE)
        d = r.json()
        check(
            "7. öğrenci+atama → ogrenci-ata True",
            d["checklist"]["ogrenci-ata"] is True and d["checklist"]["program-kur"] is False,
            f"{d['checklist']}",
        )

        # 8. program + yayınlanmış görev
        with SessionLocal() as db:
            db.add(WeeklyProgram(
                student_id=ctx["s1"], coach_id=ctx["coach"],
                start_date=date.today(), end_date=date.today(),
            ))
            db.add(Task(
                student_id=ctx["s1"], date=date.today(),
                title=f"{PFX} görev", is_draft=False,
                published_at=datetime.now(timezone.utc),
            ))
            db.commit()
        r = c.get(BASE)
        d = r.json()
        check(
            "8. program+görev → program-kur & yayinla-duyur & hafta-takip True",
            d["checklist"]["program-kur"] is True
            and d["checklist"]["yayinla-duyur"] is True
            and d["checklist"]["hafta-takip"] is True
            and d["checklist"]["deneme-gir"] is False,
            f"{d['checklist']}",
        )

        # 9. deneme
        with SessionLocal() as db:
            db.add(ExamResult(
                student_id=ctx["s1"], created_by_id=ctx["coach"],
                title=f"{PFX} deneme", exam_date=date.today(),
                section=ExamSection.LGS, total_correct=50, total_wrong=15,
                total_blank=25, net=45.0,
            ))
            db.commit()
        r = c.get(BASE)
        d = r.json()
        check("9. deneme → deneme-gir True", d["checklist"]["deneme-gir"] is True, f"{d['checklist']}")

        # 10. tüm bölümler
        for ch in d["chapters"]:
            r = c.post(f"{BASE}/progress", json={"action": "chapter_done", "chapter": ch})
        d = r.json()
        check(
            "10. tüm bölümler → completed",
            d["state"]["status"] == "completed" and d["state"]["completed_at"],
            f"{d['state']}",
        )

        r = c.post(f"{BASE}/progress", json={"action": "dismiss"})
        d = r.json()
        ok_dismiss = d["state"]["status"] == "dismissed" and d["state"]["dismissed_at"]
        r = c.post(f"{BASE}/progress", json={"action": "start"})
        d = r.json()
        check(
            "11. dismiss → dismissed; start → in_progress",
            ok_dismiss and d["state"]["status"] == "in_progress"
            and len(d["state"]["chapters_done"]) == 7,
            f"{d['state']}",
        )

        r = c.post(f"{BASE}/progress", json={"action": "reset"})
        d = r.json()
        check(
            "12. reset → boş + hosgeldin + taban sıfır (eski kitap taze değil)",
            d["state"]["chapters_done"] == []
            and d["state"]["current_chapter"] == "hosgeldin"
            and d["checklist"]["kitap-ekle"] is False
            and d["preexisting"]["kitap-ekle"] is True,
            f"{d['state']} {d['checklist']} {d.get('preexisting')}",
        )

        r = c.post(f"{BASE}/progress", json={"action": "bogus"})
        ok_a = r.status_code == 422
        r = c.post(f"{BASE}/progress", json={"action": "chapter_done"})
        check(
            "13. geçersiz action / chapter'sız chapter_done → 422",
            ok_a and r.status_code == 422,
            f"{r.status_code}",
        )

        cb = login("coach_b")
        r = cb.get(BASE)
        d = r.json()
        check(
            "14. izolasyon: coach_b not_started",
            d["state"]["status"] == "not_started" and d["state"]["chapters_done"] == [],
            f"{d['state']}",
        )

        # 15. ÖNCEDEN VAR: rehber başlamadan mevcut kitap taze SAYILMAZ
        with SessionLocal() as db:
            from datetime import timedelta

            subj_b = Subject(name=f"{PFX} Fizik", teacher_id=ctx["coach_b"])
            db.add(subj_b)
            db.flush()
            old_book = Book(
                teacher_id=ctx["coach_b"], subject_id=subj_b.id,
                name=f"{PFX} Eski Kitap", type=BookType.SORU_BANKASI,
            )
            db.add(old_book)
            db.flush()
            # "rehberden önce" senaryosu: kitabı geçmişe tarihle
            old_book.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
            db.commit()
        cb.post(f"{BASE}/progress", json={"action": "start"})
        backdate_start(ctx["coach_b"], seconds=5)
        r = cb.get(BASE)
        d = r.json()
        check(
            "15. önceden var → checklist False + preexisting True",
            d["checklist"]["kitap-ekle"] is False and d["preexisting"]["kitap-ekle"] is True,
            f"{d['checklist']} {d.get('preexisting')}",
        )

        # 16. start SONRASI yeni kitap → taze eylem tanınır
        with SessionLocal() as db:
            subj_b2 = db.query(Subject).filter_by(
                teacher_id=ctx["coach_b"], name=f"{PFX} Fizik"
            ).one()
            db.add(Book(
                teacher_id=ctx["coach_b"], subject_id=subj_b2.id,
                name=f"{PFX} Yeni Kitap", type=BookType.SORU_BANKASI,
            ))
            db.commit()
        r = cb.get(BASE)
        d = r.json()
        check(
            "16. start sonrası yeni kitap → checklist True",
            d["checklist"]["kitap-ekle"] is True,
            f"{d['checklist']}",
        )

        # 17. watch kalıcılığı — adımlar sunucuda, yeni istemci de görür
        for st_i in (0, 1, 1, 3):
            r = cb.post(
                f"{BASE}/progress",
                json={"action": "watch", "chapter": "program-kur", "step": st_i},
            )
        d = r.json()
        cb2 = login("coach_b")  # taze oturum (logout/yeniden giriş simülasyonu)
        d2 = cb2.get(BASE).json()
        check(
            "17. watch sunucuda kalıcı + mükerrersiz + invalidate boş",
            d["state"]["steps_watched"]["program-kur"] == [0, 1, 3]
            and d2["state"]["steps_watched"]["program-kur"] == [0, 1, 3]
            and d2["state"]["current_chapter"] == "program-kur"
            and d.get("invalidate") == [],
            f"{d['state'].get('steps_watched')} / {d2['state'].get('steps_watched')}",
        )

        r = cb.post(f"{BASE}/progress", json={"action": "watch"})
        check("18. watch chapter'sız → 422", r.status_code == 422, f"{r.status_code}")

        # 19-20. Öğrenci rehberi
        SBASE = "/api/v2/me/guide/student_onboarding"
        r = st.get(SBASE)
        d = r.json() if r.status_code == 200 else {}
        r2 = c.get(SBASE)
        check(
            "19. öğrenci rehberi: öğrenci 200 + ogr bölümleri; koç 404",
            r.status_code == 200
            and d["chapters"][0] == "ogr-hosgeldin"
            and len(d["chapters"]) == 7
            and r2.status_code == 404,
            f"{r.status_code}/{r2.status_code} {d.get('chapters')}",
        )
        st.post(f"{SBASE}/progress", json={"action": "start"})
        r = st.post(
            f"{SBASE}/progress",
            json={"action": "chapter_done", "chapter": "ogr-hosgeldin"},
        )
        d = r.json()
        st.post(f"{SBASE}/progress", json={"action": "watch", "chapter": "ogr-bugun", "step": 2})
        d2 = st.get(SBASE).json()
        check(
            "20. öğrenci akışı: sıradaki bölüm + watch kalıcı",
            d["state"]["current_chapter"] == "ogr-bugun"
            and d2["state"]["steps_watched"]["ogr-bugun"] == [2],
            f"{d['state']} {d2['state'].get('steps_watched')}",
        )
    finally:
        cleanup()

    print(f"\n  Sonuç: {passed} PASS / {len(failed)} FAIL")
    for f in failed:
        print(f"    FAIL: {f}")
    return 1 if failed else 0


def cleanup():
    with SessionLocal() as db:
        users = db.query(User).filter(User.email.like(f"{PFX}_%")).all()
        ids = [u.id for u in users]
        if ids:
            db.query(UserGuideState).filter(UserGuideState.user_id.in_(ids)).delete(
                synchronize_session=False
            )
            db.query(ExamResult).filter(ExamResult.student_id.in_(ids)).delete(
                synchronize_session=False
            )
            db.query(Task).filter(Task.student_id.in_(ids)).delete(synchronize_session=False)
            db.query(WeeklyProgram).filter(WeeklyProgram.student_id.in_(ids)).delete(
                synchronize_session=False
            )
            db.query(StudentBook).filter(StudentBook.student_id.in_(ids)).delete(
                synchronize_session=False
            )
            db.query(Book).filter(Book.teacher_id.in_(ids)).delete(synchronize_session=False)
            db.query(Subject).filter(Subject.teacher_id.in_(ids)).delete(
                synchronize_session=False
            )
            for u in users:
                db.delete(u)
        db.query(SuspiciousIp).filter(SuspiciousIp.ip == "testclient").delete(
            synchronize_session=False
        )
        db.commit()


if __name__ == "__main__":
    raise SystemExit(main())
