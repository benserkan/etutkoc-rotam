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

  ÖNİZLE-DÜZENLE-GÖNDER (2026-09-10, koç isteği: "mail içeriği önizlenmeli ve
  düzenlenebilmeli; bazı ifadeleri kaldırmak isteyebilirim"):
  15. Önizleme ucu gönderim YAPMAZ (salt okuma) + içerik mailin aynısı
  16. Önizlemede alıcı veliler + GİTMEYECEKLERİN SEBEBİ görünür
  17. Koçun DÜZENLEDİĞİ metin gider (kural motorunun cümlesi değil)
  18. include_subjects=false → ders tablosu maile GİRMEZ
  19. narrative=[] → yorumsuz gider (sayılar durur, mail patlamaz)
  20. Doğrulama: fazla satır kırpılır · uzun satır kesilir · boş satır atılır
  21. Gövdesiz POST eski davranışı korur (mobil/eski istemci kırılmaz)
  22. Duyurulmuş denemede önizleme already_notified=True der
  23. Sahiplik: başka koçun denemesinin önizlemesi → 404

  "EN RAHAT OLDUĞU BÖLÜM" MANTIK DÜZELTMESİ (2026-09-10, koç ekran görüntüsü:
  "en rahat bölüm Matematik çıkmış ama Fen 15'te 15/20 — formül doğru mu?"):
  24. ELİF VAKASI: oran doğru/TOPLAM SORU (boş DAHİL) — cümledeki sayıyla
      aynı temel. Boş hariç bakınca 26/34 olan Matematik, 15/20 olan Fen'i
      geçiyordu; veli ise "26 doğru / 40 soru" (%65) okuyordu.
  25. Maarif/okul birleşik ders adları alan filtresine takılmaz
      ("Fen Bilimleri" SAYISAL'ın belkemiği, "Türk Dili ve Edebiyatı" = Türkçe)
  26. Tek aday kalırsa "en rahat" DENMEZ (karşılaştırma iddiası, tek dersle olmaz)
  27. Hiçbir derste yarıyı geçemediyse "en rahat" DENMEZ
  28. Soru sayısı farkı adil: 20 soruluk %80 ile 40 soruluk %80'de büyük olan kazanır
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

        # Düzenleme senaryoları için ayrı denemeler (her duyuru tek seferlik).
        # DİKKAT: tarihleri `cur`dan SONRA — araya girerlerse cur'un "bir
        # önceki TYT" kıyası değişir ve senaryo 4/7 yanlış kırmızı verir.
        edited = mk(st.id, "Düzenlenecek TYT", date(2026, 9, 10),
                    ExamSection.TYT, 50, 20, 50, 45.0, nets)
        limits = mk(st.id, "Sınır TYT", date(2026, 9, 11),
                    ExamSection.TYT, 50, 20, 50, 45.0, nets)
        plain = mk(st.id, "Gövdesiz TYT", date(2026, 9, 12),
                   ExamSection.TYT, 50, 20, 50, 45.0, nets)

        # --- ELİF VAKASI (saha, 2026-09-10): Maarif birleşik ders adları +
        #     boş bırakılan sorular. Beklenen "en rahat": Fen (15/20 = %75),
        #     Matematik DEĞİL (26/40 = %65 — boş hariç bakılınca %76 görünüp
        #     kazanıyordu).
        elif_nets = (
            '[{"name":"Fen Bilimleri","correct":15,"wrong":5,"blank":0,"net":13.75},'
            '{"name":"Matematik","correct":26,"wrong":8,"blank":6,"net":24.0},'
            '{"name":"Sosyal Bilimler","correct":16,"wrong":4,"blank":5,"net":15.0},'
            '{"name":"Türk Dili ve Edebiyatı","correct":25,"wrong":11,"blank":4,'
            '"net":22.25}]'
        )
        elif_exam = mk(st.id, "ÇAP Maarif Birinci Basamak", date(2026, 9, 13),
                       ExamSection.TYT, 82, 28, 15, 75.0, elif_nets)

        # Tek aday: SAYISAL öğrencide yalnız Matematik core → karşılaştırma yok
        solo_nets = (
            '[{"name":"Matematik","correct":30,"wrong":5,"blank":5,"net":28.75},'
            '{"name":"Sosyal Bilimler","correct":16,"wrong":4,"blank":5,"net":15.0}]'
        )
        solo_subj = mk(st.id, "Tek Ders TYT", date(2026, 9, 14),
                       ExamSection.TYT, 46, 9, 10, 43.75, solo_nets)

        # Hiçbir derste yarı yok → "en rahat" cümlesi kurulmamalı
        weak_nets = (
            '[{"name":"Matematik","correct":10,"wrong":20,"blank":10,"net":5.0},'
            '{"name":"Fen Bilimleri","correct":8,"wrong":10,"blank":2,"net":5.5}]'
        )
        weak_exam = mk(st.id, "Zayıf TYT", date(2026, 9, 15),
                       ExamSection.TYT, 18, 30, 12, 10.5, weak_nets)

        # Soru sayısı adaleti: aynı %80, farklı hacim → büyük örneklem kazanır
        size_nets = (
            '[{"name":"Matematik","correct":32,"wrong":6,"blank":2,"net":30.5},'
            '{"name":"Fen Bilimleri","correct":16,"wrong":3,"blank":1,"net":15.25}]'
        )
        size_exam = mk(st.id, "Hacim TYT", date(2026, 9, 16),
                       ExamSection.TYT, 48, 9, 3, 45.75, size_nets)

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
            "edited": edited.id, "limits": limits.id, "plain": plain.id,
            "elif": elif_exam.id, "solo_subj": solo_subj.id,
            "weak": weak_exam.id, "size": size_exam.id,
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


def _log_count(parent_id: int) -> int:
    """Bu veliye yazılmış EXAM_RESULT satır sayısı — önizlemenin gönderim
    yapmadığını kanıtlamak için (salt okuma iddiası ölçülür)."""
    with SessionLocal() as db:
        return (
            db.query(NotificationLog)
            .filter(NotificationLog.parent_id == parent_id,
                    NotificationLog.kind == NotificationKind.EXAM_RESULT)
            .count()
        )


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

        # ---- 15. ÖNİZLEME salt okuma + içerik mailin aynısı
        pv = c.get(f"/api/v2/teacher/exams/{s['cur']}/parent-preview")
        pvd = pv.json() if pv.status_code == 200 else {}
        logs_before = _log_count(s["parent_id"])
        pv2 = c.get(f"/api/v2/teacher/exams/{s['cur']}/parent-preview")
        check("15. önizleme GÖNDERİM YAPMAZ + net/D-Y-B/ders/yorum döner",
              pv.status_code == 200 and pv2.status_code == 200
              and _log_count(s["parent_id"]) == logs_before
              and pvd.get("net_text") == "52,50"
              and pvd.get("correct") == 58 and pvd.get("wrong") == 22
              and len(pvd.get("subjects", [])) == 5
              and len(pvd.get("narrative", [])) >= 2
              and pvd.get("already_notified") is False,
              f"status={pv.status_code} log {logs_before}→{_log_count(s['parent_id'])} "
              f"net={pvd.get('net_text')} subj={len(pvd.get('subjects', []))}")

        # ---- 16. alıcı listesi: kime gidecek, kime gitmeyecek + SEBEP
        recips = pvd.get("recipients", [])
        check("16. önizlemede alıcı veliler + gidecek sayısı",
              len(recips) == 1 and recips[0]["blocked"] is False
              and pvd.get("deliverable_count") == 1
              and recips[0]["name"] == "Duyuru Veli",
              f"{recips} deliverable={pvd.get('deliverable_count')}")

        # ---- 2. duyur (GÖVDESİZ — eski davranış)
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

        # ---- 22. duyurulmuş denemenin önizlemesi "zaten duyuruldu" der
        pv3 = c.get(f"/api/v2/teacher/exams/{s['cur']}/parent-preview").json()
        check("22. duyurulmuş denemede önizleme already_notified=True + damga",
              pv3.get("already_notified") is True and bool(pv3.get("notified_at")),
              f"{pv3.get('already_notified')} {pv3.get('notified_at')}")

        # ---- 17/18. KOÇUN DÜZENLEDİĞİ metin gider + ders tablosu çıkarılabilir
        #      (asıl istek: "bazı ifadeleri kaldırmak isteyebilirim")
        r = c.post(
            f"/api/v2/teacher/exams/{s['edited']}/notify-parents",
            json={
                "narrative": [
                    "Merhaba, Emir bu denemede 45 net çıkardı.",
                    "Görüşmemizde ayrıntısını konuşacağız.",
                ],
                "include_subjects": False,
            },
        )
        pe = last_payload(s["parent_id"])
        auto_line = "Programına önümüzdeki dönemde"
        check("17. koçun düzenlediği metin gider — kural motorunun cümlesi GİTMEZ",
              r.status_code == 200 and r.json()["data"]["queued"] == 1
              and pe.get("narrative") == [
                  "Merhaba, Emir bu denemede 45 net çıkardı.",
                  "Görüşmemizde ayrıntısını konuşacağız.",
              ]
              and not any(auto_line in ln for ln in pe.get("narrative", [])),
              f"status={r.status_code} narrative={pe.get('narrative')}")
        check("18. include_subjects=false → ders tablosu maile GİRMEZ "
              "(sayılar durur)",
              pe.get("subjects") == [] and pe.get("net_text") == "45,00"
              and pe.get("correct") == 50,
              f"subjects={pe.get('subjects')} net={pe.get('net_text')}")

        # ---- 19/20. yorumsuz gönderim + doğrulama sınırları
        long_line = "A" * 900
        r = c.post(
            f"/api/v2/teacher/exams/{s['limits']}/notify-parents",
            json={
                "narrative": (
                    ["  ", "", long_line]
                    + [f"satır {i}" for i in range(20)]
                ),
            },
        )
        pl = last_payload(s["parent_id"])
        nl = pl.get("narrative", [])
        check("20. doğrulama: boş satır atılır · uzun satır kesilir · "
              "satır sayısı sınırlanır",
              r.status_code == 200 and len(nl) == 12
              and all(len(x) <= 500 for x in nl)
              and nl[0] == "A" * 500 and "" not in nl,
              f"n={len(nl)} ilk={len(nl[0]) if nl else 0}")

        # ---- 19. tamamen yorumsuz (koç hepsini sildi) — mail yine gider
        r = c.post(
            f"/api/v2/teacher/exams/{s['plain']}/notify-parents",
            json={"narrative": [], "include_subjects": True},
        )
        pp = last_payload(s["parent_id"])
        check("19. narrative=[] → yorumsuz gider, sayılar+tablo durur",
              r.status_code == 200 and r.json()["data"]["queued"] == 1
              and pp.get("narrative") == [] and len(pp.get("subjects", [])) == 5,
              f"status={r.status_code} narr={pp.get('narrative')} "
              f"subj={len(pp.get('subjects', []))}")

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

        # ---- 24-28. "EN RAHAT OLDUĞU BÖLÜM" mantığı (koç saha bulgusu)
        #      Önizleme ucundan okunur — gönderim gerekmez, damga harcanmaz.
        def narr_of(exam_id: int) -> list[str]:
            pv = c.get(f"/api/v2/teacher/exams/{exam_id}/parent-preview")
            return pv.json().get("narrative", []) if pv.status_code == 200 else []

        el = " ".join(narr_of(s["elif"]))
        check(
            "24/25. ELİF VAKASI: 'en rahat' = Fen Bilimleri (15/20=%75), "
            "Matematik (26/40=%65) DEĞİL — oran TOPLAM soru üzerinden",
            "En rahat olduğu bölüm Fen Bilimleri (15 doğru / 20 soru)" in el
            and "En rahat olduğu bölüm Matematik" not in el,
            el[:300],
        )

        so = " ".join(narr_of(s["solo_subj"]))
        check(
            "26. tek karşılaştırılabilir ders kalırsa 'en rahat' DENMEZ",
            "En rahat olduğu bölüm" not in so and len(so) > 40,
            so[:220],
        )

        wk = " ".join(narr_of(s["weak"]))
        check(
            "27. hiçbir derste yarıyı geçemediyse 'en rahat' DENMEZ",
            "En rahat olduğu bölüm" not in wk and len(wk) > 40,
            wk[:220],
        )

        sz = " ".join(narr_of(s["size"]))
        check(
            "28. aynı %80'de büyük örneklem kazanır (40 soruluk Matematik, "
            "20 soruluk Fen'i geçer)",
            "En rahat olduğu bölüm Matematik (32 doğru / 40 soru)" in sz,
            sz[:260],
        )

        # ---- 21. TERCİH KAPALIYKEN önizleme bunu SÖYLER (koç boşuna beklemesin)
        #      Bastırma kararı gerçek gönderimle AYNI fonksiyondan gelir
        #      (notification_producer.suppression_reason) — çelişemez.
        pv4 = c.get(f"/api/v2/teacher/exams/{s['ayt']}/parent-preview").json()
        rec4 = pv4.get("recipients", [])
        check("21. veli bildirimi kapatmışsa önizleme SEBEBİYLE gösterir "
              "(gidecek sayısı 0)",
              len(rec4) == 1 and rec4[0]["blocked"] is True
              and "kapatmış" in (rec4[0].get("blocked_label") or "")
              and pv4.get("deliverable_count") == 0,
              f"{rec4} deliverable={pv4.get('deliverable_count')}")

        # ---- 12/23. sahiplik
        r = c.post(f"/api/v2/teacher/exams/{s['foreign_exam']}/notify-parents")
        r23 = c.get(f"/api/v2/teacher/exams/{s['foreign_exam']}/parent-preview")
        check("12/23. başka koçun denemesi → 404 (gönderim VE önizleme)",
              r.status_code == 404 and r23.status_code == 404,
              f"post={r.status_code} preview={r23.status_code}")
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
