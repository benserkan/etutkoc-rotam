"""İçe aktarılmış bir denemeyi KARNE GERÇEK satırlarıyla düzelt (yerine yaz).

Kullanım:
  python -m scripts.fix_exam_from_truth <exam_id> <truth.json> [--apply]

truth.json: {"subjects":[...], "rows":[{subject, no, topic, dc, oc, result}]}
(karne PDF'inin metin katmanından çıkarılır). Kuru çalışma varsayılan.

Kurallar:
  - Konu eşleşmesi KAYITLI satırdan korunur (build_edit_draft — eşleşmemişler
    güncel taksonomi + sözlükle yeniden denenir); karnede olup kayıtta olmayan
    satır aynı ham etiketli başka satırın konusunu alır.
  - "iptal" (DC=X) soru karnede DOĞRU sayılır → dogru.
  - Net / toplamlar / ders kırılımı update_imported ile satırlardan yeniden
    hesaplanır; PDF kanıtı ve soru sayısı dışı alanlar korunur.
"""
from __future__ import annotations

import json
import sys

from app.database import SessionLocal
from app.models import ExamResult, User
from app.services import exam_import_service as svc


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    exam_id, path = int(args[0]), args[1]
    truth = json.load(open(path, encoding="utf-8"))

    with SessionLocal() as db:
        exam = db.get(ExamResult, exam_id)
        student = db.get(User, exam.student_id)
        actor = db.get(User, exam.created_by_id) if exam.created_by_id else student
        draft = svc.build_edit_draft(db, student, exam)

        def key(subj, no):
            return (svc._subject_key(subj), int(no) if no is not None else None)

        saved = {key(r["subject_raw"], r["question_no"]): r for r in draft["rows"]}
        by_label = {}
        for r in draft["rows"]:
            if r.get("topic_id") and r.get("topic_raw"):
                by_label.setdefault(r["topic_raw"].strip(), r["topic_id"])

        rows, changed, added = [], 0, 0
        for t in truth["rows"]:
            res = "dogru" if t["result"] == "iptal" else t["result"]
            dc = (t.get("dc") or "").upper() or None
            oc = (t.get("oc") or "").upper() or None
            s = saved.get(key(t["subject"], t["no"]))
            if s is None:
                added += 1
                tid = by_label.get((t.get("topic") or "").strip())
                print(f"  + eklendi {t['subject']} {t['no']} ({res}) konu={tid}")
            else:
                tid = s.get("topic_id")
                if (s.get("result"), s.get("correct_answer"), s.get("student_answer")) != (res, dc, oc):
                    changed += 1
                    print(f"  ~ {t['subject']:<28} {t['no']:>3}: "
                          f"{s.get('correct_answer')}/{s.get('student_answer')} {s.get('result')} → "
                          f"{dc}/{oc} {res}")
            rows.append({
                "subject_raw": t["subject"], "question_no": t["no"],
                "topic_raw": (s or {}).get("topic_raw") or t.get("topic"),
                "topic_id": tid, "correct_answer": dc, "student_answer": oc,
                "result": res, "is_suspect": False, "manually_edited": False,
            })
        extra = set(saved) - {key(t["subject"], t["no"]) for t in truth["rows"]}
        print(f"değişen {changed} · eklenen {added} · kayıtta fazla {len(extra)}")
        D = sum(r["result"] == "dogru" for r in rows)
        Y = sum(r["result"] == "yanlis" for r in rows)
        B = sum(r["result"] == "bos" for r in rows)
        print(f"önce {exam.total_correct}D {exam.total_wrong}Y {exam.total_blank}B net {exam.net}")
        print(f"sonra {D}D {Y}Y {B}B · bağlı konu {sum(1 for r in rows if r['topic_id'])}/{len(rows)}")
        if not apply:
            print("KURU ÇALIŞMA — yazmak için --apply")
            return
        payload = {"title": exam.title, "exam_date": exam.exam_date.isoformat(),
                   "section": exam.section.value, "rows": rows,
                   "grade_hint": draft.get("grade_hint"), "scope": draft.get("scope")}
        svc.update_imported(db, student, exam, payload, actor=actor)
        db.commit()
        db.refresh(exam)
        print(f"YAZILDI: {exam.total_correct}D {exam.total_wrong}Y {exam.total_blank}B net {exam.net}")


if __name__ == "__main__":
    main()
