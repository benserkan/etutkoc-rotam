"""Kazanım cümlesi → alt konu kesin kuralı (Beril #86 viraj.pdf, 2026-11-10).

Öğrenilmiş YZ sözlüğü "ana fikir / yardımcı fikir / söz sanatı" kazanımlarını alt konular
eklenmeden önce genel "Paragrafta Anlam"a bağlamıştı. Kural katmanı öncelikli; aynı ad başka
derste de varsa (TYT/LGS) öğrencinin dersi seçilir; belirsizse bağlamaz.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from app.services.exam_import_service import _kazanim_rule  # noqa: E402


class T:
    def __init__(self, i, n, sid):
        self.id, self.name, self.subject_id = i, n, sid


ts = [T(1, "Paragrafta Ana Düşünce", 5), T(2, "Paragrafta Yardımcı Düşünce", 5), T(3, "Söz Sanatları", 5),
      T(4, "Hikâye Unsurları ve Anlatıcı", 5), T(5, "Paragrafta Anlam", 5),
      T(11, "Paragrafta Ana Düşünce", 9), T(12, "Söz Varlığı (Deyim ve Atasözleri)", 5)]
cases = [
    ("Metnin ana fikrini/ana duygusunu belirler.", 5, 1),
    ("Metindeki yardımcı fikirleri belirler.", 5, 2),
    ("Metindeki söz sanatlarını tespit eder.", 5, 3),
    ("Okuduğu metinlerdeki hikâye unsurlarını belirler.", 5, 4),
    ("Deyim, atasözü ve özdeyişlerin metne katkısını belirler.", 5, 12),
    ("Metnin içeriğini yorumlar.", 5, None),
    ("Metnin ana fikrini belirler.", 9, 11),          # aynı ad başka derste → öğrencinin dersi
    ("Metnin ana fikrini belirler.", None, None),      # ders belirsiz + iki aday → bağlama
]
ok = 0
for label, sid, exp in cases:
    r = _kazanim_rule(label, ts, sid)
    got = r.id if r else None
    good = got == exp
    ok += good
    print(f"  [{'PASS' if good else 'FAIL'}] {label!r} ders={sid} → {got} (beklenen {exp})")
print(f"\n{ok} passed · {len(cases) - ok} failed")
sys.exit(0 if ok == len(cases) else 1)
