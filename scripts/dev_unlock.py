"""Dev veritabanı kilidini çöz — yetim test süreçlerini temizler (2026-09-05).

NEDEN: bir smoke testi yarıda kesilince (timeout / TaskStop / Ctrl-C) Windows'ta
python ÇOCUK süreci yaşamaya devam ediyor ve dev SQLite dosyasını açık bir
transaction ile tutuyor. Sonraki her test/istek "database is locked" ile
saatlerce asılı kalabiliyor — ve sebebi görünmüyor.

Bu araç:
  1. lgs.db'yi tutan YETİM python süreçlerini bulur (yalnız `scripts/...` veya
     pytest komut satırlıları — çalışan dev sunucusuna DOKUNMAZ),
  2. ister öldürür, ister sadece raporlar,
  3. artık journal/WAL dosyalarını temizler,
  4. yazma erişimini fiilen doğrular.

Çalıştırma:
  python -m scripts.dev_unlock            # teşhis (hiçbir şey öldürmez)
  python -m scripts.dev_unlock --kill     # yetim test süreçlerini öldür
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Bu desenleri taşıyan python süreçleri "test artığı" sayılır. Dev sunucusu
# (uvicorn / run_dev_patched) BİLİNÇLİ olarak listede yok — onu asla öldürmeyiz.
TEST_MARKERS = ("scripts/test_", "scripts\\test_", "scripts.test_", "pytest")
SERVER_MARKERS = ("uvicorn", "run_dev_patched", "app.main")


# Bu makinede `powershell` PATH'te YOK (Git Bash'ten çağrılamıyor) — tam yol
# denenmeden araç sessizce "0 süreç" raporluyordu. Sırayla dene, ilk çalışanı kullan.
_PS_CANDIDATES = (
    os.path.join(
        os.environ.get("SystemRoot", "C:" + os.sep + "Windows"),
        "System32", "WindowsPowerShell", "v1.0", "powershell.exe",
    ),
    os.path.join("C:" + os.sep, "Program Files", "PowerShell", "7", "pwsh.exe"),
    "powershell",
    "pwsh",
)


def _powershell(cmd: str) -> str:
    for exe in _PS_CANDIDATES:
        try:
            out = subprocess.run(
                [exe, "-NoProfile", "-Command", cmd],
                capture_output=True, text=True, timeout=30,
            )
        except (FileNotFoundError, NotADirectoryError, OSError):
            continue
        except Exception:
            continue
        if out.stdout:
            return out.stdout
    return ""


def find_orphans() -> list[tuple[int, str]]:
    """(pid, komut satırı) — DB'yi tutuyor olabilecek test süreçleri."""
    rows: list[tuple[int, str]] = []
    if os.name != "nt":
        try:
            out = subprocess.run(
                ["ps", "-eo", "pid,args"], capture_output=True, text=True, timeout=20
            ).stdout
        except Exception:
            return rows
        for line in out.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            pid_s, _, args = line.partition(" ")
            if not pid_s.isdigit() or "python" not in args:
                continue
            if any(m in args for m in SERVER_MARKERS):
                continue
            if any(m in args for m in TEST_MARKERS):
                rows.append((int(pid_s), args.strip()))
        return rows

    raw = _powershell(
        "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
        "ForEach-Object { $age = [int]((Get-Date) - $_.CreationDate).TotalSeconds; "
        "\"$($_.ProcessId)|$age|$($_.CommandLine)\" }"
    )
    parsed: list[tuple[int, int, str]] = []
    for line in raw.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3 or not parts[0].strip().isdigit():
            continue
        pid_i = int(parts[0].strip())
        age_i = int(parts[1]) if parts[1].strip().lstrip("-").isdigit() else 0
        cmd_s = parts[2].strip()
        if any(m in cmd_s for m in SERVER_MARKERS):
            continue
        if any(m in cmd_s for m in TEST_MARKERS):
            parsed.append((pid_i, age_i, cmd_s))
    return [(pid_i, f"[{age_i}sn] {cmd_s}") for pid_i, age_i, cmd_s in parsed]



def kill(pid: int) -> bool:
    try:
        if os.name == "nt":
            # `powershell` PATH'te olmayabilir → aynı aday listesi
            for exe in _PS_CANDIDATES:
                try:
                    subprocess.run(
                        [exe, "-NoProfile", "-Command",
                         f"Stop-Process -Id {pid} -Force -ErrorAction Stop"],
                        capture_output=True, timeout=20,
                    )
                    return True
                except OSError:
                    continue
            return False
        else:
            os.kill(pid, 9)
        return True
    except Exception:
        return False


def sweep_journals() -> list[str]:
    """Sahipsiz journal/WAL artıklarını sil (aktif bağlantı varsa dokunmaz)."""
    removed: list[str] = []
    for name in ("lgs.db-journal", "lgs.db-wal", "lgs.db-shm"):
        if not os.path.exists(name):
            continue
        try:
            os.remove(name)
            removed.append(name)
        except OSError:
            pass  # hâlâ açık — normal, WAL'da yaşayan dosya olabilir
    return removed


def probe_write() -> tuple[bool, str]:
    """Yazma erişimini FİİLEN dene (rapor 'iyi' derken kilit kalmasın)."""
    try:
        from sqlalchemy import text

        from app.database import SessionLocal

        db = SessionLocal()
        try:
            db.execute(text("create table if not exists _dev_unlock_probe(x int)"))
            db.commit()
            db.execute(text("drop table _dev_unlock_probe"))
            db.commit()
            return True, "yazma OK"
        finally:
            db.close()
    except Exception as e:
        return False, str(e).splitlines()[0][:160]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kill", action="store_true",
                    help="Yetim test süreçlerini öldür (varsayılan: yalnız rapor)")
    ap.add_argument("--force", action="store_true",
                    help="DB kilitli olmasa da öldür (dikkat: koşan testi keser)")
    args = ap.parse_args()

    # ÖNCE durumu ölç: DB zaten sağlamsa öldürecek bir şey YOK — o an koşan
    # meşru bir testi kesmeyelim. Bu kontrol olmadan araç kendi ayağına sıkar.
    ok_before, msg_before = probe_write()
    orphans = find_orphans()
    print(f"Yetim test sureci : {len(orphans)}")
    for pid, cmd in orphans:
        print(f"  #{pid}  {cmd[:110]}")

    if orphans and not args.kill:
        print("\nTeshis modu - hicbir sey oldurulmedi. Uygulamak icin: --kill")

    if args.kill and ok_before and not args.force:
        print("\nDB zaten YAZILABILIR - oldurulecek bir sey yok.")
        print("Listedeki surecler muhtemelen SU AN kosan testler; kesmiyoruz.")
        print("Yine de zorlamak icin: --kill --force")
        return 0

    if args.kill:
        for pid, _ in orphans:
            print(("  oldurdu  " if kill(pid) else "  olduremedi ") + str(pid))
        removed = sweep_journals()
        if removed:
            print("Silinen artik dosya:", ", ".join(removed))

    ok, msg = (probe_write() if args.kill else (ok_before, msg_before))
    print(f"DB durumu         : {'IYI' if ok else 'KILITLI'} ({msg})")
    if not ok and not args.kill:
        print("Cozum: python -m scripts.dev_unlock --kill")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
