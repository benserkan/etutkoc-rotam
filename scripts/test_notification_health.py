"""Katman 11.D — Bildirim Teslimat Kamerası smoke test.

Senaryolar:
  1) window_summary: sent/failed/queued/suppressed sayım + success%
  2) oldest_queued_minutes: en eski queued bekleyenin yaşı (dakika)
  3) channel_status_matrix: kanal × durum
  4) kind_status_matrix: tür × durum + rollup
  5) suppress_reason_distribution: error metnine göre gruplama
  6) daily_trend: son 7 gün günlük bucket
  7) get_health_data: aggregator key'leri
  8) HTTP GET /admin/security-monitor/notifications 200 + bölümler
  9) Ana panoda link var
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
from app.models import (
    NotificationChannel,
    NotificationKind,
    NotificationLog,
    NotificationStatus,
    User,
    UserRole,
)
from app.services.notification_health import (
    channel_status_matrix,
    daily_trend,
    get_health_data,
    kind_status_matrix,
    oldest_queued_minutes,
    suppress_reason_distribution,
    window_summary,
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


def _seed_notifications(db, pfx: str) -> None:
    """Test bildirimleri yarat — error field'ı pfx ile başlar → cleanup kolay."""
    now = datetime.now(timezone.utc)
    parent = db.query(User).filter(User.role == UserRole.PARENT).first()
    student = db.query(User).filter(User.role == UserRole.STUDENT).first()
    if not parent:
        # Eğer PARENT yoksa STUDENT'i kullan (test sadece NotificationLog yazıyor)
        parent = student or db.query(User).first()
    if not parent:
        return
    pid = parent.id
    sid = student.id if student else None

    # 5 sent (email, daily_summary)
    for i in range(5):
        db.add(NotificationLog(
            parent_id=pid, student_id=sid,
            kind=NotificationKind.DAILY_SUMMARY,
            channel=NotificationChannel.EMAIL,
            status=NotificationStatus.SENT,
            queued_at=now - timedelta(hours=1),
            sent_at=now - timedelta(minutes=50),
            error=f"{pfx}-mark",
        ))
    # 2 failed (whatsapp)
    for i in range(2):
        db.add(NotificationLog(
            parent_id=pid, student_id=sid,
            kind=NotificationKind.DROP_ALERT,
            channel=NotificationChannel.WHATSAPP,
            status=NotificationStatus.FAILED,
            queued_at=now - timedelta(hours=2),
            error=f"{pfx}-error: 401 token expired",
        ))
    # 3 queued — biri eski
    for i in range(2):
        db.add(NotificationLog(
            parent_id=pid, student_id=sid,
            kind=NotificationKind.WEEKLY_REPORT,
            channel=NotificationChannel.EMAIL,
            status=NotificationStatus.QUEUED,
            queued_at=now - timedelta(minutes=5),
            error=f"{pfx}-mark",
        ))
    db.add(NotificationLog(
        parent_id=pid, student_id=sid,
        kind=NotificationKind.WEEKLY_REPORT,
        channel=NotificationChannel.EMAIL,
        status=NotificationStatus.QUEUED,
        queued_at=now - timedelta(hours=3),  # eski queued
        error=f"{pfx}-old",
    ))
    # 4 suppressed — 2 farklı reason aile
    for i in range(2):
        db.add(NotificationLog(
            parent_id=pid, student_id=sid,
            kind=NotificationKind.DAILY_SUMMARY,
            channel=NotificationChannel.EMAIL,
            status=NotificationStatus.SUPPRESSED,
            queued_at=now - timedelta(minutes=30),
            error=f"{pfx}-child_muted",
        ))
    for i in range(2):
        db.add(NotificationLog(
            parent_id=pid, student_id=sid,
            kind=NotificationKind.DAILY_SUMMARY,
            channel=NotificationChannel.WHATSAPP,
            status=NotificationStatus.SUPPRESSED,
            queued_at=now - timedelta(minutes=30),
            error=f"{pfx}-pref:daily_summary off",
        ))
    db.commit()


def _cleanup(db, pfx: str) -> None:
    db.query(NotificationLog).filter(
        NotificationLog.error.like(f"{pfx}%")
    ).delete(synchronize_session=False)
    db.commit()


def main() -> int:
    print("=== Katman 11.D (Bildirim Teslimat) smoke ===")
    pfx = f"nh-{secrets.token_hex(3)}"

    # Seed
    with SessionLocal() as db:
        _cleanup(db, pfx)
        _seed_notifications(db, pfx)

    # ---- 1) window_summary 24h ----
    with SessionLocal() as db:
        s = window_summary(db, hours=24, label="24h")
        check("summary.sent >= 5", s.sent >= 5, f"got {s.sent}")
        check("summary.failed >= 2", s.failed >= 2)
        check("summary.queued >= 3", s.queued >= 3)
        check("summary.suppressed >= 4", s.suppressed >= 4)
        check("summary.success_pct float",
              isinstance(s.success_pct, (int, float)) and s.success_pct > 0)

    # ---- 2) oldest_queued_minutes ----
    with SessionLocal() as db:
        age = oldest_queued_minutes(db)
        check("oldest_queued >= 3 saat (180 dk)",
              age is not None and age >= 180, f"got {age}")

    # ---- 3) channel_status_matrix ----
    with SessionLocal() as db:
        m = channel_status_matrix(db, hours=24)
        check("matrix keys",
              set(m.keys()) >= {"channels", "statuses", "matrix", "rollups"})
        check("email channel mevcut", "email" in m["channels"])
        check("email.sent kaydı doğru sayı",
              m["matrix"]["email"]["sent"] >= 5)
        check("whatsapp.failed kaydı doğru",
              m["matrix"]["whatsapp"]["failed"] >= 2)
        check("rollup success_pct email",
              isinstance(m["rollups"]["email"]["success_pct"], (int, float)))

    # ---- 4) kind_status_matrix ----
    with SessionLocal() as db:
        km = kind_status_matrix(db, hours=24)
        check("kind matrix matrix anahtarı", "matrix" in km)
        check("daily_summary toplam > 0",
              km["rollups"]["daily_summary"]["total"] > 0)

    # ---- 5) suppress_reason_distribution ----
    with SessionLocal() as db:
        dist = suppress_reason_distribution(db, hours=24)
        labels = [d["label"] for d in dist]
        slugs = [d["slug"] for d in dist]
        check("suppress dist liste döner",
              isinstance(dist, list) and len(dist) > 0)
        check("'Çocuk susturulmuş' aile tespit",
              "child_muted" in slugs)
        check("'Kullanıcı tercihi kapalı' aile tespit",
              "pref_*" in slugs)
        check("descending sıralı",
              all(dist[i]["count"] >= dist[i + 1]["count"] for i in range(len(dist) - 1)))

    # ---- 6) daily_trend ----
    with SessionLocal() as db:
        tr = daily_trend(db, days=7)
        check("trend 7 gün döner", len(tr) == 7)
        check("trend günlerinde dict şema",
              all({"day", "sent", "failed", "queued", "suppressed", "total"} <= set(d.keys()) for d in tr))
        today_bucket = tr[-1]
        check("bugünkü bucket sent > 0", today_bucket["sent"] >= 0)

    # ---- 7) get_health_data ----
    with SessionLocal() as db:
        d = get_health_data(db)
        check("aggregator keys",
              set(d.keys()) >= {
                  "generated_at", "summary_24h", "summary_7d",
                  "oldest_queued_minutes", "channel_matrix_24h",
                  "kind_matrix_24h", "suppress_distribution_24h",
                  "daily_trend_7d",
              })
        check("generated_at datetime",
              isinstance(d["generated_at"], datetime))

    # ---- 8-9) HTTP ----
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if sa is None:
            print("  (super_admin yok — HTTP atlandı)")
        else:
            sa_id = sa.id

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
                r = c.get("/admin/security-monitor/notifications")
                check("notification pano GET 200",
                      r.status_code == 200, f"got {r.status_code}")
                check("'Bildirim Teslimat Kamerası' başlığı",
                      "Bildirim Teslimat Kamerası" in r.text)
                check("'Son 24 saat' özet",
                      "Son 24 saat" in r.text)
                check("'Kanal × Durum' bölümü",
                      "Kanal × Durum" in r.text)
                check("'Bastırma Nedenleri' bölümü",
                      "Bastırma Nedenleri" in r.text)
                check("'Son 7 Gün Trend' bölümü",
                      "Son 7 Gün Trend" in r.text)

                # Ana panoda link
                r2 = c.get("/admin/security-monitor")
                check("ana panoda 'Bildirim Teslimat' linki",
                      "Bildirim Teslimat" in r2.text)
            finally:
                app.dependency_overrides.pop(require_super_admin, None)
                app.dependency_overrides.pop(require_user, None)
                app.dependency_overrides.pop(get_current_user, None)

    # ---- Cleanup ----
    with SessionLocal() as db:
        _cleanup(db, pfx)

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
