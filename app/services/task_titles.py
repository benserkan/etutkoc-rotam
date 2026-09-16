"""Kitaplı görev başlığı — TEK MERKEZ (2026-09-16).

Başlık türetilmiş veridir: "Kitap — Bölüm: N test". Kalemler değişince
(haftaya yay sıradaki bölüme geçti, kalem eklendi, sayı değişti) başlık da
YENİDEN üretilmeli; aksi hâlde "Vektörler: 4 test" yazan görevin içinde
Tork ve Denge testleri durur (Taha #84, 2026-09 sahası — 7 görev).

Kurallar:
  · Tek kitap-kalemi  → "Kitap — Bölüm: N test"
  · Aynı kitaptan çok kalem → "Kitap — Bölüm A: n test · Bölüm B: m test"
  · Farklı kitaplardan kalemler → her kalem kendi kitabıyla, " · " ile
  · Kitapsız kalemler (deneme/konu çalışması) başlığa GİRMEZ — onların
    etiketi kalemin kendisinde (label). Hiç kitap kalemi yoksa None döner.
  · `is_auto_title` koçun elle yazdığı başlığı korumak için: yalnız bu
    biçime uyan başlıklar otomatik tazelenir.
"""
from __future__ import annotations

import re
from typing import Iterable

_DENEME_TYPES = ("brans_denemesi", "genel_deneme")
_AUTO_RE = re.compile(r"^.+ — .+: \d+ (test|deneme)( · .+: \d+ (test|deneme))*$")


def unit_word(book) -> str:
    btype = getattr(book, "type", None)
    bval = getattr(btype, "value", btype)
    return "deneme" if bval in _DENEME_TYPES else "test"


def compose_single(book, section, planned_count: int) -> str:
    return f"{book.name} — {section.label}: {planned_count} {unit_word(book)}"


def compose_entries(entries: Iterable[tuple[object, object, int]]) -> str | None:
    """entries = [(book, section, planned_count)] (yalnız kitaplı kalemler)."""
    rows = [(b, s, int(n)) for (b, s, n) in entries if b is not None and s is not None]
    if not rows:
        return None
    if len(rows) == 1:
        b, s, n = rows[0]
        return compose_single(b, s, n)
    books = {id(b) if getattr(b, "id", None) is None else b.id for (b, _, _) in rows}
    if len(books) == 1:
        b = rows[0][0]
        parts = [f"{s.label}: {n} {unit_word(b)}" for (_, s, n) in rows]
        return f"{b.name} — " + " · ".join(parts)
    return " · ".join(compose_single(b, s, n) for (b, s, n) in rows)


def compose_from_task(task) -> str | None:
    """Yüklü ilişkilerle (item.book / item.section) görevin olması gereken
    başlığı üret. Kitap kalemi yoksa None."""
    entries = []
    for it in getattr(task, "book_items", None) or []:
        if it.book_id is None or it.book_section_id is None:
            continue
        book = getattr(it, "book", None)
        section = getattr(it, "section", None)
        if book is None or section is None:
            continue
        entries.append((book, section, it.planned_count or 0))
    return compose_entries(entries)


def is_auto_title(title: str | None) -> bool:
    return bool(title) and _AUTO_RE.match(title.strip()) is not None


def refresh_auto_title(task) -> bool:
    """Başlık otomatik biçimdeyse (veya boş/placeholder) kalemlerden yeniden
    üret. Koçun elle yazdığı serbest başlığa DOKUNMAZ. Değişti mi döner."""
    current = (task.title or "").strip()
    if current and current not in ("Görev", "—") and not is_auto_title(current):
        return False
    new_title = compose_from_task(task)
    if not new_title or new_title == current:
        return False
    task.title = new_title
    return True
