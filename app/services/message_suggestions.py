"""WhatsApp mesaj önerileri — "Bugünün mesajları" (2026-11-14, koç kararları).

Sistemin öğrenci hakkında fark ettiği her durum bir mesaj adayıdır:
  · sorun (görev birikmesi, boş gün, tamamlama düşüşü, kaçınılan ders, deneme düşüşü)
    → VELİYE bilgi (haftalık raporu beklemeden)
  · olumlu gelişme → ÖĞRENCİYE tebrik + VELİYE bilgi
  · hatırlatma (dünü işaretlemedi, bugün başlamadı) → ÖĞRENCİYE
  · yeni rapor (deneme analizi, haftalık rapor) → ÖĞRENCİ + VELİ, bağlantıyla

Kurallar: sınır YOK (koç seçer), koça bugün kaç mesaj gönderdiği gösterilir;
veri güvenilirliği uyarıları (toplu işaretleme, D/Y girilmiyor) veliye gitmez —
listede hiç yer almaz. Ölçüm YENİ değildir: student_flags (Genel sekmesiyle aynı).
Gönderim Meta hattı gelene kadar koçun kendi WhatsApp'ından (wa.me).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import ExamResult, Task, User
from app.models.task import TaskStatus
from app.models.message_suggestion import ACTION_SENT, MessageSuggestionAction

LINK_TOKEN = "[rapor bağlantısı]"

#: Veliye bilgi olarak gidebilecek sorun kodları (veri güvenilirliği bilinçli YOK).
PARENT_PROBLEM_CODES = {"empty_streak", "completion_low", "completion_drop", "deneme_skipped"}
POSITIVE_CODES = {"good_streak", "good_completion", "good_deneme", "good_net_up"}

KIND_LABELS = {
    "problem": "Dikkat",
    "positive": "Tebrik",
    "reminder": "Hatırlatma",
    "report": "Yeni rapor",
}


@dataclass
class Suggestion:
    key: str
    audience: str            # "parent" | "student"
    kind: str                # problem | positive | reminder | report
    title: str
    reason: str
    text: str
    report: dict | None = None   # {"kind": "exam"|"weekly", "exam_id"?, "week_start"?}
    order: int = 50
    extra: dict = field(default_factory=dict)


def _first(name: str | None) -> str:
    return (name or "").strip().split(" ")[0] if name else ""


def _tr_today() -> date:
    return (datetime.now(timezone.utc) + timedelta(hours=3)).date()


def _iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}w{w:02d}"


def _genitive(name: str) -> str:
    from app.services.parent_weekly_mail import genitive

    return genitive(name)


def build_for_student(db: Session, student: User, today: date | None = None) -> list[Suggestion]:
    """Bir öğrenci için bugünün aday mesajları (karar verilmiş olanlar dahil — süzme ayrıca)."""
    from app.services.student_flags import evaluate_flags

    today = today or _tr_today()
    first = _first(student.full_name) or "Öğrencimiz"
    gen = _genitive(first)
    out: list[Suggestion] = []

    rep = evaluate_flags(db, student, today)
    warns = list(rep.primary) + list(rep.secondary)
    goods = list(rep.good)
    codes = {w.code: w for w in warns}

    # --- sorunlar → veliye bilgi
    for w in warns:
        code = w.code
        base = code if code in PARENT_PROBLEM_CODES else ("subject_avoid" if code.startswith("subject_avoid_") else None)
        if base is None or getattr(w, "coach_only", False):
            continue
        detail = (w.detail or "").strip()
        out.append(Suggestion(
            key=f"{code}:{_iso_week(today)}",
            audience="parent", kind="problem",
            title=w.title, reason=detail,
            text=(f"Merhaba, {gen} programıyla ilgili kısa bir bilgi vermek istedim: {w.title.rstrip('.')}. "
                  f"{detail} Bu konuyu {first} ile konuşacağım; evde de hatırlatırsanız çok faydalı olur."),
            order=10,
        ))

    # --- olumlu gelişmeler → öğrenciye tebrik + veliye bilgi
    for w in goods:
        if w.code not in POSITIVE_CODES:
            continue
        detail = (w.detail or "").strip()
        k = f"{w.code}:{_iso_week(today)}"
        out.append(Suggestion(
            key=k, audience="student", kind="positive", title=w.title, reason=detail,
            text=f"Tebrikler {first}! {w.title.rstrip('.')}. {detail} Böyle devam, seninle gurur duyuyorum.",
            order=30,
        ))
        out.append(Suggestion(
            key=k, audience="parent", kind="positive", title=w.title, reason=detail,
            text=(f"Merhaba, {gen} güzel bir gelişmesini paylaşmak istedim: {w.title.rstrip('.')}. {detail} "
                  f"Onu tebrik ederseniz çok sevinir."),
            order=30,
        ))

    # --- haftalık ilerleme (Genel sekmesiyle AYNI ölçü): görev birikmesi, kaçınılan ders,
    #     branş denemeleri → veliye bilgi. Zamanlama/yük/doğruluk koç işi, veliye gitmez.
    wk = _iso_week(today)
    try:
        from app.services.weekly_progress import build_weekly_progress

        wp = build_weekly_progress(db, student, today=today)
    except Exception:  # noqa: BLE001
        wp = {}
    for a in wp.get("actions") or []:
        if a.get("key") == "carry":
            n = a["title"].split()[1] if a["title"].startswith("Kalan ") else ""
            why = a.get("why", "")
            out.append(Suggestion(
                key=f"carry:{wk}:{n}", audience="parent", kind="problem",
                title=f"Bu hafta {n} görev yapılmadı", reason=why,
                text=(f"Merhaba, {gen} bu haftaki programıyla ilgili bilgi vermek istedim: {why} "
                      f"Kalan görevleri birlikte planlayacağız; evde günlük programını tamamlamasını "
                      f"hatırlatırsanız çok faydalı olur."),
                order=8,
            ))
            out.append(Suggestion(
                key=f"carry:{wk}:{n}", audience="student", kind="reminder",
                title=f"Bu hafta {n} görev kaldı", reason=why,
                text=(f"Merhaba {first}, bu hafta {n} görevin yapılmadan kaldı. Bugünkü programınla başla, "
                      f"kalanları birlikte planlayalım. Takipteyim, yapabilirsin."),
                order=9,
            ))
        elif a.get("key") == "avoid":
            why = a.get("why", "")
            subj = a["title"].split(" için ")[0]
            out.append(Suggestion(
                key=f"avoid:{wk}:{subj}", audience="parent", kind="problem",
                title=f"{subj} dersinde görevler aksıyor", reason=why,
                text=(f"Merhaba, {gen} programında {subj} dersi geride kalıyor. {why} "
                      f"Bu konuyu seansta konuşacağız; evde de sorarsanız destek olur."),
                order=11,
            ))
        elif a.get("key") == "brans" and a["title"].startswith("Branş denemelerini"):
            why = a.get("why", "")
            out.append(Suggestion(
                key=f"brans:{wk}", audience="parent", kind="problem",
                title="Branş denemeleri çözülmüyor", reason=why,
                text=(f"Merhaba, {gen} programındaki branş denemeleriyle ilgili bilgi vermek istedim: {why} "
                      f"Bu denemeler hangi konuda net kaybettiğini görmemizi sağlıyor; çözmesi için desteğiniz önemli."),
                order=12,
            ))

    # --- denemeler ve hedef (Genel sekmesindeki deneme satırlarıyla aynı)
    try:
        from app.services.student_overview import exam_overview

        eo = exam_overview(db, student, today)
    except Exception:  # noqa: BLE001
        eo = {}
    for ex in eo.get("exams") or []:
        label = (ex.get("series_label") or "Deneme").replace(" (genel deneme)", "")
        txt = (ex.get("text") or "").strip()
        k = f"exam_trend:{ex.get('series_key')}:{wk}"
        if ex.get("tone") == "warn" and (ex.get("count") or 0) >= 2:
            out.append(Suggestion(
                key=k, audience="parent", kind="problem", title=f"{label} denemelerinde düşüş", reason=txt,
                text=(f"Merhaba, {gen} {label} denemeleriyle ilgili bilgi vermek istedim: {txt} "
                      f"Eksik konular üzerinde birlikte çalışacağız."),
                order=13,
            ))
        elif ex.get("tone") == "good" and (ex.get("count") or 0) >= 2:
            out.append(Suggestion(
                key=k, audience="student", kind="positive", title=f"{label} netleri yükseliyor", reason=txt,
                text=f"Tebrikler {first}! {label} denemelerinde netlerin yükseliyor. {txt} Böyle devam!",
                order=31,
            ))
            out.append(Suggestion(
                key=k, audience="parent", kind="positive", title=f"{label} netleri yükseliyor", reason=txt,
                text=(f"Merhaba, {gen} güzel bir gelişmesini paylaşmak istedim: {label} denemelerinde netleri "
                      f"yükseliyor. {txt} Onu tebrik ederseniz çok sevinir."),
                order=31,
            ))
    for tg in eo.get("targets") or []:
        if tg.get("tone") != "good":
            continue
        label = (tg.get("series_label") or "").replace(" (genel deneme)", "")
        txt = (tg.get("text") or "").strip()
        k = f"target_good:{tg.get('series_key')}:{wk}"
        out.append(Suggestion(
            key=k, audience="student", kind="positive", title=f"{label} hedefine doğru gidiyor".strip(),
            reason=txt, text=f"Tebrikler {first}! Hedefine doğru ilerliyorsun. {txt}", order=32,
        ))
        out.append(Suggestion(
            key=k, audience="parent", kind="positive", title=f"{label} hedefine doğru gidiyor".strip(),
            reason=txt, text=f"Merhaba, {first} hedefine doğru ilerliyor. {txt} Desteğiniz için teşekkürler.",
            order=32,
        ))

    # --- hatırlatmalar → öğrenciye
    y = today - timedelta(days=1)
    y_tasks = (db.query(Task).filter(Task.student_id == student.id, Task.date == y,
                                     Task.is_draft.is_(False)).all())
    if y_tasks and not any(t.status == TaskStatus.COMPLETED for t in y_tasks) and not any(
            (bi.completed_count or 0) > 0 for t in y_tasks for bi in t.book_items):
        out.append(Suggestion(
            key=f"remind_mark:{y.isoformat()}", audience="student", kind="reminder",
            title="Dünkü program işaretlenmemiş",
            reason=f"Dün {len(y_tasks)} görev vardı; hiçbiri işaretlenmedi.",
            text=(f"Merhaba {first}, dünkü programında {len(y_tasks)} görev vardı ama hiçbirini işaretlemedin. "
                  f"Yaptıklarını bugün işaretlersen ilerlemeni görebilirim. Takipteyim."),
            order=20,
        ))
    if "today_no_tick" in codes:
        w = codes["today_no_tick"]
        out.append(Suggestion(
            key=f"today_no_tick:{today.isoformat()}", audience="student", kind="reminder",
            title="Bugün henüz başlamadı", reason=(w.detail or "").strip(),
            text=(f"Merhaba {first}, bugünkü programında henüz bir görevi işaretlemedin. "
                  f"Bir görevle başla, gerisi gelir. Seni takip ediyorum, başarabilirsin."),
            order=21,
        ))

    # --- yeni rapor → öğrenci + veli
    since = datetime.now(timezone.utc) - timedelta(days=3)
    from app.models.exam_result import analysis_exam_filter

    exams = (db.query(ExamResult)
             .filter(ExamResult.student_id == student.id, ExamResult.created_at >= since, analysis_exam_filter())
             .order_by(ExamResult.created_at.desc()).limit(2).all())
    for ex in exams:
        net = f"{ex.net:.2f}".replace(".", ",").rstrip("0").rstrip(",") if ex.net is not None else ""
        out.append(Suggestion(
            key=f"report_exam:{ex.id}", audience="parent", kind="report",
            title=f"Deneme analizi hazır: {ex.title}", reason=f"{ex.exam_date:%d.%m.%Y} · {net} net",
            text=(f"Merhaba, {gen} {_exam_phrase(ex.title, own=False)} analizi hazır ({net} net). Konu konu durumu ve evde "
                  f"nasıl destek olabileceğinizi raporda bulabilir, sesli olarak da dinleyebilirsiniz:\n{LINK_TOKEN}"),
            report={"kind": "exam", "exam_id": ex.id}, order=5,
        ))
        out.append(Suggestion(
            key=f"report_exam:{ex.id}", audience="student", kind="report",
            title=f"Deneme analizi hazır: {ex.title}", reason=f"{ex.exam_date:%d.%m.%Y} · {net} net",
            text=(f"Merhaba {first}, {_exam_phrase(ex.title, own=True)} analizi hazır ({net} net). Hangi konularda net "
                  f"kazanabileceğini görmek için bir göz at:\n{LINK_TOKEN}"),
            report={"kind": "exam", "exam_id": ex.id}, order=5,
        ))

    if today.weekday() <= 1:  # Pazartesi–Salı: geçen haftanın raporu
        from app.services.admin_digest import report_week

        ws, we = report_week(today)
        has_week = db.query(Task.id).filter(Task.student_id == student.id, Task.date >= ws,
                                            Task.date <= we, Task.is_draft.is_(False)).first()
        if has_week:
            label = f"{ws.day}–{we.day} {_month(we)}" if ws.month == we.month else f"{ws.day} {_month(ws)} – {we.day} {_month(we)}"
            out.append(Suggestion(
                key=f"report_weekly:{ws.isoformat()}", audience="parent", kind="report",
                title=f"Haftalık rapor hazır ({label})", reason="Geçen haftanın görev uyumu, dersleri ve önerileri",
                text=(f"Merhaba, {gen} {label} haftasının raporu hazır: görev uyumu, ders ders durum, denemeler ve "
                      f"gelecek hafta. Sesli olarak da dinleyebilirsiniz:\n{LINK_TOKEN}"),
                report={"kind": "weekly", "week_start": ws.isoformat()}, order=6,
            ))
    out.sort(key=lambda s: s.order)
    return out


def _exam_phrase(title: str, *, own: bool) -> str:
    """"LGS Deneme 4" → "LGS Deneme 4" (adı zaten deneme diyor); "Özdebir TG-3" → "Özdebir TG-3 denemesinin"."""
    t = (title or "").strip()
    if "deneme" in t.lower():
        return f"{t} sonucunun" if not own else f"{t} sonucunun"
    return f"{t} denemesinin" if not own else f"{t} denemenin"


_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
           "Kasım", "Aralık"]


def _month(d: date) -> str:
    return _MONTHS[d.month - 1]


def decided_keys(db: Session, student_ids: list[int]) -> set[tuple[int, str, str]]:
    if not student_ids:
        return set()
    rows = (db.query(MessageSuggestionAction.student_id, MessageSuggestionAction.audience,
                     MessageSuggestionAction.suggestion_key)
            .filter(MessageSuggestionAction.student_id.in_(student_ids)).all())
    return {(r[0], r[1], r[2]) for r in rows}


def sent_today(db: Session, coach_id: int) -> int:
    start_tr = datetime.combine(_tr_today(), datetime.min.time())
    start_utc = (start_tr - timedelta(hours=3)).replace(tzinfo=timezone.utc)
    return (db.query(MessageSuggestionAction)
            .filter(MessageSuggestionAction.coach_id == coach_id,
                    MessageSuggestionAction.action == ACTION_SENT,
                    MessageSuggestionAction.created_at >= start_utc).count())


def record(db: Session, *, coach_id: int, student_id: int, audience: str, key: str, action: str,
           target_user_id: int | None) -> None:
    row = (db.query(MessageSuggestionAction)
           .filter(MessageSuggestionAction.student_id == student_id,
                   MessageSuggestionAction.audience == audience,
                   MessageSuggestionAction.suggestion_key == key).first())
    if row is None:
        db.add(MessageSuggestionAction(coach_id=coach_id, student_id=student_id, audience=audience,
                                       suggestion_key=key[:120], action=action, target_user_id=target_user_id))
    elif row.action != ACTION_SENT:
        row.action = action
        row.target_user_id = target_user_id
        row.coach_id = coach_id
    db.flush()


def report_link(db: Session, *, student: User, report: dict, actor_id: int) -> str | None:
    from app.models.exam_parent_report import REPORT_KIND_EXAM, REPORT_KIND_WEEKLY
    from app.services.exam_parent_report import get_or_create_link, report_url

    if report.get("kind") == "exam":
        ex = db.get(ExamResult, report.get("exam_id"))
        if ex is None or ex.student_id != student.id:
            return None
        rep, _ = get_or_create_link(db, kind=REPORT_KIND_EXAM, student_id=student.id, actor_id=actor_id, exam_id=ex.id)
        return report_url(rep.token)
    if report.get("kind") == "weekly":
        ws = date.fromisoformat(report["week_start"])
        rep, _ = get_or_create_link(db, kind=REPORT_KIND_WEEKLY, student_id=student.id, actor_id=actor_id,
                                    week_start=ws)
        return report_url(rep.token)
    return None
