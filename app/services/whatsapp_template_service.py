"""P2 — WhatsApp şablon servisi (render + helper'lar).

Tek bağımsız sorumluluk: `render_preview(template, values, defs)` — `{{key}}`
değişkenlerini doldurup metin döndürür + uyarı listesi (eksik/bilinmeyen
anahtarlar). Click-to-WA URL üretimi (P3) bu rendered metni kullanır.

Sözdizimi: `{{key}}` (iki süslü). Tek `{` veya `{...}` yok sayılır (Jinja
desenli; UI tutarlı). Bu seçim bilinçli — WhatsApp/wa.me URL encoding'de
özel karakter problemi yaratmaz.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass


# `{{ key }}` veya `{{key}}` — boşluk toleranslı
TEMPLATE_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


@dataclass
class PreviewResult:
    rendered: str
    warnings: list[str]
    used_keys: list[str]
    missing_keys: list[str]
    unknown_keys: list[str]


def extract_template_keys(template: str) -> list[str]:
    """Şablon metnindeki tüm `{{key}}` anahtarlarını sırayla döndürür (uniq)."""
    seen: list[str] = []
    for m in TEMPLATE_VAR_RE.finditer(template or ""):
        k = m.group(1)
        if k not in seen:
            seen.append(k)
    return seen


def render_preview(
    template: str,
    values: dict[str, str] | None = None,
    variable_defs: list[dict] | None = None,
) -> PreviewResult:
    """Şablonu doldurup metin + uyarıları döndür.

    - `values[key]` doluysa onu yaz
    - yoksa `variable_defs` listesinde key bulunursa example'ı yaz
    - hiçbiri yoksa `{{key}}` olarak bırak + warning
    """
    values = values or {}
    defs_list = variable_defs or []
    def_examples: dict[str, str] = {}
    for d in defs_list:
        if not isinstance(d, dict):
            continue
        k = d.get("key")
        if isinstance(k, str):
            def_examples[k] = str(d.get("example") or "")

    used_keys = extract_template_keys(template)
    defined_keys = set(def_examples.keys())

    warnings: list[str] = []
    missing_keys: list[str] = []   # defs'te var ama template'de yok
    unknown_keys: list[str] = []   # template'de var ama defs'te yok

    for k in used_keys:
        if k not in defined_keys:
            unknown_keys.append(k)
            warnings.append(
                f"Şablonda kullanılan '{{{{{k}}}}}' tanım listesinde yok."
            )

    for k in defined_keys:
        if k not in used_keys:
            missing_keys.append(k)

    def replacer(m: re.Match[str]) -> str:
        k = m.group(1)
        if k in values and str(values[k]).strip():
            return str(values[k])
        if k in def_examples and def_examples[k]:
            return def_examples[k]
        warnings.append(f"'{{{{{k}}}}}' için değer yok — placeholder olarak bırakıldı.")
        return m.group(0)

    rendered = TEMPLATE_VAR_RE.sub(replacer, template or "")

    return PreviewResult(
        rendered=rendered,
        warnings=warnings,
        used_keys=used_keys,
        missing_keys=missing_keys,
        unknown_keys=unknown_keys,
    )


def parse_variables_json(raw: str | None) -> list[dict]:
    """`variables_json` Text alanını parse et — hata olursa boş liste."""
    if not raw:
        return []
    try:
        v = json.loads(raw)
        if isinstance(v, list):
            return v
    except json.JSONDecodeError:
        pass
    return []


def serialize_variables(variables: list[dict]) -> str:
    """Liste'i JSON'a serialize et (UTF-8 + ensure_ascii=False)."""
    return json.dumps(variables, ensure_ascii=False, default=str)
