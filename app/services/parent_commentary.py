"""Rota Veli Asistanı P1 — yorum motoru (TEK MERKEZ).

İki yorum türü (kind):
  - "program": bu hafta + geçen hafta kıyası + gün gün durum + YAPILMAYAN
    görevler (adlarıyla) + yanlış arşivi özeti → velinin diline çevrilmiş anlatım
  - "deneme": son denemeler + soru-satırlı konu analizi (net fırsatları,
    unutulan konular) + tür-içi trend → velinin diline çevrilmiş anlatım

Model YALNIZ burada paketlenen veriyi görür (koç-özel seans notları ASLA
pakete girmez; modelin veri erişimi yok → sızıntı/injection yapısal olarak
kapalı). TEK Gemini çağrısı İKİ metin üretir:
  - sections: ekran metni bölümleri (rakamlı)
  - speech_text: seslendirme metni (sayılar YAZIYLA, TTS kurallı)

Bayatlık SAKLANMAZ, hesaplanır: based_on imzası güncel imzayla karşılaştırılır.
Ses ilk dinlemede üretilir (tts.synthesize_speech) ve satırda saklanır; yorum
yeniden üretilince ses temizlenir. Kredi/kapı yönetimi ÇAĞIRANDA (router).
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, undefer

from app.models import (
    EXAM_SECTION_LABELS,
    PC_DAILY_GENERATION_LIMIT,
    PC_KIND_DENEME,
    PC_KIND_PROGRAM,
    PC_KINDS,
    ParentCommentary,
    Task,
    UsageEvent,
    UsageKind,
    User,
)
from app.models.exam_result import ExamResult
from app.models.task import TaskStatus
from app.services import gemini
from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable

__all__ = [
    "AIInvalidResponse",
    "AIServiceUnavailable",
    "build_bundle",
    "compute_signature",
    "daily_generation_count",
    "generate_commentary",
    "is_stale",
]


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


# ---------------------------------------------------------------------------
# Veri paketleri — model yalnız bunları görür
# ---------------------------------------------------------------------------

def _missing_tasks(db: Session, student_id: int, start: date, end: date) -> list[dict]:
    """Aralıkta yayınlanmış ama TAMAMLANMAMIŞ görevler (adlarıyla, en çok 10)."""
    rows = (
        db.query(Task)
        .filter(
            Task.student_id == student_id,
            Task.date >= start,
            Task.date <= end,
            Task.is_draft.is_(False),
            Task.status != TaskStatus.COMPLETED,
        )
        .order_by(Task.date.asc(), Task.id.asc())
        .limit(10)
        .all()
    )
    return [{"date": t.date.isoformat(), "title": t.title or "Görev"} for t in rows]


def _wrong_archive_brief(db: Session, student_id: int) -> dict | None:
    """YSA'nın veliye uygun özeti (koç notları girmez)."""
    try:
        from app.services import wrong_question_service as wqs

        s = wqs.coach_summary(db, student_id)
        return {
            "open": s.counts.open,
            "closed_last_30d": s.closed_last_30d,
            "top_topics": [
                {"topic": t.topic_name, "subject": t.subject_name, "open": t.open_count}
                for t in s.by_topic[:3]
                if t.open_count > 0
            ],
        }
    except Exception:  # noqa: BLE001 — yorum arşivsiz de üretilir
        return None


def _program_bundle(db: Session, parent: User, student: User, today: date) -> dict:
    from app.services.parent_weekly_report import build_weekly_report

    monday = _monday_of(today)
    report = build_weekly_report(db, parent, student.id, week_start=monday, today=today)
    bundle: dict[str, Any] = {
        "student_name": student.full_name,
        "today": today.isoformat(),
        "week": {
            "start": report["start"],
            "gorev_done": report["gorev_done"],
            "gorev_total": report["gorev_total"],
            "completion_pct": report["completion_pct"],
            "test_completed": report["test_completed"],
            "test_planned": report["test_planned"],
            "active_days": report["active_days"],
        },
        "daily": report["daily"],
        "subjects": report["subjects"],
        "comparison": report["comparison"],
        "verdict_level": report["verdict_level"],
        # Yapılmayanlar YALNIZ bugüne kadar olan günlerden — yarının görevi
        # "aksama" değildir. Pencere DAİMA dünü kapsar: Pazartesi günü hafta
        # yeni başladığından "bu hafta" boş kalır ama veli "dün neler
        # yapılmadı?" diye sorar (Pazar görevleri) — karşılama adları
        # söylerken modelin paketi boş kalmasın (2026-07-27 Pazartesi dersi).
        "missing_tasks_so_far": _missing_tasks(
            db, student.id, min(monday, today - timedelta(days=1)), today
        ),
    }
    wa = _wrong_archive_brief(db, student.id)
    if wa:
        bundle["wrong_archive"] = wa
    return bundle


def _recent_exams(db: Session, student_id: int, limit: int = 8) -> list[ExamResult]:
    return (
        db.query(ExamResult)
        .filter(ExamResult.student_id == student_id)
        .order_by(ExamResult.exam_date.desc(), ExamResult.id.desc())
        .limit(limit)
        .all()
    )


def _deneme_bundle(db: Session, parent: User, student: User, today: date) -> dict:
    exams = _recent_exams(db, student.id)
    bundle: dict[str, Any] = {
        "student_name": student.full_name,
        "today": today.isoformat(),
        "exams": [
            {
                "date": e.exam_date.isoformat(),
                "title": e.title,
                "section": EXAM_SECTION_LABELS.get(e.section, str(e.section)),
                "net": e.net,
                "correct": e.total_correct,
                "wrong": e.total_wrong,
                "blank": e.total_blank,
                "questions": (e.total_correct or 0) + (e.total_wrong or 0) + (e.total_blank or 0),
            }
            for e in exams
        ],
    }
    # Aynı türde son iki deneme arası net değişimi (basit trend)
    by_section: dict[Any, list[ExamResult]] = {}
    for e in exams:
        by_section.setdefault(e.section, []).append(e)
    for sec, rows in by_section.items():
        if len(rows) >= 2:
            bundle["last_trend"] = {
                "section": EXAM_SECTION_LABELS.get(sec, str(sec)),
                "last_net": rows[0].net,
                "prev_net": rows[1].net,
                "delta": round(rows[0].net - rows[1].net, 2),
            }
            break
    try:
        from app.services.exam_topic_analysis import exam_insight_summary

        es = exam_insight_summary(db, student)
        if es:
            bundle["topic_analysis"] = es
    except Exception:  # noqa: BLE001 — analizsiz de üretilir
        pass
    wa = _wrong_archive_brief(db, student.id)
    if wa:
        bundle["wrong_archive"] = wa
    return bundle


def build_chat_bundle(db: Session, parent: User, student: User, today: date | None = None) -> dict:
    """Sohbet (P2) veri paketi — program + deneme paketlerinin birleşimi.

    Model YALNIZ bunu görür; koç-özel notlar asla girmez.
    """
    today = today or date.today()
    return {
        "program": _program_bundle(db, parent, student, today),
        "deneme": _deneme_bundle(db, parent, student, today),
    }


def build_bundle(db: Session, parent: User, student: User, kind: str, today: date | None = None) -> dict:
    today = today or date.today()
    if kind == PC_KIND_PROGRAM:
        return _program_bundle(db, parent, student, today)
    if kind == PC_KIND_DENEME:
        return _deneme_bundle(db, parent, student, today)
    raise ValueError(f"bilinmeyen kind: {kind}")


# ---------------------------------------------------------------------------
# Bayatlık imzası — is_stale HESAPLANIR
# ---------------------------------------------------------------------------

def compute_signature(db: Session, student_id: int, kind: str, today: date | None = None) -> dict:
    today = today or date.today()
    if kind == PC_KIND_PROGRAM:
        monday = _monday_of(today)
        q = db.query(Task).filter(
            Task.student_id == student_id,
            Task.date >= monday,
            Task.date <= monday + timedelta(days=6),
            Task.is_draft.is_(False),
        )
        total = q.count()
        done = q.filter(Task.status == TaskStatus.COMPLETED).count()
        return {"week": monday.isoformat(), "total": total, "done": done}
    ids = [e.id for e in _recent_exams(db, student_id)]
    return {"exam_ids": ids}


def is_stale(db: Session, row: ParentCommentary, today: date | None = None) -> bool:
    return row.based_on != compute_signature(db, row.student_id, row.kind, today)


# ---------------------------------------------------------------------------
# Günlük üretim limiti — veli başına (koç kredisini koruma rayı)
# ---------------------------------------------------------------------------

def daily_generation_count(db: Session, parent_id: int) -> int:
    day_start = datetime.combine(
        datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc
    )  # UTC günü — yerel saat UTC'den ilerideyken (TR 00:00-03:00) sayaç delinmesin
    return (
        db.query(func.count(UsageEvent.id))
        .filter(
            UsageEvent.kind == UsageKind.AI_PARENT_COMMENTARY,
            UsageEvent.actor_user_id == parent_id,
            UsageEvent.occurred_at >= day_start,
        )
        .scalar()
        or 0
    )


def daily_limit_reached(db: Session, parent_id: int) -> bool:
    return daily_generation_count(db, parent_id) >= PC_DAILY_GENERATION_LIMIT


# ---------------------------------------------------------------------------
# Üretim — tek Gemini çağrısında ekran + ses metni
# ---------------------------------------------------------------------------

_RULES = """Sen "Rota"sın — Etütkoç Rotam'ın veli asistanı. Aşağıdaki VERİ
paketinden bir öğrenci velisine yönelik yorum hazırlayacaksın.

DİL KURALLARI (kesin):
- Teknolojiye uzak bir veliye anlatır gibi: sade Türkçe, kısa cümleler.
  Terminoloji YASAK ("net" gibi zorunlu kavramları tek cümleyle açıkla).
- Suçlayıcı/etiketleyici dil YASAK; çocuğu velinin gözünde küçük düşürme.
  Cesaretlendirici ama GERÇEKÇİ — sorun varsa nazikçe ve somutça söyle.
- SOMUT ol: görev/konu ADLARINI kullan ("iki görev eksik" değil,
  "Doğrusal Denklemler testi yapılmadı").
- Tıbbi/psikolojik teşhis YASAK.
- En fazla BİR "koçla görüşün" önerisi; yalnız veri gerektiriyorsa.
- Yalnız verilen veriyi kullan; veri yoksa uydurma, "henüz veri yok" de.

ÇIKTI (yalnız geçerli JSON):
{
  "sections": [{"title": "...", "body": "..."}, ...],   // 3-5 bölüm, ekran için (rakam kullanabilirsin)
  "speech_text": "..."                                   // TEK parça seslendirme metni
}
sections bölüm başlıkları şu sırayla olsun (uygunları):
""".strip()

_PROGRAM_SECTIONS = (
    '"Bu hafta ne oldu" · "İyi gidenler" · "Aksayan noktalar" · '
    '"Evde nasıl destek olursunuz"'
)
_DENEME_SECTIONS = (
    '"Son denemeler ne söylüyor" · "Nereden puan kazanılır" · '
    '"Unutulmaya başlayan konular" · "Evde nasıl destek olursunuz"'
)

_SPEECH_RULES = """
speech_text SESLENDİRME içindir (Rota sesli okuyacak):
- SAYILAR YAZIYLA ("%67" değil "yüzde altmış yedi"; "11.33" değil
  "on bir virgül otuz üç").
- Kısaltmalar açık: "LGS" → "L G S". Sembol/parantez kullanma.
- Konuşma dili, akıcı; 150-250 kelime. Bölüm başlığı okuma, doğal anlat.
- İçerik sections ile AYNI hikâye olsun (çelişme).
""".strip()


def _build_prompt(kind: str, bundle: dict) -> str:
    sections_hint = _PROGRAM_SECTIONS if kind == PC_KIND_PROGRAM else _DENEME_SECTIONS
    intro = (
        "KONU: Çocuğun HAFTALIK PROGRAM ilerlemesi (görev takibi)."
        if kind == PC_KIND_PROGRAM
        else "KONU: Çocuğun DENEME SINAVI sonuçları ve konu analizi."
    )
    return (
        f"{_RULES}\n{sections_hint}\n\n{_SPEECH_RULES}\n\n{intro}\n\n"
        f"--- VERİ ---\n{json.dumps(bundle, ensure_ascii=False, default=str)}"
    )


def _normalize(obj: dict) -> dict:
    sections: list[dict] = []
    raw = obj.get("sections")
    if isinstance(raw, list):
        for s in raw:
            if not isinstance(s, dict):
                continue
            title = str(s.get("title") or "").strip()
            body = str(s.get("body") or "").strip()
            if title and body:
                sections.append({"title": title, "body": body})
    speech = obj.get("speech_text")
    speech = speech.strip() if isinstance(speech, str) else ""
    if not sections or not speech:
        raise AIInvalidResponse("Yorum çıktısı eksik (sections/speech_text).")
    return {"sections": sections[:6], "speech_text": speech}


def generate_from_bundle(kind: str, bundle: dict, *, timeout: float = 90.0) -> dict:
    """Hazır paketten Gemini yorumu — DB'ye DOKUNMAZ.

    Çağıran, uzun Gemini çağrısı sırasında SQLite kilidi tutulmasın diye
    paketi kurduktan sonra açık işlemi kapatır (db.commit/rollback), SONRA
    bunu çağırır (2026-07-26 saha dersi: işlem içinde 30 sn'lik dış çağrı →
    "database is locked" 500'leri).
    """
    prompt = _build_prompt(kind, bundle)
    text = gemini.generate(
        [gemini.text_part(prompt)], personal_data=True, json_mode=True,
        max_output_tokens=8192, timeout=timeout,
    )
    return _normalize(gemini.extract_json(text))


def generate_commentary(
    db: Session, parent: User, student: User, kind: str, *, timeout: float = 90.0
) -> dict:
    """Paketi kur → Gemini → {sections, speech_text}. Kredi ÇAĞIRANDA."""
    if kind not in PC_KINDS:
        raise ValueError(f"bilinmeyen kind: {kind}")
    bundle = build_bundle(db, parent, student, kind)
    return generate_from_bundle(kind, bundle, timeout=timeout)


def upsert_commentary(
    db: Session, parent: User, student: User, kind: str, result: dict
) -> ParentCommentary:
    """Üretimi sakla — SES TEMİZLENİR (metinle ses ayrışmasın). Commit çağıranda."""
    row = (
        db.query(ParentCommentary)
        .options(undefer(ParentCommentary.audio))
        .filter(
            ParentCommentary.student_id == student.id,
            ParentCommentary.kind == kind,
        )
        .first()
    )
    if row is None:
        row = ParentCommentary(student_id=student.id, kind=kind)
        db.add(row)
    row.set_sections(result["sections"])
    row.speech_text = result["speech_text"]
    row.set_based_on(compute_signature(db, student.id, kind))
    row.audio = None
    row.audio_content_type = None
    row.audio_generated_at = None
    row.generated_by_id = parent.id
    row.generated_at = datetime.now(timezone.utc)
    return row
