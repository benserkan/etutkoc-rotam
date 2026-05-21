from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import settings
from app.models.audit_log import AUDIT_ACTION_LABELS
from app.models.book import BOOK_TYPE_LABELS, BookType
from app.models.task import TASK_TYPE_LABELS, TaskStatus, TaskType
from app.models.task_request import REQUEST_STATUS_LABELS, REQUEST_TYPE_LABELS


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


# Türkiye saati = UTC + 3 (DST yok)
_TR_TZ = timezone(timedelta(hours=3))


def _ensure_utc(dt):
    """Naive datetime'ı UTC olarak yorumla."""
    if dt is None:
        return None
    if not isinstance(dt, datetime):
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def dt_dual(dt) -> str:
    """Çift saat formatı: '16.05 01:40 TR · 15.05 22:40 UTC'.

    Gün farkı yoksa kısa: '01:40 TR · 22:40 UTC'.
    Naive datetime UTC olarak yorumlanır.
    """
    dt = _ensure_utc(dt)
    if dt is None or not isinstance(dt, datetime):
        return ""
    tr = dt.astimezone(_TR_TZ)
    utc = dt.astimezone(timezone.utc)
    if tr.date() == utc.date():
        return f"{tr.strftime('%H:%M')} TR · {utc.strftime('%H:%M')} UTC"
    return (
        f"{tr.strftime('%d.%m %H:%M')} TR · "
        f"{utc.strftime('%d.%m %H:%M')} UTC"
    )


def dt_tr(dt, fmt: str = "%d.%m %H:%M") -> str:
    """Sadece Türkiye saati — kompakt yerler için."""
    dt = _ensure_utc(dt)
    if dt is None or not isinstance(dt, datetime):
        return ""
    return f"{dt.astimezone(_TR_TZ).strftime(fmt)} TR"


def dt_tr_full(dt) -> str:
    """Tam tarih + saat Türkiye + UTC parantez (bir kerelik detaylı yerler için)."""
    dt = _ensure_utc(dt)
    if dt is None or not isinstance(dt, datetime):
        return ""
    tr = dt.astimezone(_TR_TZ)
    utc = dt.astimezone(timezone.utc)
    return (
        f"{tr.strftime('%d.%m.%Y %H:%M:%S')} TR "
        f"({utc.strftime('%H:%M:%S')} UTC)"
    )

templates.env.globals["AUDIT_ACTION_LABELS"] = AUDIT_ACTION_LABELS
templates.env.globals["BOOK_TYPE_LABELS"] = BOOK_TYPE_LABELS
templates.env.globals["BookType"] = BookType
templates.env.globals["TASK_TYPE_LABELS"] = TASK_TYPE_LABELS
templates.env.globals["TaskType"] = TaskType
templates.env.globals["TaskStatus"] = TaskStatus
templates.env.globals["REQUEST_TYPE_LABELS"] = REQUEST_TYPE_LABELS
templates.env.globals["REQUEST_STATUS_LABELS"] = REQUEST_STATUS_LABELS
templates.env.globals["settings"] = settings
# Today helper — phase aktif olup olmadığı kontrolü için
templates.env.globals["today_date"] = lambda: date.today()
# Audit list "son N gün" kısayolları için: today_iso(-7) → "2026-05-02"
templates.env.globals["today_iso"] = lambda offset_days=0: (
    date.today() + timedelta(days=offset_days)
).isoformat()

# Katman 11.K.1 — çift saat filtreleri (TR + UTC)
templates.env.filters["dt_dual"] = dt_dual
templates.env.filters["dt_tr"] = dt_tr
templates.env.filters["dt_tr_full"] = dt_tr_full
