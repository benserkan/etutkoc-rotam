"""GÖREV / TEST / DENEME — kontrol mekanizması (tek komut).

Kullanıcı (2026-06-02): "Ya ben sürekli bu kartların doğruluğunu mu sorgulayacağım,
yok mu bir kontrol mekanizması." → Bu runner görev/test/deneme ayrımını + kart
tutarlılığını + projeksiyon izolasyonunu doğrulayan TÜM testleri sırayla koşar.
Görev/test/deneme veya kart-sayısı mantığını değiştiren her işten sonra çalıştır:

    PYTHONPATH=. python scripts/run_gorev_checks.py
    PYTHONPATH=. python scripts/run_gorev_checks.py -v   # tam çıktı

Tümü PASS değilse exit kodu 1 (CI/regresyon için).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CHECKS = [
    ("Çekirdek sınıflandırma (görev/test/deneme/etkinlik)", "test_gorev_stats.py"),
    ("KART TUTARLILIK (5 yüzey aynı sayı + deneme≠test)", "test_card_consistency.py"),
    ("Projeksiyon izolasyon (deneme envanteri girmez)", "test_projection_tests_only.py"),
    ("Boş-gün eşiği 3 + günlük özet kaldırıldı", "test_daily_empty_threshold.py"),
    ("Hafta görev-% + Veliye duyur önizleme", "test_api_v2_teacher_week_activity_pct.py"),
]


def run_one(script: str, verbose: bool):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script)
    if not os.path.exists(path):
        return (False, 0, 0, 0.0, "script yok")
    start = time.time()
    proc = subprocess.run(
        [sys.executable, path], capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONPATH": os.path.dirname(os.path.dirname(path))},
    )
    elapsed = time.time() - start
    out = proc.stdout or ""
    passed = failed = 0
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("=== ") and ("passed" in s or "PASS" in s or "SONUÇ" in s):
            m = re.search(r"(\d+)\s*(?:passed|/)", s)
            if m:
                passed = int(m.group(1))
            m2 = re.search(r"(\d+)\s*failed", s)
            if m2:
                failed = int(m2.group(1))
    success = (proc.returncode == 0) and (failed == 0)
    if verbose:
        print(out)
        if proc.stderr:
            print("--- stderr ---\n" + proc.stderr)
    return (success, passed, failed, elapsed, "")


def main() -> int:
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    print("=" * 68)
    print("GÖREV / TEST / DENEME — kontrol mekanizması")
    print("=" * 68)
    results = []
    ok_all = True
    tot_p = tot_f = 0
    for label, script in CHECKS:
        print(f"\n-> {label}")
        ok, p, f, el, note = run_one(script, verbose)
        results.append((label, ok, p, f, el, note))
        tot_p += p
        tot_f += f
        ok_all = ok_all and ok
        print(f"   [{'PASS' if ok else 'FAIL'}] {p} passed / {f} failed ({el:.1f}s){(' — ' + note) if note else ''}")
    print("\n" + "=" * 68)
    for label, ok, p, f, el, note in results:
        print(f"  {'✅' if ok else '❌'} {label}: {p}/{p + f}")
    print("=" * 68)
    if ok_all:
        print(f"🎉 KONTROL TEMİZ — {tot_p}/{tot_p} · 0 başarısız")
    else:
        print(f"⚠️  {tot_f} başarısız — kart/görev mantığı bozulmuş olabilir.")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
