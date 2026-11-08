# -*- coding: utf-8 -*-
"""Takip listesi tohumu — CLAUDE.md'de tarihe bağlanmış bekleyen işler (2026-11-08).

İdempotent: `key` varsa ATLAR (kapatılmış/silinmiş kayıt yeniden açılmaz;
silinen key yeniden eklenir — silmek yerine iptal etmek tercih edilir).
start.sh her açılışta koşar.

    python -m scripts.seed_follow_ups
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import FollowUp  # noqa: E402
from app.services import follow_up_service as fus  # noqa: E402

SEEDS = [
    dict(
        key="rec-engine-coach-review-1",
        title="Öneri motoru — koç bazında isabeti yeniden değerlendir",
        due_on=date(2026, 11, 29), category="olcum", priority="high", recurrence_days=28,
        check_kind="metric_trend",
        check_params={"metric_key": "rec.shown", "owner_type": "coach", "min_change": 3},
        baseline_on=date(2026, 11, 8),
        description=(
            "8 Kasım'da yeni öneri motoru canlıya alındı (ekranda isabet %6 → %49). "
            "Bakılacaklar: (1) isabeti düşen koç var mı — varsa o koçun son haftalarındaki "
            "kaçakları `python -m scripts.backtest_suggestions --student <id> --diag` ile incele; "
            "(2) bir koça özel öğrenilen ağırlık varsayılanı geçti mi (Ölçümler → koç kırılımı); "
            "(3) 'neden istemiyorum' ret nedenlerinin yapılıp yapılmayacağına karar ver."
        ),
    ),
    dict(
        key="skeleton-acceptance-review-1",
        title="İskelet önerileri — çip kabul oranı hedefi (≥%60) tuttu mu?",
        due_on=date(2026, 11, 15), category="olcum", priority="normal",
        check_kind="metric_trend",
        check_params={"metric_key": "skeleton.acceptance", "owner_type": "coach", "min_change": 5},
        baseline_on=date(2026, 11, 8),
        description=(
            "İskelet F1 (26 Eylül) sonrası 2-3 hafta gerçek kullanımla kabul oranı ölçülecekti. "
            "Hedef: çiplerin ≥%60'ı kabul. Altındaysa `scripts/backtest_skeleton_chips.py` "
            "prod'da yeniden koşulup canlı kabulle kıyaslanır."
        ),
    ),
    dict(
        key="facebook-username-retry",
        title="Facebook işletme sayfası kullanıcı adı: 'etutkoc'u yeniden dene",
        due_on=date(2026, 11, 10), category="pazarlama",
        description=(
            "Facebook serbest kalan adı bir süre tutuyordu. Sayfa ayarları → Kullanıcı adı. "
            "Alınınca: etutkoc.com Footer/LocalSEO + Rotam page.tsx sameAs → facebook.com/etutkoc."
        ),
    ),
    dict(
        key="yandex-sitemaps",
        title="Yandex Webmaster: iki site haritasını ekle",
        due_on=date(2026, 11, 12), category="pazarlama",
        description=(
            "Yandex site haritası gönderimi geçici salt okuma modundaydı. etutkoc.com ve "
            "rotam.etutkoc.com site haritalarını ekle."
        ),
    ),
    dict(
        key="program-overlap-apply",
        title="Çakışan eski programları düzelt (fix_overlapping_programs --apply)",
        due_on=date(2026, 11, 10), category="veri",
        description=(
            "27 Ekim kuru çalışmada 5 öğrencide 6 çakışan program bulundu (#5 · #36 · #145 · "
            "#112+#137 · #127). Komut: `docker compose exec web python -m "
            "scripts.fix_overlapping_programs --apply`. Önce kuru çalıştırıp listeyi gözden geçir."
        ),
    ),
    dict(
        key="neslihan-sinan-kuzucu-731",
        title="Neslihan Aşkın — Sinan Kuzucu kitabını (#731) kapak + içindekilerle düzelt",
        due_on=date(2026, 11, 15), category="musteri",
        description=(
            "Kitap elle 'test 1…24' olarak açılmıştı. Kapak + içindekiler gelince doğru bölüm "
            "ve test sayılarıyla güncellenecek. Gelmediyse hatırlat."
        ),
    ),
    dict(
        key="profizik-toc-09-10",
        title="ProFizik TYT Fizik: 09-10. ünitelerin içindekiler sayfası",
        due_on=date(2026, 11, 20), category="urun",
        description=(
            "Katalog kaydı (prod #104) 08. üniteye kadar. Son içindekiler sayfasının fotoğrafı "
            "gelince Dalgalar/Optik bölümleri eklenecek (--reset ile)."
        ),
    ),
    dict(
        key="kvkk-retention-first-run",
        title="KVKK saklama süresi: 5 pasif öğrencinin anonimleştirmesi gerçekleşti mi?",
        due_on=date(2027, 1, 31), category="veri", priority="high",
        description=(
            "Sayaç 1 Kasım 2026'da başladı: 16 Ocak'ta koçlara uyarı, 30 Ocak'ta anonimleştirme "
            "(Elvin #12, Efe #15 ve Hatice'nin 3 öğrencisi). KVKK sayfasında kayıtları ve "
            "kvkk_retention_inactive gece işinin sonucunu doğrula."
        ),
    ),
]


def main() -> int:
    added = skipped = 0
    with SessionLocal() as db:
        existing = {k for (k,) in db.query(FollowUp.key).filter(FollowUp.key.isnot(None))}
        for s in SEEDS:
            if s["key"] in existing:
                skipped += 1
                continue
            it = fus.create(db, actor_id=None, **s)
            if it.check_kind:
                fus.evaluate(db, it)
            added += 1
        db.commit()
    print(f"seed_follow_ups: {added} eklendi, {skipped} zaten vardı")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
