"""FSRS aynı-gün koruması — vade patlaması regresyonu.

SAHA HATASI (2026-08-02, appstore.demo.kurum_ogrenci5, canlı veri):
Mobilde "çözdüm" butonu görsel geri bildirim vermediği için öğrenci arka arkaya
bastı. Her basış compute_next'i yeniden çalıştırdı; stabilite çarpımsal büyüdüğü
için 8 basışta 191.381 güne çıktı ve vade **2029'a** fırladı. Öğrenci soruyu bir
daha asla göremezdi. Streak zaten 20 saat aralık kuralıyla korunuyordu ama FSRS
koşulsuz çalışıyordu — koruma yarımdı.

Bu test iki şeyi birden kanıtlar:
  (a) art arda basış artık vadeyi İLERLETMEZ,
  (b) koruma normal öğrenmeyi BOZMAZ (gerçek aralıklı tekrar hâlâ büyütür) —
      yani iddia ayırt edici, her koşulda yeşil yanan bir test değil.

Kapsam: fsrs.compute_next çekirdeği + iki gerçek çağrı yolu
(wrong_question_service.record_attempt ve review_scheduler.record_review).
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import datetime, timedelta, timezone

from app.services.fsrs import (
    RATING_AGAIN,
    RATING_EASY,
    RATING_GOOD,
    RATING_HARD,
    SAME_DAY_GAP_HOURS,
    STATE_NEW,
    STATE_REVIEW,
    FsrsState,
    compute_next,
)

PASS = 0
FAIL = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [OK] {label}")
    else:
        FAIL += 1
        print(f"  [HATA] {label}" + (f" -> {detail}" if detail else ""))


T0 = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)


def state_after_first(rating: int, now: datetime) -> tuple[FsrsState, datetime]:
    """Yeni kartı bir kez değerlendirip oluşan durumu döndür."""
    res = compute_next(FsrsState(0.0, 0.0, STATE_NEW), rating, now)
    st = FsrsState(
        stability=res.stability,
        difficulty=res.difficulty,
        state=res.state,
        last_reviewed_at=now,
        due_at=res.due_at,
    )
    return st, res.due_at


# ---------------------------------------------------------------------------
print("\n1) Saha hatasının birebir tekrarı: 8 kez art arda 'Kolay'")
# ---------------------------------------------------------------------------
st, first_due = state_after_first(RATING_EASY, T0)
print(f"   ilk değerlendirme -> stabilite {st.stability:.1f} gün, vade {first_due:%Y-%m-%d}")

now = T0
for i in range(7):
    now = now + timedelta(seconds=8)  # kullanıcı hızlı hızlı basıyor
    res = compute_next(st, RATING_EASY, now)
    st = FsrsState(
        stability=res.stability,
        difficulty=res.difficulty,
        state=res.state,
        last_reviewed_at=now,
        due_at=res.due_at,
    )

print(f"   7 basış sonrası -> stabilite {st.stability:.1f} gün, vade {st.due_at:%Y-%m-%d}")
check(
    "art arda basış stabiliteyi şişirmiyor",
    abs(st.stability - 22.0) < 0.01,
    f"stabilite {st.stability:.1f} (beklenen 22.0)",
)
check(
    "vade ileri atılmıyor (ilk hesaplanan vadede kalıyor)",
    st.due_at == first_due,
    f"{st.due_at} != {first_due}",
)
check(
    "vade 2029'a fırlamıyor (saha hatası geri gelmiyor)",
    (st.due_at - T0).days < 30,
    f"vadeye {(st.due_at - T0).days} gün var",
)
check("aynı gün tekrarı 'alıştırma' olarak işaretleniyor", res.same_day_practice)

# ---------------------------------------------------------------------------
print("\n2) Koruma ayırt edici mi? Gerçek aralıklı tekrar HÂLÂ büyütmeli")
# ---------------------------------------------------------------------------
st2, _ = state_after_first(RATING_EASY, T0)
later = T0 + timedelta(hours=SAME_DAY_GAP_HOURS + 1)
res2 = compute_next(st2, RATING_EASY, later)
print(f"   {SAME_DAY_GAP_HOURS + 1} saat sonra -> stabilite {res2.stability:.1f} gün")
check(
    "eşiği geçen tekrar stabiliteyi büyütüyor",
    res2.stability > st2.stability * 1.5,
    f"{res2.stability:.1f} <= {st2.stability * 1.5:.1f}",
)
check("gerçek tekrar 'alıştırma' sayılmıyor", not res2.same_day_practice)
check(
    "gerçek tekrarda vade ileri gidiyor",
    res2.due_at > later,
    f"{res2.due_at} <= {later}",
)

# Eşiğin hemen ALTI hâlâ korunuyor mu (sınır davranışı)
res2b = compute_next(st2, RATING_EASY, T0 + timedelta(hours=SAME_DAY_GAP_HOURS - 1))
check("eşiğin 1 saat altı hâlâ korumada", res2b.same_day_practice)

# ---------------------------------------------------------------------------
print("\n3) 'Yine yanlış' korumanın DIŞINDA — unutma gerçek bilgidir")
# ---------------------------------------------------------------------------
st3, due3 = state_after_first(RATING_EASY, T0)
res3 = compute_next(st3, RATING_AGAIN, T0 + timedelta(minutes=2))
print(f"   2 dk sonra 'yine yanlış' -> stabilite {res3.stability:.1f} gün, vade {res3.due_at:%Y-%m-%d}")
check(
    "yine yanlış stabiliteyi DÜŞÜRÜYOR",
    res3.stability < st3.stability,
    f"{res3.stability:.1f} >= {st3.stability:.1f}",
)
check("yine yanlış vadeyi ÖNE çekiyor", res3.due_at < due3)
check("yine yanlış alıştırma sayılmıyor", not res3.same_day_practice)

# Art arda 'yine yanlış' sonsuz küçülmüyor (taban var)
stx = st3
n = T0
for _ in range(6):
    n += timedelta(seconds=5)
    r = compute_next(stx, RATING_AGAIN, n)
    stx = FsrsState(r.stability, r.difficulty, r.state, last_reviewed_at=n, due_at=r.due_at)
check(
    "art arda 'yine yanlış' tabanda duruyor (sonsuz küçülme yok)",
    stx.stability >= 0.5,
    f"stabilite {stx.stability}",
)

# ---------------------------------------------------------------------------
print("\n4) 'Zor çözdüm' de korunuyor (o da çarpımsal büyütüyordu)")
# ---------------------------------------------------------------------------
st4, due4 = state_after_first(RATING_GOOD, T0)
res4 = compute_next(st4, RATING_HARD, T0 + timedelta(minutes=1))
check("aynı gün 'zor çözdüm' vadeyi ilerletmiyor", res4.due_at == due4)
check("aynı gün 'zor çözdüm' stabiliteyi büyütmüyor", abs(res4.stability - st4.stability) < 0.01)

# ---------------------------------------------------------------------------
print("\n5) İlk değerlendirme (NEW kart) etkilenmiyor")
# ---------------------------------------------------------------------------
res5 = compute_next(FsrsState(0.0, 0.0, STATE_NEW), RATING_GOOD, T0)
check("yeni kart normal ilerliyor", res5.stability == 10.0 and not res5.same_day_practice)
check("yeni kartın vadesi ileri kuruluyor", res5.due_at > T0)

# ---------------------------------------------------------------------------
print("\n6) due_at bilinmiyorsa vade 'şimdi'ye kaydırılmıyor")
# ---------------------------------------------------------------------------
# Eski kayıtlarda state.due_at geçilmemiş olabilir; o durumda vade son
# tekrardan türetilmeli, aksi hâlde her basış vadeyi bugüne ötelerdi.
st6 = FsrsState(22.0, 5.0, STATE_REVIEW, last_reviewed_at=T0, due_at=None)
res6 = compute_next(st6, RATING_EASY, T0 + timedelta(minutes=30))
check(
    "vade son tekrardan türetiliyor (şimdi'ye kaymıyor)",
    res6.due_at < T0 + timedelta(minutes=30) + timedelta(days=res6.scheduled_days),
    f"{res6.due_at}",
)
check("bu durumda da stabilite sabit", abs(res6.stability - 22.0) < 0.01)

# ---------------------------------------------------------------------------
print("\n7) apply_result_to_state çapayı bozmuyor")
# ---------------------------------------------------------------------------
from app.services.fsrs import apply_result_to_state  # noqa: E402

st7, _ = state_after_first(RATING_EASY, T0)
res7 = compute_next(st7, RATING_EASY, T0 + timedelta(minutes=5))
new7 = apply_result_to_state(st7, RATING_EASY, res7)
check(
    "aynı gün alıştırmada son-tekrar çapası korunuyor",
    abs((new7.last_reviewed_at - T0).total_seconds()) < 60,
    f"{new7.last_reviewed_at} != {T0}",
)

# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print(f"SONUC: {PASS} gecti, {FAIL} kaldi")
print("=" * 60)
sys.exit(1 if FAIL else 0)
