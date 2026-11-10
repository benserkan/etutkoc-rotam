"""Öğrenci detayı · Genel sekmesinin üst sırası (2026-11-09, koç onaylı).

Yalnız koç görür (öğrenci/veli yüzeylerine gitmez):
  1. Veri güvenilirliği — işaretleme düzeni + doğru/yanlış girme oranı
  2. Deneme gidişatı tek satır — son deneme farkı + son 5 denemenin eğilimi (Gelişim Raporu ile aynı)
  3. Hedef gerçekçiliği — hedef nete gereken haftalık artış ile son denemelerin temposu

Kurallar (koç kararı): ertesi gün işaretlemek tek başına sorun değil → BİLGİ notu; bir günün
bütün görevlerinin saniyeler içinde "yapıldı" yapılması → SARI uyarı.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Task, User
from app.services import gorev_stats

RELIAB_DAYS = 14          # işaretleme düzeni: son N gün
BULK_MIN_TASKS = 3        # bir günün en az N görevi…
BULK_SECONDS = 120        # …bu kadar saniye içinde işaretlendiyse "toplu"
BULK_WARN_DAYS = 3        # en az N gün ve işaretli günlerin yarısı toplu → sarı
NEXT_DAY_MIN_DAYS = 5     # ertesi gün notu için en az N işaretli gün
NEXT_DAY_SHARE = 0.6      # işaretli günlerin ≥%60'ı ertesi gün → bilgi notu
RESULT_DAYS = 28          # doğru/yanlış girme oranı penceresi
RESULT_MIN_TESTS = 10
RESULT_LOW = 0.2          # %20'nin altı → sarı
TREND_EPS = 0.5           # deneme başına ±0,5 net altı "yatay"


def _wp():
    from app.services import weekly_progress
    return weekly_progress


def _sgn(v: float) -> str:
    return "+" if v > 0 else "−" if v < 0 else ""


# ---------------------------------------------------------------- 1. veri güvenilirliği

def reliability(tasks: list[Task], today: date) -> list[dict]:
    wp = _wp()
    out: list[dict] = []
    since = today - timedelta(days=RELIAB_DAYS)
    by_day: dict[date, list[datetime]] = defaultdict(list)
    for t in tasks:
        if since <= t.date < today and wp._is_done(t) and t.completed_at:
            by_day[t.date].append(wp._tr(t.completed_at))
    marked = len(by_day)
    next_day = bulk = 0
    example = None
    for d in sorted(by_day):
        ts = by_day[d]
        first = min(ts)
        nd = d + timedelta(days=1)
        if first.date() > nd or (first.date() == nd and first.hour >= 5):
            next_day += 1
        span = (max(ts) - min(ts)).total_seconds()
        if len(ts) >= BULK_MIN_TASKS and span <= BULK_SECONDS:
            bulk += 1
            example = (d, len(ts), int(span))
    next_note = marked >= NEXT_DAY_MIN_DAYS and next_day >= NEXT_DAY_SHARE * marked
    if bulk >= BULK_WARN_DAYS and bulk >= marked / 2 and example:
        d, n, sec = example
        txt = (f"Son {RELIAB_DAYS} günde işaretleme yapılan {marked} günün {bulk} tanesinde o günün bütün "
               f"görevleri {BULK_SECONDS // 60} dakikadan kısa sürede \"yapıldı\" olarak işaretlendi "
               f"(ör. {wp._d(d)}: {n} görev {sec} saniyede).")
        if next_note:
            txt += f" İşaretleme genelde ertesi gün yapılıyor ({marked} günün {next_day} tanesinde)."
        out.append({
            "key": "bulk", "tone": "warn", "title": "Görevler saniyeler içinde toplu işaretleniyor",
            "text": txt + " Bu düzen görevlerin gerçekten yapıldığını göstermez.",
            "agenda": "Görevleri yaptıkça işaretlemesini konuş; toplu işaretleme çalışmayı ölçmemizi engelliyor.",
            "bulk_days": bulk, "marked_days": marked, "next_day_days": next_day,
        })
    elif next_note:
        out.append({
            "key": "next_day", "tone": "info", "title": "Görevlerini ertesi gün işaretliyor",
            "text": (f"Son {RELIAB_DAYS} günde işaretleme yapılan {marked} günün {next_day} tanesinde görevler "
                     "ertesi gün işaretlendi. Tek başına sorun değil (akşam çalışıp sabah işaretleyebilir); "
                     "\"gününde tamamlama\" bu yüzden düşük görünür."),
            "agenda": None,
            "bulk_days": bulk, "marked_days": marked, "next_day_days": next_day,
        })
    elif marked >= NEXT_DAY_MIN_DAYS:
        out.append({"key": "marking_ok", "tone": "ok", "title": "Görevlerini gününde işaretliyor",
                    "text": f"Son {RELIAB_DAYS} günde işaretleme düzeni olağan ({marked} gün).", "agenda": None,
                    "bulk_days": bulk, "marked_days": marked, "next_day_days": next_day})

    r_since = today - timedelta(days=RESULT_DAYS)
    done_t = res_t = 0
    for t in tasks:
        if not (r_since <= t.date < today):
            continue
        for it in t.book_items:
            if not gorev_stats.item_is_test(it):
                continue
            c = int(it.completed_count or 0)
            done_t += c
            if c and (it.correct_count is not None or it.wrong_count is not None):
                res_t += c
    if done_t >= RESULT_MIN_TESTS:
        pct = round(100 * res_t / done_t)
        if res_t < RESULT_LOW * done_t:
            out.append({
                "key": "results", "tone": "warn", "title": "Doğru/yanlış girilmiyor",
                "text": ((f"Son 4 haftada çözülen {done_t} testin hiçbirinde doğru/yanlış girilmedi."
                          if res_t == 0 else
                          f"Son 4 haftada çözülen {done_t} testin yalnız {res_t} tanesinde doğru/yanlış girildi "
                          f"(%{pct}).")
                         + " Doğruluk ve zorlandığı konular bu yüzden ölçülemiyor."),
                "agenda": "Testlerde doğru/yanlış/boş girmeyi alışkanlık yap — zorlandığı konular ancak böyle görünür.",
                "tests_done": done_t, "tests_with_result": res_t,
            })
        else:
            out.append({"key": "results", "tone": "ok", "title": "Doğru/yanlış giriliyor",
                        "text": f"Son 4 haftada çözülen {done_t} testin {res_t} tanesinde sonuç var (%{pct}).",
                        "agenda": None, "tests_done": done_t, "tests_with_result": res_t})
    return out


# ---------------------------------------------------------------- 2-3. deneme + hedef

_SECTION_ORDER = ["lgs", "tyt", "ayt_say", "ayt_ea", "ayt_soz", "ayt_dil",
                  "maarif_1", "maarif_2", "maarif_9", "maarif_10", "maarif_11",
                  "gis_9", "gis_10", "gis_11", "gis_12", "okul"]
_TRACK_AYT = {"sayisal": "ayt_say", "ea": "ayt_ea", "sozel": "ayt_soz", "dil": "ayt_dil"}


def _relevant_section(student: User, sec: str) -> bool:
    """Öğrencinin girdiği/gireceği sınav türü mü? Ortaokul (5-8) -> LGS + okul; lise/mezun -> LGS dışı.
    AYT alanı biliniyorsa yalnız o alan."""
    g = student.grade_level
    middle = g is not None and g <= 8 and not student.is_graduate
    if sec == "okul":
        return True
    if middle:
        return sec == "lgs"
    if sec == "lgs":
        return False
    tr = getattr(student.track, "value", student.track)
    alan = _TRACK_AYT.get(str(tr).lower()) if tr else None
    if alan and sec.startswith("ayt_"):
        return sec == alan
    return True


def _series_block(db: Session, student: User, today: date, ser: list, key: str) -> tuple[dict, dict | None]:
    from app.services import exam_scope
    from app.services.exam_progress import SLOPE_WINDOW, _slope, get_targets

    wp = _wp()
    num, d_ = wp._num, wp._d
    label = exam_scope.exam_scope(ser[-1]).series_label
    nets = [round(e.net, 2) for e in ser]
    last, prev = ser[-1], (ser[-2] if len(ser) > 1 else None)
    diff = round(last.net - prev.net, 2) if prev else None
    win_nets = nets[-SLOPE_WINDOW:]
    slope = _slope(win_nets)
    avg3 = round(sum(nets[-3:]) / len(nets[-3:]), 2)

    txt = (f"Son deneme {num(last.net)} net ({d_(last.exam_date)})" if len(ser) > 1
           else f"İlk deneme {num(last.net)} net ({d_(last.exam_date)})")
    if diff is not None:
        txt += f", öncekine göre {_sgn(diff)}{num(abs(diff))}"
    if slope is not None:
        yon = "aşağı" if slope <= -TREND_EPS else "yukarı" if slope >= TREND_EPS else "yatay"
        ters = (diff or 0) > 0 and slope <= -TREND_EPS or (diff or 0) < 0 and slope >= TREND_EPS
        txt += (f"{'; ama' if ters else ';'} son {len(win_nets)} denemenin eğilimi {yon} "
                f"(deneme başına {_sgn(slope)}{num(abs(slope))} net)")
    txt += f". Son 3 ortalama {num(avg3)}." if len(ser) > 1 else "."
    if len(ser) == 1:
        txt += " Gidişat ikinci denemeden sonra görünür."
    tone = ("info" if slope is None else "warn" if slope <= -TREND_EPS else
            "good" if slope >= TREND_EPS else "info")
    exam = {
        "series_key": key, "series_label": label, "count": len(ser), "last_net": round(last.net, 2),
        "last_date": last.exam_date.isoformat(), "prev_net": round(prev.net, 2) if prev else None,
        "diff": diff, "slope": slope, "slope_window": len(win_nets), "avg_last3": avg3,
        "tone": tone, "text": txt,
    }
    tgt = get_targets(db, student.id).get(exam_scope.section_of_key(key))
    target = None
    if tgt and tgt.get("target_net"):
        tnet = float(tgt["target_net"])
        gap = round(tnet - avg3, 2)
        try:
            tdate = date.fromisoformat(tgt["target_date"]) if tgt.get("target_date") else None
        except ValueError:
            tdate = None
        weeks_left = max(0, (tdate - today).days // 7) if tdate else None
        need = round(gap / weeks_left, 2) if (weeks_left and gap > 0) else None
        pace = None
        if slope is not None:
            w_ex = ser[-len(win_nets):]
            span = (w_ex[-1].exam_date - w_ex[0].exam_date).days
            if span > 0:
                pace = round(slope * (len(w_ex) - 1) / (span / 7), 2)
        head = (f"{label} hedefi: {d_(tdate) + ' tarihine kadar ' if tdate else ''}{num(tnet)} net. "
                f"Son 3 ortalama {num(avg3)}")
        realistic: bool | None
        if gap <= 0:
            t_tone, realistic = "good", True
            txt_t = f"{head}; hedef tuttu."
        elif tdate and weeks_left == 0:
            t_tone, realistic = "warn", False
            txt_t = (f"{head} → {num(gap)} net açık ve hedef tarihine bir haftadan az kaldı. "
                     "Yeni bir tarih ya da hedef belirle.")
        elif need is not None:
            pace_txt = ("hesaplanamıyor" if pace is None else f"haftada {_sgn(pace)}{num(abs(pace))} net")
            realistic = pace is not None and pace >= need
            t_tone = "good" if realistic else "warn"
            txt_t = (f"{head} → {num(gap)} net açık; {weeks_left} hafta kaldı, haftada +{num(need)} net artış gerekiyor. "
                     f"Son denemelerin temposu {pace_txt}.")
            txt_t += (" Bu tempoyla hedef tutar." if realistic else
                      " Bu tarih gerçekçi görünmüyor; hedefi ya da tarihi öğrenciyle birlikte gözden geçir.")
        else:
            t_tone, realistic = "info", None
            txt_t = f"{head} → {num(gap)} net açık. Hedef tarihi yok; tempo kıyası için tarih ekle."
        target = {"series_key": key, "series_label": label, "target_net": tnet, "target_date": tdate.isoformat() if tdate else None, "gap": gap,
                  "weeks_left": weeks_left, "per_week_needed": need, "pace_per_week": pace,
                  "realistic": realistic, "tone": t_tone, "text": txt_t,
                  "agenda": (None if realistic is not False else
                             f"{label} hedefi ({num(tnet)} net) ve tarihini birlikte gözden geçir.")}
    return exam, target


def exam_overview(db: Session, student: User, today: date) -> dict:
    """Deneme gidişatı + hedef — öğrencinin girdiği HER sınav türü ayrı (TYT ve AYT yan yana).

    Kural (koç, 2026-11-10): en çok denemesi olan tür öne çıkarılmaz; öğrencinin sınav türüne
    uygun her genel seri kendi satırıyla görünür. Sayılar Gelişim Raporu ile aynı (aynı sınıf
    dönemi, aynı eğim penceresi). Türüne uymayan seri (12. sınıfta LGS denemesi gibi)
    gidişata girmez; ayrıca not edilir.
    """
    from app.models.curriculum import EXAM_SECTION_LABELS, ExamSection
    from app.models.exam_result import ExamResult, analysis_exam_filter
    from app.services import exam_scope, grade_period_service

    win = grade_period_service.resolve_window(db, student.id, None)
    q = db.query(ExamResult).filter(ExamResult.student_id == student.id, analysis_exam_filter())
    if win.start is not None:
        q = q.filter(ExamResult.exam_date >= win.start)
    if win.end is not None:
        q = q.filter(ExamResult.exam_date <= win.end)
    genel = [e for e in q.order_by(ExamResult.exam_date.asc(), ExamResult.id.asc()).all()
             if exam_scope.classify(e) == "genel"]
    by_key: dict[str, list] = defaultdict(list)
    for e in genel:
        by_key[exam_scope.series_key(e)].append(e)

    def order(k: str) -> int:
        sec = exam_scope.section_of_key(k)
        return _SECTION_ORDER.index(sec) if sec in _SECTION_ORDER else len(_SECTION_ORDER)

    exams: list[dict] = []
    targets: list[dict] = []
    skipped: list[str] = []
    for k in sorted(by_key, key=order):
        sec = exam_scope.section_of_key(k)
        if not _relevant_section(student, sec):
            try:
                lab = EXAM_SECTION_LABELS[ExamSection(sec)]
            except (ValueError, KeyError):
                lab = sec.upper()
            skipped.append(f"{lab} ({len(by_key[k])} deneme)")
            continue
        ex, tg = _series_block(db, student, today, by_key[k], k)
        exams.append(ex)
        if tg:
            targets.append(tg)
    # okul yazılısı yalnız sınav serisi yoksa gösterilir
    if any(exam_scope.section_of_key(x["series_key"]) != "okul" for x in exams):
        exams = [x for x in exams if exam_scope.section_of_key(x["series_key"]) != "okul"]
    note = None
    if skipped:
        note = ("Öğrencinin sınav türüne uymayan denemeler gidişata katılmadı: " + ", ".join(skipped)
                + ". Yanlış öğrenciye ya da yanlış türle yüklendiyse Denemeler sekmesinden düzelt.")
    return {"exam": exams[0] if exams else None, "target": targets[0] if targets else None,
            "exams": exams, "targets": targets, "exam_note": note}


def build_overview(db: Session, student: User, today: date) -> dict:
    from sqlalchemy.orm import selectinload

    from app.models import TaskBookItem

    since = today - timedelta(days=max(RELIAB_DAYS, RESULT_DAYS))
    tasks = (db.query(Task)
             .options(selectinload(Task.book_items).joinedload(TaskBookItem.book))
             .filter(Task.student_id == student.id, Task.is_draft.is_(False),
                     Task.date >= since, Task.date < today).all())
    return {"reliability": reliability(tasks, today), **exam_overview(db, student, today)}
