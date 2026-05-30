"""Faz 1 — Tüm Click-to-WhatsApp smoke testlerini sırayla çalıştır + özet.

Kullanım:
    python scripts/run_faz1_smokes.py
    python scripts/run_faz1_smokes.py -v       # her testin tam çıktısı

Çıktı: paket başına PASS/FAIL sayım + toplam + exit kodu.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# Faz 1 paketleri sırasıyla
SMOKE_TESTS = [
    ("P0  Veli bildirim kanalı + KVKK aktivasyon", "test_api_v2_parent_wa_channel.py"),
    ("P1  Telefon altyapısı + /me/phone/*", "test_api_v2_phone_verification.py"),
    ("P2  Admin WhatsApp şablon registry CRUD", "test_api_v2_admin_whatsapp_templates.py"),
    ("P3  Click-to-WA URL üretici + yetki + log", "test_api_v2_messaging_wa_link.py"),
    ("P4  Tekli dialog (kapsamlı 5-kullanıcı)", "test_api_v2_messaging_p4_comprehensive.py"),
    ("P5  Toplu gönderim sihirbazı", "test_api_v2_messaging_bulk.py"),
    ("P6  Spam guard + admin dispatch log", "test_api_v2_messaging_p6_spam_audit.py"),
]


def run_one(label: str, script: str, verbose: bool) -> tuple[bool, int, int, float]:
    """Tek smoke test çalıştır. Dönüş: (success, passed, failed, elapsed_sec)."""
    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), script,
    )
    if not os.path.exists(script_path):
        print(f"  [SKIP] script bulunamadı: {script}")
        return (False, 0, 0, 0.0)

    start = time.time()
    proc = subprocess.run(
        [sys.executable, script_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.time() - start

    out = proc.stdout or ""
    err = proc.stderr or ""

    # "=== Result: N passed, M failed ===" satırını yakala
    passed = 0
    failed = 0
    for line in out.splitlines():
        line_s = line.strip()
        if line_s.startswith("=== Result:") or line_s.startswith("=== SONUÇ"):
            # "=== Result: 14 passed, 0 failed ===" formatı
            import re
            m = re.search(r"(\d+)\s+pass", line)
            if m:
                passed = int(m.group(1))
            m = re.search(r"(\d+)\s+fail", line)
            if m:
                failed = int(m.group(1))
            break

    success = (proc.returncode == 0) and (failed == 0)

    if verbose:
        print(out)
        if err:
            print("--- stderr ---")
            print(err)

    return (success, passed, failed, elapsed)


def main() -> int:
    verbose = "-v" in sys.argv or "--verbose" in sys.argv

    print("=" * 70)
    print("FAZ 1 — Click-to-WhatsApp smoke runner")
    print("=" * 70)
    print()

    total_passed = 0
    total_failed = 0
    overall_ok = True
    results: list[tuple[str, bool, int, int, float]] = []

    for label, script in SMOKE_TESTS:
        print(f"-> {label}")
        ok, p, f, elapsed = run_one(label, script, verbose=verbose)
        results.append((label, ok, p, f, elapsed))
        total_passed += p
        total_failed += f
        if not ok:
            overall_ok = False
        status = "PASS" if ok else "FAIL"
        print(f"   [{status}] {p} passed / {f} failed  ({elapsed:.1f}s)")
        print()

    print("=" * 70)
    print("ÖZET")
    print("=" * 70)
    for label, ok, p, f, elapsed in results:
        marker = "✅" if ok else "❌"
        print(f"  {marker} {label:55s}  {p:>3}/{p+f:<3}  ({elapsed:.1f}s)")
    print()
    print(f"TOPLAM: {total_passed} passed · {total_failed} failed")
    if overall_ok and total_failed == 0:
        print("🎉 Faz 1 — TÜM SMOKE TESTLERİ YEŞİL")
        return 0
    else:
        print("⚠ Bazı testler başarısız — yukarıda detay")
        return 1


if __name__ == "__main__":
    sys.exit(main())
