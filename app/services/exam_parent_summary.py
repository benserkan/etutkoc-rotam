"""Deneme sonucu — veli e-postası için konuşma dilinde özet (2026-09-05).

Koç "Veliye duyur" düğmesine basınca üretilir. KURAL TABANLI ve KREDİSİZ:
her deneme için AI harcanmaz ve koçun paketi ne olursa olsun çalışır.

VELİ DİLİ İLKELERİ (weekly_parent_report ile aynı çizgi):
  · Suçlayıcı değil, somut. "Kötü" / "başarısız" gibi sözcük yok.
  · Sayı verilir ama yorum sade: "geçen denemeye göre 4,5 net artmış".
  · Tek bir odak önerisi — liste hâlinde eleştiri yok.
  · Koça özel notlar, soru-satırı detayları GİRMEZ (yalnız ders bazı + net).
  · Karşılaştırma AYNI SINAV TÜRÜ içinde yapılır (TYT 120 soru ile AYT 80
    soruyu kıyaslamak yanıltıcı olur — 2026-07-17'de yaşanan tuzak).
  · ALANA GÖRE ODAK: sayısal öğrenciye "Coğrafya'ya ağırlık vereceğiz" demek
    koçluk değil tablo okumaktır. Odak yalnız alanın BELKEMİĞİ derslerinden
    seçilir; alan-dışı ders tabloda görünür ama cümleye girmez.
  · KONU DÜZEYİ: deneme içe aktarılmışsa (soru satırı + konu eşleşmesi var)
    "matematikte 3 soruda takıldı: Fonksiyonlar, ..." denir. Ders adı tek
    başına koça da veliye de bir şey söylemez; konu söyler.
"""
from __future__ import annotations

import json
from datetime import date

from sqlalchemy.orm import Session

from app.models import ExamResult
from app.models.curriculum import Subject, Topic
from app.models.exam_result import EQ_RESULT_YANLIS, ExamResultQuestion
from app.models.user import Track

# Bir dersi "öne çıkan" saymak için en az bu kadar soru olmalı — 2 soruluk
# bir dersten "en güçlü dersi" çıkarmak yanıltıcı olur.
MIN_QUESTIONS_FOR_HIGHLIGHT = 5


def _subjects(exam: ExamResult) -> list[dict]:
    if not exam.subject_nets:
        return []
    try:
        rows = json.loads(exam.subject_nets) or []
    except (ValueError, TypeError):
        return []
    out = []
    for r in rows:
        try:
            c = int(r.get("correct", 0))
            w = int(r.get("wrong", 0))
            b = int(r.get("blank", 0))
            out.append({
                "name": str(r.get("name", "")).strip() or "—",
                "correct": c, "wrong": w, "blank": b,
                "net": float(r.get("net", 0.0)),
                "questions": c + w + b,
                # Müfredata bağlanmamış satır (ham belge başlığı) — veliye
                # "ders" diye sunulmaz, yalnız tabloda görünür.
                "unmatched": bool(r.get("unmatched", False)),
            })
        except (TypeError, ValueError):
            continue
    return out


def _previous_same_section(db: Session, exam: ExamResult) -> ExamResult | None:
    """Aynı sınav TÜRÜNDEKİ bir önceki deneme (kıyas ancak böyle anlamlı)."""
    return (
        db.query(ExamResult)
        .filter(
            ExamResult.student_id == exam.student_id,
            ExamResult.section == exam.section,
            ExamResult.id != exam.id,
            ExamResult.exam_date <= exam.exam_date,
        )
        .order_by(ExamResult.exam_date.desc(), ExamResult.id.desc())
        .first()
    )


def _fmt(n: float) -> str:
    """Türkçe ondalık: 102.75 → '102,75'."""
    return f"{n:.2f}".replace(".", ",")


def _wilson_lower(correct: int, total: int, z: float = 1.96) -> float:
    """Doğruluk için Wilson %95 alt sınırı — az soruyla gelen yüksek oranı
    cezalandırır (5/5 = 0.57 iken 36/40 = 0.77). Veliye "en güçlü ders"
    söylerken tesadüfi bir %100'ü öne çıkarmamak için."""
    if total <= 0:
        return 0.0
    p = correct / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5)
    return max(0.0, (centre - margin) / denom)


# Bir dersi "odak" olarak önermek için en az bu kadar YANLIŞ olmalı — tek
# yanlış tesadüftür, ondan zayıflık çıkarmak veliyi yanıltır.
MIN_WRONG_FOR_FOCUS = 2

# Odak cümlesinde en fazla kaç ders / ders başına kaç konu adı geçsin.
MAX_FOCUS_SUBJECTS = 2
MAX_TOPICS_PER_SUBJECT = 3

# "En rahat / en zayıf bölüm" bir KARŞILAŞTIRMA iddiası — en az bu kadar
# karşılaştırılabilir ders olmalı. Tek aday kalmışsa cümle kurulmaz
# (2026-09-10: alan filtresi diğerlerini eleyince sistem tek dersi
# karşılaştırmasız "en rahat" ilan ediyordu).
MIN_SUBJECTS_FOR_COMPARISON = 2

# Hiçbir derste yarıdan fazlasını yapamadıysa "en rahat olduğu bölüm" demek
# veliyi yanıltır — o denemede rahat olduğu bir bölüm yoktur.
MIN_BEST_ACCURACY = 0.50

# Alanın belkemiği dersleri (ders adı "TYT Matematik" / "AYT Geometri" gibi
# önekli gelir → anahtar kelimeyle eşleşir). Türkçe her alanda kritiktir:
# TYT'nin en yüksek soru ağırlıklı dersi.
# SAHA HATASI (2026-09-10, koç): Maarif/okul sınavlarında dersler BİRLEŞİK
# adla gelir ("Fen Bilimleri", "Sosyal Bilimler", "Türk Dili ve Edebiyatı").
# Liste yalnız TYT/AYT adlarıyla yazıldığı için SAYISAL bir öğrencide
# "Fen Bilimleri" (alanın belkemiği!) ve "Türk Dili ve Edebiyatı" eleniyor,
# geriye TEK ders kalıyordu → sistem karşılaştırma yapmadan ona "en rahat
# olduğu bölüm" diyordu. Birleşik adlar da anahtar kelime olarak eklendi.
_TRACK_CORE: dict[Track, set[str]] = {
    Track.SAYISAL: {
        "matematik", "geometri", "fizik", "kimya", "biyoloji",
        "fen bilimleri", "fen",
        "turkce", "turk dili", "edebiyat",
    },
    Track.EA: {
        "matematik", "geometri", "turkce", "turk dili", "edebiyat",
        "tarih", "cografya", "sosyal bilimler",
    },
    Track.SOZEL: {
        "turkce", "turk dili", "edebiyat", "tarih", "cografya", "felsefe",
        "din", "sosyal bilimler",
    },
    Track.DIL: {"turkce", "turk dili", "edebiyat", "ingilizce", "yabanci dil"},
}

_TR_MAP = str.maketrans("İIıŞşĞğÜüÖöÇç", "iiissgguuoocc")


def _norm(text: str | None) -> str:
    """Türkçe-güvenli sadeleştirme ('TYT Türkçe' → 'tyt turkce')."""
    return (text or "").translate(_TR_MAP).lower()


def _is_core_subject(name: str, track: Track | None) -> bool:
    """Ders öğrencinin alanının belkemiği mi? Alan yoksa (LGS / 9-10 / henüz
    seçmemiş) filtre uygulanmaz — hepsi kritik sayılır."""
    keywords = _TRACK_CORE.get(track) if track else None
    if not keywords:
        return True
    n = _norm(name)
    return any(k in n for k in keywords)


def _short_subject(name: str) -> str:
    """Veli cümlesinde sınav öneki gürültü: 'TYT Matematik' → 'Matematik'."""
    for prefix in ("TYT ", "AYT ", "YDT ", "LGS "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def _short_topic(name: str) -> str:
    """'Katı Cisimler (Prizma, Piramit, ...)' → 'Katı Cisimler'."""
    return name.split("(")[0].strip(" -–") or name


def _wrong_topics_by_subject(db: Session, exam: ExamResult) -> dict[str, list[str]]:
    """Ders → yanlış yapılan KONU adları (müfredata bağlanmış sorulardan).

    Yalnız içe aktarılmış (soru satırlı) denemelerde doludur; elle girilen
    denemede boş döner → çağıran ders-bazlı eski dile düşer.
    """
    rows = (
        db.query(Subject.name, Topic.name)
        .select_from(ExamResultQuestion)
        .join(Subject, Subject.id == ExamResultQuestion.subject_id)
        .join(Topic, Topic.id == ExamResultQuestion.topic_id)
        .filter(
            ExamResultQuestion.exam_result_id == exam.id,
            ExamResultQuestion.result == EQ_RESULT_YANLIS,
        )
        .all()
    )
    out: dict[str, list[str]] = {}
    for subject_name, topic_name in rows:
        bucket = out.setdefault(subject_name, [])
        label = _short_topic(topic_name)
        if label not in bucket:  # aynı konudan 2 yanlış → tek kez yaz
            bucket.append(label)
    return out


# Veliye gösterilecek en büyük net fırsatı sayısı — mail liste hâline
# gelmesin (veli dili ilkesi: tek odak, eleştiri listesi değil).
MAX_PARENT_OPPORTUNITIES = 4


def _net_opportunities(db: Session, exam: ExamResult) -> dict:
    """"Bu konular kapanırsa deneme başına +X net" — veli sürümü.

    KOÇ İSTEĞİ (2026-09-10): panelde koçun gördüğü "Net Fırsatı" tablosu
    veliye giden maile de girsin, hangi konulardan geldiği yorumla anlatılsın.

    Kaynak koç paneliyle AYNI servis (`exam_topic_analysis`) — sayılar
    ayrışamaz. Farklar bilinçli: veliye en büyük 4 satır gider (mail liste
    olmasın) ve dil "kayıp" değil "kazanç" üzerinden kurulur.

    Yalnız İÇE AKTARILMIŞ (soru satırlı) denemelerde doludur; elle girilen
    denemede boş döner → mailde bölüm hiç görünmez.
    """
    from app.services.exam_topic_analysis import build_exam_topic_analysis

    if exam.student is None:
        return {"rows": [], "exam_count": 0, "total_gain": 0.0}
    try:
        data = build_exam_topic_analysis(
            db, exam.student, section=exam.section.value,
        )
    except Exception:  # analiz düşerse mail düşmesin (best-effort)
        return {"rows": [], "exam_count": 0, "total_gain": 0.0}

    rows = [
        {
            "subject": _short_subject(o["subject_name"]),
            "topic": _short_topic(o["topic_name"]),
            "gain": float(o["net_gain_per_exam"]),
            "gain_text": _fmt(float(o["net_gain_per_exam"])),
            "wrong": int(o.get("wrong", 0)),
            "blank": int(o.get("blank", 0)),
        }
        for o in data.get("opportunities", [])[:MAX_PARENT_OPPORTUNITIES]
    ]
    total = round(sum(r["gain"] for r in rows), 2)
    return {
        "rows": rows,
        "exam_count": len(data.get("exams", [])),
        "section_label": data.get("section_label"),
        "total_gain": total,
        "total_gain_text": _fmt(total),
    }


# Karşılaştırma tablosunda kaç deneme gösterilsin (bu deneme DAHİL).
# Mail 580px — daha fazla sütun ders adını kırpar.
MAX_HISTORY_EXAMS = 4


def _subject_history(db: Session, exam: ExamResult) -> dict:
    """Aynı TÜRDEKİ son denemelerin ders bazlı net tablosu (karşılaştırma).

    KOÇ İSTEĞİ (2026-09-10): "geçmiş tarihlerdeki denemeleri de ders bazlı
    tablo hâlinde maile yerleştir; böylece önceki denemelerle karşılaştırma
    fırsatı olur."

    KIYAS AYNI TÜR İÇİNDE: TYT (120 soru) ile AYT (80 soru) yan yana konursa
    veli düşüş sanır — 2026-07-17'de yaşanan tuzak. Bu yüzden tablo yalnız
    `exam.section` ile aynı türdeki denemeleri taşır.

    Ders eşleşmesi ada göre (normalize) yapılır; bir derste veri yoksa hücre
    boş kalır ("—"), uydurulmaz.
    """
    rows = (
        db.query(ExamResult)
        .filter(
            ExamResult.student_id == exam.student_id,
            ExamResult.section == exam.section,
            ExamResult.exam_date <= exam.exam_date,
        )
        .order_by(ExamResult.exam_date.desc(), ExamResult.id.desc())
        .limit(MAX_HISTORY_EXAMS)
        .all()
    )
    exams = list(reversed(rows))          # eskiden yeniye — soldan sağa okunur
    if len(exams) < 2:
        return {"exams": [], "rows": [], "has_data": False}

    cols = [
        {
            "title": e.title,
            "date_tr": format_tr_date(e.exam_date.isoformat() if e.exam_date else None),
            "net_text": _fmt(float(e.net or 0)),
            "is_current": e.id == exam.id,
        }
        for e in exams
    ]

    # Ders adı → sütun başına net. Ad normalize edilir ("TYT Matematik" ile
    # "Matematik" aynı satırda buluşsun); gösterimde en uzun ad kullanılır.
    order: list[str] = []
    by_key: dict[str, dict] = {}
    for idx, e in enumerate(exams):
        for s in _subjects(e):
            if s["unmatched"]:
                continue          # ham belge başlığı — ders değil, tabloya girmez
            key = _norm(_short_subject(s["name"]))
            if key not in by_key:
                by_key[key] = {
                    "label": _short_subject(s["name"]),
                    "nets": [None] * len(exams),
                }
                order.append(key)
            cell = by_key[key]
            if len(_short_subject(s["name"])) > len(cell["label"]):
                cell["label"] = _short_subject(s["name"])
            cell["nets"][idx] = float(s["net"])

    out_rows = []
    for key in order:
        c = by_key[key]
        nets = c["nets"]
        # Trend: SON iki DOLU hücre (araya boş deneme girse de anlamlı kalır)
        filled = [v for v in nets if v is not None]
        direction = None
        if len(filled) >= 2:
            d = filled[-1] - filled[-2]
            direction = "up" if d > 0.5 else "down" if d < -0.5 else "flat"
        out_rows.append({
            "subject": c["label"],
            "nets": [(None if v is None else _fmt(v)) for v in nets],
            "direction": direction,
        })

    return {
        "exams": cols,
        "rows": out_rows,
        "totals": [c["net_text"] for c in cols],
        "has_data": bool(out_rows),
    }


def build_parent_exam_summary(db: Session, exam: ExamResult) -> dict:
    """Veli e-postasının içeriği: sayılar + konuşma dilinde cümleler."""
    subjects = _subjects(exam)
    total_q = exam.total_correct + exam.total_wrong + exam.total_blank

    prev = _previous_same_section(db, exam)
    delta: float | None = None
    if prev is not None and prev.net is not None and exam.net is not None:
        delta = round(float(exam.net) - float(prev.net), 2)

    # --- konuşma dilinde cümleler
    lines: list[str] = []
    name = (exam.student.full_name if exam.student else "Öğrencimiz").split(" ")[0]

    lines.append(
        f"{name}, {exam.title} denemesinde {total_q} sorunun "
        f"{exam.total_correct} tanesini doğru yanıtladı ve "
        f"{_fmt(float(exam.net or 0))} net çıkardı."
    )

    if delta is None:
        lines.append(
            "Bu, bu türdeki ilk denemesi. Bundan sonraki denemelerle "
            "karşılaştırarak gidişatı birlikte takip edeceğiz."
        )
    elif delta > 0.5:
        lines.append(
            f"Bir önceki denemesine göre {_fmt(delta)} net artış var — "
            "emeğinin karşılığını almaya başlamış."
        )
    elif delta < -0.5:
        lines.append(
            f"Bir önceki denemesine göre {_fmt(abs(delta))} net geride kaldı. "
            "Tek bir deneme tek başına gidişatı göstermez; hangi konularda "
            "zorlandığını birlikte inceliyoruz."
        )
    else:
        lines.append(
            "Bir önceki denemesine göre neti aşağı yukarı aynı — "
            "istikrarlı bir tablo."
        )

    # --- Odak ALANA GÖRE daralır: sayısal öğrenciye "Coğrafya'ya ağırlık
    # vereceğiz" demek koçluk değil. Alan-dışı ders tabloda görünür, cümleye
    # girmez. Alan yoksa (LGS / 9-10) filtre uygulanmaz.
    track = exam.student.track if exam.student else None
    ranked = [
        s for s in subjects
        if not s["unmatched"]
        and s["questions"] >= MIN_QUESTIONS_FOR_HIGHLIGHT
        and _is_core_subject(s["name"], track)
    ]

    # ORAN = doğru / TOPLAM SORU (boş DAHİL).
    #
    # SAHA HATASI (2026-09-10, koç): oran `doğru/(doğru+yanlış)` ile
    # hesaplanıyordu — yani boş bırakılanlar paydadan düşüyordu. Cümlede ise
    # "26 doğru / 40 soru" yazıyordu. Veli %65 okurken sistem %76'ya göre
    # karar veriyordu; 15/20 (%75) yapılan Fen, 26/8/6 olan Matematik'e
    # kaybediyordu. İki sebeple toplam soru doğru payda:
    #   · Gösterilen sayı ile karar AYNI temele oturur (koç/veli doğrulayabilir).
    #   · Boş bırakmak da "o soruyu yapamadı" demektir; "en rahat olduğu bölüm"
    #     derken bunu yok saymak dersi olduğundan iyi gösterir.
    #
    # HAM ORAN YETMEZ: 5 soruda %100, 40 soruda %90'dan güçlü kanıt değil
    # (küçük örneklem tesadüfü). Wilson alt sınırı az soruyu cezalandırır →
    # 20 soruluk Sosyal ile 40 soruluk Türkçe adil kıyaslanır.
    def acc(s: dict) -> float:
        total = s["questions"]
        if not total:
            return 0.0
        return _wilson_lower(s["correct"], total)

    best = worst = None
    if len(ranked) >= MIN_SUBJECTS_FOR_COMPARISON:
        # "En rahat/en zayıf" bir KARŞILAŞTIRMA iddiasıdır: tek aday kalmışsa
        # (diğerleri alan-dışı ya da az soruluysa) kurulmaz.
        ranked_sorted = sorted(ranked, key=acc)
        worst = ranked_sorted[0]
        best = ranked_sorted[-1]
        if best is worst or acc(best) - acc(worst) < 0.15:
            # Dersler birbirine yakınsa "en zayıf" demek haksızlık olur.
            worst = None
        # Hiçbir derste rahat değilse "en rahat" demek veliyi yanıltır.
        if best["correct"] / best["questions"] < MIN_BEST_ACCURACY:
            best = None

    if best is not None:
        lines.append(
            f"En rahat olduğu bölüm {_short_subject(best['name'])} "
            f"({best['correct']} doğru / {best['questions']} soru)."
        )

    # --- Odak cümlesi: önce KONU düzeyi (içe aktarılmış denemede soru satırı
    # var → "matematikte şu konularda takıldı"), yoksa ders düzeyine düşer.
    # Ders adı tek başına ne koça ne veliye bir şey söyler; konu söyler.
    wrong_topics = _wrong_topics_by_subject(db, exam)
    focus_bits: list[str] = []
    for s in sorted(
        (s for s in ranked if s["wrong"] >= MIN_WRONG_FOR_FOCUS), key=acc
    )[:MAX_FOCUS_SUBJECTS]:
        topics = wrong_topics.get(s["name"], [])[:MAX_TOPICS_PER_SUBJECT]
        if topics:
            focus_bits.append(
                f"{_short_subject(s['name'])} ({s['wrong']} soru): "
                + ", ".join(topics)
            )

    if focus_bits:
        lines.append(
            "Bu denemede en çok şu konularda takıldı — " + " · ".join(focus_bits) + "."
        )
        lines.append(
            "Programına önümüzdeki dönemde bu konulardan çalışma ekleyeceğiz."
        )
    elif worst is not None:
        lines.append(
            f"Önümüzdeki dönemde {_short_subject(worst['name'])} bölümüne "
            "ağırlık vereceğiz; programına bu konudan çalışma ekleyeceğiz."
        )

    # --- NET FIRSATI (koç isteği 2026-09-10): panelde koçun gördüğü tablo
    # veliye de gitsin + hangi konulardan geldiği YORUMLA anlatılsın.
    # ÖNEMLİ AYRIM: yukarıdaki odak cümlesi BU denemeye, buradaki fırsat
    # SON N DENEMENİN BİRİKİMİNE dayanır — cümle bunu açıkça söyler ki
    # veli iki listeyi karıştırmasın.
    opportunities = _net_opportunities(db, exam)
    opp_rows = opportunities["rows"]
    if opp_rows:
        names = " · ".join(f"{r['subject']} — {r['topic']}" for r in opp_rows[:3])
        scope = (
            f"Son {opportunities['exam_count']} denemesine bakınca"
            if opportunities["exam_count"] > 1
            else "Bu denemeye bakınca"
        )
        lines.append(
            f"{scope} en çok kazanç şu konulardan gelebilir: {names}. "
            f"Bu başlıklar kapandığında deneme başına yaklaşık "
            f"{opportunities['total_gain_text']} net daha çıkarabilir."
        )

    history = _subject_history(db, exam)

    return {
        "student_name": exam.student.full_name if exam.student else "",
        "exam_title": exam.title,
        "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
        "section_label": _section_label(exam),
        "net": float(exam.net or 0),
        "net_text": _fmt(float(exam.net or 0)),
        "correct": exam.total_correct,
        "wrong": exam.total_wrong,
        "blank": exam.total_blank,
        "total_questions": total_q,
        "delta": delta,
        "delta_text": (_fmt(abs(delta)) if delta is not None else None),
        "delta_direction": (
            None if delta is None else ("up" if delta > 0.5 else "down" if delta < -0.5 else "flat")
        ),
        "prev_title": prev.title if prev is not None else None,
        "prev_net_text": (
            _fmt(float(prev.net)) if prev is not None and prev.net is not None else None
        ),
        "prev_date": (
            prev.exam_date.isoformat() if prev is not None and prev.exam_date else None
        ),
        "subjects": subjects,
        "focus_topics": focus_bits,
        # Net fırsatı (koç paneliyle AYNI servis) + geçmiş denemelerin ders
        # bazlı karşılaştırma tablosu — ikisi de içe aktarılmış/çok denemeli
        # durumda dolar, yoksa mailde bölüm hiç görünmez.
        "opportunities": opp_rows,
        "opportunity_total_text": opportunities.get("total_gain_text"),
        "opportunity_exam_count": opportunities.get("exam_count", 0),
        "history": history,
        "narrative": lines,
    }


def build_email_context(
    db: Session,
    exam: ExamResult,
    *,
    narrative: list[str] | None = None,
    include_subjects: bool = True,
    include_history: bool = True,
    include_opportunities: bool = True,
) -> dict:
    """Deneme sonucu mailinin ŞABLON BAĞLAMI — tek kaynak.

    Hem gerçek e-posta (`produce_exam_result`) hem koçun "PDF olarak indir"
    çıktısı bu fonksiyondan beslenir; ikisi ayrışamaz. Veliye özel alanlar
    (unsubscribe_token) çağıranda eklenir.

    Koç düzenlemesi burada uygulanır: `narrative` verilirse kural motorunun
    cümleleri yerine koçun metni gider; `include_*` bayrakları ilgili bölümü
    tamamen çıkarır (şablon `{% if %}` ile zaten atlar).
    """
    summary = build_parent_exam_summary(db, exam)
    if narrative is not None:
        summary["narrative"] = narrative
    if not include_subjects:
        summary["subjects"] = []
    if not include_history:
        summary["history"] = {"exams": [], "rows": [], "has_data": False}
    if not include_opportunities:
        summary["opportunities"] = []
    return {
        "__template": "parent_exam_result",
        "student_id": exam.student_id,
        "student_name": (exam.student.full_name if exam.student else ""),
        **summary,
        "exam_date_tr": format_tr_date(summary.get("exam_date")),
        "prev_date_tr": format_tr_date(summary.get("prev_date")),
    }


def _section_label(exam: ExamResult) -> str:
    from app.models.curriculum import EXAM_SECTION_LABELS

    return EXAM_SECTION_LABELS.get(exam.section, "—")


def format_tr_date(iso: str | None) -> str:
    """'2026-09-02' → '02.09.2026' (şablonda okunur tarih)."""
    if not iso:
        return "—"
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return d.strftime("%d.%m.%Y")
