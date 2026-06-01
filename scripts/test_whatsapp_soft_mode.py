"""WhatsApp soft-mod telefon kontrolü — can_message_phone birim testi.

Soft mod (SMS doğrulama henüz canlı değil): numara varsa Click-to-WhatsApp
gönderilebilir (kimse doğrulayamadığı için doğrulama şartı kaldırılır).
SMS canlıyken doğrulama tekrar zorunlu.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import datetime, timezone
from types import SimpleNamespace

import app.services.sms_provider as smsmod
from app.services.whatsapp_link_service import can_message_phone

now = datetime.now(timezone.utc)
passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def u(phone, verified):
    return SimpleNamespace(phone=phone, phone_verified_at=verified)


def main() -> int:
    print("\n=== WhatsApp soft-mod can_message_phone ===\n")
    orig = smsmod.is_sms_enabled
    try:
        # --- Soft mod: SMS doğrulama KAPALI ---
        smsmod.is_sms_enabled = lambda: False
        chk("soft: numara yok → False", can_message_phone(u(None, None)) is False)
        chk("soft: numara var + doğrulanmamış → True (FIX — eskiden False)",
            can_message_phone(u("905321234567", None)) is True)
        chk("soft: numara var + doğrulanmış → True",
            can_message_phone(u("905321234567", now)) is True)

        # --- SMS doğrulama CANLI ---
        smsmod.is_sms_enabled = lambda: True
        chk("canlı: numara var + doğrulanmamış → False (doğrulama şart)",
            can_message_phone(u("905321234567", None)) is False)
        chk("canlı: numara var + doğrulanmış → True",
            can_message_phone(u("905321234567", now)) is True)
        chk("canlı: numara yok → False", can_message_phone(u(None, None)) is False)
    finally:
        smsmod.is_sms_enabled = orig

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
