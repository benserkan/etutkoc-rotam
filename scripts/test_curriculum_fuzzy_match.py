"""Esnek eşleştirme katmanı (2026-10-28) — kullanıcı kuralı: birebir ad şartı YOK,
ama belirsizlikte ASLA bağlanmaz. Builtin müfredat konuları üstünde saf fonksiyon testi."""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import Subject, Topic
from app.services import curriculum_mapping as cm

passed, failed = 0, []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label} ({detail})")


def index(db, subject: str, grade: int | None = None):
    ts = (db.query(Topic).join(Subject)
          .filter(Subject.name == subject, Subject.is_builtin.is_(True)).all())
    parents = {t.parent_id for t in ts if t.parent_id}
    ts = [t for t in ts if t.id not in parents
          and (grade is None or t.grade_level in (None, grade))]
    return cm._topics_by_norm(ts)


def res(label, idx):
    m = cm.resolve_label(label, idx)
    return (m.topic.name, m.source) if m else None


with SessionLocal() as db:
    tr = index(db, "Türkçe", 8)
    tm = index(db, "TYT Matematik")
    print("== Kullanıcı vakası (Sözel Mantık)")
    for lab in ["Sözel Mantık ve Muhakeme", "Mantık – Muhakeme Soruları",
                "Sözel Mantık Muhakeme", "Mantık Soruları", "Akıl Yürütme Soruları"]:
        r = res(lab, tr)
        check(f"'{lab}' → Sözel Mantık", r and r[0] == "Sözel Mantık", str(r))
    r = res("Görsel Tablo Grafik Yorumlama", tr)
    check("tek sözcüğü farklı (Yorumlama/Okuma) → Görsel, Tablo ve Grafik Okuma",
          r and r[0] == "Görsel, Tablo ve Grafik Okuma", str(r))
    r = res("Bölünebilme Kuralları Testleri", tm)
    check("parça etiket → Bölme ve Bölünebilme", r and r[0] == "Bölme ve Bölünebilme", str(r))
    print("== Korumalar (bağlanMAMALI)")
    for lab, why in [
        ("Asal Çarpanlara Ayırma ve Bölen Sayısı", "çok fazla anlamlı sözcük"),
        ("Asal Çarpanlara Ayırma", "fazla sözcük başka konunun adı (Asal Sayılar)"),
        ("İkinci Dereceden Denklemler", "karşıtlık: ikinci ≠ birinci"),
        ("II. Dereceden Denklemler", "Roma rakamı karşıtlığı"),
        ("Yüzde ve Kâr-Zarar Problemleri", "etikette iki ayrı konu"),
        ("Denklemler", "birden çok konunun parçası"),
        ("Sayılar", "geniş sözcük tek başına"),
        ("test 1", "anlamsız etiket"),
    ]:
        r = res(lab, tm)
        check(f"'{lab}' bağlanmaz ({why})", r is None or r[1] in ("exact", "tail"), str(r))
    r = res("Problemler", tm)
    check("'Problemler' yalnız birebir 'Problemler (Karma)'ya", r and r[1] == "exact", str(r))

print(f"\n=== {passed} passed, {len(failed)} failed ===")
sys.exit(0 if not failed else 1)
