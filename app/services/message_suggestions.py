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


def _num(v) -> str:
    if v is None:
        return ""
    return f"{v:.2f}".replace(".", ",").rstrip("0").rstrip(",")


def _join(items: list[str], more_word: str = "konu") -> str:
    """"A, B ve C" — en çok 3 ad; fazlası "ve N konu daha"."""
    items = [x for x in items if x]
    if not items:
        return ""
    head, rest = items[:3], len(items) - 3
    if rest > 0:
        return ", ".join(head) + f" ve {rest} {more_word} daha"
    return head[0] if len(head) == 1 else ", ".join(head[:-1]) + " ve " + head[-1]


def _panel_url(student: User) -> str:
    from app.config import settings

    base = (getattr(settings, "app_base_url", "") or "").rstrip("/")
    return f"{base}/parent/students/{student.id}"


def _short_topic(t: Task) -> list[str]:
    """Yapılmayan görevin kısa konu adı: "Kimya · Sıvı Çözeltiler" yerine "Sıvı Çözeltiler (Kimya)"."""
    out: list[str] = []
    for bi in t.book_items or []:
        rem = (bi.planned_count or 0) - (bi.completed_count or 0)
        if rem <= 0:
            continue
        subj = None
        if bi.book is not None and getattr(bi.book, "subject", None) is not None:
            subj = bi.book.subject.name
        elif getattr(bi, "exam_subject", None) is not None:
            subj = bi.exam_subject.name
        if getattr(bi, "exam_kind", None):
            out.append(f"{subj} branş denemesi" if subj else "deneme")
            continue
        name = None
        if bi.section is not None:
            name = bi.section.label
        elif getattr(bi, "topic", None) is not None:
            name = bi.topic.name
        if name:
            name = name.split("·")[-1].split(" — ")[-1].strip()
            out.append(f"{name} ({subj})" if subj and subj.lower() not in name.lower() else name)
    if not out:
        title = (t.title or "").split(":")[0].split(" — ")[-1].strip()
        if title:
            out.append(title)
    return out


def _missing_topics(db: Session, student: User, start: date, end: date) -> list[str]:
    from sqlalchemy.orm import selectinload

    from app.models import TaskBookItem

    tasks = (db.query(Task).options(selectinload(Task.book_items).joinedload(TaskBookItem.book))
             .filter(Task.student_id == student.id, Task.is_draft.is_(False),
                     Task.date >= start, Task.date <= end).order_by(Task.date, Task.id).all())
    seen: list[str] = []
    for t in tasks:
        if t.status == TaskStatus.COMPLETED:
            continue
        for name in _short_topic(t):
            if name not in seen:
                seen.append(name)
    return seen


def build_for_student(db: Session, student: User, today: date | None = None) -> list[Suggestion]:
    """Bir öğrenci için bugünün aday mesajları (karar verilmiş olanlar dahil — süzme ayrıca).

    Dil (2026-11-14, koç): öğrenciye SOHBET açan mesaj ("dikkatimi çekti, sence ne oldu?"),
    veliye kısa BİLGİ + ayrıntı için Rotam bağlantısı. Konular kısa adla, virgülle, en çok 3."""
    from app.services.student_flags import evaluate_flags

    if getattr(student, "is_paused", False) or not student.is_active:
        return []  # molada / pasif öğrenciye ve velisine öneri yok
    today = today or _tr_today()
    first = _first(student.full_name) or "Öğrencimiz"
    gen = _genitive(first)
    more = f"Ayrıntıları Rotam'da görebilirsiniz: {_panel_url(student)}"
    wk = _iso_week(today)
    out: list[Suggestion] = []

    rep = evaluate_flags(db, student, today)
    warns = list(rep.primary) + list(rep.secondary)
    goods = list(rep.good)
    codes = {w.code: w for w in warns}

    # --- haftalık ilerleme (Genel sekmesiyle AYNI ölçü)
    try:
        from app.services.weekly_progress import build_weekly_progress

        wp = build_weekly_progress(db, student, today=today)
    except Exception:  # noqa: BLE001
        wp = {}
    week = wp.get("week") or {}
    actions = {a.get("key"): a for a in wp.get("actions") or []}

    carry = actions.get("carry")
    if carry and week.get("start"):
        n = carry["title"].split()[1] if carry["title"].startswith("Kalan ") else ""
        ws = date.fromisoformat(week["start"])
        topics = _missing_topics(db, student, ws, today - timedelta(days=1))
        tl = _join(topics)
        out.append(Suggestion(
            key=f"carry:{wk}:{n}", audience="parent", kind="problem",
            title=f"Bu hafta {n} görev yapılmadı", reason=tl or carry.get("why", ""),
            text=(f"Merhaba, {gen} bu haftaki programından kısa bir bilgi: {n} görev yapılmadan kaldı"
                  + (f". Aksayan konular: {tl}." if tl else ".")
                  + f" Kalanları birlikte planlayacağız; evde günlük programını sormanız çok destek olur.\n{more}"),
            order=8,
        ))
        out.append(Suggestion(
            key=f"carry:{wk}:{n}", audience="student", kind="problem",
            title=f"Bu hafta {n} görev kaldı", reason=tl or carry.get("why", ""),
            text=(f"Merhaba {first}, bu hafta {n} görevin yapılmadan kaldı"
                  + (f"; özellikle {tl} dikkatimi çekti." if tl else ", bu dikkatimi çekti.")
                  + " Sence ne oldu, zorlandığın bir yer mi var? Yazarsan kalanları birlikte planlayalım."),
            order=9,
        ))

    avoid = actions.get("avoid")
    if avoid:
        subj = avoid["title"].split(" için ")[0]
        why = avoid.get("why", "")
        out.append(Suggestion(
            key=f"avoid:{wk}:{subj}", audience="parent", kind="problem",
            title=f"{subj} dersi geride kalıyor", reason=why,
            text=(f"Merhaba, {gen} programından kısa bir bilgi: son haftalarda {subj} görevleri diğer derslere "
                  f"göre daha az yapılıyor. Bu konuyu seansta konuşacağız.\n{more}"),
            order=11,
        ))
        out.append(Suggestion(
            key=f"avoid:{wk}:{subj}", audience="student", kind="problem",
            title=f"{subj} geride kalıyor", reason=why,
            text=(f"Merhaba {first}, son haftalarda {subj} görevlerinin diğer derslerden geride kaldığını fark ettim. "
                  f"Bu derste seni zorlayan bir şey mi var? Konuşalım, birlikte çözelim."),
            order=11,
        ))

    brans = actions.get("brans")
    if brans and brans["title"].startswith("Branş denemelerini"):
        import re

        m = re.search(r"(\d+) branş denemesi kondu, (\d+) tanesi çözüldü", brans.get("why", ""))
        given, solved = (m.group(1), m.group(2)) if m else ("", "")
        fact = (f"son 4 haftada programa konan {given} branş denemesinin {solved} tanesi çözüldü" if m
                else "programdaki branş denemelerinin bir kısmı çözülmedi")
        out.append(Suggestion(
            key=f"brans:{wk}", audience="parent", kind="problem",
            title="Branş denemeleri çözülmüyor", reason=brans.get("why", ""),
            text=(f"Merhaba, {gen} branş denemeleriyle ilgili kısa bir bilgi: {fact}. Bu denemeler hangi "
                  f"konularda net kaybettiğini görmemizi sağlıyor.\n{more}"),
            order=12,
        ))
        out.append(Suggestion(
            key=f"brans:{wk}", audience="student", kind="problem",
            title="Branş denemeleri çözülmüyor", reason=brans.get("why", ""),
            text=(f"Merhaba {first}, programındaki branş denemelerinin bir kısmını çözmediğini gördüm. "
                  f"Süre mi yetmiyor, yoksa zor mu geliyor? Hangisi olduğunu bilirsem programı ona göre ayarlarım."),
            order=12,
        ))

    # --- denemeler ve hedef (Genel sekmesindeki deneme satırlarıyla aynı)
    try:
        from app.services.student_overview import exam_overview

        eo = exam_overview(db, student, today)
    except Exception:  # noqa: BLE001
        eo = {}
    for ex in eo.get("exams") or []:
        if (ex.get("count") or 0) < 2:
            continue
        label = (ex.get("series_label") or "Deneme").replace(" (genel deneme)", "")
        diff = ex.get("diff")
        last = f"son denemesinde {_num(ex.get('last_net'))} net yaptı"
        if diff is not None:
            last += f" (öncekine göre {'+' if diff >= 0 else '−'}{_num(abs(diff))})"
        k = f"exam_trend:{ex.get('series_key')}:{wk}"
        if ex.get("tone") == "warn":
            out.append(Suggestion(
                key=k, audience="parent", kind="problem", title=f"{label} denemelerinde eğilim aşağı",
                reason=ex.get("text", ""),
                text=(f"Merhaba, {gen} {label} denemelerinden kısa bir bilgi: {last}. Son "
                      f"{ex.get('slope_window') or ''} denemenin genel eğilimi ise aşağı yönlü; eksik konular "
                      f"üzerinde birlikte çalışacağız.\n{more}").replace("Son  denemenin", "Son denemelerin"),
                order=13,
            ))
            out.append(Suggestion(
                key=k, audience="student", kind="problem", title=f"{label} denemelerinde eğilim aşağı",
                reason=ex.get("text", ""),
                text=(f"Merhaba {first}, son {label} denemende {_num(ex.get('last_net'))} net yaptın. "
                      f"Ama son denemelere birlikte bakınca netlerin biraz aşağı gidiyor. Sence hangi derste "
                      f"zorlanıyorsun? Bir sonraki seansta üzerine gidelim."),
                order=13,
            ))
        elif ex.get("tone") == "good":
            out.append(Suggestion(
                key=k, audience="student", kind="positive", title=f"{label} netleri yükseliyor",
                reason=ex.get("text", ""),
                text=(f"Tebrikler {first}! {label} denemelerinde netlerin yükseliyor; son denemende "
                      f"{_num(ex.get('last_net'))} net. Sence bu yükselişte en çok ne işe yaradı? Böyle devam!"),
                order=31,
            ))
            out.append(Suggestion(
                key=k, audience="parent", kind="positive", title=f"{label} netleri yükseliyor",
                reason=ex.get("text", ""),
                text=(f"Merhaba, {gen} güzel bir gelişmesini paylaşmak istedim: {label} denemelerinde netleri "
                      f"yükseliyor, {last}. Onu tebrik ederseniz çok sevinir.\n{more}"),
                order=31,
            ))
    for tg in eo.get("targets") or []:
        if tg.get("tone") != "good":
            continue
        label = (tg.get("series_label") or "").replace(" (genel deneme)", "")
        k = f"target_good:{tg.get('series_key')}:{wk}"
        out.append(Suggestion(
            key=k, audience="student", kind="positive", title=f"{label} hedefine doğru gidiyor".strip(),
            reason=tg.get("text", ""),
            text=f"Tebrikler {first}! {label} hedefine doğru ilerliyorsun. Bu tempoyu korumak için neye ihtiyacın var?",
            order=32,
        ))
        out.append(Suggestion(
            key=k, audience="parent", kind="positive", title=f"{label} hedefine doğru gidiyor".strip(),
            reason=tg.get("text", ""),
            text=f"Merhaba, {first} {label} hedefine doğru ilerliyor. Desteğiniz için teşekkürler.\n{more}",
            order=32,
        ))

    # --- sistem uyarıları (boş gün serisi, tamamlama düşüşü, deneme atlandı) → veliye bilgi
    for w in warns:
        code = w.code
        if code not in PARENT_PROBLEM_CODES or getattr(w, "coach_only", False):
            continue
        if code in ("completion_low", "completion_drop") and carry:
            continue  # aynı şeyi "görev yapılmadı" mesajı zaten söylüyor
        out.append(Suggestion(
            key=f"{code}:{wk}", audience="parent", kind="problem",
            title=w.title, reason=(w.detail or "").strip(),
            text=f"Merhaba, {gen} programından kısa bir bilgi: {w.title[0].lower() + w.title[1:]}.\n{more}",
            order=10,
        ))

    # --- olumlu gelişmeler (eksiksiz günler, yüksek tamamlama) → tebrik + bilgi
    for w in goods:
        if w.code not in POSITIVE_CODES or w.code == "good_net_up":
            continue  # net artışı yukarıdaki deneme satırında
        k = f"{w.code}:{wk}"
        t = w.title[0].lower() + w.title[1:]
        out.append(Suggestion(
            key=k, audience="student", kind="positive", title=w.title, reason=(w.detail or "").strip(),
            text=f"Tebrikler {first}! {w.title.rstrip('.')}. Bu düzen çok değerli; seninle gurur duyuyorum.",
            order=30,
        ))
        out.append(Suggestion(
            key=k, audience="parent", kind="positive", title=w.title, reason=(w.detail or "").strip(),
            text=f"Merhaba, {gen} güzel bir gelişmesini paylaşmak istedim: {t}. Onu tebrik ederseniz çok sevinir.\n{more}",
            order=30,
        ))

    # --- hatırlatmalar → öğrenciye (sohbet)
    y = today - timedelta(days=1)
    y_tasks = (db.query(Task).filter(Task.student_id == student.id, Task.date == y,
                                     Task.is_draft.is_(False)).all())
    if y_tasks and not any(t.status == TaskStatus.COMPLETED for t in y_tasks) and not any(
            (bi.completed_count or 0) > 0 for t in y_tasks for bi in t.book_items):
        out.append(Suggestion(
            key=f"remind_mark:{y.isoformat()}", audience="student", kind="reminder",
            title="Dünkü program işaretlenmemiş",
            reason=f"Dün {len(y_tasks)} görev vardı; hiçbiri işaretlenmedi.",
            text=(f"Merhaba {first}, dünkü programında {len(y_tasks)} görev vardı ama hiç işaret göremedim. "
                  f"Yapabildin mi, yoksa bir şey mi oldu? İşaretlersen nerede olduğunu birlikte görürüz."),
            order=20,
        ))
    if "today_no_tick" in codes:
        out.append(Suggestion(
            key=f"today_no_tick:{today.isoformat()}", audience="student", kind="reminder",
            title="Bugün henüz başlamadı", reason=(codes["today_no_tick"].detail or "").strip(),
            text=(f"Merhaba {first}, bugün henüz bir görev işaretlemedin. Nasıl gidiyor, başlayabildin mi? "
                  f"İlk görevle başlarsan gerisi kolaylaşır."),
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


# =============================================================================
# Önbellek (2026-11-14): öğrenci başına ~0,15 sn; çok öğrencili koçta liste yavaşlamasın.
# 5 dakika; karar verilenler önbellekten SONRA süzülür (gönder/atla anında düşer).
# =============================================================================
import time as _time

_CACHE: dict[tuple, tuple[float, list]] = {}
CACHE_TTL = 300.0


def cached_for_student(db: Session, student: User, today: date | None = None) -> list[Suggestion]:
    if getattr(student, "is_paused", False) or not student.is_active:
        return []  # mola/pasif önbellekten ÖNCE — molaya alınan öğrenci anında düşer
    today = today or _tr_today()
    k = ("s", student.id, today.isoformat())
    hit = _CACHE.get(k)
    now = _time.monotonic()
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    val = build_for_student(db, student, today)
    _CACHE[k] = (now, val)
    if len(_CACHE) > 5000:
        _CACHE.clear()
    return val


# =============================================================================
# Kurum yöneticisi → koç (2026-11-14): koçun öğrencilerinde görülen durumlar için
# koça hazır WhatsApp mesajı. Ölçüm YENİ DEĞİL: kurum Program Uyumu + risk analizi
# (Müdahale Merkezi ile aynı). Koça sohbet açan, kısa, isimli mesajlar.
# =============================================================================

def build_for_institution(db: Session, institution_id: int, today: date | None = None) -> dict[int, list[Suggestion]]:
    """Koç id → öneriler."""
    from app.models import UserRole
    from app.services.institution_compliance import compute_compliance
    from app.services.risk_analysis import bulk_risk_assessment, filter_at_risk

    today = today or _tr_today()
    wk = _iso_week(today)
    comp = compute_compliance(db, institution_id=institution_id, weeks=2, today=today)
    coaches = {int(u.id): u for u in db.query(User).filter(
        User.role == UserRole.TEACHER, User.institution_id == institution_id, User.is_active.is_(True)).all()}
    out: dict[int, list[Suggestion]] = {cid: [] for cid in coaches}

    def coach_first(cid: int) -> str:
        return _first(coaches[cid].full_name) or "Hocam"

    for e in comp.get("empty_program") or []:
        cid = e.get("teacher_id")
        if cid not in coaches:
            continue
        names = _join(e.get("sample_students") or [], "öğrenci")
        out[cid].append(Suggestion(
            key=f"inst_empty:{wk}:{e['count']}", audience="coach", kind="problem",
            title=f"{e['count']} öğrencinin bu hafta programı yok", reason=names,
            text=(f"Merhaba {coach_first(cid)} Hocam, bu hafta {names} için henüz program görünmüyor. "
                  f"Fırsat bulduğunda programlarını girebilir misin? Yardımcı olabileceğim bir şey varsa yaz lütfen."),
            order=5,
        ))
    for t in comp.get("teachers") or []:
        cid = t.get("teacher_id")
        if cid not in coaches or not t.get("student_count"):
            continue
        rate, last = t.get("rate"), t.get("last_rate")
        if rate is not None and rate < 60:
            prev = f" (geçen hafta %{last})" if last is not None else ""
            out[cid].append(Suggestion(
                key=f"inst_low:{wk}", audience="coach", kind="problem",
                title=f"Son 7 günde tamamlama %{rate}", reason=f"{t['student_count']} öğrenci{prev}",
                text=(f"Merhaba {coach_first(cid)} Hocam, son 7 günde öğrencilerin planlanan testlerin "
                      f"%{rate} kadarını çözmüş görünüyor{prev}. Sence programların yükü mü fazla, yoksa öğrencilerde "
                      f"başka bir şey mi var? Bu hafta kısaca konuşalım mı?"),
                order=8,
            ))
        elif rate is not None and rate >= 85 and t["student_count"] >= 2:
            out[cid].append(Suggestion(
                key=f"inst_good:{wk}", audience="coach", kind="positive",
                title=f"Son 7 günde tamamlama %{rate}", reason=f"{t['student_count']} öğrenci",
                text=(f"Merhaba {coach_first(cid)} Hocam, son 7 günde öğrencilerin planlanan testlerin "
                      f"%{rate} kadarını çözmüş. Emeğin için teşekkürler, harika gidiyor!"),
                order=30,
            ))

    students = db.query(User).filter(User.role == UserRole.STUDENT, User.teacher_id.in_(list(coaches)),
                                     User.is_active.is_(True)).all() if coaches else []
    students = [st for st in students if not getattr(st, "is_paused", False)]
    if students:
        assess = bulk_risk_assessment(db, students=students)
        risky: dict[int, list] = {}
        idle: dict[int, list] = {}
        for a in filter_at_risk(assess, min_level="high"):
            risky.setdefault(a.student.teacher_id, []).append(a)
        rset = {int(a.student.id) for v in risky.values() for a in v}
        for a in assess:
            if int(a.student.id) in rset:
                continue
            if any(i.code == "consecutive_empty" for i in a.indicators):
                idle.setdefault(a.student.teacher_id, []).append(a)
        for cid, lst in risky.items():
            if cid not in coaches:
                continue
            lst.sort(key=lambda a: -a.score)
            names = _join([a.student.full_name for a in lst], "öğrenci")
            reasons = _join(sorted({i.title for a in lst for i in a.indicators[:2]}), "neden")
            out[cid].append(Suggestion(
                key=f"inst_risk:{wk}:{len(lst)}", audience="coach", kind="problem",
                title=f"{len(lst)} öğrencide risk sinyali", reason=reasons,
                text=(f"Merhaba {coach_first(cid)} Hocam, sistemde {names} için risk sinyali görünüyor "
                      f"({reasons.lower()}). Bu öğrencilerle bu hafta birebir görüşme fırsatın olur mu?"),
                order=6,
            ))
        for cid, lst in idle.items():
            if cid not in coaches:
                continue
            names = _join([a.student.full_name for a in lst], "öğrenci")
            out[cid].append(Suggestion(
                key=f"inst_idle:{wk}:{len(lst)}", audience="coach", kind="problem",
                title=f"{len(lst)} öğrenci programını yapmıyor", reason=names,
                text=(f"Merhaba {coach_first(cid)} Hocam, {names} birkaç gündür programını yapmıyor görünüyor. "
                      f"Öğrencilerle iletişime geçebilir misin? Destek gerekirse buradayım."),
                order=7,
            ))
    for cid in out:
        out[cid].sort(key=lambda x: x.order)
    return out


def cached_for_institution(db: Session, institution_id: int) -> dict[int, list[Suggestion]]:
    today = _tr_today()
    k = ("i", institution_id, today.isoformat())
    hit = _CACHE.get(k)
    now = _time.monotonic()
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]  # type: ignore[return-value]
    val = build_for_institution(db, institution_id, today)
    _CACHE[k] = (now, val)  # type: ignore[assignment]
    return val


def dispatch_direct(db: Session, *, sender: User, target: User, text: str, key: str) -> dict:
    """Kişiye doğrudan WhatsApp bağlantısı + denetim kaydı (kurum → koç)."""
    import json

    from app.models.whatsapp_dispatch_log import WhatsAppDispatchLog
    from app.services import comm_log
    from app.services.whatsapp_link_service import (
        WaDispatchError, build_wa_url, can_message_phone, can_send_wa_to, mask_phone_e164)
    from urllib.parse import quote

    if not can_send_wa_to(db, sender=sender, target=target):
        raise WaDispatchError("target_not_found", "Kişi bulunamadı.", status=404)
    clean = (text or "").strip()
    wa_url = build_wa_url(target.phone, clean) if can_message_phone(target) else \
        f"https://wa.me/?text={quote(clean, safe='')}"
    db.add(WhatsAppDispatchLog(sender_user_id=sender.id, target_user_id=target.id,
                               template_key=f"sugg:{key}"[:80], template_id=None,
                               params_json=json.dumps({"key": key}, ensure_ascii=False),
                               character_count=len(clean)))
    db.flush()
    comm_log.log_whatsapp(db=db, status="sent", to_user_id=target.id,
                          to_address=mask_phone_e164(target.phone) if target.phone else "kişi WhatsApp'ta seçildi",
                          category="coach_message", subject=f"Kurum mesajı · {target.full_name}"[:120],
                          meta_json=json.dumps({"sender_id": sender.id, "key": key}))
    return {"wa_url": wa_url, "target_name": target.full_name if can_message_phone(target) else None}
