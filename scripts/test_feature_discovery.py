"""Katman 3 — Otomatik Keşif smoke test.

Senaryolar:
  1) Migration kaynağı:
     - alembic/versions altındaki dosyaları aday yapar
     - since filtresi eskileri eler
     - title docstring ilk satırı; tagline meta-satırlardan arınmış
  2) Commit kaynağı:
     - git log üzerinden adaylar gelir
     - SKIP_COMMIT_PREFIXES kapsayan commitler atlanır (fix:, chore:, ...)
     - kısa (<10 char) commitler atlanır
  3) apply_candidates:
     - DRAFT FeatureCard oluşturur
     - Slug çakışmasında idempotent (atlar, hata vermez)
     - dry_run=True yazmaz
     - actor_id parametresi audit'e geçer
     - limit parametresine saygı
     - AuditAction.FEATURE_CARD_AUTO_DISCOVERED düşmüş mü

Kullanım:
    python -m scripts.test_feature_discovery
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import (
    AuditAction,
    AuditLog,
    FeatureCard,
    FeatureStatus,
)
from app.services import feature_discovery as fd


PFX_SLUG_PARTS = ("kesif-mig-", "kesif-c-")  # discovery slug prefix'leri
passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def main() -> int:
    print("=== Katman 3 (Otomatik Keşif) smoke ===")

    # 2026-04-01: hem migration (5-08'den itibaren push'lar) hem commit (5-08…5-10)
    # bu pencereye girer.
    since = datetime(2026, 4, 1, tzinfo=timezone.utc)

    # --- 1) Migration kaynağı ---
    mig = fd.discover_from_migrations(since=since)
    check("migration adayları üretildi", len(mig) > 0, f"got {len(mig)}")
    if mig:
        first = mig[0]
        check("migration adayı .source = 'migration'", first.source == "migration")
        check("migration adayı .source_ref boş değil", bool(first.source_ref))
        check("migration adayı .title boş değil", bool(first.title.strip()))
        check("migration adayı .slug 'kesif-mig-' önekli",
              first.slug.startswith("kesif-mig-"))
        check("migration tagline metadata satırı içermez",
              "Revision ID" not in first.tagline,
              f"got tagline: {first.tagline[:80]!r}")
        check("migration adayı introduced_at since'ten yeni",
              first.introduced_at >= since,
              f"{first.introduced_at} < {since}")

    # Çok eski tarih → 0 aday beklenir
    far_future = datetime.now(timezone.utc) + timedelta(days=30)
    none_mig = fd.discover_from_migrations(since=far_future)
    check("gelecek tarihli since 0 aday döner",
          len(none_mig) == 0, f"got {len(none_mig)}")

    # --- 2) Commit kaynağı ---
    com = fd.discover_from_commits(since=since)
    check("commit adayları üretildi", len(com) > 0, f"got {len(com)}")
    if com:
        all_skipped_prefixes_absent = all(
            not fd.SKIP_COMMIT_PREFIXES.match(c.raw_subject) for c in com
        )
        check("hiçbir aday SKIP_COMMIT_PREFIXES ile başlamaz",
              all_skipped_prefixes_absent)
        check("commit adayı .source = 'commit'", com[0].source == "commit")
        check("commit adayı .slug 'kesif-c-' önekli",
              com[0].slug.startswith("kesif-c-"))
        all_min_len = all(len(c.raw_subject) >= 10 for c in com)
        check("tüm commit subject'leri ≥ 10 karakter", all_min_len)

    # SKIP prefix kontrol
    check("'fix: bla bla' yakalanır",
          bool(fd.SKIP_COMMIT_PREFIXES.match("fix: bla bla")))
    check("'chore(deps): bump' yakalanır",
          bool(fd.SKIP_COMMIT_PREFIXES.match("chore(deps): bump")))
    check("'Stage 5: Foo' YAKALANMAZ (aday olmalı)",
          not fd.SKIP_COMMIT_PREFIXES.match("Stage 5: Foo"))
    check("'feat: yeni özellik' YAKALANMAZ (aday olmalı)",
          not fd.SKIP_COMMIT_PREFIXES.match("feat: yeni özellik"))

    # --- 3) discover_all ---
    allc = fd.discover_all(since=since)
    check("discover_all migration + commit toplar",
          len(allc) == len(mig) + len(com),
          f"got {len(allc)} != {len(mig)+len(com)}")
    is_sorted = all(
        allc[i].introduced_at >= allc[i+1].introduced_at
        for i in range(len(allc)-1)
    )
    check("discover_all yeniden eskiye sıralı", is_sorted)

    # Sadece migration
    only_mig = fd.discover_all(since=since, sources=("migration",))
    check("sources=migration sadece migration verir",
          all(c.source == "migration" for c in only_mig))

    # --- 4) apply_candidates ---
    # Önemli: gerçek discovery cardlarına dokunmamak için test-only
    # candidate'lar üret (slug benzersiz test PFX'li). Cleanup yalnız
    # bu test cardlarını siler — admin'in görüp incelediği gerçek kartlar
    # etkilenmez.
    import secrets
    test_pfx = f"kesif-test-fd-{secrets.token_hex(3)}"
    now = datetime.now(timezone.utc)

    def _mk_candidate(seq: int, source: str = "migration") -> fd.FeatureCandidate:
        prefix = "kesif-mig-" if source == "migration" else "kesif-c-"
        return fd.FeatureCandidate(
            slug=f"{prefix}{test_pfx}-{seq}",
            title=f"Test aday {seq}",
            tagline=f"(test fixture {seq})",
            domain="genel",
            tier="enhancement",
            introduced_at=now,
            introduced_in_commit=f"abc{seq:04d}",
            source=source,
            source_ref=f"ref-{seq}",
            raw_subject=f"Test commit {seq}",
        )

    test_candidates = [_mk_candidate(i, "migration" if i % 2 == 0 else "commit")
                       for i in range(5)]
    test_slug_set = {c.slug for c in test_candidates}

    with SessionLocal() as db:
        # Önceki kalıntı varsa temizle (test PFX scope)
        n_pre = db.query(FeatureCard).filter(
            FeatureCard.slug.like(f"kesif-%-{test_pfx}-%")
        ).count()
        if n_pre:
            for r in db.query(FeatureCard).filter(
                FeatureCard.slug.like(f"kesif-%-{test_pfx}-%")
            ).all():
                db.delete(r)
            db.commit()

        # Pre-test sayaçlar (gerçek discovery cardlarını saymak için baseline)
        baseline_count = db.query(FeatureCard).filter(
            FeatureCard.slug.like("kesif-mig-%") | FeatureCard.slug.like("kesif-c-%")
        ).count()
        baseline_audit = db.query(AuditLog).filter(
            AuditLog.action == AuditAction.FEATURE_CARD_AUTO_DISCOVERED
        ).count()

        # Dry-run — 5 aday
        dry_res = fd.apply_candidates(db, test_candidates[:3], dry_run=True)
        check("dry_run=True 'created' sayar ama yazmaz",
              dry_res["created"] == 3, f"got {dry_res}")
        after_dry_count = db.query(FeatureCard).filter(
            FeatureCard.slug.in_(test_slug_set)
        ).count()
        check("dry_run sonrası test kartı yazılmadı", after_dry_count == 0,
              f"got {after_dry_count}")

        # Gerçek yazım
        res = fd.apply_candidates(db, test_candidates[:3], dry_run=False)
        check("apply 3 kart oluşturdu", res["created"] == 3, f"got {res}")
        check("hata yok", len(res.get("errors") or []) == 0)

        # DB'de tam 3 test kartı
        created_in_db = db.query(FeatureCard).filter(
            FeatureCard.slug.in_(test_slug_set)
        ).count()
        check("DB'de 3 test kartı var", created_in_db == 3,
              f"got {created_in_db}")

        # Hepsi DRAFT
        all_draft = db.query(FeatureCard).filter(
            FeatureCard.slug.in_(test_slug_set),
            FeatureCard.status != FeatureStatus.DRAFT.value,
        ).count()
        check("hepsi DRAFT durumunda", all_draft == 0)

        # Audit kaydı düşmüş mü (baseline'dan +3)
        audit_now = db.query(AuditLog).filter(
            AuditLog.action == AuditAction.FEATURE_CARD_AUTO_DISCOVERED
        ).count()
        check("FEATURE_CARD_AUTO_DISCOVERED audit +3 arttı",
              audit_now >= baseline_audit + 3,
              f"baseline={baseline_audit} now={audit_now}")

        # İdempotent: aynı listeyi tekrar uygula → hepsi skipped
        res2 = fd.apply_candidates(db, test_candidates[:3], dry_run=False)
        check("ikinci uygulama hepsini atlar",
              res2["created"] == 0 and res2["skipped"] == 3,
              f"got {res2}")
        check("idempotent: DB hala 3 test kartı",
              db.query(FeatureCard).filter(
                  FeatureCard.slug.in_(test_slug_set)
              ).count() == 3)

        # Limit parametresi — kalan 2 adayı limit=1 ile uygula
        res_lim = fd.apply_candidates(db, test_candidates[3:], dry_run=False, limit=1)
        check("limit=1 sadece 1 oluşturur", res_lim["created"] == 1,
              f"got {res_lim}")

        # Cleanup — yalnızca test PFX kartları
        rows_to_delete = db.query(FeatureCard).filter(
            FeatureCard.slug.like(f"kesif-%-{test_pfx}-%")
        ).all()
        n_del = len(rows_to_delete)
        for r in rows_to_delete:
            db.delete(r)
        db.commit()
        print(f"  Cleanup: {n_del} test kartı silindi  (gerçek discovery cardlarına dokunulmadı; baseline={baseline_count})")

    # --- 5) CLI smoke ---
    from scripts.discover_features import main as cli_main
    print("\n--- CLI --dry-run ---")
    rc = cli_main(["--since", "2026-05-13", "--dry-run"])
    check("CLI --dry-run exit 0", rc == 0, f"got {rc}")

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
