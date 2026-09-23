"""Deneme konu normalizasyonu — "Ünite / Konu" etiketleri + bölünen konular.

2026-09-23 (Emir #113): karne "Denklemler ve Eşitsizlikler / Oran - Orantı"
yazıyordu; bütün etiket aranınca AI önekteki sözcüğe kanıp Basit
Eşitsizlikler'i seçti ve bu SÖZLÜĞE yazıldı → her karnede tekrar. Kural:
kuyruk önce; bütün etiketin AI kaydı yalnız kuyruk sonuçsuzsa; koç kaydı
her şeyi ezer; ünite başı son çare.

    PYTHONPATH=. python scripts/test_exam_topic_unit_label.py
"""
from __future__ import annotations

import sys

from app.database import SessionLocal
from app.models import Subject, Topic
from app.models.exam_result import ALIAS_SOURCE_AI, ALIAS_SOURCE_COACH, ExamTopicAlias
from app.services import exam_import_service as S
from app.services.curriculum_mapping import _label_key

sys.stdout.reconfigure(encoding="utf-8")
passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} -- {detail}")


def main() -> int:
    db = SessionLocal()
    try:
        subs = (db.query(Subject)
                .filter(Subject.is_builtin.is_(True), Subject.curriculum_model.is_(None),
                        Subject.name.like("TYT %")).all())
        tops = db.query(Topic).filter(Topic.subject_id.in_([s.id for s in subs]),
                                      Topic.is_builtin.is_(True)).all()
        by = {(next(s.name for s in subs if s.id == t.subject_id), t.name): t for t in tops}
        need = [("TYT Matematik", "Oran ve Orantı"), ("TYT Matematik", "Basit Eşitsizlikler"),
                ("TYT Türkçe", "Paragrafta Yapı"), ("TYT Türkçe", "Paragraf (Karma)"),
                ("TYT Geometri", "Kare"), ("TYT Geometri", "Üçgenler (Karma)"),
                ("TYT Tarih", "Uluslararası İlişkilerde Denge Stratejisi (1774-1914)"),
                ("TYT Din Kültürü ve Ahlak Bilgisi", "Din ve İslam")]
        missing = [n for n in need if n not in by]
        if missing:
            print("seed eksik:", missing)
            return 1

        def run(label: str, subject_raw: str = "Temel Matematik") -> dict:
            rows = [{"subject_raw": subject_raw, "topic_raw": label}]
            S.normalize_topics(db, rows, universe="tyt", subjects=subs, topics=tops, use_ai=False)
            return rows[0]

        oran_label = "Denklemler ve Eşitsizlikler / Oran - Orantı"
        # geçmişte AI'ın yanlış öğrendiği bütün-etiket kaydı
        home = S.resolve_subject("Temel Matematik", S._subjects_by_key(subs))
        wrong = ExamTopicAlias(scope="tyt", subject_id=home.id if home else None, label_key=_label_key(oran_label),
                               label_raw=oran_label, topic_id=by[("TYT Matematik", "Basit Eşitsizlikler")].id,
                               source=ALIAS_SOURCE_AI, hit_count=3)
        db.add(wrong)
        db.flush()
        r = run(oran_label)
        check("1. yanlış AI sözlük kaydı kuyruğun birebir karşılığını EZEMEZ",
              r.get("topic_id") == by[("TYT Matematik", "Oran ve Orantı")].id, str(r))

        wrong.source = ALIAS_SOURCE_COACH
        db.flush()
        r = run(oran_label)
        check("2. koçun elle düzelttiği kayıt kuyruğu ezer",
              r.get("topic_id") == by[("TYT Matematik", "Basit Eşitsizlikler")].id
              and r.get("topic_source") == "alias", str(r))
        db.delete(wrong)
        db.flush()

        r = run("Anlam Bilgisi / Paragrafta Yapı", "Türkçe")
        check("3. paragraf alt konusu birebir", r.get("topic_id") == by[("TYT Türkçe", "Paragrafta Yapı")].id, str(r))
        r = run("Paragraf", "Türkçe")
        check("4. yalın 'Paragraf' → Paragraf (Karma)",
              r.get("topic_id") == by[("TYT Türkçe", "Paragraf (Karma)")].id, str(r))
        r = run("Dörtgenler ve Çokgenler / Kare")
        check("5. geometri alt konusu (ders başlığı Matematik) → TYT Geometri/Kare",
              r.get("topic_id") == by[("TYT Geometri", "Kare")].id, str(r))
        r = run("Üçgenler / Bilinmeyen Alt Konu")
        check("6. alt konu yoksa ünite başı SON ÇARE → Üçgenler (Karma)",
              r.get("topic_id") == by[("TYT Geometri", "Üçgenler (Karma)")].id, str(r))
        r = run("Uluslararası İlişkilerde Denge Stratejisi (1774-1914) / Osmanlı Dağılma Dönemi (19. Yüzyıl)",
                "Sosyal Bilimler")
        check("7. ünite adı resmi konuysa ona (Tarih 1774-1914)",
              r.get("topic_id") == by[("TYT Tarih", "Uluslararası İlişkilerde Denge Stratejisi (1774-1914)")].id,
              str(r))
        r = run("Din ve İslam", "Sosyal Bilimler")
        check("8. eklenen Din ünitesi birebir",
              r.get("topic_id") == by[("TYT Din Kültürü ve Ahlak Bilgisi", "Din ve İslam")].id, str(r))
        def tid(subj: str, name: str) -> int | None:
            t = by.get((subj, name))
            return t.id if t else None

        r = run("Kimyanın Temel Kanunları ve Kimyasal Hesaplamalar / Mol Kavramı", "Fen Bilimleri")
        check("10. Kimya alt konusu (Mol Kavramı)",
              r.get("topic_id") == tid("TYT Kimya", "Mol Kavramı"), str(r))
        r = run("Hücre / Hücre ve Organeller", "Fen Bilimleri")
        check("11. 'Hücre ve Organeller' → Hücre Organelleri (Karma değil)",
              r.get("topic_id") == tid("TYT Biyoloji", "Hücre Organelleri"), str(r))
        r = run("Hücresel Solunum", "Biyoloji")
        check("12. Enerji konusu eklendi (Hücresel Solunum, Ortak Özellikler'e değil)",
              r.get("topic_id") == tid("TYT Biyoloji", "Hücresel Solunum ve Fermantasyon"), str(r))
        r = run("Kalıtımın Genel İlkeleri / Kalıtım", "Fen Bilimleri")
        check("13. ünite geneli etiket → Kalıtımın Genel İlkeleri (Karma)",
              r.get("topic_id") == tid("TYT Biyoloji", "Kalıtımın Genel İlkeleri (Karma)"), str(r))
        r = run("Enerji", "Fizik")
        check("14. tek kelimelik genel 'Enerji' ön-ekle 'Enerji Kaynakları'na BAĞLANMAZ",
              r.get("topic_id") != tid("TYT Fizik", "Enerji Kaynakları"), str(r))
        r = run("Problemler / Yaş Problemleri")
        check("9. ayraçlı sıradan etiket bozulmadı (Yaş Problemleri)",
              (r.get("topic_name") or "") == "Yaş Problemleri", str(r))
    finally:
        db.rollback()
        db.close()
    print(f"\n=== {passed} passed, {failed} failed ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
