"""Öğretmen ayarları (e-posta + cron zamanlamaları)."""

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db, require_teacher
from app.models import CronSchedule, User
from app.services.email_service import send_email
from app.templating import templates


router = APIRouter(prefix="/teacher")


# Job key → veliye anlamlı başlık ve detaylı açıklama. Template bu sözlükten
# okur; teknik anahtarın yerine bunlar gösterilir.
JOB_INFO: dict[str, dict[str, str]] = {
    "daily_summary": {
        "title": "Günlük öğrenci özeti",
        "what": "O gün programı olan öğrenciler için, günün tamamlama oranını "
                "ve ders bazlı detayı veliye e-posta/WhatsApp ile gönderir. "
                "Aynı gün hiç görev tamamlanmamışsa 'boş gün uyarısı' "
                "tetiklenir (üst üste 3 günü geçince susar).",
            "applies": "Sadece o gün planlı görevi olan öğrencilere uygulanır. "
                       "Salı programı olan öğrenciye Salı, Çarşamba programı "
                       "olana Çarşamba bildirim gider — sistem zaman bazlı "
                       "değil, öğrenci bazlı karar verir.",
            "default_hint": "Önerilen UTC 18:00 ≈ TR 21:00 (akşam)",
    },
    "weekly_backstop": {
        "title": "Haftalık rapor (yedek tetikleyici)",
        "what": "Haftalık rapor aslında öğrencinin 7 günlük döngüsünün son "
                "gününde otomatik tetiklenir. Bu cron yedek emniyettir: "
                "düşmüş tetikleyicileri yakalamak için her gece son 7 günde "
                "haftalık rapor gönderilmemiş öğrencileri kontrol eder.",
        "applies": "Her öğrenci için sadece kendi 7-günlük döngüsünün son gününde "
                   "rapor üretir. Olay tabanlı tetikleyici çalıştığında bu cron "
                   "skipped döner; sadece backup rolü oynar.",
        "default_hint": "Önerilen UTC 23:55 ≈ TR 02:55 (gün dönümü)",
    },
    "drop_alert": {
        "title": "Performans düşüş uyarısı",
        "what": "Pazartesi sabahları çalışır. Her öğrencinin geçen haftaki "
                "tamamlama oranını önceki haftaya göre kıyaslar; %30+ "
                "düşüş tespit edilen öğrencilerin velilerine uyarı gönderir.",
        "applies": "Sadece son iki haftada veri olan öğrencilerde tetiklenir. "
                   "İlk hafta veya programsız öğrenci atlanır.",
        "default_hint": "Önerilen UTC 06:00 ≈ TR 09:00 (Pazartesi sabahı)",
    },
}


def _utc_to_tr_label(hour: int, minute: int) -> str:
    """UTC saati TR (UTC+3) saatine çevir, gün kayması varsa belirt."""
    base = datetime(2000, 1, 1, hour, minute, tzinfo=timezone.utc)
    tr = base + timedelta(hours=3)
    label = f"{tr.hour:02d}:{tr.minute:02d}"
    if tr.day != base.day:
        label += " (ertesi gün)"
    return label


def _summarize_run(results: dict[str, dict]) -> str:
    """Cron tick sonuçlarını insancıl tek-satır özetlere çevirir."""
    parts: list[str] = []
    for key, counts in results.items():
        if not isinstance(counts, dict):
            parts.append(f"{key}: {counts}")
            continue
        if "error" in counts:
            parts.append(f"{key}: HATA — {counts['error']}")
            continue

        title = JOB_INFO.get(key, {}).get("title", key)

        if key == "daily_summary":
            d = counts.get("daily", 0)
            e = counts.get("empty", 0)
            sk_z = counts.get("skipped_zero", 0)
            sk_r = counts.get("skipped_recent", 0)
            sk_s = counts.get("skipped_streak", 0)
            bits = []
            if d:
                bits.append(f"{d} özet üretildi")
            if e:
                bits.append(f"{e} boş gün uyarısı")
            skipped = sk_z + sk_r + sk_s
            if not bits and skipped:
                bits.append(f"{skipped} öğrenci tarandı, bildirim gerekmedi")
            elif skipped:
                bits.append(f"{skipped} atlandı")
            parts.append(f"{title}: {', '.join(bits) if bits else 'işlem yok'}")
        elif key == "weekly_backstop":
            s = counts.get("sent", 0)
            sk_r = counts.get("skipped_recent", 0)
            sk_n = counts.get("skipped_no_tasks", 0)
            bits = []
            if s:
                bits.append(f"{s} haftalık rapor üretildi (kaçırılmış tetik yakalandı)")
            if sk_r:
                bits.append(f"{sk_r} zaten gönderilmiş")
            if sk_n:
                bits.append(f"{sk_n} öğrencide görev yok")
            parts.append(f"{title}: {', '.join(bits) if bits else 'işlem yok'}")
        elif key == "drop_alert":
            s = counts.get("sent", 0)
            nd = counts.get("skipped_no_drop", 0)
            nf = counts.get("skipped_no_data", 0)
            sk_r = counts.get("skipped_recent", 0)
            bits = []
            if s:
                bits.append(f"{s} düşüş uyarısı üretildi")
            if nd:
                bits.append(f"{nd} öğrencide düşüş yok")
            if nf:
                bits.append(f"{nf} öğrenci yetersiz veri")
            if sk_r:
                bits.append(f"{sk_r} zaten gönderilmiş")
            parts.append(f"{title}: {', '.join(bits) if bits else 'işlem yok'}")
        else:
            parts.append(f"{title}: {counts}")
    return " · ".join(parts)


@router.get("/usage")
def teacher_usage(
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmen kredi paneli — kurumlu için kurum havuzu link'i, bağımsız için kendi havuzu."""
    from app.models import USAGE_KIND_LABELS_TR
    from app.services.credits import (
        CreditOwner, current_period, daily_usage_series,
        get_or_create_account, recent_events, usage_breakdown_by_kind,
        KIND_CREDITS, PLAN_ALLOCATIONS,
    )

    # Kurumlu öğretmen → kurumun usage paneline yönlendir
    if user.institution_id is not None:
        return RedirectResponse(url="/teacher/settings", status_code=303)

    owner = CreditOwner.for_user(user)
    period = current_period()
    account = get_or_create_account(db, owner=owner, period=period)
    db.commit()

    breakdown = usage_breakdown_by_kind(db, owner=owner, period=period)
    series = daily_usage_series(db, owner=owner, days=30)
    events = recent_events(db, owner=owner, limit=50)

    return templates.TemplateResponse(
        "teacher/usage_dashboard.html",
        {
            "request": request,
            "user": user,
            "account": account,
            "period": period,
            "breakdown": breakdown,
            "series": series,
            "events": events,
            "kind_labels": USAGE_KIND_LABELS_TR,
            "plan_allocations": PLAN_ALLOCATIONS,
            "kind_costs": KIND_CREDITS,
        },
    )


@router.get("/settings")
def settings_page(
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
    cron_test: str | None = Query(None, alias="cron-test"),
):
    flash_ok = request.query_params.get("ok")
    flash_err = request.query_params.get("err")

    # ?cron-test=1 (veya herhangi bir değer) → enabled cron'ları manuel
    # tetikle, schedule kontrolünü atla.
    if cron_test:
        from app.services.cron_runner import tick as cron_tick
        from app.services.notification_dispatcher import dispatch_pending
        try:
            results = cron_tick(db, now=datetime.now(timezone.utc), force=True)
            disp = dispatch_pending(db)
            if results:
                summary = _summarize_run(results)
                sent = disp.get("sent", 0)
                supp = disp.get("suppressed", 0)
                disp_bits = []
                if sent:
                    disp_bits.append(f"{sent} bildirim gönderildi")
                if supp:
                    disp_bits.append(
                        f"{supp} bastırıldı (veli tercihi · sessiz saat · mute)"
                    )
                disp_label = " · ".join(disp_bits) if disp_bits else "yeni gönderim yok"
                flash_ok = f"✓ Manuel tarama tamam — {summary} → {disp_label}"
            else:
                flash_ok = (
                    "Manuel tetikleme: hiç açık bildirim türü bulunamadı. "
                    "Aşağıdaki tabloda 'Durum' sütununu kontrol edin."
                )
        except Exception as e:
            flash_err = f"Manuel cron çalıştırma hatası: {e}"

    cron_schedules = (
        db.query(CronSchedule).order_by(CronSchedule.id.asc()).all()
    )

    return templates.TemplateResponse(
        "teacher/settings.html",
        {
            "request": request,
            "user": user,
            "settings": settings,
            "flash_ok": flash_ok,
            "flash_err": flash_err,
            "cron_schedules": cron_schedules,
            "job_info": JOB_INFO,
            "utc_to_tr": _utc_to_tr_label,
        },
    )


@router.post("/settings/test-email")
def test_email(
    request: Request,
    to: str = Form(...),
    user: User = Depends(require_teacher),
):
    target = (to or "").strip() or user.email
    ok = send_email(
        to=target,
        template="teacher_new_request",
        ctx={
            "teacher": user,
            "student": user,
            "request": type("R", (), {
                "type": type("T", (), {"value": "question"})(),
                "task": None,
                "proposed_count": None,
                "proposed_book": None,
                "proposed_section": None,
                "message": "Bu bir test e-postasıdır. Mail yapılandırmanız çalışıyor.",
            })(),
            "type_label": "Test E-postası",
        },
    )
    if ok:
        msg = f"Test e-postası gönderildi: {target}"
        return RedirectResponse(url=f"/teacher/settings?ok={quote(msg)}", status_code=303)
    if not settings.email_enabled:
        msg = "E-posta gönderimi devre dışı (EMAIL_ENABLED=false)."
    elif not settings.smtp_host:
        msg = "SMTP_HOST tanımlı değil."
    else:
        msg = "Test e-postası gönderilemedi. Sunucu loglarında ayrıntı vardır."
    return RedirectResponse(url=f"/teacher/settings?err={quote(msg)}", status_code=303)


@router.post("/settings/cron/{schedule_id}")
def update_cron_schedule(
    schedule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    hour: int = Form(...),
    minute: int = Form(0),
    day_of_week: str = Form(""),
    enabled: str = Form(""),
):
    sch = db.get(CronSchedule, schedule_id)
    if not sch:
        raise HTTPException(status_code=404, detail="Schedule bulunamadı")

    # Sınır kontrolleri
    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        msg = "Saat 0-23, dakika 0-59 aralığında olmalı."
        return RedirectResponse(url=f"/teacher/settings?err={quote(msg)}", status_code=303)

    sch.hour = hour
    sch.minute = minute
    dow_str = day_of_week.strip()
    if dow_str == "" or dow_str.lower() == "none":
        sch.day_of_week = None
    else:
        try:
            v = int(dow_str)
            sch.day_of_week = v if 0 <= v <= 6 else None
        except ValueError:
            sch.day_of_week = None
    sch.enabled = (enabled == "yes" or enabled == "1" or enabled == "on")

    db.commit()

    msg = f"{sch.job_key} → {sch.time_label} ({sch.dow_label}) güncellendi."
    return RedirectResponse(url=f"/teacher/settings?ok={quote(msg)}#cron", status_code=303)
