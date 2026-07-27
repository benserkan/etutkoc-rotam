# -*- coding: utf-8 -*-
"""Veli rehberi — Elif için seans + tahsilat demo verisi (Seans Hareketleri).

Veli panelindeki /parent/students/228/sessions sayfası dolu ve öğretici
görünsün: seans ücreti 2.000 TL · son 3 ayda 6 yapılmış + 1 ertelenmiş seans ·
önceki iki ay ödemeyle KAPALI, bu ay kısmi ödendi → açık hesap 2.000 TL.
Tarihler bugüne göreli (yeniden çekimde de taze kalır). İdempotent: Elif'in
rate kaydı varsa atlar; --reset ile silip yeniden kurar. YALNIZ DEV.

  PYTHONPATH=. python scripts/seed_guide_demo_sessions.py [--reset]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import date

from app.database import SessionLocal
from app.models import User
from app.models.coach_billing import (
    CoachPayment,
    CoachPaymentMethod,
    CoachStudentRate,
)
from app.models.coaching_session import (
    CoachingChannel,
    CoachingSession,
    CoachingSessionStatus,
)

ELIF = 228
FEE = 2000


def month_shift(y: int, m: int, delta: int) -> tuple[int, int]:
    m += delta
    while m <= 0:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return y, m


def safe_day(y: int, m: int, d: int) -> date:
    today = date.today()
    dt = date(y, m, min(d, 28))
    # bu ayın günü henüz gelmediyse geriye çek (gelecekte seans görünmesin)
    if dt > today:
        dt = today
    return dt


def main() -> int:
    reset = "--reset" in sys.argv
    today = date.today()

    with SessionLocal() as db:
        elif_u = db.get(User, ELIF)
        if elif_u is None or not elif_u.teacher_id:
            print("Elif (228) veya koçu yok — önce seed_guide_demo koşulmalı.")
            return 1
        coach_id = elif_u.teacher_id

        existing = (
            db.query(CoachStudentRate)
            .filter(CoachStudentRate.student_id == ELIF)
            .first()
        )
        if existing and not reset:
            print("Elif'in seans ücreti kaydı zaten var — atlandı (--reset ile yenile).")
            return 0
        if reset:
            db.query(CoachingSession).filter(CoachingSession.student_id == ELIF).delete()
            db.query(CoachPayment).filter(CoachPayment.student_id == ELIF).delete()
            db.query(CoachStudentRate).filter(CoachStudentRate.student_id == ELIF).delete()
            db.flush()

        db.add(CoachStudentRate(coach_id=coach_id, student_id=ELIF, session_fee=FEE))

        y0, m0 = today.year, today.month          # bu ay
        y1, m1 = month_shift(y0, m0, -1)          # geçen ay
        y2, m2 = month_shift(y0, m0, -2)          # iki ay önce

        plan = [
            # (tarih, durum, süre, kanal, gündem)
            (safe_day(y2, m2, 10), CoachingSessionStatus.DONE, 45, CoachingChannel.IN_PERSON,
             "Haftalık program değerlendirmesi + matematik tekrar planı"),
            (safe_day(y2, m2, 24), CoachingSessionStatus.DONE, 40, CoachingChannel.ONLINE,
             "Deneme sonucu üzerinden konu öncelikleri"),
            (safe_day(y1, m1, 7), CoachingSessionStatus.DONE, 45, CoachingChannel.IN_PERSON,
             "Yaz dönemi çalışma temposu + kaynak durumu"),
            (safe_day(y1, m1, 21), CoachingSessionStatus.DONE, 40, CoachingChannel.ONLINE,
             "Yanlış soru arşivi alışkanlığı + hedef gözden geçirme"),
            (safe_day(y0, m0, 6), CoachingSessionStatus.DONE, 45, CoachingChannel.IN_PERSON,
             "Deneme analizi — fen bilimleri net fırsatları"),
            (safe_day(y0, m0, 13), CoachingSessionStatus.POSTPONED, None, CoachingChannel.ONLINE,
             "Veli görüşmesi ertelendi — gelecek haftaya alındı"),
            (safe_day(y0, m0, 20), CoachingSessionStatus.DONE, 40, CoachingChannel.ONLINE,
             "Program uyumu + son deneme karşılaştırması"),
        ]
        for dt, st, dur, ch, agenda in plan:
            db.add(CoachingSession(
                coach_id=coach_id, student_id=ELIF, session_date=dt,
                status=st, duration_min=dur, channel=ch, agenda=agenda,
            ))

        payments = [
            # (tarih, tutar, yöntem, kapatılan ay, not)
            (safe_day(y1, m1, 2), 2 * FEE, CoachPaymentMethod.CASH,
             f"{y2:04d}-{m2:02d}", "Ay sonu elden ödeme"),
            (safe_day(y0, m0, 3), 2 * FEE, CoachPaymentMethod.TRANSFER,
             f"{y1:04d}-{m1:02d}", "Havale ile ay kapatıldı"),
            (safe_day(y0, m0, 10), FEE, CoachPaymentMethod.CASH,
             f"{y0:04d}-{m0:02d}", "Kısmi ödeme — kalan ay sonunda"),
        ]
        for dt, amount, method, period, note in payments:
            db.add(CoachPayment(
                coach_id=coach_id, student_id=ELIF, amount=amount,
                paid_at=dt, method=method, period_month=period, note=note,
            ))

        db.commit()
        done = sum(1 for p in plan if p[1] == CoachingSessionStatus.DONE)
        accrued = done * FEE
        paid = sum(p[1] for p in payments)
        print(f"seans: {len(plan)} (yapıldı {done}) · tahakkuk {accrued} · ödenen {paid} · açık {accrued - paid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
