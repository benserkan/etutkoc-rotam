"""Bildirim KUYRUĞU derin teşhisi — "396 queued / dispatcher takıldı mı?" SALT-OKUMA.

Alarm 'Kuyrukta uzun süre bekleyen bildirim' (oldest_queued_minutes) YALNIZ
queued_at'e bakar; scheduled_at (sessiz saat ertelemesi) GÖRMEZ. Bu script
QUEUED satırları gerçek dispatch kriterine göre ayırır:

  HAZIR        = scheduled_at<=now AND (next_attempt<=now veya null)  → dispatcher ALIR
  ERTELENMİŞ   = scheduled_at>now (sessiz saat)                       → ALMAZ (doğru)
  RETRY-BACKOFF= next_attempt_at>now                                  → ALMAZ (geçici)

HAZIR sayısı yüksek + eskiyse → GERÇEK dispatcher sorunu.
ERTELENMİŞ yüksek + HAZIR ~0 → sessiz-saat yanlış alarmı.

  python -m scripts.diagnose_notification_queue
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.database import SessionLocal
from app.models import NotificationLog, NotificationStatus
from app.services import notification_health as nh

now = datetime.now(timezone.utc)


def _aw(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def run() -> int:
    db = SessionLocal()
    try:
        print(f"=== BİLDİRİM KUYRUĞU TEŞHİSİ — şu an (UTC): {now:%Y-%m-%d %H:%M} ===\n")

        # Alarmın gördüğü değer
        oqm = nh.oldest_queued_minutes(db)
        print(f"Alarm metriği oldest_queued_minutes = {oqm} dk "
              f"(queued_at-bazlı; scheduled_at'i GÖRMEZ)")

        q = db.query(NotificationLog).filter(NotificationLog.status == NotificationStatus.QUEUED).all()
        total = len(q)
        print(f"Toplam QUEUED = {total}\n")
        if total == 0:
            print("Kuyruk BOŞ — hiç bekleyen yok.")
        ready = deferred = retry = 0
        ready_rows = []
        sched_hour = Counter()
        kind_c = Counter()
        chan_c = Counter()
        for r in q:
            sa = _aw(r.scheduled_at)
            na = _aw(r.next_attempt_at)
            kind_c[r.kind.value] += 1
            chan_c[r.channel.value] += 1
            is_deferred = sa is not None and sa > now
            is_retry = na is not None and na > now
            if is_deferred:
                deferred += 1
                sched_hour[sa.strftime("%m-%d %H:00")] += 1
            elif is_retry:
                retry += 1
            else:
                ready += 1
                ready_rows.append(r)

        print(f"  HAZIR (dispatcher şimdi almalı) : {ready}")
        print(f"  ERTELENMİŞ (sessiz saat, ileri)  : {deferred}")
        print(f"  RETRY-BACKOFF (geçici bekleme)   : {retry}")
        print(f"\n  tür dağılımı  : {dict(kind_c)}")
        print(f"  kanal dağılımı: {dict(chan_c)}")
        if sched_hour:
            print(f"  ertelenmiş scheduled_at saatleri: {dict(sched_hour.most_common(8))}")

        # En eski queued satır detayı
        oldest = (db.query(NotificationLog)
                  .filter(NotificationLog.status == NotificationStatus.QUEUED)
                  .order_by(NotificationLog.queued_at.asc()).first())
        if oldest:
            qa, sa = _aw(oldest.queued_at), _aw(oldest.scheduled_at)
            print(f"\n  En eski QUEUED: id={oldest.id} kind={oldest.kind.value} "
                  f"queued={qa:%m-%d %H:%M} ({(now-qa).total_seconds()/60:.0f}dk önce) "
                  f"scheduled={sa.strftime('%m-%d %H:%M') if sa else 'YOK'} "
                  f"attempts={oldest.attempts}")

        # HAZIR ama eskimiş olanlar = GERÇEK SORUN sinyali
        if ready_rows:
            ready_rows.sort(key=lambda r: _aw(r.queued_at))
            print(f"\n  ⚠️ HAZIR (gönderilmeyi bekleyen) örnekler:")
            for r in ready_rows[:10]:
                qa = _aw(r.queued_at)
                print(f"     id={r.id} {r.kind.value:14} {r.channel.value:8} "
                      f"queued={qa:%m-%d %H:%M} ({(now-qa).total_seconds()/60:.0f}dk) "
                      f"attempts={r.attempts} err={r.error or '-'}")

        # Dispatcher canlılığı: son SENT zamanları + saatlik
        print("\n-- Dispatcher aktivitesi --")
        last_sent = db.query(func.max(NotificationLog.sent_at)).filter(
            NotificationLog.status == NotificationStatus.SENT).scalar()
        last_sent = _aw(last_sent)
        if last_sent:
            print(f"  son SENT: {last_sent:%Y-%m-%d %H:%M} ({(now-last_sent).total_seconds()/60:.0f}dk önce)")
        for h, lbl in [(1, "son 1h"), (6, "son 6h"), (24, "son 24h")]:
            c = db.query(func.count(NotificationLog.id)).filter(
                NotificationLog.status == NotificationStatus.SENT,
                NotificationLog.sent_at >= now - timedelta(hours=h)).scalar()
            print(f"  SENT {lbl}: {c}")
        # Son 24h FAILED
        fc = db.query(func.count(NotificationLog.id)).filter(
            NotificationLog.status == NotificationStatus.FAILED,
            NotificationLog.queued_at >= now - timedelta(hours=24)).scalar()
        print(f"  FAILED son 24h: {fc}")

        # VERDİKT
        print("\n=== VERDİKT ===")
        if total == 0:
            print("  Kuyruk boş — sorun yok.")
        elif ready == 0 and deferred > 0:
            print(f"  ✓ {deferred} bildirim SESSİZ SAAT için ertelenmiş (scheduled_at ileri).")
            print("    Dispatcher bunları DOĞRU şekilde beklemede tutuyor; 07:00'de gönderecek.")
            print("    Alarm YANLIŞ POZİTİF — queued_at'e bakıp scheduled_at'i yok sayıyor.")
        elif ready > 0:
            print(f"  ⚠️ {ready} bildirim HAZIR ama gönderilmemiş → dispatcher/worker'ı KONTROL ET.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(run())
