"""Kopuk tetikleyici denetimi — 'çalıştırılması beklenen' servis fonksiyonları
yalnızca script/test'ten mi çağrılıyor (app route/cron/dep'ten DEĞİL)?

feature_discovery.run_scan deseninin kardeşlerini bulur: kod var, çalışıyor,
ama canlı app'te hiçbir yerden tetiklenmiyor.
"""
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP = Path("app")
SVC = APP / "services"
SEP = os.sep

TRIGGER = re.compile(
    r"^(run_|scan_|evaluate_|refresh_|sync_|rebuild_|recompute_|generate_|"
    r"backfill_|reconcile_|process_|expire_|dispatch_|record_daily|send_)"
)
EXTRA = {"record_daily_snapshots", "run_all", "evaluate_all", "run_scan", "discover_all"}

# trigger-stili public fonksiyon -> modül
defs: dict[str, str] = {}
for p in SVC.glob("*.py"):
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and (TRIGGER.match(n.name) or n.name in EXTRA):
            defs.setdefault(n.name, p.stem)


def count(name: str, files) -> int:
    pat = re.compile(r"\b" + re.escape(name) + r"\s*\(")
    c = 0
    for p in files:
        try:
            c += len(pat.findall(p.read_text(encoding="utf-8")))
        except OSError:
            continue
    return c


app_files = [p for p in APP.rglob("*.py") if (SEP + "services" + SEP) not in str(p)]
svc_files = list(SVC.glob("*.py"))
script_files = list(Path("scripts").glob("*.py"))

print("=== Tetikleyici-stili servis fonksiyonları ===")
print("(app = route/cron/dep çağrısı · svc = başka servis · script = script/test)\n")
orphans = []
ok = 0
for name, mod in sorted(defs.items()):
    a = count(name, app_files)
    s = count(name, svc_files) - 1  # kendi tanımını çıkar
    k = count(name, script_files)
    if a == 0 and s <= 0:
        flag = " <-- KOPUK (canlı app'ten tetiklenmiyor)" if k > 0 else " <-- HİÇ çağrılmıyor"
        orphans.append(f"  {name:30s} [{mod:26s}] app={a} svc={max(s,0)} script={k}{flag}")
    else:
        ok += 1

if orphans:
    for o in orphans:
        print(o)
else:
    print("  (kopuk tetikleyici yok — hepsi route/cron/servisten çağrılıyor)")
print(f"\nÖzet: {len(defs)} tetikleyici fonksiyon · {ok} bağlı · {len(orphans)} şüpheli")
