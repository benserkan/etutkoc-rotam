"""İçe aktarılmış denemede ÇİFT SAYILAN ders satırlarını temizle + toplamları
ve ders kırılımını satırlardan yeniden kur.

Vaka (2026-10-11, Yağmur Ongan #224, deneme #200 — CADDEM 12. sınıf CİS-1 TYT):
iki Gemini okuması Din Kültürü / Seçmeli Felsefe derslerini farklı adla yazdı
("TYT_DinKültürü" ↔ "Din Kültürü ve Ahlak Bilgisi", "TYT_Seç. Felsefe" ↔
"Seçmeli Felsefe"); eşanlam kanonu olmadığından merge kovaları ayrışıp 10
soru iki kez kaydedildi (125 → 135 satır; 86D 20Y 19B → 91D 20Y 24B).
Kod düzeltmesi (`_SUBJECT_ALIASES`) yeni aktarımları korur; bu betik kayıtlı
denemeyi onarır.

Kural: aynı deneme içinde kanonik ders anahtarı (`_subject_key`) aynı olan
iki ham ad grubu varsa ve soru numaraları birebir örtüşüyorsa, SONRAKİ grup
(ikinci okumanın kopyası) silinir. Toplamlar/net satırlardan yeniden
hesaplanır; kırılım `rebuild_subject_nets` ile güncel sunum kuralına kurulur.

Kullanım (kuru çalışma varsayılan):
    python -m scripts.fix_exam_duplicate_subject_rows --exam 200
    python -m scripts.fix_exam_duplicate_subject_rows --exam 200 --apply
    python -m scripts.fix_exam_duplicate_subject_rows --scan   # tüm sistemi tara
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

from app.database import SessionLocal
from app.models import ExamResult, User
from app.models.exam_result import (
    EQ_RESULT_BOS, EQ_RESULT_DOGRU, EQ_RESULT_YANLIS, ExamResultQuestion,
    compute_net,
)
from app.services.exam_import_service import _subject_key, rebuild_subject_nets


def duplicate_groups(questions: list[ExamResultQuestion]) -> list[tuple[str, str, list[ExamResultQuestion]]]:
    """[(kanonik anahtar, silinecek ham ad, silinecek satırlar)]"""
    by_key: dict[str, dict[str, list[ExamResultQuestion]]] = defaultdict(lambda: defaultdict(list))
    for q in questions:
        by_key[_subject_key(q.subject_name_raw)][(q.subject_name_raw or "").strip()].append(q)
    out = []
    for key, raws in by_key.items():
        if len(raws) < 2:
            continue
        # ilk görünen ham ad KALIR (id sırası), diğerleri numara kümesi
        # birebir örtüşüyorsa kopyadır
        ordered = sorted(raws.items(), key=lambda kv: min(q.id for q in kv[1]))
        keep_raw, keep_rows = ordered[0]
        keep_nos = sorted(q.question_no for q in keep_rows)
        for raw, rows in ordered[1:]:
            nos = sorted(q.question_no for q in rows)
            if nos == keep_nos:
                out.append((key, raw, rows))
            else:
                print(f"  ! {key!r}: {raw!r} numaraları {keep_raw!r} ile örtüşmüyor "
                      f"({nos} vs {keep_nos}) — DOKUNULMADI, elle bak")
    return out


def repair(db, exam: ExamResult, apply: bool) -> bool:
    qs = sorted(exam.questions, key=lambda q: q.id)
    dups = duplicate_groups(qs)
    print(f"#{exam.id} {exam.exam_date} {exam.title!r} satır={len(qs)} "
          f"D/Y/B={exam.total_correct}/{exam.total_wrong}/{exam.total_blank} net={exam.net}")
    if not dups:
        print("  kopya grup yok")
        return False
    drop_ids: set[int] = set()
    for key, raw, rows in dups:
        print(f"  kopya: {raw!r} (kanon {key!r}) → {len(rows)} satır silinecek")
        drop_ids.update(q.id for q in rows)
    kept = [q for q in qs if q.id not in drop_ids]
    c = sum(1 for q in kept if q.result == EQ_RESULT_DOGRU)
    y = sum(1 for q in kept if q.result == EQ_RESULT_YANLIS)
    b = sum(1 for q in kept if q.result == EQ_RESULT_BOS)
    net = compute_net(c, y, exam.section)
    print(f"  sonra: satır={len(kept)} D/Y/B={c}/{y}/{b} net={net}")
    if not apply:
        print("  (kuru çalışma — --apply ile uygula)")
        return False
    db.query(ExamResultQuestion).filter(ExamResultQuestion.id.in_(drop_ids)).delete(
        synchronize_session=False)
    db.flush()
    db.expire(exam, ["questions"])
    exam.total_correct, exam.total_wrong, exam.total_blank, exam.net = c, y, b, net
    try:
        meta = json.loads(exam.analysis_meta) if exam.analysis_meta else {}
    except ValueError:
        meta = {}
    meta["suspect_count"] = sum(1 for q in exam.questions if q.is_suspect)
    meta["dedup_repaired_rows"] = len(drop_ids)
    exam.analysis_meta = json.dumps(meta, ensure_ascii=False)
    student = db.get(User, exam.student_id)
    rebuild_subject_nets(db, exam, student)
    db.commit()
    db.refresh(exam)
    print(f"  UYGULANDI: satır={len(exam.questions)} D/Y/B="
          f"{exam.total_correct}/{exam.total_wrong}/{exam.total_blank} net={exam.net}")
    for row in json.loads(exam.subject_nets or "[]"):
        print("   ", row)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exam", type=int, help="tek deneme id")
    ap.add_argument("--scan", action="store_true", help="tüm pdf_import denemeleri tara")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        if a.exam:
            exams = [db.get(ExamResult, a.exam)]
            if exams[0] is None:
                print("deneme yok")
                return 1
        elif a.scan:
            exams = (db.query(ExamResult)
                     .filter(ExamResult.import_source == "pdf_import")
                     .order_by(ExamResult.id).all())
        else:
            ap.print_help()
            return 1
        touched = 0
        for e in exams:
            if not e.questions:
                continue
            if repair(db, e, a.apply):
                touched += 1
        print(f"\n{len(exams)} deneme bakıldı, {touched} onarıldı")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
