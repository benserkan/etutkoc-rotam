"""Deneme verisi bütünlük denetimi — SALT OKUMA (prod'da da güvenle koşulur).

Her deneme kaydı için ham veriden BAĞIMSIZ yeniden hesap yapar ve kayıtlı değerle kıyaslar:
  A1 soru satırları (pdf_import) → D/Y/B toplamı = kayıtlı total_correct/wrong/blank
  A2 net = D − Y/ceza (LGS 3, diğerleri 4) — kayıtlı net ile
  A3 subject_nets ders kırılımı toplamı = kayıtlı toplamlar (D/Y/B ve net)
  A4 subject_nets satırında ad boş / şema dışı anahtar
  A5 aynı öğrenci + aynı gün + aynı başlıkta mükerrer kayıt
  A6 soru satırı sonuç kodu bilinmeyen / konu eşleşmesi yüzdesi

  python -m scripts.audit_exam_integrity [--exclude-demo] [--student N]
Çıktı: sorun listesi + özet; kod 0 döner (rapor aracı).
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.models.exam_result import ExamResult, ExamResultQuestion, section_penalty  # noqa: E402

EPS = 0.011


def main() -> None:
    exclude_demo = "--exclude-demo" in sys.argv
    only = None
    if "--student" in sys.argv:
        only = int(sys.argv[sys.argv.index("--student") + 1])
    db = SessionLocal()
    q = db.query(ExamResult)
    if only:
        q = q.filter(ExamResult.student_id == only)
    exams = q.order_by(ExamResult.student_id, ExamResult.exam_date).all()
    names = {u.id: (u.full_name or "", bool(getattr(u, "is_demo", False)))
             for u in db.query(User).filter(User.id.in_({e.student_id for e in exams} or {0}))}
    qrows: dict[int, list] = defaultdict(list)
    ids = [e.id for e in exams]
    for i in range(0, len(ids), 500):
        for r in db.query(ExamResultQuestion).filter(ExamResultQuestion.exam_result_id.in_(ids[i:i + 500])):
            qrows[r.exam_result_id].append(r)

    issues: list[str] = []
    stats = Counter()
    dup = Counter()
    for e in exams:
        nm, demo = names.get(e.student_id, ("?", False))
        if exclude_demo and (demo or "demo" in nm.lower()):
            continue
        stats["exam"] += 1
        tag = f"#{e.id} öğr#{e.student_id} {nm[:18]} · {e.exam_date} · {e.section.value} · {e.import_source or 'manual'} · {e.title[:40]}"
        pen = section_penalty(e.section)
        # A2
        exp_net = round(max(0.0, e.total_correct - e.total_wrong / pen), 2)  # compute_net ile aynı (taban 0)
        if abs(exp_net - float(e.net)) > EPS:
            issues.append(f"A2 net {e.net} ≠ D−Y/{pen:g} = {exp_net} | {tag}")
        # A1
        rows = qrows.get(e.id, [])
        if rows:
            stats["with_rows"] += 1
            res = Counter((r.result or "").lower() for r in rows)
            c, w, b = res.get("dogru", 0), res.get("yanlis", 0), res.get("bos", 0)
            other = sum(v for k, v in res.items() if k not in ("dogru", "yanlis", "bos"))
            if other:
                issues.append(f"A6 bilinmeyen sonuç kodu {dict(res)} | {tag}")
            if (c, w, b) != (e.total_correct, e.total_wrong, e.total_blank):
                issues.append(f"A1 satırlar D/Y/B {c}/{w}/{b} ≠ kayıt {e.total_correct}/{e.total_wrong}/{e.total_blank} | {tag}")
            matched = sum(1 for r in rows if r.topic_id)
            stats["q"] += len(rows)
            stats["q_matched"] += matched
            if matched < len(rows) * 0.8:
                issues.append(f"A6 konu eşleşmesi düşük {matched}/{len(rows)} | {tag}")
        # A3/A4
        if e.subject_nets:
            try:
                sn = json.loads(e.subject_nets)
            except Exception:
                issues.append(f"A4 subject_nets JSON bozuk | {tag}")
                sn = []
            if isinstance(sn, list) and sn:
                sc = sum(int(x.get("correct") or 0) for x in sn)
                sw = sum(int(x.get("wrong") or 0) for x in sn)
                sb = sum(int(x.get("blank") or 0) for x in sn)
                snet = round(sum(float(x.get("net") or 0) for x in sn), 2)
                if any(not (x.get("name") or "").strip() for x in sn):
                    issues.append(f"A4 ders adı boş satır | {tag}")
                if (sc, sw) != (e.total_correct, e.total_wrong):
                    issues.append(f"A3 ders kırılımı D/Y {sc}/{sw} ≠ kayıt {e.total_correct}/{e.total_wrong} | {tag}")
                elif sb != e.total_blank:
                    issues.append(f"A3b ders kırılımı boş {sb} ≠ kayıt {e.total_blank} (alan dışı boş düşmüş olabilir) | {tag}")
                if abs(snet - float(e.net)) > 0.05:
                    issues.append(f"A3c ders netleri toplamı {snet} ≠ net {e.net} | {tag}")
        dup[(e.student_id, e.exam_date, (e.title or "").strip().lower())] += 1
    for k, n in dup.items():
        if n > 1:
            issues.append(f"A5 mükerrer ×{n}: öğr#{k[0]} {k[1]} '{k[2][:40]}'")

    by = Counter(i.split()[0] for i in issues)
    print(f"Deneme: {stats['exam']} · soru satırlı: {stats['with_rows']} · soru: {stats['q']} "
          f"(konu eşli {stats['q_matched']})")
    print("Sorun sayıları:", dict(by) or "yok")
    for i in issues:
        print(" ", i)


if __name__ == "__main__":
    main()
