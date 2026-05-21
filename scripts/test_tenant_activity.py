"""Katman 11.H — Tenant aktivite kamerası smoke test.

Senaryolar:
  1) aggregate_activity: dau/wau/mau int
  2) Sentetik LOGIN_SUCCESS audit → dau artar
  3) per_tenant_activity: tenant_id, dau/wau/mau alanlar
  4) hour_day_heatmap: 24 × 7 matris
  5) daily_dau_trend: N gün bucket
  6) silent_tenants: 7g sessiz olanlar
  7) get_activity_panel_data: aggregator keys
  8) HTTP GET /admin/security-monitor/activity 200 + bölümler
  9) Ana panoda 'Aktivite' linki
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, get_db, require_super_admin, require_user
from app.main import app
from app.models import AuditAction, AuditLog, User, UserRole
from app.services.tenant_activity import (
    aggregate_activity,
    daily_dau_trend,
    get_activity_panel_data,
    hour_day_heatmap,
    per_tenant_activity,
    silent_tenants,
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
    print("=== Katman 11.H (Tenant Aktivite) smoke ===")
    pfx = f"act-{secrets.token_hex(3)}"

    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        teacher_with_inst = (
            db.query(User)
            .filter(User.role == UserRole.TEACHER, User.institution_id.isnot(None))
            .first()
        )
        if not sa:
            print("  (super_admin yok — testler atlandı)")
            return 0
        sa_id = sa.id

    # ---- 1) aggregate_activity ----
    with SessionLocal() as db:
        a = aggregate_activity(db)
        check("aggregate keys",
              {"dau", "wau", "mau"} <= set(a.keys()))
        check("dau int", isinstance(a["dau"], int))

    # ---- 2) Sentetik LOGIN_SUCCESS → dau artar ----
    with SessionLocal() as db:
        baseline = aggregate_activity(db)["dau"]
        # 3 farklı user için login_success yaz
        users = db.query(User).limit(3).all()
        now = datetime.now(timezone.utc)
        for u in users:
            db.add(AuditLog(
                actor_id=u.id,
                email_attempted=f"{pfx}-login",
                action=AuditAction.LOGIN_SUCCESS,
                ip_address="10.0.0.1",
                created_at=now - timedelta(minutes=10),
            ))
        db.commit()
        after = aggregate_activity(db)["dau"]
        check("DAU sentetik kayıt sonrası artmış (>= baseline)",
              after >= baseline, f"baseline={baseline} after={after}")

    # ---- 3) per_tenant_activity ----
    if teacher_with_inst:
        with SessionLocal() as db:
            # teacher için login yaz
            db.add(AuditLog(
                actor_id=teacher_with_inst.id,
                email_attempted=f"{pfx}-tenant-login",
                action=AuditAction.LOGIN_SUCCESS,
                ip_address="10.0.0.2",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            ))
            db.commit()

            per = per_tenant_activity(db, top=50)
            tenant_match = [
                t for t in per
                if t["tenant_id"] == teacher_with_inst.institution_id
            ]
            check("teacher tenant per_tenant'ta", len(tenant_match) >= 1)
            if tenant_match:
                t = tenant_match[0]
                check("tenant.dau >= 1", t["dau"] >= 1)
                check("tenant.wau >= 1", t["wau"] >= 1)
                check("tenant_name dolu", t["tenant_name"])

    # ---- 4) hour_day_heatmap ----
    with SessionLocal() as db:
        hm = hour_day_heatmap(db, days=7)
        check("heatmap keys",
              {"matrix", "max_value", "day_labels", "total"} <= set(hm.keys()))
        check("matrix 24 saat", len(hm["matrix"]) == 24)
        check("her saatte 7 gün", all(len(hm["matrix"][h]) == 7 for h in range(24)))
        check("day_labels 7", len(hm["day_labels"]) == 7)

    # ---- 5) daily_dau_trend ----
    with SessionLocal() as db:
        tr = daily_dau_trend(db, days=14)
        check("trend 14 gün", len(tr) == 14)
        check("şema",
              all({"day", "dau"} <= set(d.keys()) for d in tr))

    # ---- 6) silent_tenants ----
    with SessionLocal() as db:
        sil = silent_tenants(db, days=7)
        check("silent_tenants liste",
              isinstance(sil, list))
        if sil:
            check("şema",
                  {"tenant_id", "tenant_name", "plan"} <= set(sil[0].keys()))

    # ---- 7) get_activity_panel_data ----
    with SessionLocal() as db:
        d = get_activity_panel_data(db)
        check("aggregator keys",
              {"generated_at", "totals", "per_tenant", "heatmap",
               "dau_trend_14d", "silent_tenants_7d"} <= set(d.keys()))

    # ---- 8-9) HTTP ----
    with SessionLocal() as db:
        def _ov():
            def factory():
                db2 = SessionLocal()
                try:
                    from sqlalchemy.orm import joinedload
                    u = (
                        db2.query(User)
                        .options(joinedload(User.institution))
                        .filter(User.id == sa_id).first()
                    )
                    _ = u.institution
                    db2.expunge_all()
                    return u
                finally:
                    db2.close()
            return factory

        app.dependency_overrides[require_super_admin] = _ov()
        app.dependency_overrides[require_user] = _ov()
        app.dependency_overrides[get_current_user] = _ov()
        try:
            c = TestClient(app)
            # Varsayılan = today sekmesi + segment=all
            r = c.get("/admin/security-monitor/activity")
            check("activity pano GET 200",
                  r.status_code == 200, f"got {r.status_code}")
            check("'Hesap Aktivitesi Kamerası' başlığı",
                  "Hesap Aktivitesi Kamerası" in r.text)
            check("Kritik Özet kartı (her sekmede)",
                  "Kritik Özet" in r.text)
            check("Sekme barı — 6 sekme",
                  all(t in r.text for t in [
                      "🩺 Bugün", "🚨 Risk", "🔁 Tutunma",
                      "🎨 Kullanım Derinliği", "🗺 Zaman", "🏆 Karşılaştırma"]))
            check("Segment toggle — 3 segment",
                  all(t in r.text for t in [
                      "🌐 Hepsi", "🏢 Kurumlar", "👤 Bağımsız Öğretmenler"]))
            check("today sekmesi — Günlük Aktif Kullanıcı kartı",
                  "Günlük Aktif Kullanıcı" in r.text)
            # Solo özel panel (segment=all default'unda görünür)
            check("Bağımsız öğretmen özel paneli",
                  "Bağımsız Öğretmene Özel Metrikler" in r.text)
            check("Solo özel — veli iletişim oranı",
                  "Veli İletişim Oranı" in r.text)
            check("Solo özel — disiplin metriği",
                  "Öğrenci Başına Haftalık Görev" in r.text)
            check("Solo özel — tutarlılık skoru",
                  "Haftalık Tutarlılık" in r.text)

            # segment=institution — solo özel panel görünmemeli + başlıklar kurum-odaklı
            r_inst = c.get("/admin/security-monitor/activity?segment=institution&tab=risk")
            check("segment=institution risk GET 200",
                  r_inst.status_code == 200, f"got {r_inst.status_code}")
            check("segment=institution'da solo özel panel YOK",
                  "Bağımsız Öğretmene Özel Metrikler" not in r_inst.text)
            check("segment=institution risk'te 'Kurum Kalp Atışı' başlığı",
                  "Kurum Kalp Atışı" in r_inst.text)
            check("segment=institution risk'te 'Kurum Sönüş Hızı' başlığı",
                  "Kurum Sönüş Hızı" in r_inst.text)

            # segment=solo — başlıklar öğretmen-odaklı olmalı
            r_solo = c.get("/admin/security-monitor/activity?segment=solo")
            check("segment=solo GET 200",
                  r_solo.status_code == 200, f"got {r_solo.status_code}")
            check("segment=solo'da solo özel panel VAR",
                  "Bağımsız Öğretmene Özel Metrikler" in r_solo.text)

            r_solo_risk = c.get("/admin/security-monitor/activity?segment=solo&tab=risk")
            check("segment=solo risk'te 'Öğretmen Kalp Atışı' başlığı",
                  "Öğretmen Kalp Atışı" in r_solo_risk.text)
            check("segment=solo risk'te 'Bağımsız Öğretmen Sönüş Hızı' başlığı",
                  "Bağımsız Öğretmen Sönüş Hızı" in r_solo_risk.text)

            r_solo_depth = c.get("/admin/security-monitor/activity?segment=solo&tab=depth")
            check("segment=solo depth'te 'Bağımsız Öğretmen × Aktif Öğrenci'",
                  "Bağımsız Öğretmen × Aktif Öğrenci Sayısı" in r_solo_depth.text)
            check("segment=solo depth'te 'Bağımsız Öğretmen × Özellik'",
                  "Bağımsız Öğretmen × Özellik" in r_solo_depth.text)

            r_solo_ret = c.get("/admin/security-monitor/activity?segment=solo&tab=retention")
            check("segment=solo retention'da 'Yeni Bağımsız Öğretmen Onboarding'",
                  "Yeni Bağımsız Öğretmen Onboarding" in r_solo_ret.text)

            r_solo_bench = c.get("/admin/security-monitor/activity?segment=solo&tab=benchmark")
            check("segment=solo benchmark'ta 'Champion Bağımsız Öğretmenler'",
                  "Champion Bağımsız Öğretmenler" in r_solo_bench.text)

            r_solo_time = c.get("/admin/security-monitor/activity?segment=solo&tab=time")
            check("segment=solo time'da en aktif kurumlar tablosu YOK",
                  "En Aktif Kurumlar" not in r_solo_time.text)
            check("segment=solo time'da bilgi notu var",
                  "Champion paneline" in r_solo_time.text)

            # risk sekmesi
            r_risk = c.get("/admin/security-monitor/activity?tab=risk")
            check("risk sekmesi GET 200",
                  r_risk.status_code == 200, f"got {r_risk.status_code}")
            check("risk sekmesinde 'Sessizleşen Hesaplar'",
                  "Sessizleşen Hesaplar" in r_risk.text)

            # time sekmesi
            r_time = c.get("/admin/security-monitor/activity?tab=time")
            check("time sekmesi GET 200",
                  r_time.status_code == 200, f"got {r_time.status_code}")
            check("time sekmesinde 'Isı Haritası'",
                  "Isı Haritası" in r_time.text)
            check("time sekmesinde 'Günlük Aktif Kullanıcı Trendi'",
                  "Günlük Aktif Kullanıcı Trendi" in r_time.text)

            # retention, depth, benchmark sekmelerinin 200 dönmesi
            for slug in ("retention", "depth", "benchmark"):
                r_s = c.get(f"/admin/security-monitor/activity?tab={slug}")
                check(f"{slug} sekmesi GET 200",
                      r_s.status_code == 200, f"got {r_s.status_code}")

            # 3 segment × 6 sekme = 18 kombinasyon — hepsi 200 dönmeli
            for seg in ("all", "institution", "solo"):
                for tab in ("today", "risk", "retention",
                             "depth", "time", "benchmark"):
                    r_c = c.get(
                        f"/admin/security-monitor/activity?tab={tab}&segment={seg}")
                    check(f"tab={tab}&segment={seg} → 200",
                          r_c.status_code == 200, f"got {r_c.status_code}")

            # Geçersiz tab + geçersiz segment → fallback
            r_inv = c.get("/admin/security-monitor/activity?tab=invalid&segment=junk")
            check("geçersiz tab+segment → 200 (fallback)",
                  r_inv.status_code == 200, f"got {r_inv.status_code}")

            # Ana panoda link
            r2 = c.get("/admin/security-monitor")
            check("ana panoda 'Aktivite' linki",
                  "📊 Aktivite" in r2.text or "Aktivite" in r2.text)
        finally:
            app.dependency_overrides.pop(require_super_admin, None)
            app.dependency_overrides.pop(require_user, None)
            app.dependency_overrides.pop(get_current_user, None)

    # Cleanup
    with SessionLocal() as db:
        db.query(AuditLog).filter(AuditLog.email_attempted.like(f"{pfx}%")).delete()
        db.commit()

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
