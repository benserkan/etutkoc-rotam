"""Stage 13 — Burnout (tükenmişlik) tespiti.

Çalışma örüntüsünde anomali sinyalleri:
1. **night_owl**         — Son 14 gün gece 22-04 arası tamamlama / toplam > %30
2. **weekend_no_break**  — Son 21 günde HİÇBİR hafta sonu boş günü yok (sürekli çalıştı)
3. **intensity_spike**   — Bu hafta vs geçen hafta tamamlanan sayı +%50+ arttı
4. **completion_drop**   — Bu hafta vs geçen hafta tamamlama %50+ düştü (aniden tükenme)
5. **streak_break**      — 5+ günlük tamamlama serisi son 3 gündür bozuk

Her sinyal severity döner: 'low' / 'medium' / 'high'.
Genel risk skoru: ağırlıklı toplam (0-100). 60+ "kritik".

Veri kaynağı: Task.date + Task.completed_at + Task.status.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.models import Task, TaskStatus
from app.services.study_dna import (
    TR_OFFSET_HOURS,
    _utc_to_tr_hour_weekday,
    detect_batch_completion_ids,
    resolve_effective_hour,
)


Severity = Literal["low", "medium", "high"]
SeverityScore = {"low": 25, "medium": 50, "high": 80}


SIGNAL_LABELS_TR: dict[str, str] = {
    "night_owl": "Gece geç saatlerde aşırı çalışma",
    "weekend_no_break": "Hafta sonu mola eksikliği",
    "intensity_spike": "Ani yoğunluk artışı",
    "completion_drop": "Tamamlama oranında ani düşüş",
    "streak_break": "Çalışma serisinde kopma",
}

SIGNAL_EMOJI: dict[str, str] = {
    "night_owl": "🌙",
    "weekend_no_break": "📅",
    "intensity_spike": "🔥",
    "completion_drop": "📉",
    "streak_break": "⛓️‍💥",
}


@dataclass
class BurnoutSignal:
    kind: str           # 'night_owl', vb.
    severity: Severity  # low/medium/high
    label: str          # TR insan-okur
    emoji: str
    detail: str         # "Son 14 gün 12/40 görev gece 22:00-04:00 arasında bitirildi"
    metric: float | None = None  # ham metrik (ör. yüzde)


@dataclass
class BurnoutReport:
    student_id: int
    computed_at: datetime
    signals: list[BurnoutSignal] = field(default_factory=list)

    @property
    def risk_score(self) -> int:
        """Sinyal ağırlıklı 0-100 risk skoru."""
        if not self.signals:
            return 0
        # En şiddetli 3 sinyalin ortalaması — overflow önler
        scores = sorted(
            [SeverityScore[s.severity] for s in self.signals], reverse=True
        )[:3]
        return min(100, int(sum(scores) / max(1, len(scores))))

    @property
    def risk_level(self) -> Literal["healthy", "watch", "warn", "critical"]:
        s = self.risk_score
        if s >= 75:
            return "critical"
        if s >= 50:
            return "warn"
        if s >= 25:
            return "watch"
        return "healthy"


# ============================================================================
# Sinyal dedektörleri
# ============================================================================


def _detect_night_owl(tasks: list[Task]) -> BurnoutSignal | None:
    """Son 14 günde gece 22-04 arası tamamlama oranı — batch-aware.

    Toplu işaretleme yapan öğrenci (gün sonunda 22:00'de hepsini tikleyen)
    için completed_at yanıltıcı — eskiden bu false positive üretiyordu.
    Şimdi `resolve_effective_hour` ile saat verisi: batch içindeyse ve
    scheduled_hour varsa o; yoksa bu görev sayımdan tamamen dışlanır
    (none confidence). Veri yetersizse sinyal vermez (None döner).
    """
    batch_ids = detect_batch_completion_ids(tasks)
    night = 0
    total = 0
    for t in tasks:
        hour, _wd, conf = resolve_effective_hour(t, batch_ids=batch_ids)
        if hour is None or conf == "none":
            continue
        total += 1
        if hour >= 22 or hour < 4:
            night += 1
    if total < 5:
        return None
    ratio = night / total
    if ratio < 0.20:
        return None
    if ratio >= 0.50:
        severity: Severity = "high"
    elif ratio >= 0.35:
        severity = "medium"
    else:
        severity = "low"
    return BurnoutSignal(
        kind="night_owl",
        severity=severity,
        label=SIGNAL_LABELS_TR["night_owl"],
        emoji=SIGNAL_EMOJI["night_owl"],
        detail=f"Son 14 gün: {night}/{total} güvenilir saatli tamamlama gece 22:00-04:00 arası (%{int(ratio*100)}).",
        metric=ratio * 100,
    )


def _detect_weekend_no_break(tasks: list[Task], now: datetime) -> BurnoutSignal | None:
    """Son 21 günde hiç hafta sonu boş günü yok mu (Cmt+Paz'larda hep çalıştı)."""
    today = now.date()
    start = today - timedelta(days=21)
    weekend_days_completed: set[date] = set()
    weekend_days_total: set[date] = set()
    cur = start
    while cur <= today:
        if cur.weekday() >= 5:  # Cmt(5) Paz(6)
            weekend_days_total.add(cur)
        cur += timedelta(days=1)
    for t in tasks:
        if t.status not in (TaskStatus.COMPLETED, TaskStatus.PARTIAL):
            continue
        if t.date in weekend_days_total:
            weekend_days_completed.add(t.date)
    if not weekend_days_total:
        return None
    missed = weekend_days_total - weekend_days_completed
    if missed:
        return None  # En az bir hafta sonu boş = sağlıklı
    # Tamamı dolu — 3 haftalık aralıkta ≥6 hafta sonu günü = ciddi
    severity: Severity = "high" if len(weekend_days_total) >= 6 else "medium"
    return BurnoutSignal(
        kind="weekend_no_break",
        severity=severity,
        label=SIGNAL_LABELS_TR["weekend_no_break"],
        emoji=SIGNAL_EMOJI["weekend_no_break"],
        detail=f"Son 21 günde {len(weekend_days_total)}/{len(weekend_days_total)} hafta sonu gününde çalışma var; mola yok.",
        metric=float(len(weekend_days_total)),
    )


def _detect_intensity_spike(tasks: list[Task], now: datetime) -> BurnoutSignal | None:
    """Bu hafta vs geçen hafta tamamlanan sayısı +%50 fark."""
    today = now.date()
    this_start = today - timedelta(days=6)
    last_end = this_start - timedelta(days=1)
    last_start = last_end - timedelta(days=6)
    this_n = sum(
        1 for t in tasks
        if t.status in (TaskStatus.COMPLETED, TaskStatus.PARTIAL)
        and this_start <= t.date <= today
    )
    last_n = sum(
        1 for t in tasks
        if t.status in (TaskStatus.COMPLETED, TaskStatus.PARTIAL)
        and last_start <= t.date <= last_end
    )
    if last_n < 5 or this_n < 5:
        return None
    if this_n <= last_n * 1.5:
        return None
    spike = (this_n - last_n) / last_n * 100
    if spike >= 100:
        severity: Severity = "high"
    elif spike >= 75:
        severity = "medium"
    else:
        severity = "low"
    return BurnoutSignal(
        kind="intensity_spike",
        severity=severity,
        label=SIGNAL_LABELS_TR["intensity_spike"],
        emoji=SIGNAL_EMOJI["intensity_spike"],
        detail=f"Bu hafta {this_n}, geçen hafta {last_n} görev tamamlandı (+%{int(spike)}).",
        metric=spike,
    )


def _detect_completion_drop(tasks: list[Task], now: datetime) -> BurnoutSignal | None:
    """Bu hafta vs geçen hafta tamamlama -%50+ düşüş (önceden çalışıyordu)."""
    today = now.date()
    this_start = today - timedelta(days=6)
    last_end = this_start - timedelta(days=1)
    last_start = last_end - timedelta(days=6)
    this_n = sum(
        1 for t in tasks
        if t.status in (TaskStatus.COMPLETED, TaskStatus.PARTIAL)
        and this_start <= t.date <= today
    )
    last_n = sum(
        1 for t in tasks
        if t.status in (TaskStatus.COMPLETED, TaskStatus.PARTIAL)
        and last_start <= t.date <= last_end
    )
    if last_n < 5:
        return None
    if this_n >= last_n * 0.5:
        return None
    drop = (last_n - this_n) / last_n * 100
    if drop >= 80 or this_n == 0:
        severity: Severity = "high"
    elif drop >= 65:
        severity = "medium"
    else:
        severity = "low"
    return BurnoutSignal(
        kind="completion_drop",
        severity=severity,
        label=SIGNAL_LABELS_TR["completion_drop"],
        emoji=SIGNAL_EMOJI["completion_drop"],
        detail=f"Bu hafta {this_n}, geçen hafta {last_n} görev tamamlandı (-%{int(drop)}).",
        metric=drop,
    )


def _detect_streak_break(tasks: list[Task], now: datetime) -> BurnoutSignal | None:
    """5+ günlük tamamlama serisi son 3 gündür bozuldu mu."""
    today = now.date()
    # Son 21 günü kontrol
    completed_days: set[date] = set()
    for t in tasks:
        if t.status not in (TaskStatus.COMPLETED, TaskStatus.PARTIAL):
            continue
        completed_days.add(t.date)
    # Streak hesabı: bugünden geriye, hiç olmayan ilk gün streak'i kırar
    # Önce 4-21 gün öncesinde 5+ gün streak var mı?
    streak_len = 0
    longest_recent = 0
    for offset in range(3, 21):
        d = today - timedelta(days=offset)
        if d in completed_days:
            streak_len += 1
            longest_recent = max(longest_recent, streak_len)
        else:
            streak_len = 0
    # Son 3 gün boş mu?
    last3_empty = all(
        (today - timedelta(days=i)) not in completed_days for i in range(0, 3)
    )
    if longest_recent >= 5 and last3_empty:
        if longest_recent >= 10:
            severity: Severity = "high"
        elif longest_recent >= 7:
            severity = "medium"
        else:
            severity = "low"
        return BurnoutSignal(
            kind="streak_break",
            severity=severity,
            label=SIGNAL_LABELS_TR["streak_break"],
            emoji=SIGNAL_EMOJI["streak_break"],
            detail=f"{longest_recent} gün aralıksız çalıştıktan sonra son 3 gündür hiçbir görev tamamlanmadı.",
            metric=float(longest_recent),
        )
    return None


# ============================================================================
# Genel
# ============================================================================


def compute_burnout(
    db: Session,
    *,
    student_id: int,
    window_days: int = 21,
    now: datetime | None = None,
) -> BurnoutReport:
    """Öğrenci için window içindeki burnout sinyallerini topla."""
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    window_start = now.date() - timedelta(days=window_days)
    tasks: list[Task] = (
        db.query(Task)
        .filter(Task.student_id == student_id, Task.date >= window_start)
        .all()
    )

    report = BurnoutReport(student_id=student_id, computed_at=now)

    detectors = [
        _detect_night_owl(tasks),
        _detect_weekend_no_break(tasks, now),
        _detect_intensity_spike(tasks, now),
        _detect_completion_drop(tasks, now),
        _detect_streak_break(tasks, now),
    ]
    for sig in detectors:
        if sig is not None:
            report.signals.append(sig)

    # Severity DESC sırala
    sev_order = {"high": 0, "medium": 1, "low": 2}
    report.signals.sort(key=lambda s: sev_order[s.severity])

    return report


def bulk_burnout_for_teacher(
    db: Session, *, teacher_id: int, now: datetime | None = None
) -> list[dict]:
    """Öğretmenin tüm öğrencileri için risk_score özet listesi (dashboard için)."""
    from app.models import User, UserRole
    if now is None:
        now = datetime.now(timezone.utc)
    students = (
        db.query(User)
        .filter(
            User.teacher_id == teacher_id,
            User.role == UserRole.STUDENT,
        )
        .order_by(User.full_name)
        .all()
    )
    # NOT: pasif öğrenciler burnout panelinde görünür (silik render);
    # gerçek bildirim üreticileri pasifleri atlıyor.
    rows = []
    for s in students:
        report = compute_burnout(db, student_id=s.id, now=now)
        rows.append({
            "student": s,
            "report": report,
            "risk_score": report.risk_score,
            "risk_level": report.risk_level,
            "signal_count": len(report.signals),
        })
    rows.sort(key=lambda r: (-r["risk_score"], r["student"].full_name.lower()))
    return rows
