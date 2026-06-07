"""parent_new_program render hatasını reprodüksiyon — SALT-OKUMA.

Dispatcher 'template_render_failed:parent_new_program' yazdığında hangi payload
ve hangi gerçek istisna olduğunu gösterir. NotificationLog.payload_json'dan
gerçek veriyle email_service._render çağrılır (gönderim YOK).

  python -m scripts.diagnose_new_program_render
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import traceback
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import NotificationKind, NotificationLog, NotificationStatus
from app.services import email_service

now = datetime.now(timezone.utc)


def run() -> int:
    db = SessionLocal()
    try:
        # 1) Başarısız NEW_PROGRAM logları (render hatası dahil)
        failed = (
            db.query(NotificationLog)
            .filter(
                NotificationLog.kind == NotificationKind.NEW_PROGRAM,
                NotificationLog.status == NotificationStatus.FAILED,
            )
            .order_by(NotificationLog.queued_at.desc())
            .limit(10)
            .all()
        )
        print(f"=== Başarısız NEW_PROGRAM logları: {len(failed)} ===")
        for lg in failed:
            print(f"  id={lg.id} student={lg.student_id} parent={lg.parent_id} "
                  f"queued={lg.queued_at} err={lg.error}")

        # 2) Repro: önce başarısızların payload'ı, yoksa en son NEW_PROGRAM payload'ı
        targets = failed[:]
        if not targets:
            print("\n(FAILED yok — en son NEW_PROGRAM payload'ı ile render denenir)")
            targets = (
                db.query(NotificationLog)
                .filter(NotificationLog.kind == NotificationKind.NEW_PROGRAM)
                .order_by(NotificationLog.queued_at.desc())
                .limit(3)
                .all()
            )

        for lg in targets:
            print(f"\n--- RENDER REPRO: log id={lg.id} student={lg.student_id} ---")
            if not lg.payload_json:
                print("   payload_json BOŞ — render edilemez (asıl sorun bu olabilir)")
                continue
            try:
                payload = json.loads(lg.payload_json)
            except Exception as e:
                print(f"   payload JSON decode hatası: {e}")
                continue
            # daily_breakdown gün sayısı + recent_exams sayısı (boyut ipucu)
            db_len = len(payload.get("daily_breakdown") or [])
            ex_len = len(payload.get("recent_exams") or [])
            print(f"   payload: daily_breakdown={db_len} gün · recent_exams={ex_len} · "
                  f"keys={sorted(payload.keys())}")
            try:
                subject, html, plain = email_service._render("parent_new_program", payload)
                print(f"   ✓ RENDER OK — subject={subject!r} html_len={len(html)}")
            except Exception:
                print("   ✗ RENDER PATLADI:")
                traceback.print_exc()
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(run())
