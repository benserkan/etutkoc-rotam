"""Risk altındaki öğrenci tespiti — agrega skor + neden listesi.

`generate_warnings` (analytics.py) öğrenci detayında "akıllı uyarılar"
gösteriyor; bu modül onun listeleme tarafındaki karşılığıdır:
- N öğrencinin risk skorunu hızlıca hesaplar
- Skoru en yüksekten sıralar
- Her öğrencinin "niye risk altında" göstergelerini yapılandırılmış
  olarak döner (UI panel'inde collapsible olarak gösterilir)

Tasarım kararları:
- Skor 0-100 (hesap kolaylığı + UI yorumu)
- Göstergelerin ağırlıkları sabit; ileride kurum başına özelleştirme
- "Mute" 7 gün — yanlış alarm durumunda gürültüyü kessin diye
- 0 plan'lı öğrenci de risk: "henüz programı yok" — kurum yöneticisi için
  öğretmen "uyumakta" sinyali

Performans: bulk_risk_assessment N=500'e kadar dakika altı; her öğrenci
için 2 SQL (week_stats_for + last_login). >500 öğrenci olunca tek SQL'e
optimize edilebilir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Literal

from sqlalchemy.orm import Session

from app.models import User, UserRole
from app.services.analytics import (
    daily_completed_series,
    week_stats_for,
)


logger = logging.getLogger(__name__)


# ---------------------------- Skor sabitleri ----------------------------


# Gösterge ağırlıkları — toplamı 100. Değiştirirsen UI etiketleri de güncelle.
WEIGHTS = {
    "no_login_5d": 25,        # son giriş 5+ gün
    "low_completion": 30,     # haftalık tamamlama < %40
    "consecutive_empty": 20,  # üst üste 3+ gün boş
    "drop_30pct": 15,         # bu hafta vs geçen hafta %30+ düşüş
    "no_program": 10,         # bu hafta planlı görev yok
}

# Skor seviye eşikleri (alt sınır dahil)
LEVEL_THRESHOLDS = [
    (80, "critical"),  # 🔴
    (60, "high"),      # 🟠
    (30, "medium"),    # 🟡
    (0, "ok"),         # 🟢
]

LEVEL_LABELS_TR = {
    "critical": "Kritik",
    "high": "Risk",
    "medium": "Dikkat",
    "ok": "Sağlıklı",
}

LEVEL_EMOJIS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "ok": "🟢",
}


# ---------------------------- Veri yapıları ----------------------------


@dataclass
class RiskIndicator:
    """Tek bir risk göstergesi — sebep + ağırlık + insan-okur metin."""
    code: str
    title: str
    detail: str
    weight: int


@dataclass
class RiskAssessment:
    student: User
    score: int                # 0-100
    level: Literal["ok", "medium", "high", "critical"]
    level_label: str          # Türkçe
    level_emoji: str
    indicators: list[RiskIndicator] = field(default_factory=list)
    last_login_days: int | None = None
    weekly_completed: int = 0
    weekly_planned: int = 0
    weekly_rate_pct: int | None = None


# ---------------------------- Hesaplayıcı ----------------------------


def _level_for_score(score: int) -> str:
    for threshold, level in LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return "ok"


def _days_since(dt: datetime | None, now: datetime) -> int | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (now - dt).days)


def _consecutive_empty_days(db: Session, student_id: int, today: date) -> int:
    """Bugünden geriye giderek üst üste kaç gün hiç tamamlama yok."""
    series = daily_completed_series(db, student_id, today, 14)
    # series: dict[date, int] (sıralı değil garanti — dict comprehension)
    count = 0
    d = today
    for _ in range(14):
        if series.get(d, 0) > 0:
            break
        count += 1
        d -= timedelta(days=1)
    return count


def compute_risk_score(
    db: Session, *, student: User, today: date | None = None,
    now: datetime | None = None,
) -> RiskAssessment:
    """Bir öğrencinin risk skorunu hesapla + göstergeleri çıkar.

    Sadece is_active=True ve role=STUDENT öğrenciler için anlamlı.
    Pasif öğrenci çağrılırsa skor=0, level='ok' döner.
    """
    if today is None:
        today = date.today()
    if now is None:
        now = datetime.now(timezone.utc)

    indicators: list[RiskIndicator] = []
    score = 0

    # Onboarding kuralı: yeni oluşturulmuş öğrenci hemen "giriş yok / programsız"
    # ile işaretlenmemeli (false-positive). Hesap yaşı eşiğin altındaysa o sinyal
    # üretilmez. (Kullanıcı 2026-05-23 — yeni öğrenci yanlış-pozitif uyarısı.)
    account_age_days = _days_since(student.created_at, now)

    # Pasif öğrenci için skor hesaplama yok (panelden zaten filtrelenir).
    # NOT: is_paused öğrenci için risk skoru ÜRETMEYE devam ederiz — koç
    # panelde silik gözükmüş halini görmek isteyebilir. Yalnız is_active=False
    # tamamen kapalı hesaplar erken çıkış yapar.
    if not student.is_active or student.role != UserRole.STUDENT:
        return RiskAssessment(
            student=student, score=0, level="ok",
            level_label=LEVEL_LABELS_TR["ok"],
            level_emoji=LEVEL_EMOJIS["ok"],
        )

    # Haftalık özet
    week = week_stats_for(db, student.id, today)
    rate_pct: int | None = None
    if week.planned > 0:
        rate_pct = int(round(100 * week.completed / week.planned))

    # 1) Son giriş 5+ gün önce. Hiç giriş yapmamışsa, "kaç gündür giriş yok" =
    # hesap yaşı kadar sayılır → yeni öğrenci (hesap < 5 gün) işaretlenmez.
    last_login_days = _days_since(student.last_login_at, now)
    effective_no_login = (
        last_login_days if last_login_days is not None else account_age_days
    )
    if effective_no_login is not None and effective_no_login >= 5:
        indicators.append(RiskIndicator(
            code="no_login_5d",
            title="5+ gündür giriş yok",
            detail=(
                "Öğrenci hiç giriş yapmamış" if last_login_days is None
                else f"Son giriş: {last_login_days} gün önce"
            ),
            weight=WEIGHTS["no_login_5d"],
        ))
        score += WEIGHTS["no_login_5d"]

    # 2) Haftalık tamamlama < %40 (sadece plan varsa)
    if week.planned > 0 and rate_pct is not None and rate_pct < 40:
        indicators.append(RiskIndicator(
            code="low_completion",
            title="Düşük haftalık tamamlama",
            detail=f"Son 7 günde planlanan {week.planned} görevin sadece %{rate_pct}'i tamamlandı",
            weight=WEIGHTS["low_completion"],
        ))
        score += WEIGHTS["low_completion"]

    # 3) Üst üste 3+ gün boş — SADECE plan varsa anlamlı.
    # (Programsız öğrenciye "boş geçti" demek false-positive üretir; bu zaten
    # 'no_program' göstergesi tarafından kapsanıyor.)
    if week.planned > 0:
        empty_days = _consecutive_empty_days(db, student.id, today)
        if empty_days >= 3:
            indicators.append(RiskIndicator(
                code="consecutive_empty",
                title=f"{empty_days} gün üst üste boş",
                detail=f"Son {empty_days} günde hiç görev tamamlaması yok",
                weight=WEIGHTS["consecutive_empty"],
            ))
            score += WEIGHTS["consecutive_empty"]

    # 4) Bu hafta vs geçen hafta %30+ düşüş
    prev_week_end = today - timedelta(days=7)
    prev_week = week_stats_for(db, student.id, prev_week_end)
    prev_rate = (
        int(round(100 * prev_week.completed / prev_week.planned))
        if prev_week.planned > 0 else None
    )
    if (
        prev_rate is not None and rate_pct is not None
        and prev_rate >= 30  # geçen hafta anlamlı bir aktivite vardı
        and (prev_rate - rate_pct) >= 30
    ):
        drop = prev_rate - rate_pct
        indicators.append(RiskIndicator(
            code="drop_30pct",
            title=f"%{drop} performans düşüşü",
            detail=f"Geçen hafta %{prev_rate} → bu hafta %{rate_pct}",
            weight=WEIGHTS["drop_30pct"],
        ))
        score += WEIGHTS["drop_30pct"]

    # 5) Bu hafta planlı görev yok — yeni öğrenciye (hesap < 3 gün) "Programsız"
    # demek erken; koça programı kurması için onboarding süresi tanı.
    if week.planned == 0 and (account_age_days is None or account_age_days >= 3):
        indicators.append(RiskIndicator(
            code="no_program",
            title="Programsız",
            detail="Bu haftaya planlanmış hiç görev yok — öğretmen henüz programı oluşturmamış olabilir",
            weight=WEIGHTS["no_program"],
        ))
        score += WEIGHTS["no_program"]

    score = min(score, 100)
    level = _level_for_score(score)

    return RiskAssessment(
        student=student,
        score=score,
        level=level,  # type: ignore[arg-type]
        level_label=LEVEL_LABELS_TR[level],
        level_emoji=LEVEL_EMOJIS[level],
        indicators=indicators,
        last_login_days=last_login_days,
        weekly_completed=week.completed,
        weekly_planned=week.planned,
        weekly_rate_pct=rate_pct,
    )


def bulk_risk_assessment(
    db: Session, *, students: Iterable[User], today: date | None = None,
    now: datetime | None = None,
) -> list[RiskAssessment]:
    """Çoklu öğrenci için risk skoru — skoru yüksekten düşüğe sıralı liste."""
    if today is None:
        today = date.today()
    if now is None:
        now = datetime.now(timezone.utc)
    out = [
        compute_risk_score(db, student=s, today=today, now=now)
        for s in students
    ]
    # Sağlıklı olanlar listenin sonuna; aynı seviyede skor desc
    out.sort(key=lambda r: (-r.score, r.student.full_name))
    return out


def filter_at_risk(assessments: list[RiskAssessment], min_level: str = "medium") -> list[RiskAssessment]:
    """Sadece belirli seviye+'sını döner. Default: medium ve üstü."""
    levels_order = ["ok", "medium", "high", "critical"]
    min_idx = levels_order.index(min_level) if min_level in levels_order else 1
    return [r for r in assessments if levels_order.index(r.level) >= min_idx]


def get_active_mutes(db: Session, teacher_id: int) -> set[int]:
    """Aktif (süresi dolmamış) mute'lardaki student_id'leri döner — panelden gizleme için."""
    from app.models import AtRiskMute
    rows = (
        db.query(AtRiskMute)
        .filter(
            AtRiskMute.teacher_id == teacher_id,
            AtRiskMute.expires_at > datetime.now(timezone.utc),
        )
        .all()
    )
    return {r.student_id for r in rows}


def get_active_mutes_for_students(db: Session, student_ids: list[int]) -> dict[int, int]:
    """student_id → teacher_id eşlemesi (institution admin görünümü için):
    bir öğrenci öğretmenin panelinde mute edilmişse kuruma bunu göster.
    """
    from app.models import AtRiskMute
    if not student_ids:
        return {}
    rows = (
        db.query(AtRiskMute)
        .filter(
            AtRiskMute.student_id.in_(student_ids),
            AtRiskMute.expires_at > datetime.now(timezone.utc),
        )
        .all()
    )
    return {r.student_id: r.teacher_id for r in rows}
