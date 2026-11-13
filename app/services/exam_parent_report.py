"""Deneme analiz raporu — veli için TEK STANDART (2026-11-13).

KOÇ İSTEĞİ: "Veliye WhatsApp" karnesi, "veliye giden maili gör/PDF" çıktısı ve
duyuru e-postası birbirinden farklıydı. Hepsi aynı standarda geçer: velinin
sonucu anlayabileceği, sayıdan çok yorum taşıyan, Rota'nın sesiyle
dinlenebilen bir analiz raporu.

TEK KAYNAK: `build_report_data` → bağlantılı web sayfası (/rapor/{token}), sunucu
PDF'i (`render_report_pdf`) ve seslendirme metni (`speech_text`) aynı sözlükten
beslenir; üçü ayrışamaz. Sayılar `exam_parent_summary.build_email_context`'ten
gelir (koç paneli + duyuru e-postasıyla aynı hesap).

Veliye GİTMEYENLER: koça özel not, soru soru cevaplar, öğrenci-koç yazışması.
Dil: suçlayıcı değil, somut; yüzde yazıyla değil sayıyla; tek odak.
"""
from __future__ import annotations

import hashlib
import html
import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import ExamResult, User
from app.models.exam_parent_report import REPORT_TTL_DAYS, ExamParentReport

LEVEL_STRONG = 75
LEVEL_OK = 50


# ---------------------------------------------------------------- bağlantı

def active_report(db: Session, exam_id: int) -> ExamParentReport | None:
    now = datetime.now(timezone.utc)
    rows = (
        db.query(ExamParentReport)
        .filter(ExamParentReport.exam_id == exam_id, ExamParentReport.revoked_at.is_(None))
        .order_by(ExamParentReport.id.desc())
        .all()
    )
    for r in rows:
        if _aware(r.expires_at) > now:
            return r
    return None


def get_or_create_report(db: Session, exam: ExamResult, actor_id: int | None) -> tuple[ExamParentReport, bool]:
    """Denemenin geçerli bağlantısı; yoksa yenisi (60 gün). (rapor, yeni_mi)."""
    found = active_report(db, exam.id)
    if found is not None:
        return found, False
    r = ExamParentReport(
        token=secrets.token_urlsafe(24),
        exam_id=exam.id,
        student_id=exam.student_id,
        created_by_id=actor_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=REPORT_TTL_DAYS),
    )
    db.add(r)
    db.flush()
    return r, True


def get_usable_by_token(db: Session, token: str) -> ExamParentReport | None:
    r = db.query(ExamParentReport).filter(ExamParentReport.token == token).first()
    if r is None or r.revoked_at is not None:
        return None
    if _aware(r.expires_at) <= datetime.now(timezone.utc):
        return None
    return r


def report_url(token: str) -> str:
    from app.config import settings

    base = (getattr(settings, "app_base_url", "") or "").rstrip("/")
    return f"{base}/rapor/{token}"


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- duyurulan metin

def find_sent_payload(db: Session, exam: ExamResult) -> dict | None:
    """Duyurulmuş denemede VELİYE GİDEN mail gövdesi (koçun düzenlediği metin)."""
    from app.models import NotificationKind, NotificationLog

    rows = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.student_id == exam.student_id,
            NotificationLog.kind == NotificationKind.EXAM_RESULT,
        )
        .order_by(NotificationLog.id.desc())
        .limit(40)
        .all()
    )
    exam_date_iso = exam.exam_date.isoformat() if exam.exam_date else None
    for log in rows:
        try:
            payload = json.loads(log.payload_json or "{}")
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("exam_id") == exam.id:
            return payload
        if (
            payload.get("exam_id") is None
            and payload.get("exam_title") == exam.title
            and payload.get("exam_date") == exam_date_iso
        ):
            return payload
    return None


# ---------------------------------------------------------------- içerik

def _genitive(name: str) -> str:
    from app.services.parent_weekly_mail import genitive

    return genitive(name)


def _level(pct: int) -> tuple[str, str]:
    if pct >= LEVEL_STRONG:
        return "strong", "Güçlü"
    if pct >= LEVEL_OK:
        return "ok", "Gelişiyor"
    return "support", "Desteklenecek"


def _subject_rows(subjects: list[dict]) -> list[dict]:
    out = []
    for s in subjects:
        q = int(s.get("questions") or 0)
        if s.get("unmatched") or q <= 0:
            continue
        pct = round(100 * int(s["correct"]) / q)
        level, label = _level(pct)
        if level == "strong":
            tail = "Rahat olduğu bir bölüm."
        elif level == "ok":
            tail = "Temeli var, düzenli çalışmayla yükselecek."
        else:
            tail = "Bu bölümde desteğe ihtiyacı var; programında yer alacak."
        out.append({
            "name": s["name"],
            "questions": q,
            "correct": int(s["correct"]),
            "wrong": int(s["wrong"]),
            "blank": int(s["blank"]),
            "net_text": _fmt(float(s.get("net") or 0)),
            "pct": pct,
            "level": level,
            "level_label": label,
            "sentence": f"{q} sorunun {s['correct']} tanesini doğru yaptı. {tail}",
        })
    return out


def _fmt(v: float) -> str:
    from app.services.exam_parent_summary import _fmt as f

    return f(v)


def _home_tips(first: str, ctx: dict) -> list[str]:
    tips: list[str] = []
    direction = ctx.get("delta_direction")
    if direction == "up":
        tips.append(
            "Artışı fark ettiğinizi ona söyleyin ve hangi çalışmanın işe yaradığını "
            "sorun; emeğin görülmesi motivasyonu en çok besleyen şeydir."
        )
    elif direction == "down":
        tips.append(
            "Tek bir deneme gidişatı göstermez. Sonucu notla değil emekle konuşun: "
            "\"Seni en çok ne zorladı?\" diye sormak, eleştiriden çok daha fazla işe yarar."
        )
    else:
        tips.append(
            "Sonucu notla değil emekle konuşun: \"Bu denemede seni en çok ne zorladı?\" "
            "sorusu, eleştiriden çok daha fazla işe yarar."
        )
    total = int(ctx.get("total_questions") or 0)
    blank = int(ctx.get("blank") or 0)
    if total and blank / total >= 0.15:
        tips.append(
            f"Boş bıraktığı soru sayısı yüksek ({blank} soru). Evde deneme çözdüğü günlerde "
            "süre tutarak oturması, sınavdaki zaman yönetimini güçlendirir."
        )
    if ctx.get("focus_topics"):
        tips.append(
            "Programında önümüzdeki günlerde zorlandığı konulardan çalışmalar olacak. "
            "O saatlerde sakin bir çalışma ortamı sağlamanız en büyük destektir."
        )
    tips.append(
        "Sorunuz olursa koçunuzla konuşabilirsiniz; bu rapordaki konuları görüşmede "
        "birlikte ele alırız."
    )
    return tips[:3]


def _speechify(text: str) -> str:
    """TTS kuralları: kısaltmalar harf harf, işaretler sade."""
    t = text.replace(" — ", ", ").replace("—", ",").replace("·", ",").replace("→", ",")
    for k, v in (("LGS", "L G S"), ("TYT", "T Y T"), ("AYT", "A Y T"), ("YKS", "Y K S"),
                 ("GİS", "G İ S"), ("%", "yüzde ")):
        t = t.replace(k, v)
    return " ".join(t.split())


def build_report_data(
    db: Session,
    exam: ExamResult,
    *,
    narrative: list[str] | None = None,
    include_subjects: bool = True,
    include_history: bool = True,
    include_opportunities: bool = True,
    include_goal: bool = True,
) -> dict:
    """Raporun tamamı. `narrative` verilmezse duyurulan (koçun düzenlediği)
    metin, o da yoksa kural motorunun cümleleri kullanılır."""
    from app.models.exam_result import section_penalty
    from app.services import branding
    from app.services.exam_parent_summary import build_email_context

    if narrative is None and exam.parent_notified_at is not None:
        sent = find_sent_payload(db, exam)
        if sent and isinstance(sent.get("narrative"), list):
            narrative = [str(x) for x in sent["narrative"]]

    ctx = build_email_context(
        db, exam,
        narrative=narrative,
        include_subjects=include_subjects,
        include_history=include_history,
        include_opportunities=include_opportunities,
        include_goal=include_goal,
    )
    student = db.get(User, exam.student_id)
    first = ((student.full_name if student else "") or "Öğrenci").split()[0]
    coach = db.get(User, student.teacher_id) if student and student.teacher_id else None
    brand = branding.brand_for_user(db, student) if student else None

    total = int(ctx.get("total_questions") or 0)
    correct = int(ctx.get("correct") or 0)
    penalty = section_penalty(exam.section)
    penalty_word = {3: "üç", 4: "dört"}.get(int(penalty), str(penalty))
    subjects = _subject_rows(ctx.get("subjects") or [])
    tips = _home_tips(first, ctx)

    headline = f"{total} sorunun {correct} tanesini doğru yaptı, {ctx['net_text']} net çıkardı."
    if ctx.get("delta_direction") == "up":
        trend_text = f"Bir önceki denemeye göre {ctx['delta_text']} net artış"
    elif ctx.get("delta_direction") == "down":
        trend_text = f"Bir önceki denemeye göre {ctx['delta_text']} net geride"
    elif ctx.get("delta_direction") == "flat":
        trend_text = "Bir önceki denemeyle aynı seviyede"
    else:
        trend_text = "Bu türdeki ilk denemesi"

    explain = (
        f"Net, doğru sayısından yanlışların cezası düşülerek bulunur: bu sınavda her "
        f"{penalty_word} yanlış bir doğruyu götürür. Boş bırakılan soru neti düşürmez ama "
        "puan da getirmez."
    )

    # --- seslendirme metni
    coach_bit = f"{coach.full_name} ile birlikte " if coach else ""
    parts = [
        f"Merhaba. Ben Rota, {coach_bit}{_genitive(first)} çalışmalarını takip ediyorum.",
        f"{_genitive(first)} {exam.title} denemesini sizin için özetliyorum.",
        *list(ctx.get("narrative") or []),
    ]
    if subjects:
        strong = [s["name"] for s in subjects if s["level"] == "strong"]
        support = [s["name"] for s in subjects if s["level"] == "support"]
        if strong:
            parts.append("Rahat olduğu bölümler: " + ", ".join(strong) + ".")
        if support:
            parts.append("Desteklenecek bölümler: " + ", ".join(support) + ".")
    parts.append("Evde neler yapabilirsiniz? " + " ".join(tips))
    parts.append("Ayrıntıları raporda bulabilirsiniz. İyi günler dilerim.")
    speech = _speechify(" ".join(parts))

    return {
        "student_first": first,
        "student_gen": _genitive(first),
        "student_name": student.full_name if student else "",
        "exam_title": exam.title,
        "exam_date_tr": _long_date(exam),
        "section_label": ctx.get("section_label"),
        "brand_name": brand.name if brand else "Etütkoç Rota",
        "brand_logo_url": (brand.logo_url if brand and getattr(brand, "logo_url", None) else None),
        "coach_name": coach.full_name if coach else None,
        "net_text": ctx["net_text"],
        "correct": correct,
        "wrong": int(ctx.get("wrong") or 0),
        "blank": int(ctx.get("blank") or 0),
        "total_questions": total,
        "correct_pct": round(100 * correct / total) if total else 0,
        "headline": headline,
        "trend_text": trend_text,
        "delta_direction": ctx.get("delta_direction"),
        "prev_title": ctx.get("prev_title"),
        "prev_net_text": ctx.get("prev_net_text"),
        "narrative": list(ctx.get("narrative") or []),
        "explain": explain,
        "subjects": subjects,
        "history": ctx.get("history") or {"has_data": False},
        "opportunities": ctx.get("opportunities") or [],
        "opportunity_total_text": ctx.get("opportunity_total_text"),
        "opportunity_exam_count": ctx.get("opportunity_exam_count") or 0,
        "tips": tips,
        "speech_text": speech,
        "speech_signature": hashlib.sha256(speech.encode("utf-8")).hexdigest()[:40],
    }


def _long_date(exam: ExamResult) -> str:
    from app.services.parent_weekly_mail import TR_MONTHS

    d = exam.exam_date
    if not d:
        return ""
    return f"{d.day} {TR_MONTHS[d.month - 1]} {d.year}"


# ---------------------------------------------------------------- PDF

_LEVEL_COLORS = {"strong": "#047857", "ok": "#b45309", "support": "#be123c"}

_CSS = """
@font-face { font-family: rf; src: url(reg.ttf); }
@font-face { font-family: rf; src: url(bold.ttf); font-weight: bold; }
* { font-family: rf; }
body { font-size: 10pt; color: #1c1917; }
h1 { font-size: 17pt; margin: 0 0 2pt 0; }
h2 { font-size: 12pt; margin: 14pt 0 5pt 0; color: #0b6178; }
p { margin: 0 0 4pt 0; line-height: 1.4; }
.muted { color: #57534e; font-size: 9pt; }
.brand { font-size: 9pt; color: #0b6178; font-weight: bold; }
.hero { background-color: #0b6178; color: #ffffff; padding: 8pt; margin-top: 8pt; }
.big { font-size: 24pt; font-weight: bold; }
.box { border: 1px solid #d6d3d1; padding: 6pt; margin-bottom: 4pt; }
table { border-collapse: collapse; width: 100%; }
td, th { border: 1px solid #d6d3d1; padding: 3pt 4pt; font-size: 9pt; text-align: left; }
th { background-color: #f5f5f4; }
li { margin-bottom: 3pt; line-height: 1.4; }
"""


def _e(s: object) -> str:
    return html.escape(str(s if s is not None else ""))


def report_html(data: dict) -> str:
    """PDF için sade HTML (PyMuPDF Story — basit CSS)."""
    h: list[str] = []
    h.append(f'<p class="brand">{_e(data["brand_name"])}</p>')
    h.append(f'<h1>{_e(data["student_gen"])} deneme raporu</h1>')
    meta = f'{_e(data["exam_title"])} · {_e(data["exam_date_tr"])} · {_e(data["section_label"])}'
    h.append(f'<p class="muted">{meta}</p>')
    h.append(
        f'<div class="hero"><p class="big">{_e(data["net_text"])} net</p>'
        f'<p>{_e(data["headline"])}</p><p>{_e(data["trend_text"])}'
        + (f' (önceki: {_e(data["prev_net_text"])} net)' if data.get("prev_net_text") else "")
        + '</p></div>'
    )
    h.append(
        f'<p class="muted">Doğru {data["correct"]} · Yanlış {data["wrong"]} · Boş {data["blank"]} '
        f'· Toplam {data["total_questions"]} soru</p>'
    )
    if data["narrative"]:
        h.append("<h2>Kısaca</h2><ul>" + "".join(f"<li>{_e(x)}</li>" for x in data["narrative"]) + "</ul>")
    if data["subjects"]:
        h.append("<h2>Ders ders</h2><table><tr><th>Ders</th><th>Doğru / Soru</th><th>Net</th><th>Durum</th></tr>")
        for s in data["subjects"]:
            color = _LEVEL_COLORS[s["level"]]
            h.append(
                f'<tr><td>{_e(s["name"])}</td><td>{s["correct"]} / {s["questions"]}</td>'
                f'<td>{_e(s["net_text"])}</td><td><b style="color:{color}">{_e(s["level_label"])}</b></td></tr>'
            )
        h.append("</table>")
    hist = data.get("history") or {}
    if hist.get("has_data"):
        h.append("<h2>Önceki denemelerle karşılaştırma</h2><table><tr><th>Ders</th>")
        for col in hist["exams"]:
            h.append(f'<th>{_e(col["date_tr"])}</th>')
        h.append("</tr>")
        for row in hist["rows"]:
            h.append(f'<tr><td>{_e(row["subject"])}</td>')
            for v in row["nets"]:
                h.append(f"<td>{_e(v or '—')}</td>")
            h.append("</tr>")
        h.append("<tr><td><b>Toplam net</b></td>" + "".join(f"<td><b>{_e(t)}</b></td>" for t in hist["totals"]) + "</tr></table>")
    if data["opportunities"]:
        scope = (f"Son {data['opportunity_exam_count']} denemeye göre"
                 if data["opportunity_exam_count"] > 1 else "Bu denemeye göre")
        h.append(f"<h2>Nerede net kazanabilir?</h2><p class='muted'>{scope}, bu konular kapandığında deneme başına kazanç:</p><table>")
        for o in data["opportunities"]:
            h.append(f'<tr><td>{_e(o["subject"])} · {_e(o["topic"])}</td><td><b>+{_e(o["gain_text"])} net</b></td></tr>')
        h.append(f'<tr><td><b>Hepsi kapanırsa</b></td><td><b>+{_e(data["opportunity_total_text"])} net</b></td></tr></table>')
    h.append("<h2>Evde nasıl destek olabilirsiniz?</h2><ul>" + "".join(f"<li>{_e(t)}</li>" for t in data["tips"]) + "</ul>")
    h.append(f'<h2>Net nasıl hesaplanır?</h2><p>{_e(data["explain"])}</p>')
    if data.get("coach_name"):
        h.append(f'<p class="muted">Koç: {_e(data["coach_name"])}</p>')
    return "<body>" + "".join(h) + "</body>"


def render_report_pdf(data: dict) -> bytes:
    import io

    try:
        import pymupdf
    except ImportError:  # eski paket adı (yerel geliştirme)
        import fitz as pymupdf

    import os

    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ]
    reg, bold = next(((r, b) for r, b in candidates if os.path.exists(r) and os.path.exists(b)), (None, None))
    if reg is None:
        raise RuntimeError("Türkçe font bulunamadı")
    archive = pymupdf.Archive()
    with open(reg, "rb") as f:
        archive.add(f.read(), "reg.ttf")
    with open(bold, "rb") as f:
        archive.add(f.read(), "bold.ttf")
    story = pymupdf.Story(html=report_html(data), user_css=_CSS, archive=archive)
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (36, 36, -36, -36)
    more = True
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    out = buf.getvalue()
    # Yazı tiplerini alt kümeye indir (dosya küçülsün)
    try:
        doc = pymupdf.open(stream=out, filetype="pdf")
        doc.subset_fonts()
        out = doc.tobytes(garbage=3, deflate=True)
    except Exception:  # alt küme başarısızsa tam dosya kalır
        pass
    return out


def pdf_filename(data: dict) -> str:
    """ASCII dosya adı (Content-Disposition güvenli)."""
    import re
    import unicodedata

    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    raw = f"{data.get('student_name') or 'ogrenci'}-{data.get('exam_title') or 'deneme'}-rapor"
    s = unicodedata.normalize("NFKD", raw.translate(tr)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()[:80]
    return f"{s or 'deneme-raporu'}.pdf"
