"""Öğrenci analitik hesaplamaları.

Tek merkezden beslenir: öğrenci detayı (öğretmen), öğrenci kendi paneli,
öğretmen dashboard uyarıları ve veli raporu aynı fonksiyonları kullanır.

Terminoloji:
- **planned**: task.book_items.planned_count toplamı (öğretmenin atadığı hedef)
- **completed**: task.book_items.completed_count toplamı (öğrencinin tiklediği)
- **rate**: günlük ortalama tamamlanan test (son N gün)
- **remaining**: tüm kitapların toplam_test − çözüldü − rezerv
- **projection**: kalan süre × mevcut hız → tamamlanabilir test
- **gap**: projection − remaining (pozitif = yetecek, negatif = yetmeyecek)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Literal

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import (
    AcademicYear,
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskStatus,
    User,
)
from app.services import gorev_stats


# ---------------------------- Veri türleri ----------------------------


@dataclass
class DailyStats:
    planned: int = 0
    completed: int = 0
    tasks_total: int = 0
    tasks_completed: int = 0


@dataclass
class Projection:
    exam_date: date | None
    days_left: int | None
    rate_per_day: float          # son penceredeki günlük genel ortalama (basit)
    window_days: int             # tarihçe penceresi (gün)
    total_tests: int
    completed: int
    reserved: int
    remaining: int               # yeni rezerv açılabilir alan (kalan − rezerv)
    projected_completable: int   # gerçekçi tahmin (DOW × etkili gün)
    gap: int                     # projection − kalan_iş
    required_rate: float         # günlük gereken hız (kalan_iş / etkili_gün)
    # === Gerçekçi model ek alanları ===
    buffer_days: int = 5         # sınav öncesi tampon — son N gün üretken sayılmaz
    effective_days: int = 0      # bugünden buffer_end'e kadar gün sayısı
    dow_rates: dict[int, float] = field(default_factory=dict)        # tamamlanan ortalama (0-6)
    dow_planned_rates: dict[int, float] = field(default_factory=dict)  # planlanan ortalama (0-6)
    dow_hit_rates: dict[int, float] = field(default_factory=dict)    # tutturma oranı (0..1, planlı gün varsa)
    dow_hit_measured: dict[int, bool] = field(default_factory=dict)  # geçmişte tutturma ölçülebildi mi
    simple_projected: int = 0    # eski naif yöntem (karşılaştırma için)
    confidence_level: str = "low"   # "high"/"medium"/"low"  (veri yeterliliğine göre)
    methodology: str = "dow_weighted"   # "naive" / "dow_weighted"


@dataclass
class Warning:
    level: Literal["green", "amber", "red"]
    code: str
    title: str
    detail: str
    # Kanıt: uyarının neden üretildiğini gösteren (etiket, değer) satırları —
    # koç "bu doğru mu?" sorusunu veriye bakarak yanıtlayabilsin.
    evidence: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class StudentSnapshot:
    student: User
    today: DailyStats
    week: DailyStats
    rate_7d: float
    rate_30d: float
    consistency_7d: float        # 0..1 — son 7 günün kaçında tik var
    hit_rate_7d: float           # 0..1 — planlanan→tamamlanan
    projection: Projection
    warnings: list[Warning] = field(default_factory=list)
    worst_warning_level: Literal["green", "amber", "red"] = "green"


# ---------------------------- Yardımcılar ----------------------------


def _daterange(start: date, end_inclusive: date) -> Iterable[date]:
    d = start
    while d <= end_inclusive:
        yield d
        d += timedelta(days=1)


_TR_MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def _d(d: date) -> str:
    """Kısa tarih: '28 Eyl'."""
    return f"{d.day} {_TR_MONTHS[d.month - 1]}"


def _tr_now() -> datetime:
    """Türkiye saati (UTC+3, yaz saati yok) — sunucu UTC çalışsa da doğru saat."""
    return datetime.now(timezone.utc) + timedelta(hours=3)


def _as_local_date(dt: datetime | None) -> date | None:
    if dt is None:
        return None
    # Eğer naive ise UTC kabul et; ardından local (sistem) tarihe dönüştür
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().date()


# ---------------------------- Günlük seriler ----------------------------


def daily_completed_series(
    db: Session, student_id: int, end_date: date, days_back: int,
    tests_only: bool = False,
) -> dict[date, int]:
    """Son N gün için her günün tamamlanan test sayısı.

    Görevin **plan tarihine (Task.date)** göre bucket'lanır — bu hit_rate hesabı için
    plan-gerçekleşme tutarlılığını sağlar. Yani bir görevi geç tıklamak hala görevin
    asıl tarihine puan yazar.

    tests_only=True → yalnız soru bankası kalemleri (deneme kitabı + kitapsız tam
    deneme HARİÇ). "test/gün hız" ve projeksiyon için (deneme soruları test'e
    karışmaz). Varsayılan False → eski davranış (hacim/engagement, geriye uyum).
    """
    start = end_date - timedelta(days=days_back - 1)
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items).joinedload(TaskBookItem.book))
        .filter(Task.student_id == student_id)
        .filter(Task.date >= start)
        .filter(Task.date <= end_date)
        .all()
    )
    result = {d: 0 for d in _daterange(start, end_date)}
    for t in tasks:
        if t.date not in result:
            continue
        items = (
            [it for it in t.book_items if gorev_stats.item_is_test(it)]
            if tests_only else t.book_items
        )
        total = sum(it.completed_count for it in items)
        if total > 0:
            result[t.date] += total
    return result


def daily_action_series(
    db: Session, student_id: int, end_date: date, days_back: int
) -> dict[date, int]:
    """Görev TIKLAMA gününe (Task.completed_at) göre seri — "öğrenci o gün ne kadar
    aktif oldu" göstergesi. UI/aktivite için kullanılabilir, hit_rate için değil.
    """
    start = end_date - timedelta(days=days_back - 1)
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(Task.student_id == student_id)
        .filter(Task.completed_at.isnot(None))
        .filter(func.date(Task.completed_at) >= start)
        .filter(func.date(Task.completed_at) <= end_date)
        .all()
    )
    result = {d: 0 for d in _daterange(start, end_date)}
    for t in tasks:
        d = _as_local_date(t.completed_at) or t.date
        if d not in result:
            continue
        total = sum(it.completed_count for it in t.book_items)
        if total > 0:
            result[d] += total
    return result


def daily_planned_series(
    db: Session, student_id: int, end_date: date, days_back: int,
    tests_only: bool = False,
) -> dict[date, int]:
    """Her gün için o güne atanmış planlanan toplam test (Task.date bazında).

    tests_only=True → yalnız soru bankası kalemleri (deneme HARİÇ; projeksiyon için).
    """
    start = end_date - timedelta(days=days_back - 1)
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items).joinedload(TaskBookItem.book))
        .filter(
            Task.student_id == student_id,
            Task.date >= start,
            Task.date <= end_date,
        )
        .all()
    )
    result = {d: 0 for d in _daterange(start, end_date)}
    for t in tasks:
        if t.date not in result:
            continue
        items = (
            [it for it in t.book_items if gorev_stats.item_is_test(it)]
            if tests_only else t.book_items
        )
        result[t.date] += sum(it.planned_count for it in items)
    return result


def daily_stats_for(db: Session, student_id: int, d: date) -> DailyStats:
    """Belirli bir gün için planlanan/tamamlanan sayılarını döner."""
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(Task.student_id == student_id, Task.date == d)
        .all()
    )
    planned = sum(it.planned_count for t in tasks for it in t.book_items)
    completed = sum(it.completed_count for t in tasks for it in t.book_items)
    return DailyStats(
        planned=planned,
        completed=completed,
        tasks_total=len(tasks),
        tasks_completed=sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
    )


def week_stats_for(
    db: Session, student_id: int, end_date: date, tests_only: bool = False
) -> DailyStats:
    """Son 7 gün toplamı (end dahil).

    tests_only=True: planned/completed yalnız TEST (soru bankası) hacmidir —
    DENEME (branş/genel deneme kitabı + kitapsız tam-deneme) soruları "test"e
    GİRMEZ (GÖREV/TEST/DENEME standardı, 2026-06-02). Yalnız yayınlanmış görevler
    (is_draft=False). Kurum panosu + öğretmen detayı bu modu kullanır ("X test"
    deneme sorularıyla şişmesin).
    """
    start = end_date - timedelta(days=6)
    if tests_only:
        tasks = (
            db.query(Task)
            .options(joinedload(Task.book_items).joinedload(TaskBookItem.book))
            .filter(
                Task.student_id == student_id,
                Task.date >= start,
                Task.date <= end_date,
                Task.is_draft.is_(False),
            )
            .all()
        )
        # Yalnız TEST kitabı kalemleri (deneme kitabı + kitapsız tam-deneme HARİÇ);
        # completed_count kullanılır — etkinlik görevlerinin "çözülen soru"su (solved_count)
        # test hacmine EKLENMEZ → tamamlama oranı ≤ %100 (kurum panosu için temiz;
        # gorev_stats.summarize.test_completed solved_count'u da ekleyip oranı bozuyordu).
        # TEK TANIM (app/services/completion.py): soru bankası + kaynaksız test
        from app.services.completion import item_counts
        planned = sum(
            it.planned_count for t in tasks for it in t.book_items
            if item_counts(it)
        )
        completed = sum(
            it.completed_count for t in tasks for it in t.book_items
            if item_counts(it)
        )
        return DailyStats(
            planned=planned,
            completed=completed,
            tasks_total=len(tasks),
            tasks_completed=sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
        )
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(
            Task.student_id == student_id,
            Task.date >= start,
            Task.date <= end_date,
        )
        .all()
    )
    planned = sum(it.planned_count for t in tasks for it in t.book_items)
    completed = sum(it.completed_count for t in tasks for it in t.book_items)
    return DailyStats(
        planned=planned,
        completed=completed,
        tasks_total=len(tasks),
        tasks_completed=sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
    )


@dataclass
class WeekTestDeneme:
    """Son 7 gün — TEST (soru bankası) SORU hacmi + DENEME ADEDİ.

    BİRİM FARKI (kullanıcı 2026-06-14): test = SORU sayısı (soru bankasından
    çözülen soru hacmi). DENEME = ADET (kaç deneme çözüldü) — soru sayısı DEĞİL
    (1 TYT denemesi = 120 soru ama "1 deneme"). Etkinlik ikisine de girmez."""
    test_planned: int = 0       # planlanan test SORUSU (soru bankası)
    test_completed: int = 0     # çözülen test SORUSU
    deneme_planned: int = 0     # planlanan DENEME ADEDİ (kaç deneme görevi)
    deneme_completed: int = 0   # tamamlanan DENEME ADEDİ


def week_test_deneme_for(db: Session, student_id: int, end_date: date) -> WeekTestDeneme:
    """Kurum panosu/öğretmen detayı için test + deneme hacimlerini AYRI döndürür.

    Görev-merkezli sınıflandırma (gorev_stats.classify_gorev): test görevi →
    test hacmi; deneme/tam_deneme görevi → deneme hacmi; etkinlik → ikisine de
    girmez. Yayınlanmış görevler (is_draft=False).
    """
    start = end_date - timedelta(days=6)
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items).joinedload(TaskBookItem.book))
        .filter(
            Task.student_id == student_id,
            Task.date >= start,
            Task.date <= end_date,
            Task.is_draft.is_(False),
        )
        .all()
    )
    from app.services.completion import item_counts
    res = WeekTestDeneme()
    for t in tasks:
        # Test hacmi TEK TANIMDAN (kalem bazlı) — Program Uyumu, Kohort, Risk ile aynı
        res.test_planned += sum(it.planned_count for it in t.book_items if item_counts(it))
        res.test_completed += sum(it.completed_count for it in t.book_items if item_counts(it))
        cat = gorev_stats.classify_gorev(t)
        if cat in ("deneme", "tam_deneme"):
            # DENEME = ADET (soru hacmi DEĞİL): kaç deneme planlandı / tamamlandı.
            res.deneme_planned += 1
            if gorev_stats.gorev_done(t):
                res.deneme_completed += 1
    return res


# ---------------------------- Hız ve projeksiyon ----------------------------


def recent_rate(
    db: Session, student_id: int, end_date: date, window_days: int,
    tests_only: bool = False,
) -> float:
    """Son N günde günde ortalama tamamlanan test.

    tests_only=True → yalnız soru bankası (deneme HARİÇ) — "test/gün hız" gösterimi.
    """
    series = daily_completed_series(db, student_id, end_date, window_days, tests_only=tests_only)
    if not series:
        return 0.0
    return sum(series.values()) / window_days


def inventory_totals(
    db: Session, student_id: int, tests_only: bool = False
) -> tuple[int, int, int]:
    """Öğrencinin kitaplarının toplam / çözüldü / rezerv test sayıları.

    tests_only=True → deneme kitapları (branş/genel deneme) HARİÇ — yalnız soru
    bankası 'test envanteri' (DNA Tamamlama + projeksiyon için; deneme test sayılmaz).
    Varsayılan False → tüm kitaplar (geriye uyum).
    """
    total = 0
    completed = 0
    reserved = 0
    sbs = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).selectinload(Book.sections),
            selectinload(StudentBook.section_progress),
        )
        .filter(
            StudentBook.student_id == student_id,
            StudentBook.archived_at.is_(None),   # P4: arşivli kitap sayılmaz
        )
        .all()
    )
    for sb in sbs:
        if tests_only and not gorev_stats.is_test_book(sb.book):
            continue
        total += sb.total_tests
        completed += sb.completed_tests
        reserved += sb.reserved_tests
    return total, completed, reserved


def get_exam_date(db: Session, student: User) -> date | None:
    """Öğrenci-spesifik sınav tarihi.

    Hedef sınav öğrencinin sınıf+mezunluk durumundan türetilir
    (User.effective_exam_target). Tarih de oradan gelir; akademik yıl
    seviyesinde tek bir 'sınav tarihi' tutmuyoruz çünkü aynı yılda LGS+YKS
    öğrenciler birlikte yer alabilir.
    """
    return student.effective_exam_date


def compute_projection(
    db: Session, student: User, today: date,
    window_days: int = 28, buffer_days: int = 5,
) -> Projection:
    """Gerçekçi projeksiyon hesaplaması.

    Yöntem (DOW-weighted forward walk):
    1. Son `window_days` gün için her **haftagünü (0-6)** ortalama tamamlanan test sayısı
       hesaplanır (dow_rates).
    2. Bugünden başlayarak **sınav tarihi − buffer_days**'e kadar her gün için o günün
       haftagününe ait ortalama eklenir → projected_completable.
       (Sınav haftasının son 5 günü tampon kabul edilir; öğrenci o günlerde sıfır
        ya da minimum çalışma yapar varsayımıdır.)
    3. Gap = projected_completable − (kalan_iş = total − completed)
    4. required_rate = kalan_iş / etkili_gün  (etkili = sınav − bugün − buffer)
    5. Karşılaştırma için **naif** yöntem (genel ortalama × etkili_gün) `simple_projected`
       alanında saklanır.
    6. Güven seviyesi: ≥21 aktif gün → high, 7-20 → medium, <7 → low.
    """
    exam_date = get_exam_date(db, student)
    days_left: int | None
    if exam_date:
        days_left = (exam_date - today).days
        if days_left < 0:
            days_left = 0
        buffer_end = exam_date - timedelta(days=buffer_days)
        effective_days = max(0, (buffer_end - today).days)
    else:
        days_left = None
        effective_days = 0

    # PROJEKSİYON = yalnız TEST envanteri (deneme test'e karışmaz). Hız/plan/envanter
    # hepsi tests_only — deneme soruları projeksiyona girmez (izole edilmiş hesap).
    # Tarihçe — günlük tamamlama (sadece geçmiş)
    series = daily_completed_series(db, student.id, today, window_days, tests_only=True)
    # Geçmiş penceresi öğrencinin İLK yayınlanmış görevinden başlar: 1 haftalık
    # öğrencinin hızı 28 güne bölünüp 4 kat küçük çıkıyordu (Zeynep Ela: gerçek
    # ~11 test/gün, projeksiyon 2.8). Başlamadan önceki boş günler haftagünü
    # ortalamalarını da sulandırıyordu.
    _first_task = (
        db.query(func.min(Task.date))
        .filter(Task.student_id == student.id, Task.is_draft.is_(False))
        .scalar()
    )
    if _first_task is not None and _first_task > today - timedelta(days=window_days - 1):
        series = {d: v for d, v in series.items() if d >= _first_task}
        window_days = max(1, (today - _first_task).days + 1)
    overall_rate = (sum(series.values()) / window_days) if window_days > 0 else 0.0

    # Planlama serisi — geçmiş + gelecek (öğretmenin tüm planını yansıtır)
    # daily_planned_series end_date'e doğru bakıyor; gelecek için ayrı çekip birleştiriyoruz.
    past_planned = daily_planned_series(db, student.id, today, window_days, tests_only=True)
    # Geleceğe planları al — gelecek görevleri sınav tarihine kadar kapsar
    from app.models import Task as _Task, TaskBookItem as _TBI
    future_q = (
        db.query(_Task)
        .options(joinedload(_Task.book_items).joinedload(_TBI.book))
        .filter(_Task.student_id == student.id, _Task.date >= today)
        .all()
    )
    future_planned: dict[date, int] = {}
    for t in future_q:
        future_planned[t.date] = future_planned.get(t.date, 0) + sum(
            it.planned_count for it in t.book_items if gorev_stats.item_is_test(it)
        )

    # DOW bazlı: tamamlanan = sadece geçmiş, planlanan = geçmiş + gelecek (yalnızca plan girilmiş günler)
    dow_completed_buckets: dict[int, list[int]] = {i: [] for i in range(7)}
    dow_planned_buckets: dict[int, list[int]] = {i: [] for i in range(7)}
    # Geçmiş tamamlama — boş günler dahil (ortalama doğru çıksın)
    for d, count in series.items():
        dow_completed_buckets[d.weekday()].append(count)
    # Planlama: yalnızca plan girilmiş günleri kullan (boş günleri ortalamaya katma)
    for d, count in {**past_planned, **future_planned}.items():
        if count > 0:
            dow_planned_buckets[d.weekday()].append(count)

    dow_rates: dict[int, float] = {}            # ortalama tamamlanan
    dow_planned_rates: dict[int, float] = {}    # ortalama planlanan (sadece planlı günler)
    dow_hit_rates: dict[int, float] = {}        # tutturma oranı (sadece planlı geçmiş günler)
    # Geçmişte planlı ve tamamlanmış DOW hit oranı için ayrı bucket
    dow_past_planned_buckets: dict[int, int] = {i: 0 for i in range(7)}
    dow_past_completed_buckets: dict[int, int] = {i: 0 for i in range(7)}
    for d, count in past_planned.items():
        if count > 0:
            dow_past_planned_buckets[d.weekday()] += count
            dow_past_completed_buckets[d.weekday()] += series.get(d, 0)
    dow_hit_measured: dict[int, bool] = {}
    for dow in range(7):
        c_vals = dow_completed_buckets[dow]
        p_vals = dow_planned_buckets[dow]
        dow_rates[dow] = (sum(c_vals) / len(c_vals)) if c_vals else 0.0
        dow_planned_rates[dow] = (sum(p_vals) / len(p_vals)) if p_vals else 0.0
        if dow_past_planned_buckets[dow] > 0:
            dow_hit_rates[dow] = dow_past_completed_buckets[dow] / dow_past_planned_buckets[dow]
            dow_hit_measured[dow] = True
        else:
            dow_hit_rates[dow] = 0.0
            dow_hit_measured[dow] = False

    total, completed, reserved = inventory_totals(db, student.id, tests_only=True)
    remaining_unassigned = total - completed - reserved
    remaining_overall = total - completed  # tüm hedef iş

    # Forward projection
    # Algoritma: o günün planlanan ortalama × o günün tutturma oranı
    # Planlı gün yoksa: completed-bazlı dow_rates kullan (geçmişten direkt)
    # Hiçbir veri yoksa: overall_rate fallback
    # Genel tutturma oranı (fallback olarak)
    total_past_planned = sum(dow_past_planned_buckets.values())
    total_past_completed = sum(dow_past_completed_buckets.values())
    overall_hit_rate = (total_past_completed / total_past_planned) if total_past_planned > 0 else 0.0

    projected_real = 0.0
    if effective_days > 0:
        for i in range(effective_days):
            d = today + timedelta(days=i)
            dow = d.weekday()
            planned_avg = dow_planned_rates.get(dow, 0.0)
            hit = dow_hit_rates.get(dow, 0.0)
            past_completed = dow_rates.get(dow, 0.0)
            if planned_avg > 0 and hit > 0:
                # Plan-bazlı: gelecek günlerde bu kadar plan, bu oranda tutturuyor
                r = planned_avg * hit
            elif planned_avg > 0 and overall_hit_rate > 0:
                # Plan var ama bu DOW'da geçmiş tamamlama yok → genel hit oranı
                r = planned_avg * overall_hit_rate
            elif past_completed > 0:
                # Plan yok ama geçmişte bu DOW'da tamamlama vardı
                r = past_completed
            elif overall_rate > 0:
                # Hiç DOW verisi yok → genel ortalama
                r = overall_rate
            else:
                r = 0.0
            projected_real += r
    projected_int = int(round(projected_real))

    # Naif karşılaştırma (eski yöntem)
    simple_projected = int(round(overall_rate * effective_days)) if effective_days > 0 else 0

    # required = kalan_iş / etkili_gün (sınav günü ve son 5 gün dahil değil)
    required = (remaining_overall / effective_days) if effective_days > 0 else 0.0

    # Gap
    gap = projected_int - remaining_overall

    # Güven seviyesi — kaç günde aktivite var
    days_with_data = sum(1 for v in series.values() if v > 0)
    if days_with_data >= 21:
        confidence = "high"
    elif days_with_data >= 7:
        confidence = "medium"
    else:
        confidence = "low"

    return Projection(
        exam_date=exam_date,
        days_left=days_left,
        rate_per_day=overall_rate,
        window_days=window_days,
        total_tests=total,
        completed=completed,
        reserved=reserved,
        remaining=remaining_unassigned,
        projected_completable=projected_int,
        gap=gap,
        required_rate=required,
        buffer_days=buffer_days,
        effective_days=effective_days,
        dow_rates=dow_rates,
        dow_planned_rates=dow_planned_rates,
        dow_hit_rates=dow_hit_rates,
        dow_hit_measured=dow_hit_measured,
        simple_projected=simple_projected,
        confidence_level=confidence,
        methodology="dow_weighted",
    )


# ---------------------------- Performans skorları ----------------------------


def daily_activity_flag_series(
    db: Session, student_id: int, end_date: date, days_back: int
) -> dict[date, bool]:
    """Her gün (Task.date) için öğrenci o gün herhangi bir görevi tikledi mi.

    Aktif/tik = görevin durumu COMPLETED VEYA bir kaleminde completed_count > 0.
    İtemless etkinlik görevi (Diğer/Video/Özet/Tekrar — soru sayısı 0) tamamlandığında
    da o gün AKTİF sayılır. "İstikrar / hareket" gibi engagement metrikleri için
    soru-sayısı yerine bu görev-temelli sinyal kullanılmalı.
    """
    start = end_date - timedelta(days=days_back - 1)
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(
            Task.student_id == student_id,
            Task.date >= start,
            Task.date <= end_date,
        )
        .all()
    )
    result = {d: False for d in _daterange(start, end_date)}
    for t in tasks:
        if t.date not in result:
            continue
        done = (t.status == TaskStatus.COMPLETED) or any(
            it.completed_count > 0 for it in t.book_items
        )
        if done:
            result[t.date] = True
    return result


def consistency_score(
    db: Session, student_id: int, end_date: date, days: int = 7
) -> float:
    """Son N günün kaçında öğrenci en az 1 görevi tikledi (etkinlik dahil) / N.

    Engagement metriği — itemless etkinlik görevi tamamlaması da aktif gün sayılır.
    """
    flags = daily_activity_flag_series(db, student_id, end_date, days)
    if not flags:
        return 0.0
    active_days = sum(1 for v in flags.values() if v)
    return active_days / days


def hit_rate(
    db: Session, student_id: int, end_date: date, days: int = 7
) -> float:
    """Planlanan → tamamlanan oranı (son N gün, Task.date penceresi).

    Dönüş 0..N arası — genellikle 0..1. Bazen planlanandan fazlası çözülür
    (öğretmenin manuel kalem eklemesi, ileri tarihli görev tıklama), 1.0'ı
    aşmaması için kırpma yapmıyoruz; kullanan yer görselleştirebilir.
    """
    start = end_date - timedelta(days=days - 1)
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(
            Task.student_id == student_id,
            Task.date >= start,
            Task.date <= end_date,
        )
        .all()
    )
    planned = sum(it.planned_count for t in tasks for it in t.book_items)
    completed = sum(it.completed_count for t in tasks for it in t.book_items)
    return (completed / planned) if planned > 0 else 0.0


# ---------------------------- Ders bazında ----------------------------


def subject_breakdown(
    db: Session, student_id: int, tests_only: bool = False
) -> list[dict]:
    """Her ders için toplam/çözüldü/rezerv ve tamamlanma yüzdesi.

    tests_only=True → DENEME kitapları (branş/genel deneme) HARİÇ; yalnız 'test'
    (soru bankası/fasikül/konu anlatımlı) kitapları sayılır. Ders-bazlı 'test
    çalışması' uyarıları (henüz başlanmadı / durgunluk) deneme atamasını test
    saymasın diye — DENEME≠TEST standardı (bkz. gorev_stats).
    """
    sbs = (
        db.query(StudentBook)
        .options(
            joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(StudentBook.book).selectinload(Book.sections),
            selectinload(StudentBook.section_progress),
        )
        .filter(
            StudentBook.student_id == student_id,
            StudentBook.archived_at.is_(None),   # P4: arşivli kitap sayılmaz
        )
        .all()
    )
    bucket: dict[int, dict] = {}
    for sb in sbs:
        if tests_only and sb.book.type in gorev_stats.DENEME_BOOK_TYPES:
            continue
        s = sb.book.subject
        b = bucket.setdefault(
            s.id,
            {
                "subject_id": s.id,
                "name": s.name,
                "order": s.order,
                "total": 0,
                "completed": 0,
                "reserved": 0,
                "books": 0,
                "last_completed_at": None,
            },
        )
        b["total"] += sb.total_tests
        b["completed"] += sb.completed_tests
        b["reserved"] += sb.reserved_tests
        b["books"] += 1
    # Ders bazında "son tamamlama tarihi" — en son o derste tiklenmiş görev
    last_q = (
        db.query(Subject.id, func.max(Task.completed_at))
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .join(Book, Book.id == TaskBookItem.book_id)
        .join(Subject, Subject.id == Book.subject_id)
        .filter(Task.student_id == student_id)
        .filter(Task.completed_at.isnot(None))
    )
    if tests_only:
        last_q = last_q.filter(Book.type.notin_(gorev_stats.DENEME_BOOK_TYPES))
    last_per_subject_q = last_q.group_by(Subject.id).all()
    for sid, last in last_per_subject_q:
        if sid in bucket:
            bucket[sid]["last_completed_at"] = last
    # Yüzde
    out = []
    for b in sorted(bucket.values(), key=lambda x: (x["order"], x["name"])):
        t = b["total"]
        b["percent_done"] = int(round(100 * b["completed"] / t)) if t > 0 else 0
        b["percent_reserved"] = int(round(100 * b["reserved"] / t)) if t > 0 else 0
        b["remaining"] = t - b["completed"] - b["reserved"]
        out.append(b)
    return out


# ---------------------------- Uyarı üreticiler ----------------------------


def generate_warnings(
    db: Session, student: User, today: date, projection: Projection
) -> list[Warning]:
    """Araba-ekranı tarzı akıllı uyarılar. Sadece uyulması gereken durumlarda dön."""
    out: list[Warning] = []

    # Mola modu (is_paused): koçluk takibi duraklatıldı (yaz molası vb.) → koç-yüzü
    # uyarı ÜRETME. student_snapshot bunu kullandığından durum özeti + öğrenci
    # listesi rengi + uyarı akışı + rozet hepsi otomatik susar. Veli cron'ları
    # zaten _all_parent_student_pairs'te paused'ı atlıyor.
    if getattr(student, "is_paused", False):
        return out

    # Onboarding: yeni oluşturulmuş öğrenci (hesap < 3 gün) inaktivite uyarısı
    # ALMAZ — henüz programı/girişi olmayabilir (false-positive önleme).
    _created = student.created_at
    if _created is not None and _created.tzinfo is None:
        _created = _created.replace(tzinfo=timezone.utc)
    account_age_days = (
        max(0, (datetime.now(timezone.utc) - _created).days) if _created else None
    )

    # 1) Bugün hiç tik yapmadı mı — GÖREV-bazlı (her tür görev; etkinlik DAHİL).
    # "Tik" = görev tamamlama. Etkinlik görevi (Diğer/Video/Özet/Tekrar, soru
    # sayısı 0) de engagement'a sayılır → bugün ≥1 yayınlanmış görev var ama
    # hiçbiri tamamlanmadıysa uyarı (test hacmi 0 olsa da). Eskiden yalnız test
    # hacmi (planned>0) bakıyordu → etkinlik-only günde yanlışlıkla yeşil
    # görünüyordu (bkz. "Diğer görevler tamamlamaya sayılır").
    today_stats = daily_stats_for(db, student.id, today)
    _today_tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(Task.student_id == student.id, Task.date == today,
                Task.is_draft.is_(False))
        .all()
    )
    _today_gorev = len(_today_tasks)
    _today_gorev_done = sum(1 for t in _today_tasks if gorev_stats.gorev_done(t))
    if _today_gorev > 0 and _today_gorev_done == 0:
        # Saat geç mi? Akşam geçmiş ama hiç tik yok — kırmızı; gün hâlâ devam ediyorsa sarı
        _now_tr = _tr_now()
        level = "red" if _now_tr.hour >= 20 else "amber"
        out.append(Warning(
            level=level,
            code="today_no_tick",
            title="Bugün hiç tik yapmadı",
            detail=f"Bugüne planlanmış {_today_gorev} görev var, henüz hiçbiri yapılmadı.",
            evidence=[
                ("Bugün", _d(today)),
                ("Yayınlanmış görev", f"{_today_gorev} görev"),
                ("Tamamlanan", "0 görev"),
                ("Kontrol saati", f"{_now_tr:%H:%M} (20:00'den sonra kırmızıya döner)"),
            ],
        ))

    # 2) Dün de tik yoksa — ciddileştir (etkinlik görevi de tik sayılır)
    yesterday = today - timedelta(days=1)
    yesterday_stats = daily_stats_for(db, student.id, yesterday)
    if (
        yesterday_stats.planned > 0
        and yesterday_stats.completed == 0
        and yesterday_stats.tasks_completed == 0
    ):
        out.append(Warning(
            level="red",
            code="yesterday_no_tick",
            title="Dün hiç ilerleme yok",
            detail=f"Dün {yesterday_stats.planned} test planlı idi, tamamlanmadı.",
            evidence=[
                ("Gün", _d(yesterday)),
                ("Planlanan", f"{yesterday_stats.planned} test"),
                ("Çözülen", "0 test"),
                ("Tamamlanan görev", "0"),
            ],
        ))

    # 3) Son 3 günde hiç tik yok mu — SADECE programı olan (planlı görevi bulunan)
    # ve hesabı ≥3 günlük öğrenci için. Yeni/programsız öğrenciye "hareket yok"
    # demek yanlış-pozitif (programsızlık ayrı sinyal).
    series3 = daily_completed_series(db, student.id, today, 3)
    dby_stats = daily_stats_for(db, student.id, today - timedelta(days=2))
    planned_3 = today_stats.planned + yesterday_stats.planned + dby_stats.planned
    # Etkinlik (itemless) görev tamamlaması da "hareket" sayılır — son 3 günde
    # tamamlanan görev varsa "hareket yok" demek yanlış (soru sayısı 0 olsa bile).
    tasks_done_3 = (
        today_stats.tasks_completed
        + yesterday_stats.tasks_completed
        + dby_stats.tasks_completed
    )
    if (
        sum(series3.values()) == 0
        and tasks_done_3 == 0
        and planned_3 > 0
        and (account_age_days is None or account_age_days >= 3)
    ):
        out.append(Warning(
            level="red",
            code="inactive_3d",
            title="3 gündür hareket yok",
            detail="Son 3 günde öğrencinin hiç test ya da görev tamamlaması yok.",
            evidence=[
                (_d(today - timedelta(days=2)), f"{dby_stats.planned} test planlı · 0 çözüldü"),
                (_d(yesterday), f"{yesterday_stats.planned} test planlı · 0 çözüldü"),
                (_d(today), f"{today_stats.planned} test planlı · 0 çözüldü"),
                ("Tamamlanan görev (3 gün)", "0"),
            ],
        ))

    # 4) Haftalık tempo — son 7 TAMAMLANMIŞ gün (bugün hariç: gün sürüyor),
    # yalnız YAYINLANMIŞ görevler (taslağı öğrenci görmez), GÖREV bazlı
    # (etkinlik dahil). Eskiden test hacmiyle ölçülüp "görevlerin %X'i"
    # yazıyordu ve taslakları da sayıyordu.
    _w_end = today - timedelta(days=1)
    _w_start = today - timedelta(days=7)
    _w_tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items).joinedload(TaskBookItem.book))
        .filter(Task.student_id == student.id, Task.date >= _w_start,
                Task.date <= _w_end, Task.is_draft.is_(False))
        .all()
    )
    _wg = gorev_stats.summarize(_w_tasks)
    _w_days_prog = len({t.date for t in _w_tasks})
    _w_ev = [
        ("Dönem", f"{_d(_w_start)} – {_d(_w_end)} (son 7 gün, bugün hariç)"),
        ("Verilen görev", f"{_wg.gorev_total} görev · {_w_days_prog} gün"),
        ("Tamamlanan görev", f"{_wg.gorev_done} görev (%{_wg.gorev_pct})"),
        ("Test", f"{_wg.test_completed}/{_wg.test_planned} çözüldü"),
    ]
    if _wg.gorev_total >= 3 and _wg.gorev_done == 0:
        out.append(Warning(
            level="red",
            code="weekly_zero",
            title="Haftalık ilerleme sıfır",
            detail=f"Son 7 günde verilen {_wg.gorev_total} görevin hiçbiri tamamlanmadı.",
            evidence=_w_ev,
        ))
    elif _wg.gorev_total >= 3 and _wg.gorev_pct < 50:
        out.append(Warning(
            level="amber",
            code="weekly_miss",
            title="Haftalık tempo düşük",
            detail=(f"Son 7 günde verilen {_wg.gorev_total} görevin "
                    f"{_wg.gorev_done} tanesi tamamlandı (%{_wg.gorev_pct})."),
            evidence=_w_ev,
        ))

    # 5) Projeksiyon açığı
    if projection.days_left is not None and projection.days_left > 0:
        remaining_overall = projection.total_tests - projection.completed
        if remaining_overall > 0 and projection.rate_per_day > 0:
            if projection.gap < 0:
                # İleriye-dönük projeksiyon açığı: öğrenci AKTİF çalışıyor
                # (rate_per_day > 0) ama tempoca geride → 'dikkat' (amber), acil
                # hareketsizlik (red) ile aynı şiddette değil. Tamamen durmuş
                # öğrenci için ayrı 'projection_zero_rate' (red) var.
                out.append(Warning(
                    level="amber",
                    code="projection_shortfall",
                    title="Sınava yetişmeyecek",
                    detail=(
                        f"Mevcut hızla ({projection.rate_per_day:.1f} test/gün) "
                        f"{abs(projection.gap)} test eksik kalacak. "
                        f"Gerekli hız: {projection.required_rate:.1f} test/gün."
                    ),
                    evidence=[
                        ("Sınav tarihi", _d(projection.exam_date) if projection.exam_date else "girilmemiş"),
                        ("Kalan gün", f"{projection.days_left} gün"),
                        ("Kalan test", f"{projection.total_tests - projection.completed} test (toplam {projection.total_tests})"),
                        ("Mevcut hız", f"{projection.rate_per_day:.1f} test/gün (son {projection.window_days} gün)"),
                        ("Gereken hız", f"{projection.required_rate:.1f} test/gün"),
                    ],
                ))
            elif projection.gap < remaining_overall * 0.1:
                # Sınırda
                out.append(Warning(
                    level="amber",
                    code="projection_tight",
                    title="Projeksiyon sınırda",
                    detail=(
                        f"Mevcut hızla hedefi çok az farkla tutturuyor "
                        f"(±{projection.gap} test). Hız düşerse gecikir."
                    ),
                    evidence=[
                        ("Sınav tarihi", _d(projection.exam_date) if projection.exam_date else "girilmemiş"),
                        ("Kalan gün", f"{projection.days_left} gün"),
                        ("Kalan test", f"{projection.total_tests - projection.completed} test (toplam {projection.total_tests})"),
                        ("Mevcut hız", f"{projection.rate_per_day:.1f} test/gün (son {projection.window_days} gün)"),
                        ("Gereken hız", f"{projection.required_rate:.1f} test/gün"),
                    ],
                ))
        elif projection.rate_per_day == 0 and remaining_overall > 0:
            out.append(Warning(
                level="red",
                code="projection_zero_rate",
                title="Hız sıfır — projeksiyon imkansız",
                detail=f"Son 7 günde tik yok; {remaining_overall} test tamamlanmayı bekliyor.",
                evidence=[
                    ("Sınav tarihi", _d(projection.exam_date) if projection.exam_date else "girilmemiş"),
                    ("Kalan gün", f"{projection.days_left} gün"),
                    ("Kalan test", f"{projection.total_tests - projection.completed} test (toplam {projection.total_tests})"),
                    ("Mevcut hız", f"{projection.rate_per_day:.1f} test/gün (son {projection.window_days} gün)"),
                    ("Gereken hız", f"{projection.required_rate:.1f} test/gün"),
                ],
            ))

    # 6) Ders bazlı — yalnız VERİLMİŞ ama YAPILMAMIŞ iş (2026-09-29 düzeltmesi).
    # Eskiden atanmış kitabı olan her ders "7+ gündür tamamlama yok" diyordu;
    # koçun o hafta bilerek programlamadığı ders öğrencinin kusuru gibi
    # görünüyordu (Taha: aktif çalışırken 6 "durgunluk"). Tersine rezervi iade
    # edilmiş, verilip hiç yapılmamış ders (Boran AYT Kimya 0/4) kaçıyordu.
    # Kural: son 14 günde yayınlanmış TEST görevi olan derste yapılmamış test
    # varsa VE o dersten son çözüm 7+ gün önceyse (ya da hiç yoksa) uyarı.
    # DENEME≠TEST: deneme kitapları girmez.
    from app.models import Task as _T, TaskBookItem as _TI, Book as _B, Subject as _S
    if account_age_days is None or account_age_days >= 7:
        _s_start = today - timedelta(days=14)
        _rows = (
            db.query(_B.subject_id, _S.name, func.count(func.distinct(_T.id)),
                     func.coalesce(func.sum(_TI.planned_count), 0),
                     func.coalesce(func.sum(_TI.completed_count), 0))
            .join(_TI, _TI.book_id == _B.id)
            .join(_T, _T.id == _TI.task_id)
            .join(_S, _S.id == _B.subject_id)
            .filter(_T.student_id == student.id, _T.date >= _s_start, _T.date < today,
                    _T.is_draft.is_(False), _B.type.notin_(gorev_stats.DENEME_BOOK_TYPES))
            .group_by(_B.subject_id, _S.name)
            .all()
        )
        _last = dict(
            db.query(_B.subject_id, func.max(_T.date))
            .join(_TI, _TI.book_id == _B.id)
            .join(_T, _T.id == _TI.task_id)
            .filter(_T.student_id == student.id, _TI.completed_count > 0,
                    _B.type.notin_(gorev_stats.DENEME_BOOK_TYPES))
            .group_by(_B.subject_id)
            .all()
        )
        _programmed = {r[0] for r in _rows}
        # Kayıt dışı önceden çözülmüş (baseline) test varsa ders "başlanmadı"
        # sayılmaz — yalnız görevsiz çözüm tarihi bilinmez.
        _bd = subject_breakdown(db, student.id, tests_only=True) if _rows else []
        _has_solved = {sb["subject_id"] for sb in _bd if sb["completed"] > 0}
        for sid, sname, n_tasks, planned, completed in _rows:
            undone = int(planned) - int(completed)
            last = _last.get(sid)
            gap = (today - last).days if last else None
            if undone <= 0 or (gap is not None and gap < 7):
                continue
            ev = [
                ("Dönem", f"{_d(_s_start)} – {_d(today - timedelta(days=1))} (son 14 gün)"),
                ("Verilen", f"{n_tasks} görev · {int(planned)} test"),
                ("Çözülen", f"{int(completed)} test"),
                ("Son çözüm", f"{_d(last)} ({gap} gün önce)" if last else (
                    "görevle çözüm yok (kitapta önceden çözülmüş test var)"
                    if sid in _has_solved else "hiç yok")),
            ]
            if last is None and sid not in _has_solved:
                out.append(Warning(
                    level="amber", code=f"subject_untouched_{sid}",
                    title=f"{sname} henüz başlanmadı",
                    detail=f"Son 14 günde verilen {int(planned)} testin hiçbiri çözülmedi.",
                    evidence=ev,
                ))
            else:
                out.append(Warning(
                    level="amber", code=f"subject_stale_{sid}",
                    title=f"{sname} dersinde durgunluk",
                    detail=(f"Son 14 günde verilen {int(planned)} testin {undone} tanesi yapılmadı; "
                            + (f"bu dersten son çözüm {gap} gün önce." if last
                               else "bu derste görevle yapılmış çözüm yok.")),
                    evidence=ev,
                ))

        # Programda olmayan dersler — öğrenci kusuru DEĞİL, koç planlama
        # hatırlatması; öğrenci başına TEK satır (liste uzamasın). Yalnız
        # program yürüyen öğrencide (son 14 günde yayınlanmış görev var).
        _has_recent = db.query(_T.id).filter(
            _T.student_id == student.id, _T.date >= _s_start, _T.is_draft.is_(False),
        ).first() is not None
        if _has_recent and (account_age_days is None or account_age_days >= 14):
            _upcoming = {
                r[0] for r in (
                    db.query(_B.subject_id)
                    .join(_TI, _TI.book_id == _B.id)
                    .join(_T, _T.id == _TI.task_id)
                    .filter(_T.student_id == student.id, _T.date >= today,
                            _T.is_draft.is_(False))
                    .distinct().all()
                )
            }
            idle = [
                sb for sb in subject_breakdown(db, student.id, tests_only=True)
                if sb["total"] > 0 and sb["percent_done"] < 100
                and sb["subject_id"] not in _programmed and sb["subject_id"] not in _upcoming
            ]
            if idle:
                names = [sb["name"] for sb in idle]
                out.append(Warning(
                    level="amber", code="subjects_unprogrammed",
                    title=f"{len(idle)} ders programda yok",
                    detail=(f"{', '.join(names)}: atanmış kitabı var ama son 14 günde ve "
                            "ileriye dönük hiç görev verilmemiş."),
                    evidence=[
                        (sb["name"], f"kitapta %{sb['percent_done']} bitmiş · " + (
                            f"son çözüm {_d(_as_local_date(sb['last_completed_at']))}"
                            if sb["last_completed_at"] else "hiç çözülmedi"))
                        for sb in idle
                    ],
                ))

    # Aynı olgunun kademeleri tek uyarıda birleşir (liste uzamasın): haftalık
    # sıfır > 3 gündür hareket yok > dün ilerleme yok. En güçlüsü kalır.
    _codes = {w.code for w in out}
    _drop: set[str] = set()
    if "weekly_zero" in _codes:
        _drop |= {"inactive_3d", "yesterday_no_tick"}
    elif "inactive_3d" in _codes:
        _drop.add("yesterday_no_tick")
    if _drop:
        out = [w for w in out if w.code not in _drop]
    return out


def worst_level(warnings: list[Warning]) -> Literal["green", "amber", "red"]:
    if any(w.level == "red" for w in warnings):
        return "red"
    if any(w.level == "amber" for w in warnings):
        return "amber"
    return "green"


# ---------------------------- Birleşik snapshot ----------------------------


def student_snapshot(
    db: Session, student: User, today: date | None = None
) -> StudentSnapshot:
    """Dashboard ve detay sayfası için hepsi bir arada özet."""
    if today is None:
        today = date.today()
    today_stats = daily_stats_for(db, student.id, today)
    week_stats = week_stats_for(db, student.id, today)
    # "test/gün hız" gösterimi → yalnız soru bankası (deneme test'e karışmaz).
    # Bu alanlar yalnız gösterim; uyarılar `proj`'tan beslenir (snapshot'tan önce).
    rate7 = recent_rate(db, student.id, today, 7, tests_only=True)
    rate30 = recent_rate(db, student.id, today, 30, tests_only=True)
    cons7 = consistency_score(db, student.id, today, 7)
    hit7 = hit_rate(db, student.id, today, 7)
    # Gerçekçi projeksiyon — 28 günlük DOW penceresi + 5 günlük sınav tamponu
    proj = compute_projection(db, student, today, window_days=28, buffer_days=5)
    warnings = generate_warnings(db, student, today, proj)
    return StudentSnapshot(
        student=student,
        today=today_stats,
        week=week_stats,
        rate_7d=rate7,
        rate_30d=rate30,
        consistency_7d=cons7,
        hit_rate_7d=hit7,
        projection=proj,
        warnings=warnings,
        worst_warning_level=worst_level(warnings),
    )
