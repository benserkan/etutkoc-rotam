"""Veli bildirim (e-posta) pipeline teşhisi — bir öğrenci için + global sağlık.

SALT-OKUMA. "Efe için hangi durumda veli mesajı gider, gitti mi, gitmesi
gerekirken gitmedi mi" sorusunu yanıtlar + tüm gönderim zincirinin sağlığını
denetler (e-posta açık mı, feature-flag kapısı, cron zamanlı/çalışıyor mu,
dispatcher canlı mı).

  python -m scripts.diagnose_parent_notifications --name efe
  python -m scripts.diagnose_parent_notifications --student-id 12
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func

from app.config import settings
from app.database import SessionLocal
from app.models import (
    CronSchedule,
    FeatureFlag,
    NotificationKind,
    NotificationLog,
    NotificationStatus,
    ParentNotificationPref,
    ParentStudentLink,
    Task,
    User,
    UserRole,
)
from app.services import analytics
from app.services import cron_jobs as cj
from app.services import event_triggers as ev

now = datetime.now(timezone.utc)
today = now.date()


def _aware(dt):
    """Naive (SQLite) datetime'ı UTC kabul et — aware/naive karışımını önle."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def _pipeline_health(db):
    hr("1) PIPELINE SAĞLIĞI (global)")
    print(f"EMAIL_ENABLED         : {settings.email_enabled}")
    print(f"SMTP_HOST tanımlı mı  : {bool(settings.smtp_host)}  "
          f"(port={settings.smtp_port} tls={settings.smtp_use_tls} ssl={settings.smtp_use_ssl})")
    print(f"SMTP_FROM             : {settings.smtp_from or settings.smtp_user or '—'}")
    print(f"APP_BASE_URL          : {settings.app_base_url}")
    real_send = bool(settings.email_enabled and settings.smtp_host)
    print(f">>> Gerçek SMTP gönderim aktif mi: {'EVET' if real_send else 'HAYIR (log-only/stub)'}")

    # Feature flag kapısı (dispatcher e-postayı buna göre geçirir)
    print("\n-- Feature flag kapısı (dispatcher) --")
    for key in ("parent_notifications_email", "parent_notifications_whatsapp"):
        f = db.query(FeatureFlag).filter(FeatureFlag.key == key).first()
        if f is None:
            print(f"  {key:32}: TANIMSIZ → is_enabled defansif TRUE (engellemez)")
        else:
            print(f"  {key:32}: global={f.enabled_globally}  "
                  f"({'AÇIK' if f.enabled_globally else 'KAPALI → e-posta FAILED:feature_flag_disabled'})")

    # Parent bildirim cron'ları
    print("\n-- Veli bildirim cron'ları (CronSchedule) --")
    for jk in ("daily_summary", "weekly_backstop", "drop_alert", "exam_approaching"):
        cs = db.query(CronSchedule).filter(CronSchedule.job_key == jk).first()
        if cs is None:
            print(f"  {jk:18}: ⛔ SCHEDULE YOK → bu cron HİÇ çalışmaz")
            continue
        _lr = _aware(cs.last_run_at)
        lr = _lr.strftime("%Y-%m-%d %H:%M") if _lr else "—(hiç)"
        age = ("?" if not _lr else f"{(now - _lr).total_seconds()/3600:.1f}h önce")
        print(f"  {jk:18}: enabled={cs.enabled} {cs.dow_label} {cs.time_label} "
              f"| son çalışma={lr} ({age}) status={cs.last_status} err={cs.last_error or '-'}")

    # NotificationLog son 7 gün + dispatcher canlılığı
    print("\n-- NotificationLog (son 7 gün, tüm sistem) --")
    cutoff = now - timedelta(days=7)
    rows = db.query(NotificationLog).filter(NotificationLog.queued_at >= cutoff).all()
    by_status = Counter(r.status.value for r in rows)
    by_kind = Counter(r.kind.value for r in rows)
    print(f"  toplam={len(rows)}  durum={dict(by_status)}")
    print(f"  tür={dict(by_kind)}")
    errs = Counter(r.error for r in rows if r.status in (NotificationStatus.FAILED, NotificationStatus.SUPPRESSED) and r.error)
    if errs:
        print("  hata/suppress nedenleri:")
        for e, c in errs.most_common(10):
            print(f"     {c:>4}× {e}")
    last_sent = (
        db.query(func.max(NotificationLog.sent_at))
        .filter(NotificationLog.status == NotificationStatus.SENT)
        .scalar()
    )
    if last_sent:
        _ls = _aware(last_sent)
        agem = (now - _ls).total_seconds() / 60
        print(f"  son SENT zamanı: {_ls:%Y-%m-%d %H:%M} "
              f"({agem:.0f} dk önce) → dispatcher {'CANLI görünüyor' if agem < 24*60 else 'son 24h sessiz?'}")
    else:
        print("  ⛔ HİÇ SENT kaydı YOK — hiç e-posta gönderilmemiş olabilir")
    queued = db.query(NotificationLog).filter(NotificationLog.status == NotificationStatus.QUEUED).count()
    print(f"  şu an QUEUED bekleyen: {queued}")


def _find_students(db, name, sid):
    if sid:
        u = db.get(User, sid)
        return [u] if u and u.role == UserRole.STUDENT else []
    q = (db.query(User)
         .filter(User.role == UserRole.STUDENT, User.full_name.ilike(f"%{name}%"))
         .order_by(User.id).all())
    return q


def _student_block(db, s):
    hr(f"2) ÖĞRENCİ: {s.full_name} (id={s.id})")
    teacher = db.get(User, s.teacher_id) if s.teacher_id else None
    print(f"  rol={s.role.value} aktif={s.is_active} paused={getattr(s,'is_paused',None)} "
          f"sınıf={s.grade_level} koç={teacher.full_name if teacher else '—'} "
          f"kurum_id={s.institution_id}")
    print(f"  sınav hedefi={s.effective_exam_target} tarih={s.effective_exam_date} "
          f"etiket={s.effective_exam_label}")

    # Veli bağlantıları
    links = db.query(ParentStudentLink).filter(ParentStudentLink.student_id == s.id).all()
    print(f"\n  -- Veli bağlantıları ({len(links)}) --")
    if not links:
        print("  ⛔ HİÇ VELİ BAĞLI DEĞİL → bu öğrenci için HİÇBİR veli e-postası gitmez.")
    for ln in links:
        p = db.get(User, ln.parent_id)
        pref = db.query(ParentNotificationPref).filter(ParentNotificationPref.parent_id == ln.parent_id).first()
        print(f"   • veli={p.full_name if p else '?'} <{p.email if p else '?'}> "
              f"id={ln.parent_id} aktif={p.is_active if p else '?'} "
              f"paused={getattr(p,'is_paused',None) if p else '?'} muted={ln.muted}")
        if pref is None:
            print("       pref: YOK (kayıt oluşmamış — toggle'lar varsayılan True sayılır)")
        else:
            offs = [k for k, fld in [
                ("haftalık", "weekly_report_enabled"), ("yeni_program", "new_program_alert_enabled"),
                ("boş_gün", "empty_day_alert_enabled"), ("düşüş", "drop_alert_enabled"),
                ("öğr_notu", "teacher_note_enabled"), ("sınav", "exam_approaching_enabled"),
            ] if not getattr(pref, fld, True)]
            print(f"       e-posta KAPALI tipler: {offs or 'yok (hepsi açık)'} | "
                  f"unsubscribed={pref.unsubscribed_at is not None} | "
                  f"sessiz={pref.quiet_hours_start}-{pref.quiet_hours_end}")

    # NotificationLog geçmişi
    logs = (db.query(NotificationLog)
            .filter(NotificationLog.student_id == s.id)
            .order_by(NotificationLog.queued_at.desc()).limit(40).all())
    print(f"\n  -- NotificationLog geçmişi (son {len(logs)}) --")
    if not logs:
        print("  (hiç bildirim kaydı yok)")
    for lg in logs:
        _q, _s = _aware(lg.queued_at), _aware(lg.sent_at)
        qd = _q.strftime("%m-%d %H:%M") if _q else "?"
        sd = _s.strftime("%m-%d %H:%M") if _s else "—"
        print(f"   {qd} | {lg.kind.value:16} {lg.channel.value:8} {lg.status.value:10} "
              f"sent={sd} err={lg.error or '-'}")

    # Şu an her tür tetiklenir mi? (read-only kondisyon)
    print(f"\n  -- ŞU AN tetik koşulları (her tür için) --")
    parents = ev._active_parents_for(db, s.id)
    print(f"  aktif veli sayısı (filtreden geçen): {len(parents)}")
    if s.is_paused or not s.is_active:
        print("  ⚠️ öğrenci pasif/duraklatılmış → event-tetikli bildirimler susar")

    # WEEKLY_REPORT
    week_start = today - timedelta(days=6)
    any_task = db.query(Task.id).filter(Task.student_id == s.id, Task.date >= week_start, Task.date <= today).first()
    cycle = ev._is_cycle_complete(db, s.id, today)
    print(f"  WEEKLY_REPORT : son7g_görev={'VAR' if any_task else 'YOK'} "
          f"döngü_tamam={cycle} (backstop her gece 23:55 son7g_görev varsa + 6g'de rapor yoksa atar)")

    # EMPTY_DAY
    g = cj._gorev_day(db, s.id, today)
    streak = cj._consecutive_empty_days(db, s.id, today)
    empty = cj._is_empty_day(g)
    print(f"  EMPTY_DAY     : bugün_görev={g.gorev_total} bugün_tamam={g.gorev_done} "
          f"boş_gün_mü={empty} üst_üste_boş={streak} (eşik 3+; 21:00 cron)")

    # DROP_ALERT
    lw = analytics.week_stats_for(db, s.id, today - timedelta(days=1))
    pw = analytics.week_stats_for(db, s.id, today - timedelta(days=8))
    if lw.planned and pw.planned:
        lr = lw.completed / lw.planned
        pr = pw.completed / pw.planned
        drop = pr - lr
        print(f"  DROP_ALERT    : geçen_hafta=%{lr*100:.0f} önceki=%{pr*100:.0f} "
              f"düşüş=%{drop*100:.0f} (eşik %30+ & önceki≥%10; Pzt 06:00)")
    else:
        print(f"  DROP_ALERT    : yetersiz veri (geçen.planned={lw.planned} önceki.planned={pw.planned})")

    # EXAM_APPROACHING
    ed = s.effective_exam_date
    if ed and s.effective_exam_target:
        dl = (ed - today).days
        hit = dl in cj.EXAM_APPROACHING_THRESHOLDS
        print(f"  EXAM_APPROACH : {s.effective_exam_label} kalan={dl}g "
              f"eşikte_mi={hit} (eşikler={sorted(cj.EXAM_APPROACHING_THRESHOLDS)})")
    else:
        print(f"  EXAM_APPROACH : hedef/tarih yok → bu öğrenci için sınav bildirimi gönderilmez")

    # NEW_PROGRAM — son 14g yayınlanmış görev + son new_program kaydı
    pub = (db.query(func.count(Task.id))
           .filter(Task.student_id == s.id, Task.is_draft.is_(False),
                   Task.date >= today - timedelta(days=14))
           .scalar())
    last_np = (db.query(func.max(NotificationLog.queued_at))
               .filter(NotificationLog.student_id == s.id,
                       NotificationLog.kind == NotificationKind.NEW_PROGRAM).scalar())
    _lnp = _aware(last_np)
    last_np_s = _lnp.strftime("%Y-%m-%d %H:%M") if _lnp else "YOK"
    print(f"  NEW_PROGRAM   : son14g_yayınlı_görev={pub} son_NEW_PROGRAM_kaydı={last_np_s} "
          f"(yalnız 'Veliye duyur' butonu/publish-week tetikler)")


def run(name, sid):
    db = SessionLocal()
    try:
        _pipeline_health(db)
        students = _find_students(db, name, sid)
        if not students:
            hr("2) ÖĞRENCİ BULUNAMADI")
            print(f"  '{name or sid}' eşleşen STUDENT yok.")
            return 0
        for s in students:
            _student_block(db, s)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", type=str, default=None, help="öğrenci adı (içerir)")
    ap.add_argument("--student-id", type=int, default=None)
    args = ap.parse_args()
    raise SystemExit(run(args.name, args.student_id))
