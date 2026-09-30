"""Kişi adı biçimi — tek merkez.

Kural: her sözcüğün ilk harfi büyük, kalanı küçük; Türkçe harf eşlemesiyle
(i→İ, ı→I, I→ı, İ→i). Tireli adların her parçası ayrı büyük başlar
("ayşe-nur" → "Ayşe-Nur"). Fazla boşluklar tek boşluğa iner.

  "Güneş deridüzen"  → "Güneş Deridüzen"
  "İSMAİL EYMEN"     → "İsmail Eymen"
  "ışıl ılgaz"       → "Işıl Ilgaz"
"""
from __future__ import annotations

_UPPER = {"i": "İ", "ı": "I"}
_LOWER = {"I": "ı", "İ": "i"}


def _tr_upper(ch: str) -> str:
    return _UPPER.get(ch) or ch.upper()


def _tr_lower(s: str) -> str:
    return "".join(_LOWER.get(c) or c.lower() for c in s)


def _cap(part: str) -> str:
    if not part:
        return part
    return _tr_upper(part[0]) + _tr_lower(part[1:])


def format_person_name(name: str | None) -> str | None:
    """Adı standart biçime getirir; boş/None → None."""
    if name is None:
        return None
    words = name.split()
    if not words:
        return None
    return " ".join("-".join(_cap(p) for p in w.split("-")) for w in words)
