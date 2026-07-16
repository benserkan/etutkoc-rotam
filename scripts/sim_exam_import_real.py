"""GERÇEK PDF + GERÇEK Gemini ile deneme içe aktarma hattını uçtan uca dene.

Salt-okuma benzeri: analyze çağrılır ama COMMIT EDİLMEZ (alias sayaçları dahil
hiçbir şey kalıcılaşmaz); geçici öğrenci de kaydedilmez (flush-only + rollback).

Kullanım:
  PYTHONPATH=. python scripts/sim_exam_import_real.py "D:/yol/deneme.pdf" [grade]

Maliyet: 2 ücretli Gemini okuma (personal_data=True) + eşleşmeyen etiketler
için ücretsiz kapalı-küme çağrıları. Kredi DÜŞMEZ (router dışı doğrudan çağrı).
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from pathlib import Path

from app.database import SessionLocal
from app.models import User, UserRole
from app.services import exam_import_service as svc


def main() -> int:
    if len(sys.argv) < 2:
        print("Kullanım: sim_exam_import_real.py <pdf-yolu> [sınıf=12]")
        return 2
    pdf_path = Path(sys.argv[1])
    grade = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    pdf = pdf_path.read_bytes()
    print(f"PDF: {pdf_path.name} ({len(pdf)/1024:.0f} KB) · öğrenci sınıfı={grade}")

    with SessionLocal() as db:
        student = User(
            email="sim-exam-import@t.invalid", password_hash="x",
            full_name="Sim Öğrenci", role=UserRole.STUDENT,
            is_active=True, grade_level=grade, must_change_password=False,
        )
        db.add(student)
        db.flush()  # id gerekir; COMMIT YOK → iz kalmaz
        try:
            print("Gemini çift okuma başlıyor (60-120 sn)…")
            d = svc.analyze(db, student, pdf)
        finally:
            db.rollback()

    print("\n=== KİMLİK/TESPİT ===")
    print(f"  başlık   : {d['title']}")
    print(f"  tarih    : {d['exam_date']} · sınıf ipucu: {d['grade_hint']}")
    print(f"  tespit   : {d['universe']} / {d['section_label']} · kapsam={d['scope']}"
          f" · güven={d['confidence']}")
    if d.get("score_info"):
        print(f"  puan     : {d['score_info']}")

    print("\n=== DERS ÖZETLERİ (satırlardan; doc_net = belgedeki net) ===")
    for s in d["subjects"]:
        print(f"  {s['name']:<22} {s['questions']:>3} soru · {s['correct']}D "
              f"{s['wrong']}Y {s['blank']}B · net {s['net']}"
              f" (belge: {s['doc_net']})")

    st = d["match_stats"]
    total = len(d["rows"])
    print(f"\n=== NORMALİZASYON: {total} soru → sözlük {st['alias']} · "
          f"deterministik {st['auto']} · AI {st['ai']} · eşleşmedi {st['none']} ===")
    print(f"  şüpheli hücre: {d['suspect_count']}")

    print("\n=== İÇ TUTARLILIK KONTROLLERİ ===")
    for c in d["checks"]:
        mark = "OK " if c["ok"] else "FAIL"
        print(f"  [{mark}] {c['label']} — {c['detail']}")

    print("\n=== EŞLEŞMEYEN ETİKETLER (varsa koç önizlemede bağlar) ===")
    unmatched = {}
    for r in d["rows"]:
        if r["topic_id"] is None:
            key = (r.get("subject_name") or r.get("subject_raw"), r["topic_raw"])
            unmatched[key] = unmatched.get(key, 0) + 1
    if not unmatched:
        print("  (yok — tüm konular eşlendi)")
    for (subj, label), n in sorted(unmatched.items(), key=lambda x: -x[1]):
        print(f"  {subj}: '{label}' × {n}")

    print("\n=== ÖRNEK SATIRLAR (ders başına ilk 3) ===")
    seen: dict = {}
    for r in d["rows"]:
        k = r.get("subject_name") or r.get("subject_raw")
        seen[k] = seen.get(k, 0) + 1
        if seen[k] > 3:
            continue
        sus = " (ŞÜPHELİ)" if r["is_suspect"] else ""
        print(f"  [{k}] #{r['question_no']} '{r['topic_raw']}' → "
              f"{r['topic_name'] or '—'} [{r['topic_source']}] · "
              f"DC={r['correct_answer']} ÖC={r['student_answer']} → {r['result']}{sus}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
