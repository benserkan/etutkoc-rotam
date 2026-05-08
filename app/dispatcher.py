"""Standalone bildirim dispatcher CLI.

Kullanım:
    python -m app.dispatcher           # tek seferlik çalıştır, çık
    python -m app.dispatcher --loop    # 60sn'de bir döngüde çalış
    python -m app.dispatcher --interval 30 --loop

Production'da Render Background Worker servisi olarak `python -m app.dispatcher --loop`
ile başlatılır. Web worker'lar dispatch yapmaz; bu sayede multi-worker'da duplicate
gönderim olmaz.

Yerel dev: `app/main.py` lifespan'ında zaten 60sn'de bir çalışıyor.
"""

from __future__ import annotations

import argparse
import logging
import time

from app.database import SessionLocal
from app.services.notification_dispatcher import dispatch_pending


def main() -> None:
    parser = argparse.ArgumentParser(description="ETÜTKOÇ Rotam bildirim dispatcher")
    parser.add_argument("--loop", action="store_true", help="Sürekli döngüde çalıştır")
    parser.add_argument("--interval", type=int, default=60, help="Döngü periyodu (sn)")
    parser.add_argument("--batch-size", type=int, default=50, help="Tek seferde max satır")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("dispatcher")

    from app.services.cron_runner import tick as cron_tick

    def _tick():
        with SessionLocal() as db:
            # 1) Cron job'ları kontrol et — due olanlar enqueue eder
            try:
                cron_results = cron_tick(db)
                if cron_results:
                    logger.info("cron tick: %s", cron_results)
            except Exception as e:
                logger.exception("cron_tick hatası: %s", e)

            # 2) Bildirim kuyruğunu işle
            summary = dispatch_pending(db, batch_size=args.batch_size)
            if summary["processed"] > 0:
                logger.info("processed=%d sent=%d failed=%d suppressed=%d retried=%d",
                            summary["processed"], summary["sent"], summary["failed"],
                            summary["suppressed"], summary["retried"])

    if not args.loop:
        _tick()
        return

    logger.info("Dispatcher loop başladı (interval=%ds)", args.interval)
    try:
        while True:
            _tick()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Dispatcher kapatıldı.")


if __name__ == "__main__":
    main()
