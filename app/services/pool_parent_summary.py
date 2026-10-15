"""Havuz modu — veliye seans özeti (K53, Adım 5, 2026-10-12).

Kural: seans kapanışında özet OTOMATİK HAZIRLANIR, rehber önizler/düzenler, isterse
gönderir; OTOMATİK GİTMEZ. İçerik kural tabanlı ve KREDİSİZ; veli dili (suçlayıcı
değil, tek odak); rehbere özel seans notu / öğrenci talepleri PAYLAŞILMAZ (K52).

Kanal: mevcut veli bildirim altyapısı (`enqueue_notification`, kind=WEEKLY_REPORT —
havuz öğrencisinde Pazartesi haftalık raporu zaten susturuldu; velinin "Haftalık
rapor" tercihi bu özeti yönetir) + özel şablon `parent_pool_session_summary`.
Gönderilen hâl dönemde saklanır (`parent_summary_json`) → yeniden açma + PDF aynı.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import NotificationChannel, NotificationKind, NotificationLog, NotificationStatus, ParentStudentLink, User
from app.models.pool import PERIOD_OPEN, UNIT_ETKINLIK, PoolItem, StudyPeriod
from app.services import pool_mode as pm

MAX_LINES = 10
LINE_MAX = 400


def _fmt_date(d: date | None) -> str:
    from app.services.analytics import _d
    return _d(d) if d else "—"


def _unit_label(u: str) -> str:
    from app.models.pool import POOL_UNIT_LABELS
    return POOL_UNIT_LABELS.get(u, u)


def _item_name(it: PoolItem) -> str:
    if it.book_section_id and it.section is not None:
        return it.section.label + (f" ({it.book.name})" if it.book is not None else "")
    if it.topic_id and it.topic is not None:
        return it.topic.name
    return it.label or _unit_label(it.unit)


def carried_items(db: Session, period: StudyPeriod) -> list[PoolItem]:
    """Bu dönemden sonraki döneme devredilen kalemler (parent_item bu dönemde)."""
    ids = [it.id for it in period.items]
    if not ids:
        return []
    return db.query(PoolItem).filter(PoolItem.parent_item_id.in_(ids)).all()


def build_summary(db: Session, period: StudyPeriod, today: date | None = None) -> dict[str, Any]:
    """Veliye gidecek özetin yapısal + cümle hâli (düzenlenebilir)."""
    today = today or date.today()
    student = period.student
    summary = pm.period_summary(db, period, today)
    end = period.closed_on or today
    days = max(1, (end - period.opened_on).days)

    # ders kırılımı (veli dili: ders · bitti/toplam birim)
    per: dict[int, dict] = {}
    items_out: list[dict] = []
    for it in period.items:
        if not it.counts_toward_pool:
            continue
        t, d = pm._units(it)
        sub = it.subject.name if it.subject is not None else "Diğer"
        row = per.setdefault(it.subject_id or 0, {"subject": sub, "total": 0, "done": 0, "items": 0, "items_done": 0})
        row["total"] += t
        row["done"] += d
        row["items"] += 1
        row["items_done"] += 1 if it.is_done else 0
        items_out.append({"subject": sub, "name": _item_name(it), "quantity": it.quantity,
                          "unit": _unit_label(it.unit) if it.unit != UNIT_ETKINLIK else "etkinlik",
                          "done": it.done_units, "is_done": it.is_done, "teacher_homework": bool(it.teacher_homework)})
    subjects = sorted(per.values(), key=lambda r: (-(r["done"] / r["total"] if r["total"] else 0), r["subject"]))
    for r in subjects:
        r["pct"] = int(round(100 * r["done"] / r["total"])) if r["total"] else 0

    carried = carried_items(db, period)
    carried_out = [{"subject": c.subject.name if c.subject is not None else "Diğer", "name": _item_name(c),
                    "quantity": c.quantity, "unit": _unit_label(c.unit)} for c in carried]

    exam = pm.exam_strip(db, student=student, period=period)
    exam_out = None
    if exam and exam.get("in_period"):
        exam_out = {"title": exam["title"], "date": exam["exam_date"], "net": exam["net"], "delta": exam.get("delta"),
                    "prev_title": exam.get("prev_title")}

    # --- cümleler (veli dili; sayılar ölçüm, düzenlenemez — cümleler düzenlenebilir)
    first = (student.full_name or "").split(" ")[0] or "Öğrenciniz"
    lines: list[str] = []
    if summary.total_units == 0:
        lines.append(f"Bu dönem {first} için havuza kalem yazılmadı; yeni dönemle birlikte başlıyoruz.")
    else:
        lines.append(f"{first} bu dönem havuzundaki {summary.total_units} birimin {summary.done_units} tanesini "
                     f"tamamladı (yüzde {summary.pct}); dönem {days} gün sürdü.")
        best = next((r for r in subjects if r["total"] > 0 and r["pct"] >= 70), None)
        if best:
            lines.append(f"En düzenli ilerlediği ders {best['subject']} oldu ({best['done']}/{best['total']} birim).")
        low = [r for r in subjects if r["total"] >= 3 and r["pct"] < 40]
        if low:
            names = ", ".join(r["subject"] for r in low[:2])
            lines.append(f"{names} tarafında kalan çalışma var; yeni dönemde buraya birlikte ağırlık vereceğiz.")
    if carried_out:
        lines.append(f"Bitmeyen {len(carried_out)} kalem yeni döneme taşındı; bu normal bir devam planıdır, "
                     "ceza değil.")
    if exam_out:
        d = exam_out.get("delta")
        if d is not None:
            trend = "yükseldi" if d > 0 else ("geriledi" if d < 0 else "aynı kaldı")
            lines.append(f"Dönem içindeki {exam_out['title']} denemesinde net {exam_out['net']:.2f} — bir önceki aynı "
                         f"tür denemeye göre {abs(d):.2f} net {trend}.")
        else:
            lines.append(f"Dönem içindeki {exam_out['title']} denemesinde net {exam_out['net']:.2f}.")
    lines.append("Evde desteğin en kolay yolu: akşam \"bugün havuzdan ne aldın, neyi işaretledin?\" diye sormak; "
                 "kalan işi birlikte takvime yaymak çoğu zaman yeterli oluyor.")

    return {
        "period_id": period.id,
        "student_id": student.id,
        "student_name": student.full_name,
        "opened_on": period.opened_on.isoformat(),
        "closed_on": end.isoformat(),
        "opened_label": _fmt_date(period.opened_on),
        "closed_label": _fmt_date(end),
        "days": days,
        "pct": summary.pct,
        "done_units": summary.done_units,
        "total_units": summary.total_units,
        "items_done": summary.items_done,
        "items_total": summary.items_total,
        "subjects": subjects,
        "items": items_out,
        "carried": carried_out,
        "exam": exam_out,
        "narrative": lines[:MAX_LINES],
    }


def clean_narrative(lines: list[str] | None) -> list[str] | None:
    if lines is None:
        return None
    out = []
    for ln in lines:
        t = (ln or "").strip()
        if t:
            out.append(t[:LINE_MAX])
    return out[:MAX_LINES]


def build_email_context(db: Session, period: StudyPeriod, *, narrative: list[str] | None = None,
                        include_items: bool = True, include_exam: bool = True,
                        today: date | None = None) -> dict[str, Any]:
    base = build_summary(db, period, today)
    ctx = {k: v for k, v in base.items()}
    if narrative is not None:
        ctx["narrative"] = narrative
    ctx["include_items"] = include_items
    ctx["include_exam"] = include_exam
    if not include_exam:
        ctx["exam"] = None
    ctx["__template"] = "parent_pool_session_summary"
    return ctx


def sent_snapshot(period: StudyPeriod) -> dict | None:
    if not period.parent_summary_json:
        return None
    try:
        v = json.loads(period.parent_summary_json)
        return v if isinstance(v, dict) else None
    except Exception:
        return None


def recipients(db: Session, student_id: int) -> list[tuple[User, ParentStudentLink]]:
    links = (db.query(ParentStudentLink)
             .filter(ParentStudentLink.student_id == student_id).all())
    out = []
    for link in links:
        p = db.get(User, link.parent_id)
        if p is not None and p.is_active:
            out.append((p, link))
    return out


def send_summary(db: Session, *, period: StudyPeriod, actor: User, narrative: list[str] | None,
                 include_items: bool = True, include_exam: bool = True) -> dict:
    """Rehberin onayıyla veliye gönder (kuyruğa). Deneme duyurusu dürüstlük kuralları:
    yalnız QUEUED 'gönderildi' sayılır; üretim hatası damga atmaz."""
    from app.services.notification_producer import enqueue_notification
    from app.services.notification_producers import _unsub_token

    student = period.student
    ctx = build_email_context(db, period, narrative=narrative, include_items=include_items,
                              include_exam=include_exam)
    queued = suppressed = 0
    for parent, link in recipients(db, student.id):
        if link.muted:
            suppressed += 1
            continue
        payload = {**ctx, "unsubscribe_token": _unsub_token(db, parent.id)}
        log: NotificationLog = enqueue_notification(
            db, parent_id=parent.id, student_id=student.id, kind=NotificationKind.WEEKLY_REPORT,
            channel=NotificationChannel.EMAIL,
            subject=f"{student.full_name} · dönem özeti ({ctx['opened_label']} – {ctx['closed_label']}) · yüzde {ctx['pct']}",
            payload=payload,
        )
        if log.status == NotificationStatus.QUEUED:
            queued += 1
        else:
            suppressed += 1
    if queued:
        period.parent_summary_sent_at = datetime.now(timezone.utc)
        period.parent_summary_json = json.dumps(
            {k: v for k, v in ctx.items() if not k.startswith("__")}, ensure_ascii=False, default=str)
        db.flush()
    return {"queued": queued, "suppressed": suppressed, "sent": queued > 0}


def latest_closed_period(db: Session, student_id: int) -> StudyPeriod | None:
    return (db.query(StudyPeriod)
            .filter(StudyPeriod.student_id == student_id, StudyPeriod.status != PERIOD_OPEN)
            .order_by(StudyPeriod.closed_on.desc(), StudyPeriod.id.desc()).first())
