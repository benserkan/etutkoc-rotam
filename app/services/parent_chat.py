"""Rota Veli Asistanı P2 — yazılı sohbet servisi (TEK MERKEZ).

Veli, Rota'ya çocuğu hakkında soru sorar. Model YALNIZ sunucunun paketlediği
veriyi + son PCM_CONTEXT_MESSAGES mesajı görür (koç-özel notlar ASLA girmez;
modelin veri erişimi yok → sızıntı/injection yapısal olarak kapalı).

Kredisiz karşılama: kural-tabanlı tek cümle + duruma göre dizilen hazır
çipler ("değişen az şey var" günlerinde veli boş sohbetle karşılaşmaz).
Yorum çipleri (action="commentary") P1 önbelleğine köprüdür — arayüz kartın
ilgili sekmesini açar, taze yorum varsa krediye hiç dokunulmaz.

Kilit hijyeni (2026-07-26 dersi): uzun Gemini çağrısı DB işlemi DIŞINDA —
çağıran paketi/geçmişi okur, işlemi kapatır, `answer_question` (saf fonksiyon)
sonrası kısa atomik yazım yapar.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    PC_CHAT_DAILY_LIMIT,
    PCM_CONTEXT_MESSAGES,
    PCM_ROLE_ROTA,
    PCM_ROLE_VELI,
    ParentChatMessage,
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
    "answer_question",
    "build_greeting",
    "chat_daily_count",
    "list_messages",
]


# ---------------------------------------------------------------------------
# Günlük soru limiti — veli başına (koç kredisini koruma rayı)
# ---------------------------------------------------------------------------

def chat_daily_count(db: Session, parent_id: int) -> int:
    day_start = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
    return (
        db.query(func.count(UsageEvent.id))
        .filter(
            UsageEvent.kind == UsageKind.AI_PARENT_CHAT,
            UsageEvent.actor_user_id == parent_id,
            UsageEvent.occurred_at >= day_start,
        )
        .scalar()
        or 0
    )


def chat_daily_left(db: Session, parent_id: int) -> int:
    return max(0, PC_CHAT_DAILY_LIMIT - chat_daily_count(db, parent_id))


# ---------------------------------------------------------------------------
# Geçmiş
# ---------------------------------------------------------------------------

def list_messages(
    db: Session, parent_id: int, student_id: int, limit: int = 50
) -> list[ParentChatMessage]:
    rows = (
        db.query(ParentChatMessage)
        .filter(
            ParentChatMessage.parent_id == parent_id,
            ParentChatMessage.student_id == student_id,
        )
        .order_by(ParentChatMessage.created_at.desc(), ParentChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


# ---------------------------------------------------------------------------
# Kredisiz karşılama + hazır çipler (kural tabanlı — AI YOK)
# ---------------------------------------------------------------------------

def build_greeting(db: Session, student: User, today: date | None = None) -> dict:
    """{text, chips:[{id,label,action,payload}]} — hafif sorgularla."""
    today = today or date.today()
    yesterday = today - timedelta(days=1)
    first = (student.full_name or "").split(" ")[0] or "çocuğunuz"

    def _day_counts(d: date) -> tuple[int, int, list[str]]:
        rows = (
            db.query(Task)
            .filter(Task.student_id == student.id, Task.date == d,
                    Task.is_draft.is_(False))
            .all()
        )
        done = sum(1 for t in rows if t.status == TaskStatus.COMPLETED)
        missing = [t.title or "Görev" for t in rows
                   if t.status != TaskStatus.COMPLETED]
        return len(rows), done, missing

    y_total, y_done, y_missing = _day_counts(yesterday)
    t_total, t_done, _ = _day_counts(today)
    recent_exam = (
        db.query(ExamResult)
        .filter(ExamResult.student_id == student.id,
                ExamResult.exam_date >= today - timedelta(days=3))
        .order_by(ExamResult.exam_date.desc(), ExamResult.id.desc())
        .first()
    )

    chips: list[dict] = []
    if y_missing:
        chips.append({"id": "dun", "label": "Dün neler yapılmadı?",
                      "action": "ask", "payload": "Dün hangi görevler yapılmadı?"})
    if recent_exam:
        chips.append({"id": "deneme-yorum", "label": "Son denemeyi yorumla",
                      "action": "commentary", "payload": "deneme"})
    chips.append({"id": "uyum", "label": "Programa uyuyor mu?",
                  "action": "ask", "payload": "Çocuğum bu hafta programa uyuyor mu?"})
    chips.append({"id": "hafta-yorum", "label": "Haftayı yorumla",
                  "action": "commentary", "payload": "program"})
    if not recent_exam:
        chips.append({"id": "deneme-yorum", "label": "Denemeleri yorumla",
                      "action": "commentary", "payload": "deneme"})

    if y_missing:
        adlar = " ve ".join(y_missing[:2])
        text = f"Dün {len(y_missing)} görev eksik kaldı: {adlar}. İstersen sor."
    elif recent_exam:
        text = f"Yeni deneme sonucu var: {recent_exam.title}. İstersen yorumlatabilirsin."
    elif t_total > 0 and t_done == t_total:
        text = f"Bugünün tüm görevleri tamamlandı — {first} güzel gidiyor."
    elif t_total > 0:
        text = f"Bugün {t_done}/{t_total} görev tamamlandı. Merak ettiğini sorabilirsin."
    else:
        text = f"Merhaba! {first} hakkında merak ettiklerini bana sorabilirsin."

    return {"text": text, "chips": chips[:4]}


# ---------------------------------------------------------------------------
# Cevap üretimi — DB'siz saf fonksiyon (uzun çağrı işlem DIŞINDA)
# ---------------------------------------------------------------------------

_CHAT_RULES = """Sen "Rota"sın — Etütkoç Rotam'ın veli asistanı. Bir öğrenci
velisinin sorusunu, aşağıdaki VERİ paketine ve sohbet geçmişine dayanarak
cevaplayacaksın.

KURALLAR (kesin):
- KISA cevap: 2-6 cümle, en fazla ~120 kelime. Sohbet dili, sade Türkçe;
  terminoloji yok (gerekirse tek cümleyle açıkla).
- SOMUT ol: görev/konu ADLARI ve sayılarla konuş ("iki görev eksik" değil,
  "Doğrusal Denklemler testi ile konu videosu yapılmadı").
- YALNIZ verilen veriyi kullan. Veride olmayan şeyi UYDURMA; bilmiyorsan
  "bu bilgi elimde yok" de ve gerekirse koça sormasını öner.
- Suçlayıcı/etiketleyici dil YASAK; cesaretlendirici ama gerçekçi.
- Tıbbi/psikolojik teşhis YASAK.
- En fazla BİR eylem önerisi (örn. koçla görüşme) — yalnız veri gerektiriyorsa.
- Deneme kıyasında SORU SAYISINA bak: az sorulu branş denemesinin neti, çok
  sorulu tam denemeyle DOĞRUDAN kıyaslanmaz — ölçek farkını belirt.
- Soru çocukla/eğitimle ilgisizse kibarca kapsamını söyle ("Ben yalnız
  {ogrenci} hakkında yardımcı olabilirim").
- Düz metin yaz — başlık, madde işareti, markdown KULLANMA.
""".strip()


def answer_question(
    student_name: str,
    bundle: dict,
    history: list[dict],
    question: str,
    *,
    timeout: float = 60.0,
) -> str:
    """Saf fonksiyon: paket + geçmiş + soru → Rota cevabı (düz metin)."""
    parts = [
        _CHAT_RULES.replace("{ogrenci}", student_name),
        f"\nÖğrenci: {student_name}",
        f"\n--- VERİ ---\n{json.dumps(bundle, ensure_ascii=False, default=str)}",
    ]
    if history:
        h = "\n".join(
            f"{'VELİ' if m['role'] == PCM_ROLE_VELI else 'ROTA'}: {m['body']}"
            for m in history[-PCM_CONTEXT_MESSAGES:]
        )
        parts.append(f"\n--- SOHBET GEÇMİŞİ (eski→yeni) ---\n{h}")
    parts.append(f"\n--- VELİNİN SORUSU ---\n{question}\n\nCevabın:")
    # prefer_fast: sohbet gecikmeye duyarlı — aynı ücretli anahtarla ÖNCE flash
    # (saniyeler), üretemezse pro. max_output_tokens 8192: 2.5 ailesinin düşünme
    # tokenları 2048'lik bütçeyi yiyip BOŞ cevap bırakabiliyor (2026-07-26
    # saha bulgusu: "Cevap oluşturulamadı" 422'lerinin kökü).
    text = gemini.generate(
        [gemini.text_part("\n".join(parts))],
        personal_data=True, json_mode=False,
        max_output_tokens=8192, timeout=timeout, prefer_fast=True,
    )
    answer = (text or "").strip()
    if not answer:
        raise AIInvalidResponse("Boş sohbet cevabı")
    # Tek güvenlik makası: aşırı uzun cevabı kırp (kural zaten kısa ister)
    return answer[:2000]
