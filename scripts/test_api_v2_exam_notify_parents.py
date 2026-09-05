"""Deneme sonucu veli duyurusu — smoke (2026-09-05).

KOÇ İSTEĞİ: "koç butona basınca veliye e-posta gitsin; netler + varsa önceki
denemelere göre değişim + konuşma dilinde analiz + detay için Rotam linki.
Duyurusu yapıldığında buton 'duyuruldu'ya dönsün."

Senaryolar:
   1. Duyurulmamış denemede damga YOK (buton "Veliye duyur")
   2. Duyur → veliye e-posta kuyruğa girer + damga atılır
   3. E-postanın İÇERİĞİ: net, D/Y/B, ders kırılımı, Rotam linki
   4. KONUŞMA DİLİ + DEĞİŞİM: "bir önceki denemeye göre N net artış"
   5. İlk denemede kıyas cümlesi farklı ("bu türdeki ilk denemesi")
   6. DÜŞÜŞTE dil suçlayıcı DEĞİL (yargılayıcı kelime yok)
   7. Karşılaştırma AYNI TÜR içinde (TYT ile AYT kıyaslanmaz)
   8. Mükerrer duyuru → 409 already_notified
   9. Sessize alınmış (muted) veli atlanır
  10. Velisi olmayan öğrenci → 422 no_parent
  11. Veli tercihi kapalıysa e-posta ÜRETİLMEZ ama akış patlamaz
  12. Sahiplik: başka koçun denemesi → 404
  13. ALAN FARKINDALIĞI: sayısal öğrenciye alan-dışı ders (Coğrafya) odak
      olarak ÖNERİLMEZ — tabloda görünür ama cümleye girmez
  14. KONU DÜZEYİ: içe aktarılmış denemede "şu konularda takıldı" + gerçek
      konu adları (ders adı tek başına koçluk değil)
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models.curriculum import Subject, Topic
from app.models.exam_result import ExamResultQuestion
from app.main import app
from app.models import (
    ExamResult,
    ExamSection,
    NotificationKind,
    NotificationLog,
    ParentNotificationPref,
    ParentStudentLink,
    SuspiciousIp,
    Track,
    User,
    UserRole,
)
from app.services.security import hash_password

PFX = f"enp_{secrets.token_hex(3)}"
PWD = "TestPass123!@xyz"
passed = 0
failed: list[str] = []

# Veli diline aykırı, suçlayıcı/yargılayıcı sözcükler — üretilen metinde
# ASLA geçmemeli (weekly_parent_report ilkeleri).
YASAK = ("başarısız", "kötü", "yetersiz", "tembel", "vasat", "düşük performans")


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
                     full_name="Duyuru Koç", role=UserRole.TEACHER, is_active=True)
        other = User(email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PWD),
                     full_name="Duyuru Koç2", role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other])
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Emir Deneme", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12, track=Track.SAYISAL)
        solo = User(email=f"{PFX}_s2@test.invalid", password_hash=hash_password(PWD),
                    full_name="Velisiz Öğrenci", role=UserRole.STUDENT,
                    is_active=True, teacher_id=coach.id, grade_level=12)
        muted_st = User(email=f"{PFX}_s3@test.invalid", password_hash=hash_password(PWD),
                        full_name="Sessiz Öğrenci", role=UserRole.STUDENT,
                        is_active=True, teacher_id=coach.id, grade_level=12)
        foreign = User(email=f"{PFX}_s4@test.invalid", password_hash=hash_password(PWD),
                       full_name="Yabancı Öğrenci", role=UserRole.STUDENT,
                       is_active=True, teacher_id=other.id, grade_level=12)
        parent = User(email=f"{PFX}_p@test.invalid", password_hash=hash_password(PWD),
                      full_name="Duyuru Veli", role=UserRole.PARENT, is_active=True)
        muted_parent = User(email=f"{PFX}_p2@test.invalid",
                            password_hash=hash_password(PWD),
                            full_name="Sessiz Veli", role=UserRole.PARENT,
                            is_active=True)
        db.add_all([st, solo, muted_st, foreign, parent, muted_parent])
        db.flush()
        db.add(ParentStudentLink(parent_id=parent.id, student_id=st.id))
        db.add(ParentStudentLink(parent_id=muted_parent.id, student_id=muted_st.id,
                                 muted=True))
        db.add(ParentNotificationPref(parent_id=parent.id))
        db.flush()

        def mk(student_id, title, d, sec, c, w, b, net, nets=None) -> ExamResult:
            e = ExamResult(student_id=student_id, title=title, exam_date=d,
                           section=sec, total_correct=c, total_wrong=w,
                           total_blank=b, net=net, created_by_id=coach.id,
                           subject_nets=nets)
            db.add(e)
            db.flush()
            return e

        # KÜÇÜK ÖRNEKLEM TUZAĞI: Din 5/5 (%100) ham oranda Türkçe 36/40'ı (%90)
        # geçer ama 5 soruluk kanıt zayıftır — Wilson alt sınırı bunu eler.
        # ALAN TUZAĞI: Coğrafya 3/5 tablodaki EN ZAYIF ders — ama öğrenci
        # SAYISAL, alan-dışı derse "ağırlık vereceğiz" demek koçluk değil.
        nets = (
            '[{"name":"TYT Türkçe","correct":36,"wrong":4,"blank":0,"net":35.0},'
            '{"name":"TYT Din Kültürü","correct":5,"wrong":0,"blank":0,"net":5.0},'
            '{"name":"TYT Matematik","correct":20,"wrong":18,"blank":2,"net":15.5},'
            '{"name":"TYT Coğrafya","correct":3,"wrong":2,"blank":0,"net":2.5},'
            '{"name":"Sosyal Bilimler","correct":2,"wrong":0,"blank":0,"net":2.0,'
            '"unmatched":true}]'
        )
        # ÖNCEKİ TYT denemesi (kıyas kaynağı) + güncel TYT
        prev = mk(st.id, "Önceki TYT Denemesi", date(2026, 8, 20),
                  ExamSection.TYT, 58, 20, 42, 53.0)
        cur = mk(st.id, "ÜçDörtBeş TYT Son Düzlük", date(2026, 9, 2),
                 ExamSection.TYT, 58, 22, 40, 52.5, nets)
        # İçe aktarılmış denemenin soru satırları — konu düzeyi dilin kaynağı.
        # Coğrafya'da da yanlış var: alan filtresi çalışmazsa cümleye sızar.
        subj_ids: dict[str, int] = {}
        for sname, topics in (
            ("TYT Matematik", ["Fonksiyonlar", "Yaş Problemleri"]),
            ("TYT Coğrafya", ["Nüfus", "Yerin Şekillenmesi"]),
        ):
            sub = db.query(Subject).filter(Subject.name == sname).first()
            if sub is None:
                sub = Subject(name=sname, teacher_id=None)
                db.add(sub)
                db.flush()
            subj_ids[sname] = sub.id
            for tname in topics:
                tp = (db.query(Topic)
                      .filter(Topic.subject_id == sub.id, Topic.name == tname)
                      .first())
                if tp is None:
                    tp = Topic(subject_id=sub.id, name=tname, order=0)
                    db.add(tp)
                    db.flush()
                db.add(ExamResultQuestion(
                    exam_result_id=cur.id, subject_id=sub.id, topic_id=tp.id,
                    result="yanlis",
                ))
        db.flush()

        # AYT denemesi — TYT ile kıyaslanmamalı
        ayt = mk(st.id, "AYT Denemesi", date(2026, 9, 1),
                 ExamSection.AYT_SAY, 30, 8, 42, 28.0)
        # düşüş senaryosu için ikinci öğrenci verisi
        muted_exam = mk(muted_st.id, "Sessiz TYT", date(2026, 9, 2),
                        ExamSection.TYT, 40, 10, 70, 37.5)
        solo_exam = mk(solo.id, "Velisiz TYT", date(2026, 9, 2),
                       ExamSection.TYT, 40, 10, 70, 37.5)
        foreign_exam = mk(foreign.id, "Yabancı TYT", date(2026, 9, 2),
                          ExamSection.TYT, 40, 10, 70, 37.5)
        db.commit()
        return {
            "coach_id": coach.id, "other_id": other.id, "student_id": st.id,
            "solo_id": solo.id, "muted_st": muted_st.id, "foreign_id": foreign.id,
            "parent_id": parent.id, "muted_parent": muted_parent.id,
            "prev": prev.id, "cur": cur.id, "ayt": ayt.id,
            "muted_exam": muted_exam.id, "solo_exam": solo_exam.id,
            "foreign_exam": foreign_exam.id,
        }


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        ids = [s["coach_id"], s["other_id"], s["student_id"], s["solo_id"],
               s["muted_st"], s["foreign_id"], s["parent_id"], s["muted_parent"]]
        db.execute(sa_delete(NotificationLog).where(
            NotificationLog.parent_id.in_(ids)))
        db.execute(sa_delete(ParentNotificationPref).where(
            ParentNotificationPref.parent_id.in_(ids)))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_(ids)))
        exam_ids = [r[0] for r in db.query(ExamResult.id)
                    .filter(ExamResult.student_id.in_(ids)).all()]
        if exam_ids:
            db.execute(sa_delete(ExamResultQuestion).where(
                ExamResultQuestion.exam_result_id.in_(exam_ids)))
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(ids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


def last_payload(parent_id: int) -> dict:
    import json

    with SessionLocal() as db:
        log = (
            db.query(NotificationLog)
            .filter(NotificationLog.parent_id == parent_id,
                    NotificationLog.kind == NotificationKind.EXAM_RESULT)
            .order_by(NotificationLog.id.desc())
            .first()
        )
        if log is None:
            return {}
        try:
            return json.loads(log.payload_json or "{}")
        except (ValueError, TypeError):
            return {}


def main() -> int:
    s = seed()
    print(f"\n=== Deneme sonucu veli duyurusu (öğrenci #{s['student_id']}) ===\n")
    try:
        c = TestClient(app)
        from app.services.rate_limit import get_login_limiter
        get_login_limiter().reset()
        r = c.post("/api/v2/auth/login",
                   json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text

        sid = s["student_id"]

        # ---- 1. duyurulmamış → damga yok
        rows = c.get(f"/api/v2/teacher/students/{sid}/exams?period=all").json()
        cur_row = next(
            (x for x in rows["rows"] if x["id"] == s["cur"]), None)
        check("1. duyurulmamış denemede damga YOK",
              cur_row is not None and cur_row.get("parent_notified_at") is None,
              f"{cur_row}")

        # ---- 2. duyur
        r = c.post(f"/api/v2/teacher/exams/{s['cur']}/notify-parents")
        data = r.json().get("data", {}) if r.text else {}
        rows2 = c.get(f"/api/v2/teacher/students/{sid}/exams?period=all").json()
        cur2 = next((x for x in rows2["rows"] if x["id"] == s["cur"]), None)
        check("2. duyur → kuyruğa girdi + damga atıldı (buton 'Duyuruldu')",
              r.status_code == 200 and data.get("queued") == 1
              and cur2 and cur2.get("parent_notified_at"),
              f"status={r.status_code} data={data} damga={cur2 and cur2.get('parent_notified_at')}")

        p = last_payload(s["parent_id"])
        check("3. içerik: net + D/Y/B + ders kırılımı + öğrenci linki",
              p.get("net_text") == "52,50" and p.get("correct") == 58
              and p.get("wrong") == 22 and p.get("blank") == 40
              and len(p.get("subjects", [])) == 5
              and p.get("student_id") == sid
              and p.get("__template") == "parent_exam_result",
              f"net={p.get('net_text')} subjects={len(p.get('subjects', []))}")

        narr = " ".join(p.get("narrative", []))
        check("4. konuşma dili + ÖNCEKİ denemeye göre değişim var",
              "Emir" in narr and "deneme" in narr.lower()
              and p.get("delta") == -0.5
              and p.get("prev_title") == "Önceki TYT Denemesi",
              f"delta={p.get('delta')} prev={p.get('prev_title')} | {narr[:160]}")

        # ---- 4b. KÜÇÜK ÖRNEKLEM: 5/5 ders "en rahat" diye öne çıkmamalı
        check("4b. az soruluk %100 ders 'en güçlü' sayılmaz (Wilson alt sınırı)",
              "Din Kültürü" not in narr and "Türkçe" in narr,
              f"{narr[:220]}")

        # ---- 13. ALAN: sayısal öğrenciye Coğrafya odak olarak önerilmez
        check("13. alan-dışı ders (Coğrafya) odak cümlesine GİRMEZ, tabloda var",
              "Coğrafya" not in narr
              and any("Coğrafya" in (x.get("name") or "")
                      for x in p.get("subjects", [])),
              f"{narr[:240]}")

        # ---- 14. KONU DÜZEYİ: gerçek konu adları geçmeli
        check("14. konu düzeyi dil: 'şu konularda takıldı' + konu adları",
              "konularda takıldı" in narr
              and "Fonksiyonlar" in narr and "Yaş Problemleri" in narr
              and "Nüfus" not in narr,
              f"{narr[:240]}")

        # ---- 7. kıyas AYNI TÜR içinde (AYT karışmadı)
        check("7. karşılaştırma AYNI TÜR içinde (AYT ile TYT kıyaslanmadı)",
              p.get("prev_title") == "Önceki TYT Denemesi",
              f"{p.get('prev_title')}")

        # ---- 6. suçlayıcı dil yok
        low = narr.lower()
        # DİKKAT: boş metin de "yasak kelime içermez" — önce metnin GERÇEKTEN
        # üretildiğini doğrula, yoksa test yanlış PASS verir (2026-09-05).
        check("6. dil üretildi VE suçlayıcı değil (yargılayıcı sözcük yok)",
              len(p.get("narrative", [])) >= 2 and len(narr) > 60
              and not any(k in low for k in YASAK), f"{narr[:200]}")

        # ---- 5. ilk denemede kıyas cümlesi farklı
        r = c.post(f"/api/v2/teacher/exams/{s['ayt']}/notify-parents")
        p_ayt = last_payload(s["parent_id"])
        check("5. ilk denemede 'ilk denemesi' dili + delta yok",
              r.status_code == 200 and p_ayt.get("delta") is None
              and "ilk deneme" in " ".join(p_ayt.get("narrative", [])).lower(),
              f"delta={p_ayt.get('delta')}")

        # ---- 8. mükerrer
        r = c.post(f"/api/v2/teacher/exams/{s['cur']}/notify-parents")
        check("8. mükerrer duyuru → 409 already_notified",
              r.status_code == 409
              and (r.json().get("detail") or {}).get("code") == "already_notified",
              f"{r.status_code} {r.text[:120]}")

        # ---- 9/10. muted + velisiz
        r9 = c.post(f"/api/v2/teacher/exams/{s['muted_exam']}/notify-parents")
        r10 = c.post(f"/api/v2/teacher/exams/{s['solo_exam']}/notify-parents")
        check("9/10. sessize alınmış veli atlanır · velisiz öğrenci 422 no_parent",
              r9.status_code == 422 and r10.status_code == 422
              and (r10.json().get("detail") or {}).get("code") == "no_parent",
              f"{r9.status_code}/{r10.status_code}")

        # ---- 11. veli tercihi kapalı → e-posta üretilmez, akış patlamaz
        with SessionLocal() as db:
            pref = db.query(ParentNotificationPref).filter(
                ParentNotificationPref.parent_id == s["parent_id"]).first()
            pref.exam_result_enabled = False
            db.commit()
        before = len(last_payload(s["parent_id"]))
        r = c.post(f"/api/v2/teacher/exams/{s['prev']}/notify-parents")
        check("11. veli tercihi kapalıyken akış patlamaz (queued=0)",
              r.status_code == 200 and r.json()["data"]["queued"] == 0,
              f"status={r.status_code} {r.text[:140]} before={before}")

        # ---- 12. sahiplik
        r = c.post(f"/api/v2/teacher/exams/{s['foreign_exam']}/notify-parents")
        check("12. başka koçun denemesi → 404", r.status_code == 404,
              f"{r.status_code}")
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
