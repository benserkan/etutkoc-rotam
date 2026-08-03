"""Art arda basıştan bozulmuş yanlış-soru vadelerini onar (dry-run varsayılan).

NEDEN: 2026-08-02'ye kadar `compute_next` aynı gün içindeki tekrar başarıları da
gerçek tekrar sayıyordu. Stabilite çarpımsal büyüdüğü için (başarıda ~x2.5-5.6)
arka arkaya basılan her buton vadeyi katlıyordu; sahada 8 basışta 191.381 güne
(2029) çıktı. Öğrenci o soruyu bir daha asla görmezdi.

Çekirdek hata `fsrs.SAME_DAY_GAP_HOURS` koruması ile giderildi; bu betik ondan
ÖNCE bozulmuş kayıtları temizler.

TESPİT (iki kriter, İKİSİ DE taranır):
  A) Sıkışık tekrar: (son_deneme - olusturma) < (deneme_sayisi - 1) * 20 saat
     — en az iki deneme var ama aralar kapanış kuralının istediği 20 saatin
     altında (yalnız AÇIK kayıtlar; kapalı kayıtta program çalışmıyor).
  B) Tavan aşımı: fsrs_stability > MAX_STABILITY_DAYS (1095) — korumalı
     algoritma bu değeri ÜRETEMEZ; varlığı eski zehirin kanıtıdır. KAPALI
     kayıtlar DAHİL taranır: saha dersi (2026-08-03, kayıt #4) — Temmuz'da
     26 basışla 21 milyar güne çıkan kayıt kapalı olduğu için ilk onarımdan
     kaçtı, "yine yanlış" ile yeniden açılınca zehir geri geldi (vade 2029).
     Kapalı kayıtta yalnız stabilite sıfırlanır, status/streak DEĞİŞMEZ.

ONARIM: tek başarılı tekrar yapılmış gibi sıfırla (stabilite 10 gün = RATING_GOOD
başlangıcı), vade = son denemeden 1 gün sonra. Ratingler kayıtlı olmadığı için
TEDBIRLI yön seçilir: soru dolaşıma erken döner. En kötü ihtimalle öğrenci bildiği
bir soruyu bir kez daha çözer; alternatifi soruyu tamamen kaybetmektir.

DOKUNULMAYANLAR: correct_streak (20 saat kuralıyla zaten doğru sayılıyordu),
kapanmış sorular (amacına ulaşmış), zorluk (fsrs_difficulty).

Kullanım:
    python -m scripts.fix_crammed_wq_due_dates            # yalnız rapor
    python -m scripts.fix_crammed_wq_due_dates --apply    # uygula
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_

from app.database import SessionLocal
from app.models import User
from app.models.wrong_question import WQ_STATUS_ACIK, WrongQuestion
from app.services.fsrs import (
    MAX_STABILITY_DAYS,
    REQUEST_RETENTION,
    SAME_DAY_GAP_HOURS,
    STATE_REVIEW,
    _scheduled_days,
)

# Tek başarılı tekrarın ("çözdüm") ürettiği stabilite.
RESET_STABILITY = 10.0


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Değişiklikleri yaz")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    sched = _scheduled_days(RESET_STABILITY, REQUEST_RETENTION)

    db = SessionLocal()
    try:
        rows = (
            db.query(WrongQuestion)
            .filter(
                or_(
                    WrongQuestion.attempts_count >= 2,
                    WrongQuestion.fsrs_stability > MAX_STABILITY_DAYS,
                )
            )
            .order_by(WrongQuestion.id)
            .all()
        )

        hedef: list[tuple[WrongQuestion, datetime]] = []
        for wq in rows:
            created = _aware(wq.created_at)
            last = _aware(wq.last_attempt_at)
            if created is None or last is None:
                continue
            # Kriter B: tavan aşımı — status ne olursa olsun onar.
            poisoned = wq.fsrs_stability > MAX_STABILITY_DAYS
            # Kriter A: sıkışık tekrar — yalnız açık kayıtta anlamlı.
            span_h = (last - created).total_seconds() / 3600.0
            crammed = (
                wq.status == WQ_STATUS_ACIK
                and wq.attempts_count >= 2
                and span_h < (wq.attempts_count - 1) * SAME_DAY_GAP_HOURS
            )
            if not (poisoned or crammed):
                continue
            hedef.append((wq, last + timedelta(days=sched)))

        if not hedef:
            print("Sikisik tekrardan bozulmus kayit YOK — yapilacak bir sey yok.")
            return 0

        isim = {
            u.id: u.full_name
            for u in db.query(User).filter(User.id.in_([w.student_id for w, _ in hedef])).all()
        }

        print(f"{'ID':>5}  {'ÖĞRENCİ':<22} {'DURUM':<8} {'DEN':>3}  {'STABİLİTE':>14}  {'ESKİ VADE':<12} -> YENİ VADE")
        print("-" * 96)
        for wq, yeni in hedef:
            eski = _aware(wq.due_at)
            gun = (eski - now).days if eski else 0
            print(
                f"{wq.id:>5}  {(isim.get(wq.student_id) or '?')[:22]:<22} "
                f"{wq.status:<8} {wq.attempts_count:>3}  {wq.fsrs_stability:>12.1f}g  "
                f"{eski:%Y-%m-%d} ({gun:+5}g) -> {yeni:%Y-%m-%d}"
            )

        if not args.apply:
            print(f"\n[KURU CALISMA] {len(hedef)} kayit etkilenecek. Yazmak icin --apply")
            return 0

        for wq, yeni in hedef:
            wq.fsrs_stability = RESET_STABILITY
            wq.fsrs_state = STATE_REVIEW
            wq.due_at = yeni
        db.commit()
        print(f"\n[UYGULANDI] {len(hedef)} kaydin vadesi onarildi.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
