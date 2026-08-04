# -*- coding: utf-8 -*-
"""Moment (bağlamsal uyarı) kontrol paketi — TEK KOMUT (Faz D, 2026-08-04).

KURAL: bağlamsal kart/uyarı mantığına (görünürlük koşulu, sinyal taşıyan uç,
moment kaydı, sessizlik taraması, yükseltme anı, deneme değer sayacı, kredi
paketi) dokunan HER değişiklikten sonra bu koşulur:

    python scripts/run_moment_checks.py

Kırmızıysa bir uyarı yüzeyi bozulmuştur — deploy YASAK.
(run_gorev_checks.py deseni.)
"""
from __future__ import annotations

import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SUITES = [
    ("Moment sağlık (iz + sessizlik + alarm)", "scripts/test_moment_health.py"),
    ("Yükseltme anı + deneme değer sayacı", "scripts/test_api_v2_faz2_moments.py"),
    ("Kredi ek paketi + iptal anketi", "scripts/test_api_v2_credit_packs.py"),
    ("Deneme/paywall banner durumu", "scripts/test_api_v2_teacher_trial_status.py"),
]


def main() -> int:
    results = []
    for label, path in SUITES:
        print(f"\n>>> {label} ({path})")
        proc = subprocess.run([sys.executable, path])
        results.append((label, proc.returncode == 0))

    print("\n" + "=" * 60)
    ok = True
    for label, passed in results:
        mark = "GEÇTİ" if passed else "KALDI"
        if not passed:
            ok = False
        print(f"  [{mark}] {label}")
    print("=" * 60)
    print("SONUÇ:", "TÜM MOMENT KONTROLLERİ YEŞİL" if ok
          else "KIRMIZI — uyarı yüzeyi bozulmuş olabilir, deploy etme!")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
