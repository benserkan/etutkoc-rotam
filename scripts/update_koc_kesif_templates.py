# -*- coding: utf-8 -*-
"""Koç keşif DM şablonlarını seed spec'inden GÜNCELLE (2026-08-06).

`seed_whatsapp_templates` bilinçli olarak mevcut key'i ATLAR (panelden yapılan
düzenlemeleri ezmemek için). Bu script yalnız `koc_kesif_*` şablonlarını,
kod içindeki güncel metne eşitler — metin panelden elle değiştirildiyse
`--force` istenir.

Kullanım:
    python -m scripts.update_koc_kesif_templates          # kuru çalıştırma
    python -m scripts.update_koc_kesif_templates --apply  # yaz
"""
from __future__ import annotations

import sys

from app.database import SessionLocal
from app.models import WhatsAppTemplate
from app.services.whatsapp_template_service import serialize_variables
from scripts.seed_whatsapp_templates import SEED_TEMPLATES

KEYS = ("koc_kesif_instagram_dm", "koc_kesif_dm_devam", "koc_kesif_ilk_temas")


def main() -> int:
    apply = "--apply" in sys.argv
    specs = {t["key"]: t for t in SEED_TEMPLATES if t["key"] in KEYS}
    db = SessionLocal()
    changed = 0
    try:
        for key, spec in specs.items():
            row = (
                db.query(WhatsAppTemplate)
                .filter(WhatsAppTemplate.key == key)
                .first()
            )
            if row is None:
                row = WhatsAppTemplate(key=key)
                db.add(row)
                print(f"[YENİ] {key}")
            elif row.content_template == spec["content_template"]:
                print(f"[AYNI] {key}")
                continue
            else:
                print(f"[GÜNCEL] {key} — metin değişiyor")
            row.category = spec["category"]
            row.target_role = spec["target_role"]
            row.name_tr = spec["name_tr"]
            row.description = spec.get("description")
            row.content_template = spec["content_template"]
            row.variables_json = serialize_variables(spec.get("variables") or [])
            row.requires_date = bool(spec.get("requires_date", False))
            row.allow_bulk = bool(spec.get("allow_bulk", False))
            row.allow_freeform_note = bool(spec.get("allow_freeform_note", False))
            row.sort_order = int(spec.get("sort_order", 0))
            row.is_active = True
            changed += 1
        if apply and changed:
            db.commit()
            print(f"\n{changed} şablon güncellendi.")
        elif changed:
            db.rollback()
            print(f"\n{changed} şablon değişecek — yazmak için --apply ekle.")
        else:
            print("\nDeğişiklik yok.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
