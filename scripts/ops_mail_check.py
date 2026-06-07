"""Tek seferlik OPS: (1) test-kaynaklı abuse sinyallerini çöz, (2) canlı test maili.

Kullanıcı onayıyla (2026-06-07). YAZMA + GÖNDERME yapar:
  --resolve-abuse           açık abuse sinyallerini (test/dev IP) resolved işaretle
  --send-test EMAIL         o adrese gerçek parent_new_program şablonu (gerçek
                            veriyle, [TEST] etiketli) prod SMTP üzerinden gönder

  python -m scripts.ops_mail_check --resolve-abuse --send-test benserkan@gmail.com
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import argparse
from datetime import date, timedelta

from app.database import SessionLocal
from app.models import AbuseSignal, User, UserRole
from app.services import abuse_detection, email_service


def resolve_abuse(db) -> None:
    admin = (db.query(User).filter(User.role == UserRole.SUPER_ADMIN)
             .order_by(User.id).first())
    if not admin:
        print("  SUPER_ADMIN bulunamadı — abuse çözme atlandı.")
        return
    openrows = db.query(AbuseSignal).filter(AbuseSignal.resolved_at.is_(None)).all()
    print(f"  Açık abuse sinyali: {len(openrows)} (resolver={admin.full_name} id={admin.id})")
    for s in openrows:
        abuse_detection.resolve_signal(
            db, signal_id=s.id, resolved_by_user_id=admin.id,
            note="Test/dev kaynaklı yanlış-pozitif (kendi IP/mobil çoklu giriş + test signup) — temizlendi.",
            autocommit=False,
        )
        print(f"   ✓ çözüldü: id={s.id} kind={s.kind} (IP/details={s.details_json})")
    db.commit()
    remaining = abuse_detection.open_signal_count(db)
    print(f"  Kalan açık sinyal: {remaining} → abuse_open alarmı {'SUSAR' if remaining==0 else 'hâlâ çalar'}")


def _synthetic_ctx() -> dict:
    """100% SENTETİK içerik — gerçek öğrenci/veli verisi YOK (PII sınır ihlali yok).

    parent_new_program şablonunu gerçek render eder; yalnız SMTP teslimatını test
    etmek için uydurma ders/deneme satırları.
    """
    today = date.today()
    ws = today - timedelta(days=today.weekday())
    we = ws + timedelta(days=6)
    day_names = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
    daily = []
    for i in range(7):
        d = ws + timedelta(days=i)
        has = i < 3
        daily.append({
            "day_name": day_names[i],
            "day_label": d.strftime("%d.%m"),
            "has_tasks": has,
            "subject_groups": ([{
                "subject": "Matematik (ÖRNEK)",
                "rows": [{"section": "Örnek Konu", "book": "Örnek Soru Bankası", "planned": 20}],
            }] if has else []),
            "denemeler": [], "activities": [],
            "gorev_total": 1 if has else 0,
            "test_planned": 20 if has else 0,
            "deneme_count": 0,
        })
    return {
        "student_id": 0,
        "student_name": "[TEST] Örnek Öğrenci",
        "week_start": ws.isoformat(),
        "week_end": we.isoformat(),
        "total_tasks": 3,
        "daily_breakdown": daily,
        "recent_exams": [],
        "unsubscribe_token": "TEST-TOKEN",
    }


def send_test(db, to: str) -> None:
    ctx = _synthetic_ctx()
    print(f"  Gönderiliyor: parent_new_program (SENTETİK veri) → {to} "
          f"(gerçek render, prod SMTP)")
    ok = email_service.send_email(to=to, template="parent_new_program", ctx=ctx)
    print(f"  send_email döndü: {ok}  → "
          f"{'TESLİM İÇİN SMTP KABUL ETTİ ✓' if ok else 'GÖNDERİLEMEDİ (log-only veya SMTP hatası)'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolve-abuse", action="store_true")
    ap.add_argument("--send-test", type=str, default=None)
    args = ap.parse_args()
    db = SessionLocal()
    try:
        if args.resolve_abuse:
            print("== ABUSE SİNYALLERİNİ ÇÖZ ==")
            resolve_abuse(db)
        if args.send_test:
            print("\n== CANLI TEST MAİLİ ==")
            send_test(db, args.send_test)
    finally:
        db.close()


if __name__ == "__main__":
    main()
