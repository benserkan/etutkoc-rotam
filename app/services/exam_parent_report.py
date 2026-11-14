"""Veli raporları — bağlantı + Rota sesi + PDF, TEK STANDART (2026-11-13/14).

KOÇ İSTEĞİ: veliye giden karne, mail PDF'i ve duyuru e-postası birbirinden
farklıydı; veli sayıları anlamıyordu. Üç rapor türü aynı standarda geçer:
  · exam     — tek deneme analizi (karne)
  · progress — gelişim raporu (bir deneme serisinin gidişatı)
  · weekly   — haftalık rapor (Pazartesi–Pazar program uyumu)

TEK KAYNAK: her tür `_header` + `hero` + `sections` biçiminde GENEL bir sözlük
üretir. Bağlantılı sayfa (/rapor/{token}), sunucu PDF'i (`render_report_pdf`) ve
seslendirme metni (`speech_text`) bu sözlükten beslenir; üçü ayrışamaz. Sayılar
mevcut servislerden gelir (deneme: `build_email_context`, gelişim:
`build_progress_report`, haftalık: `build_mail_payload`) — ekranlarla aynı hesap.

Bölüm türleri: bullets · levels (çubuklu ders kartı) · bars · table · gains · tips · text.

Veliye GİTMEYENLER: koça özel not, soru soru cevaplar, öğrenci-koç yazışması,
koçun seans gündemi. Dil: suçlayıcı değil, somut, tek odak.
"""
from __future__ import annotations

import hashlib
import html
import json
import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import ExamResult, User
from app.models.exam_parent_report import (
    REPORT_KIND_EXAM,
    REPORT_KIND_PROGRESS,
    REPORT_KIND_WEEKLY,
    REPORT_TTL_DAYS,
    ExamParentReport,
)

LEVEL_STRONG = 75
LEVEL_OK = 50

KIND_TITLES = {
    REPORT_KIND_EXAM: "deneme raporu",
    REPORT_KIND_PROGRESS: "gelişim raporu",
    REPORT_KIND_WEEKLY: "haftalık raporu",
}


# ================================================================ bağlantı

def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _active_query(db: Session, *, kind: str, student_id: int, exam_id: int | None,
                  week_start: date | None, series: str | None):
    q = db.query(ExamParentReport).filter(
        ExamParentReport.kind == kind,
        ExamParentReport.student_id == student_id,
        ExamParentReport.revoked_at.is_(None),
    )
    if kind == REPORT_KIND_EXAM:
        q = q.filter(ExamParentReport.exam_id == exam_id)
    elif kind == REPORT_KIND_WEEKLY:
        q = q.filter(ExamParentReport.week_start == week_start)
    else:
        q = (q.filter(ExamParentReport.series == series) if series
             else q.filter(ExamParentReport.series.is_(None)))
    return q.order_by(ExamParentReport.id.desc())


def get_or_create_link(db: Session, *, kind: str, student_id: int, actor_id: int | None,
                       exam_id: int | None = None, week_start: date | None = None,
                       series: str | None = None) -> tuple[ExamParentReport, bool]:
    """Geçerli bağlantı varsa onu, yoksa yenisini (60 gün) döndür. (rapor, yeni_mi)."""
    now = datetime.now(timezone.utc)
    for r in _active_query(db, kind=kind, student_id=student_id, exam_id=exam_id,
                           week_start=week_start, series=series).all():
        if _aware(r.expires_at) > now:
            return r, False
    r = ExamParentReport(
        token=secrets.token_urlsafe(24), kind=kind, student_id=student_id,
        exam_id=exam_id, week_start=week_start, series=series or None,
        created_by_id=actor_id, expires_at=now + timedelta(days=REPORT_TTL_DAYS),
    )
    db.add(r)
    db.flush()
    return r, True


def get_or_create_report(db: Session, exam: ExamResult, actor_id: int | None) -> tuple[ExamParentReport, bool]:
    return get_or_create_link(db, kind=REPORT_KIND_EXAM, student_id=exam.student_id,
                              exam_id=exam.id, actor_id=actor_id)


def active_report(db: Session, exam_id: int) -> ExamParentReport | None:
    now = datetime.now(timezone.utc)
    for r in (db.query(ExamParentReport)
              .filter(ExamParentReport.exam_id == exam_id, ExamParentReport.revoked_at.is_(None))
              .order_by(ExamParentReport.id.desc()).all()):
        if _aware(r.expires_at) > now:
            return r
    return None


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


# ================================================================ duyurulan metin

def find_sent_payload(db: Session, exam: ExamResult) -> dict | None:
    """Duyurulmuş denemede VELİYE GİDEN mail gövdesi (koçun düzenlediği metin)."""
    from app.models import NotificationKind, NotificationLog

    rows = (
        db.query(NotificationLog)
        .filter(NotificationLog.student_id == exam.student_id,
                NotificationLog.kind == NotificationKind.EXAM_RESULT)
        .order_by(NotificationLog.id.desc()).limit(40).all()
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
        if (payload.get("exam_id") is None and payload.get("exam_title") == exam.title
                and payload.get("exam_date") == exam_date_iso):
            return payload
    return None


# ================================================================ ortak parçalar

def _genitive(name: str) -> str:
    from app.services.parent_weekly_mail import genitive

    return genitive(name)


def _fmt(v: float | None) -> str:
    from app.services.exam_parent_summary import _fmt as f

    return "—" if v is None else f(float(v))


def _signed(v: float) -> str:
    return ("+" if v > 0 else "−" if v < 0 else "") + _fmt(abs(v))


def _tr_date(d: date | None) -> str:
    from app.services.parent_weekly_mail import TR_MONTHS

    if not d:
        return ""
    return f"{d.day} {TR_MONTHS[d.month - 1]} {d.year}"


def _header(db: Session, student: User | None, kind: str, subtitle: str) -> dict:
    from app.services import branding

    first = ((student.full_name if student else "") or "Öğrenci").split()[0]
    coach = db.get(User, student.teacher_id) if student and student.teacher_id else None
    brand = branding.brand_for_user(db, student) if student else None
    return {
        "kind": kind,
        "student_first": first,
        "student_gen": _genitive(first),
        "student_name": student.full_name if student else "",
        "title": f"{_genitive(first)} {KIND_TITLES[kind]}",
        "subtitle": subtitle,
        "brand_name": brand.name if brand else "Etütkoç Rota",
        "brand_logo_url": (brand.logo_url if brand and getattr(brand, "logo_url", None) else None),
        "coach_name": coach.full_name if coach else None,
    }


def _speechify(text: str) -> str:
    """TTS kuralları: kısaltmalar harf harf, işaretler sade."""
    import re

    t = re.sub(r"(\S+) → (\S+) net", r"\1 netten \2 nete", text)
    t = t.replace(" — ", ", ").replace("—", ",").replace("·", ",").replace("→", ",")
    for k, v in (("LGS", "L G S"), ("TYT", "T Y T"), ("AYT", "A Y T"), ("YKS", "Y K S"),
                 ("GİS", "G İ S"), ("%", "yüzde ")):
        t = t.replace(k, v)
    return " ".join(t.split())


def _finish(data: dict, speech_parts: list[str]) -> dict:
    coach = data.get("coach_name")
    intro = (f"Merhaba. Ben Rota, {coach} ile birlikte {data['student_gen']} çalışmalarını takip ediyorum."
             if coach else f"Merhaba. Ben Rota, {data['student_gen']} çalışmalarını takip ediyorum.")
    speech = _speechify(" ".join([intro, *speech_parts,
                                  "Ayrıntıları raporda bulabilirsiniz. İyi günler dilerim."]))
    data["speech_text"] = speech
    data["speech_signature"] = hashlib.sha256(speech.encode("utf-8")).hexdigest()[:40]
    return data


def _level(pct: int) -> tuple[str, str]:
    if pct >= LEVEL_STRONG:
        return "strong", "Güçlü"
    if pct >= LEVEL_OK:
        return "ok", "Gelişiyor"
    return "support", "Desteklenecek"


_CLOSING_TIP = ("Sorunuz olursa koçunuzla konuşabilirsiniz; bu rapordaki konuları görüşmede "
                "birlikte ele alırız.")


# ================================================================ deneme

def _exam_tips(ctx: dict) -> list[str]:
    tips: list[str] = []
    direction = ctx.get("delta_direction")
    if direction == "up":
        tips.append("Artışı fark ettiğinizi ona söyleyin ve hangi çalışmanın işe yaradığını "
                    "sorun; emeğin görülmesi motivasyonu en çok besleyen şeydir.")
    elif direction == "down":
        tips.append("Tek bir deneme gidişatı göstermez. Sonucu notla değil emekle konuşun: "
                    "\"Seni en çok ne zorladı?\" diye sormak, eleştiriden çok daha fazla işe yarar.")
    else:
        tips.append("Sonucu notla değil emekle konuşun: \"Bu denemede seni en çok ne zorladı?\" "
                    "sorusu, eleştiriden çok daha fazla işe yarar.")
    total = int(ctx.get("total_questions") or 0)
    blank = int(ctx.get("blank") or 0)
    if total and blank / total >= 0.15:
        tips.append(f"Boş bıraktığı soru sayısı yüksek ({blank} soru). Evde deneme çözdüğü günlerde "
                    "süre tutarak oturması, sınavdaki zaman yönetimini güçlendirir.")
    if ctx.get("focus_topics"):
        tips.append("Programında önümüzdeki günlerde zorlandığı konulardan çalışmalar olacak. "
                    "O saatlerde sakin bir çalışma ortamı sağlamanız en büyük destektir.")
    tips.append(_CLOSING_TIP)
    return tips[:3]


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
    """Deneme raporu. `narrative` verilmezse duyurulan (koçun düzenlediği) metin,
    o da yoksa kural motorunun cümleleri kullanılır."""
    from app.models.exam_result import section_penalty
    from app.services.exam_parent_summary import build_email_context

    if narrative is None and exam.parent_notified_at is not None:
        sent = find_sent_payload(db, exam)
        if sent and isinstance(sent.get("narrative"), list):
            narrative = [str(x) for x in sent["narrative"]]

    ctx = build_email_context(
        db, exam, narrative=narrative, include_subjects=include_subjects,
        include_history=include_history, include_opportunities=include_opportunities,
        include_goal=include_goal,
    )
    student = db.get(User, exam.student_id)
    subtitle = " · ".join(x for x in [exam.title, _tr_date(exam.exam_date), ctx.get("section_label")] if x)
    data = _header(db, student, REPORT_KIND_EXAM, subtitle)

    total = int(ctx.get("total_questions") or 0)
    correct = int(ctx.get("correct") or 0)
    penalty = int(section_penalty(exam.section))
    penalty_word = {3: "üç", 4: "dört"}.get(penalty, str(penalty))
    direction = ctx.get("delta_direction")
    trend_text = {
        "up": f"Bir önceki denemeye göre {ctx.get('delta_text')} net artış",
        "down": f"Bir önceki denemeye göre {ctx.get('delta_text')} net geride",
        "flat": "Bir önceki denemeyle aynı seviyede",
    }.get(direction or "", "Bu türdeki ilk denemesi")
    if ctx.get("prev_net_text"):
        trend_text += f" (önceki {ctx['prev_net_text']} net)"

    data["hero"] = {
        "big": ctx["net_text"], "unit": "net",
        "headline": f"{total} sorunun {correct} tanesini doğru yaptı, {ctx['net_text']} net çıkardı.",
        "trend_text": trend_text, "trend_dir": direction,
        "stats": [{"label": "Doğru", "value": str(correct)},
                  {"label": "Yanlış", "value": str(ctx.get("wrong") or 0)},
                  {"label": "Boş", "value": str(ctx.get("blank") or 0)}],
    }

    sections: list[dict] = []
    narrative_lines = list(ctx.get("narrative") or [])
    if narrative_lines:
        sections.append({"type": "bullets", "title": "Kısaca", "items": narrative_lines})

    levels = []
    for s in ctx.get("subjects") or []:
        q = int(s.get("questions") or 0)
        if s.get("unmatched") or q <= 0:
            continue
        pct = round(100 * int(s["correct"]) / q)
        level, label = _level(pct)
        tail = {"strong": "Rahat olduğu bir bölüm.",
                "ok": "Temeli var, düzenli çalışmayla yükselecek.",
                "support": "Bu bölümde desteğe ihtiyacı var; programında yer alacak."}[level]
        levels.append({
            "name": s["name"], "pct": pct, "level": level, "level_label": label,
            "sentence": f"{q} sorunun {s['correct']} tanesini doğru yaptı. {tail}",
            "meta": f"{s['correct']} doğru · {s['wrong']} yanlış · {s['blank']} boş · {_fmt(s.get('net'))} net",
        })
    if levels:
        sections.append({"type": "levels", "title": "Ders ders",
                         "note": "Her derste doğru yaptığı soruların oranı.", "items": levels})

    hist = ctx.get("history") or {}
    if hist.get("has_data"):
        sections.append({
            "type": "table", "title": "Önceki denemelerle karşılaştırma",
            "note": "Aynı türdeki son denemelerin ders netleri.",
            "columns": ["Ders", *[c["date_tr"] for c in hist["exams"]]],
            "rows": [[r["subject"], *[v or "—" for v in r["nets"]]] for r in hist["rows"]],
            "total_row": ["Toplam net", *hist["totals"]],
        })

    opps = ctx.get("opportunities") or []
    if opps:
        n = int(ctx.get("opportunity_exam_count") or 0)
        sections.append({
            "type": "gains", "title": "Nerede net kazanabilir?",
            "note": f"{f'Son {n} denemeye göre' if n > 1 else 'Bu denemeye göre'}, bu konular kapandığında deneme başına kazanç.",
            "items": [{"label": o["topic"], "sub": o["subject"], "value": f"+{o['gain_text']} net"} for o in opps],
            "total": ({"label": "Hepsi kapanırsa", "value": f"+{ctx['opportunity_total_text']} net"}
                      if ctx.get("opportunity_total_text") else None),
        })

    tips = _exam_tips(ctx)
    sections.append({"type": "tips", "title": "Evde nasıl destek olabilirsiniz?", "items": tips})
    sections.append({"type": "text", "title": "Net nasıl hesaplanır?", "text": (
        f"Net, doğru sayısından yanlışların cezası düşülerek bulunur: bu sınavda her {penalty_word} "
        "yanlış bir doğruyu götürür. Boş bırakılan soru neti düşürmez ama puan da getirmez.")})
    data["sections"] = sections
    data["pdf_name_hint"] = exam.title

    speech = [f"{data['student_gen']} {exam.title} denemesini sizin için özetliyorum.", *narrative_lines]
    strong = [x["name"] for x in levels if x["level"] == "strong"]
    support = [x["name"] for x in levels if x["level"] == "support"]
    if strong:
        speech.append("Rahat olduğu bölümler: " + ", ".join(strong) + ".")
    if support:
        speech.append("Desteklenecek bölümler: " + ", ".join(support) + ".")
    speech.append("Evde neler yapabilirsiniz? " + " ".join(tips))
    return _finish(data, speech)


# ================================================================ gelişim

def build_progress_data(db: Session, student: User, series: str | None = None) -> dict:
    """Bir deneme serisinin gidişatı — veli dili (koçun seans planı GİRMEZ)."""
    from app.services.exam_progress import BLANK_HIGH_RATIO, SLOPE_WINDOW, build_progress_report

    rep = build_progress_report(db, student, section=series)
    exams = rep.get("exams") or []
    stats = rep.get("stats")
    label = (rep.get("section_label") or "Denemeler").replace(" (genel deneme)", "")
    if exams:
        first_d = date.fromisoformat(exams[0]["exam_date"])
        last_d = date.fromisoformat(exams[-1]["exam_date"])
        subtitle = f"{label} · {len(exams)} deneme · {_tr_date(first_d)} – {_tr_date(last_d)}"
    else:
        subtitle = label
    data = _header(db, student, REPORT_KIND_PROGRESS, subtitle)
    data["pdf_name_hint"] = label

    if not exams or not stats:
        data["hero"] = {"big": "—", "unit": "", "headline": "Bu seride henüz deneme yok.",
                        "trend_text": "", "trend_dir": None, "stats": []}
        data["sections"] = []
        return _finish(data, ["Bu seride henüz değerlendirilecek deneme yok."])

    n = stats["count"]
    ch = float(stats["change"])
    slope = stats.get("slope")
    direction = "up" if ch >= 1 else "down" if ch <= -1 else "flat"
    if n == 1:
        trend_text = "Bu türdeki ilk denemesi"
        headline = f"İlk denemesinde {_fmt(stats['last_net'])} net çıkardı."
        direction = None
    else:
        trend_text = (f"İlk denemeden bu yana {_signed(ch)} net" if direction != "flat"
                      else "İlk denemeyle aynı seviyede")
        headline = f"{n} denemede neti {_fmt(stats['first_net'])} → {_fmt(stats['last_net'])}."

    data["hero"] = {
        "big": _fmt(stats["last_net"]), "unit": "net", "headline": headline,
        "trend_text": trend_text, "trend_dir": direction,
        "stats": [{"label": "Deneme", "value": str(n)},
                  {"label": "En iyi net", "value": _fmt(stats["best_net"])},
                  {"label": "Son 3 ort.", "value": _fmt(stats["avg_last3"])}],
    }

    lines: list[str] = []
    first = data["student_first"]
    if n >= 2:
        lines.append(f"{first}, ilk denemesinde {_fmt(stats['first_net'])} net, son denemesinde "
                     f"{_fmt(stats['last_net'])} net çıkardı; {n} denemedeki en iyi neti {_fmt(stats['best_net'])}.")
        if slope is not None:
            k = min(n, SLOPE_WINDOW)
            if slope >= 0.5:
                lines.append(f"Son {k} denemede düzenli bir yükseliş var: deneme başına ortalama {_signed(slope)} net.")
            elif slope <= -0.5:
                lines.append(f"Son {k} denemede netler bir miktar düştü. Çalışma planını koçuyla "
                             "birlikte gözden geçiriyoruz.")
            else:
                lines.append("Son denemelerde netler yatay. Bir sonraki sıçrama için çalışma biçiminde "
                             "küçük değişiklikler planlıyoruz.")
    else:
        lines.append(f"Bu türdeki ilk denemesinde {_fmt(stats['last_net'])} net çıkardı. Gidişatı görmek "
                     "için birkaç deneme daha gerekiyor.")
    subjects = rep.get("subjects") or []
    ups = [s for s in subjects if s.get("change") is not None and s["change"] >= 2]
    downs = [s for s in subjects if s.get("change") is not None and s["change"] <= -2]
    if ups:
        b = max(ups, key=lambda s: s["change"])
        lines.append(f"En çok gelişen ders {b['name']} ({_fmt(b['first'])} → {_fmt(b['last'])} net).")
    if downs:
        w = min(downs, key=lambda s: s["change"])
        lines.append(f"Daha fazla destek gereken ders {w['name']} ({_fmt(w['first'])} → {_fmt(w['last'])} net).")
    t = rep.get("target")
    if t and t.get("target_net"):
        if t["gap"] <= 0:
            lines.append(f"Hedeflenen {_fmt(t['target_net'])} net tuttu.")
        else:
            txt = f"Hedef {_fmt(t['target_net'])} net; şu an {_fmt(t['gap'])} net uzakta."
            if t.get("exams_needed_at_pace"):
                txt += f" Bu tempoyla yaklaşık {t['exams_needed_at_pace']} deneme sonra ulaşılabilir."
            lines.append(txt)
    last = exams[-1]
    if last["questions"] and last["blank"] / last["questions"] >= BLANK_HIGH_RATIO:
        lines.append(f"Son denemede {last['blank']} soru boş kaldı; süre kullanımı üzerine çalışıyoruz.")

    sections: list[dict] = [{"type": "bullets", "title": "Kısaca", "items": lines}]
    shown = exams[-8:]
    top = max((e["net"] for e in shown), default=0) or 1
    sections.append({
        "type": "bars", "title": "Deneme deneme net",
        "note": "Son denemelerin netleri, eskiden yeniye.",
        "items": [{"label": f"{_tr_date(date.fromisoformat(e['exam_date']))} · {e['title']}",
                   "value": _fmt(e["net"]), "pct": max(2, round(100 * max(e["net"], 0) / top)),
                   "tone": "accent" if i == len(shown) - 1 else "neutral"}
                  for i, e in enumerate(shown)],
    })
    lv = []
    for s in subjects:
        if s.get("last") is None:
            continue
        c = s.get("change")
        if c is None:
            level, lab, sent = "ok", "Tek deneme", f"Son denemede {_fmt(s['last'])} net."
        elif c >= 1:
            level, lab, sent = "strong", "Yükseliyor", f"{_fmt(s['first'])} → {_fmt(s['last'])} net."
        elif c <= -1:
            level, lab, sent = "support", "Desteklenecek", f"{_fmt(s['first'])} → {_fmt(s['last'])} net."
        else:
            level, lab, sent = "ok", "Yatay", f"{_fmt(s['first'])} → {_fmt(s['last'])} net."
        top_s = max((v for v in s["nets"] if v is not None), default=0) or 1
        lv.append({"name": s["name"], "pct": max(2, round(100 * max(s["last"], 0) / top_s)),
                   "level": level, "level_label": lab, "sentence": sent,
                   "meta": f"Ortalama {_fmt(s.get('avg'))} net"})
    if lv:
        sections.append({"type": "levels", "title": "Ders ders gidişat",
                         "note": "İlk ve son denemedeki netler; çubuk, son netin en iyi netine oranı.",
                         "items": lv})
    opps = rep.get("opportunities") or []
    if opps:
        total = round(sum(float(o["net_gain_per_exam"]) for o in opps[:4]), 2)
        sections.append({
            "type": "gains", "title": "Nerede net kazanabilir?",
            "note": "Bu denemelerde en çok soru kaçırılan konular; kapandığında deneme başına kazanç.",
            "items": [{"label": o["topic_name"], "sub": o["subject_name"],
                       "value": f"+{_fmt(o['net_gain_per_exam'])} net"} for o in opps[:4]],
            "total": {"label": "Hepsi kapanırsa", "value": f"+{_fmt(total)} net"},
        })
    tips: list[str] = []
    if direction == "up":
        tips.append("Yükselişi fark ettiğinizi söyleyin; düzenli çalışmasının karşılığını gördüğünü "
                    "bilmek devam etmesini kolaylaştırır.")
    elif direction == "down":
        tips.append("Düşüşü tek bir sebebe bağlamayın; uyku, yorgunluk ve sınav kaygısı da netleri "
                    "etkiler. Neyin zorladığını dinlemek iyi bir başlangıçtır.")
    else:
        tips.append("Yatay dönemler normaldir; bu dönemde düzenli çalışmanın sürmesi, sonraki "
                    "yükselişin temelidir.")
    tips.append("Deneme günlerinde evde sakin bir ortam ve yeterli uyku, netlere doğrudan yansır.")
    tips.append(_CLOSING_TIP)
    sections.append({"type": "tips", "title": "Evde nasıl destek olabilirsiniz?", "items": tips})
    data["sections"] = sections

    speech = [f"{data['student_gen']} {label} denemelerindeki gidişatı sizin için özetliyorum.", *lines,
              "Evde neler yapabilirsiniz? " + " ".join(tips)]
    return _finish(data, speech)


# ================================================================ haftalık

_DOW = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def build_weekly_data(db: Session, student: User, week_start: date) -> dict:
    """Pazartesi–Pazar haftası — veli haftalık e-postasıyla AYNI sayılar."""
    from app.services.parent_weekly_mail import build_mail_payload

    pl = build_mail_payload(db, None, student, today=week_start + timedelta(days=7))
    data = _header(db, student, REPORT_KIND_WEEKLY, pl.get("week_label") or "")
    data["pdf_name_hint"] = f"hafta-{week_start.isoformat()}"
    first = data["student_first"]

    hist = pl.get("history") or []
    prev_pct = hist[-2]["pct"] if len(hist) >= 2 else None
    pct = int(pl.get("completion_pct") or 0)
    if prev_pct is None:
        trend_text, trend_dir = "", None
    else:
        d = pct - int(prev_pct)
        trend_dir = "up" if d >= 5 else "down" if d <= -5 else "flat"
        trend_text = (f"Geçen haftaya göre {abs(d)} puan {'yukarıda' if d > 0 else 'aşağıda'}"
                      if trend_dir != "flat" else "Geçen haftayla benzer")
    data["hero"] = {
        "big": f"%{pct}", "unit": "görev uyumu",
        "headline": pl.get("verdict_text") or "",
        "trend_text": trend_text, "trend_dir": trend_dir,
        "stats": [{"label": "Görev", "value": f"{pl.get('gorev_done', 0)}/{pl.get('gorev_total', 0)}"},
                  {"label": "Çözülen test", "value": str(pl.get("test_completed") or 0)},
                  {"label": "Çalışılan gün", "value": f"{pl.get('active_days', 0)}/7"}],
    }

    sections: list[dict] = []
    if hist:
        sections.append({
            "type": "bars", "title": "Haftadan haftaya",
            "note": "Programdaki görevlerin yüzde kaçını tamamladı.",
            "items": [{"label": h["label"], "value": f"%{h['pct']}", "pct": max(2, int(h["pct"] or 0)),
                       "tone": "accent" if i == len(hist) - 1 else "neutral"} for i, h in enumerate(hist)],
        })
    lv = []
    for s in pl.get("subjects_all") or []:
        planned = int(s.get("planned") or 0)
        if planned <= 0:
            continue
        p = int(s.get("pct") or 0)
        level, lab = (("strong", "Tamam") if p >= 90 else ("ok", "Kısmen") if p >= 60
                      else ("support", "Eksik kaldı"))
        lv.append({"name": s["subject_name"], "pct": p, "level": level, "level_label": lab,
                   "sentence": f"Programdaki {planned} testin {s['completed']} tanesini çözdü.",
                   "meta": ""})
    if lv:
        sections.append({"type": "levels", "title": "Ders ders", "items": lv,
                         "note": "Bu hafta programa konan testler ve çözülenler."})
    daily = pl.get("daily") or []
    if daily:
        rows = []
        for d in daily:
            rows.append([_DOW[int(d["weekday"])],
                         f"{d['gorev_done']}/{d['gorev_total']}" if d["gorev_total"] else "—",
                         str(d["test_completed"]) if d["test_planned"] or d["test_completed"] else "—"])
        sections.append({"type": "table", "title": "Gün gün", "columns": ["Gün", "Görev", "Çözülen test"],
                         "rows": rows})
    exam_lines = []
    for s in pl.get("series") or []:
        t = f"{s['label']}: son deneme {s['last_net']} net ({s['last_date']})"
        if s.get("diff_text"):
            t += f", {s['diff_text']}"
        if s.get("target"):
            t += f". {s['target']}"
        exam_lines.append(t + ".")
    for b in pl.get("branch") or []:
        exam_lines.append(f"Bu hafta {b['label']} branş denemesi: {b['nets']} net.")
    if exam_lines:
        sections.append({"type": "bullets", "title": "Denemeler", "items": exam_lines})
    topics = pl.get("topics") or {}
    if topics.get("items"):
        sections.append({
            "type": "gains", "title": "Nerede net kazanabilir?",
            "note": f"Son {topics.get('count')} {topics.get('series') or ''} denemesine göre deneme başına kazanç.",
            "items": [{"label": i["topic"], "sub": i["subject"], "value": f"+{i['gain']} net"}
                      for i in topics["items"]],
            "total": None,
        })
    nxt = pl.get("next_week")
    if nxt:
        txt = f"{nxt['label']} haftası için programında {nxt['tasks']} görev var"
        if nxt.get("top"):
            txt += ": en çok " + ", ".join(f"{t['subject']} ({t['count']})" for t in nxt["top"])
        txt += "."
        if nxt.get("focus_note"):
            txt += " " + nxt["focus_note"]
        sections.append({"type": "text", "title": "Gelecek hafta", "text": txt})
    notes = [n["body"] for n in (pl.get("teacher_notes") or []) if n.get("body")]
    if notes:
        sections.append({"type": "bullets", "title": "Koçunuzdan not", "items": notes})

    tips: list[str] = []
    if pct >= 80:
        tips.append(f"Haftayı iyi kapattı; bunu {first} ile paylaşın. Düzenin fark edilmesi devam etmeyi kolaylaştırır.")
    elif pct >= 50:
        tips.append("Görevlerin bir kısmı kaldı. Hangi günlerin zor geçtiğini konuşmak, gelecek haftanın "
                    "planına yardımcı olur.")
    else:
        tips.append("Bu hafta programın önemli bir kısmı yapılamadı. Sitem yerine \"Seni ne zorladı?\" "
                    "diye sormak, sorunun kaynağını bulmanın en kolay yoludur.")
    if int(pl.get("active_days") or 0) <= 3:
        tips.append("Az sayıda günde yoğun çalışmak yerine her gün kısa da olsa düzenli çalışmak "
                    "daha kalıcı sonuç verir; sabit bir çalışma saati bunu kolaylaştırır.")
    tips.append(_CLOSING_TIP)
    tips = tips[:3]
    sections.append({"type": "tips", "title": "Evde nasıl destek olabilirsiniz?", "items": tips})
    data["sections"] = sections

    speech = [f"{data['student_gen']} {pl.get('week_label') or ''} haftasını sizin için özetliyorum.",
              pl.get("verdict_text") or ""]
    if trend_text:
        speech.append(trend_text + ".")
    weak = [x["name"] for x in lv if x["level"] == "support"]
    if weak:
        speech.append("Eksik kalan dersler: " + ", ".join(weak) + ".")
    speech.extend(exam_lines[:2])
    speech.append("Evde neler yapabilirsiniz? " + " ".join(tips))
    return _finish(data, speech)


# ================================================================ dağıtıcı

def build_link_data(db: Session, rep: ExamParentReport) -> dict | None:
    """Bağlantının türüne göre raporu kur (None → kaynak yok)."""
    student = db.get(User, rep.student_id)
    if student is None:
        return None
    kind = rep.kind or REPORT_KIND_EXAM
    if kind == REPORT_KIND_EXAM:
        exam = db.get(ExamResult, rep.exam_id) if rep.exam_id else None
        return build_report_data(db, exam) if exam else None
    if kind == REPORT_KIND_PROGRESS:
        return build_progress_data(db, student, rep.series)
    if kind == REPORT_KIND_WEEKLY and rep.week_start:
        return build_weekly_data(db, student, rep.week_start)
    return None


# ================================================================ PDF

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
table { border-collapse: collapse; width: 100%; }
td, th { border: 1px solid #d6d3d1; padding: 3pt 4pt; font-size: 9pt; text-align: left; }
th { background-color: #f5f5f4; }
li { margin-bottom: 3pt; line-height: 1.4; }
"""


def _e(s: object) -> str:
    return html.escape(str(s if s is not None else ""))


def report_html(data: dict) -> str:
    """PDF için sade HTML (PyMuPDF Story — basit CSS)."""
    h: list[str] = [f'<p class="brand">{_e(data["brand_name"])}</p>',
                    f'<h1>{_e(data["title"])}</h1>', f'<p class="muted">{_e(data["subtitle"])}</p>']
    hero = data.get("hero") or {}
    h.append(f'<div class="hero"><p class="big">{_e(hero.get("big"))} {_e(hero.get("unit"))}</p>'
             f'<p>{_e(hero.get("headline"))}</p>'
             + (f'<p>{_e(hero["trend_text"])}</p>' if hero.get("trend_text") else "") + "</div>")
    if hero.get("stats"):
        h.append('<p class="muted">' + " · ".join(f'{_e(s["label"])}: {_e(s["value"])}' for s in hero["stats"]) + "</p>")
    for sec in data.get("sections") or []:
        h.append(f'<h2>{_e(sec["title"])}</h2>')
        if sec.get("note"):
            h.append(f'<p class="muted">{_e(sec["note"])}</p>')
        t = sec["type"]
        if t in ("bullets", "tips"):
            h.append("<ul>" + "".join(f"<li>{_e(x)}</li>" for x in sec["items"]) + "</ul>")
        elif t == "text":
            h.append(f"<p>{_e(sec['text'])}</p>")
        elif t == "levels":
            h.append("<table><tr><th>Ders</th><th>Açıklama</th><th>Durum</th></tr>")
            for it in sec["items"]:
                c = _LEVEL_COLORS.get(it["level"], "#1c1917")
                meta = f'<br/><span class="muted">{_e(it["meta"])}</span>' if it.get("meta") else ""
                h.append(f'<tr><td>{_e(it["name"])}</td><td>{_e(it["sentence"])}{meta}</td>'
                         f'<td><b style="color:{c}">{_e(it["level_label"])}</b></td></tr>')
            h.append("</table>")
        elif t == "bars":
            h.append("<table>" + "".join(
                f'<tr><td>{_e(it["label"])}</td><td><b>{_e(it["value"])}</b></td></tr>' for it in sec["items"])
                + "</table>")
        elif t == "table":
            h.append("<table><tr>" + "".join(f"<th>{_e(c)}</th>" for c in sec["columns"]) + "</tr>")
            for row in sec["rows"]:
                h.append("<tr>" + "".join(f"<td>{_e(v)}</td>" for v in row) + "</tr>")
            if sec.get("total_row"):
                h.append("<tr>" + "".join(f"<td><b>{_e(v)}</b></td>" for v in sec["total_row"]) + "</tr>")
            h.append("</table>")
        elif t == "gains":
            h.append("<table>" + "".join(
                f'<tr><td>{_e(it["label"])} · {_e(it["sub"])}</td><td><b>{_e(it["value"])}</b></td></tr>'
                for it in sec["items"]))
            if sec.get("total"):
                h.append(f'<tr><td><b>{_e(sec["total"]["label"])}</b></td><td><b>{_e(sec["total"]["value"])}</b></td></tr>')
            h.append("</table>")
    if data.get("coach_name"):
        h.append(f'<p class="muted">Koç: {_e(data["coach_name"])}</p>')
    return "<body>" + "".join(h) + "</body>"


def render_report_pdf(data: dict) -> bytes:
    import io
    import os

    try:
        import pymupdf
    except ImportError:  # eski paket adı (yerel geliştirme)
        import fitz as pymupdf

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
    word = {REPORT_KIND_EXAM: "deneme-raporu", REPORT_KIND_PROGRESS: "gelisim-raporu",
            REPORT_KIND_WEEKLY: "haftalik-rapor"}.get(data.get("kind", ""), "rapor")
    raw = f"{data.get('student_name') or 'ogrenci'}-{data.get('pdf_name_hint') or ''}-{word}"
    s = unicodedata.normalize("NFKD", raw.translate(tr)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()[:90]
    return f"{s or word}.pdf"
