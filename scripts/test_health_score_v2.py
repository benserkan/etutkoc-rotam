"""Sprint F.1 — Sağlık Skoru 2.0 + Erken Uyarı (Faz C) smoke test.

Test ettiği:
  - compute_health_score_v2: HealthScoreV2 dataclass + 6 component
  - score: 0-100 aralığında, band tutarlı
  - band_for_score: 5 band sınırı doğru
  - WEIGHTS_V2: 6 bileşen toplamı 100
  - record_snapshot_for: HealthScoreSnapshot yazılır
  - Aynı (inst, date) için tekrar çağrı UPDATE eder (UNIQUE)
  - record_daily_snapshots: tüm aktif kurumlar
  - get_score_history: son N gün listeler
  - detect_warning_triggers: 3 trigger doğru tespit
"""

from __future__ import annotations

import secrets
import sys
from datetime import date, datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import (
    HealthScoreSnapshot,
    Institution,
    User,
    UserRole,
    band_for_score,
)
from app.services.health_score_v2 import (
    WEIGHTS_V2,
    compute_health_score_v2,
    detect_warning_triggers,
    get_score_history,
    record_daily_snapshots,
    record_snapshot_for,
)


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
    print("=== Sprint F.1 — Sağlık Skoru 2.0 smoke ===")
    tag = f"sprintf1-{secrets.token_hex(3)}"

    with SessionLocal() as db:
        inst = db.query(Institution).filter(Institution.is_active.is_(True)).first()
        if inst is None:
            print("  (kurum yok — atlandı)")
            return 0
        inst_id = inst.id

    # ---- 1) WEIGHTS_V2 toplamı 100 ----
    check("WEIGHTS_V2: 6 bileşen, toplam %100",
          len(WEIGHTS_V2) == 6 and sum(WEIGHTS_V2.values()) == 100,
          f"got {sum(WEIGHTS_V2.values())}")

    # ---- 2) band_for_score: 5 band ----
    check("band: 95 → champion", band_for_score(95) == "champion")
    check("band: 70 → healthy", band_for_score(70) == "healthy")
    check("band: 50 → at_risk", band_for_score(50) == "at_risk")
    check("band: 30 → critical", band_for_score(30) == "critical")
    check("band: 10 → lost_imminent", band_for_score(10) == "lost_imminent")
    check("band: 0 → lost_imminent", band_for_score(0) == "lost_imminent")
    check("band: 100 → champion", band_for_score(100) == "champion")

    # ---- 3) compute_health_score_v2: shape ----
    with SessionLocal() as db:
        inst_obj = db.get(Institution, inst_id)
        h = compute_health_score_v2(db, institution=inst_obj)
        check("compute_v2: HealthScoreV2 attribs",
              hasattr(h, "score") and hasattr(h, "band")
              and hasattr(h, "components"))
        check("compute_v2: score 0-100",
              0 <= h.score <= 100, f"got {h.score}")
        check("compute_v2: 6 component",
              len(h.components) == 6, f"got {len(h.components)}")
        check("compute_v2: band consistent with band_for_score",
              h.band == band_for_score(h.score))
        # Her component için weight ve value 0-100
        for c in h.components:
            if not (0 <= c.value_pct <= 100):
                check(f"component {c.code}: value 0-100", False,
                      f"got {c.value_pct}")
                break
            if not (0 <= c.contribution <= c.weight_pct):
                check(f"component {c.code}: contribution <= weight", False,
                      f"contrib={c.contribution} weight={c.weight_pct}")
                break
        else:
            check("components: hepsi 0-100 ve katkı<=weight", True)
        # Toplam contribution == score (clamping hariç)
        sum_contrib = sum(c.contribution for c in h.components)
        check("components: katkılar toplamı = score",
              sum_contrib == h.score,
              f"sum={sum_contrib} vs score={h.score}")

    # ---- 4) record_snapshot_for: yazılır ----
    today = date.today()
    with SessionLocal() as db:
        inst_obj = db.get(Institution, inst_id)
        # Eski snapshot temizle
        db.query(HealthScoreSnapshot).filter(
            HealthScoreSnapshot.institution_id == inst_id,
            HealthScoreSnapshot.snapshot_date == today,
        ).delete()
        db.commit()

        snap = record_snapshot_for(db, institution=inst_obj, snapshot_date=today)
        check("record_snapshot: yazıldı",
              snap is not None and snap.id is not None)
        check("record_snapshot: components_json dolu",
              snap.components_json is not None and "code" in snap.components_json)

    # ---- 5) Aynı (inst, date) için tekrar çağrı UPDATE eder ----
    with SessionLocal() as db:
        inst_obj = db.get(Institution, inst_id)
        snap1 = record_snapshot_for(db, institution=inst_obj, snapshot_date=today)
        snap2 = record_snapshot_for(db, institution=inst_obj, snapshot_date=today)
        check("snapshot UNIQUE: ikinci çağrı UPDATE",
              snap1.id == snap2.id,
              f"snap1={snap1.id} vs snap2={snap2.id}")

    # ---- 6) Geçmiş günler için snapshot kaydet (history testi için) ----
    with SessionLocal() as db:
        inst_obj = db.get(Institution, inst_id)
        # 8 gün önce → bugün arası 9 snapshot
        # d_offset=8 (eski): yüksek değerler; d_offset=0 (bugün): düşük değerler
        # → monoton düşüş senaryosu
        for d_offset in range(8, -1, -1):
            sd = today - timedelta(days=d_offset)
            snap = record_snapshot_for(
                db, institution=inst_obj, snapshot_date=sd, autocommit=False,
            )
            # 8 gün önce 80 puan, bugün 56 puan (monoton düşüş)
            snap.score = 80 - ((8 - d_offset) * 3)
            # 8 gün önce 10 öğretmen, bugün 2 (büyük düşüş)
            snap.active_teacher_count = max(2, 10 - (8 - d_offset))
        db.commit()

    # ---- 7) get_score_history ----
    with SessionLocal() as db:
        history = get_score_history(db, institution_id=inst_id, days=14)
        check("get_score_history: liste",
              len(history) >= 7, f"got {len(history)}")
        # Tarihler artan sırada
        dates = [s.snapshot_date for s in history]
        check("get_score_history: artan tarih sırası",
              dates == sorted(dates))

    # ---- 8) detect_warning_triggers: T1 (teacher drop) ----
    with SessionLocal() as db:
        inst_obj = db.get(Institution, inst_id)
        triggers = detect_warning_triggers(db, institution=inst_obj)
        trigger_codes = {t.code for t in triggers}
        # Yukarıda 10 → 2 düşüş (büyük), T1 tetiklenmeli
        check("triggers: T1 (teacher_drop_30pct) tetiklendi",
              "teacher_drop_30pct" in trigger_codes,
              f"got {trigger_codes}")

    # ---- 9) detect_warning_triggers: T3 (score decline 7d) ----
    with SessionLocal() as db:
        # Yukarıda enjekte edilen monoton azalan skor → T3 tetiklenmeli
        # (8 günlük history: 80,77,74,71,68,65,62,59,56)
        inst_obj = db.get(Institution, inst_id)
        triggers = detect_warning_triggers(db, institution=inst_obj)
        trigger_codes = {t.code for t in triggers}
        check("triggers: T3 (score_decline_7d) tetiklendi",
              "score_decline_7d" in trigger_codes,
              f"got {trigger_codes}")

    # ---- 10) record_daily_snapshots: cron tüm aktif kurumlar ----
    with SessionLocal() as db:
        r = record_daily_snapshots(db, snapshot_date=today)
        check("record_daily_snapshots: count >= 1",
              r.get("count", 0) >= 1, str(r))
        check("record_daily_snapshots: snapshot_date dönüyor",
              r.get("snapshot_date") == today.isoformat())

    # ---- Cleanup history (kalıcı yan etki bırakma) ----
    with SessionLocal() as db:
        db.query(HealthScoreSnapshot).filter(
            HealthScoreSnapshot.institution_id == inst_id,
        ).delete()
        db.commit()

    print()
    print(f"=== Toplam: {passed} PASS / {len(failed)} FAIL ===")
    if failed:
        print("\nFAIL'ler:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
